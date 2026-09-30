"""AI orchestrator: shared state, routing between agents, guardrail + fallback around every step.

Two graph phases because a human gate sits in the middle (LangGraph when installed, tiny built-in runner otherwise):
  Phase A  verification : verifier -> severity                      -> (VERIFIED, waits for operator)
  Phase B  response     : dispatcher -> traffic_clearance -> reporting -> (SIMULATED, operator closes)
"""
from typing import Callable, Dict, List, Optional, Set

from agents.agent_state import AgentContext
from agents.dispatcher_agent import DispatcherAgent
from agents.fallback_supervisor import FallbackSupervisor
from agents.guardrail_agent import GuardrailAgent
from agents.llm import LLMClient
from agents.reporting_agent import ReportingAgent
from agents.severity_agent import SeverityAgent
from agents.tools.incident_tools import IncidentStore, apply_transition
from agents.traffic_clearance_agent import TrafficClearanceAgent
from agents.verifier_agent import VerifierAgent
from config import cfg
from schemas.incident import IncidentRecord, IncidentStatus

END = "__end__"


class GraphRunner:
    """nodes: {name: fn(ctx)}; route: {name: fn(ctx)->next_name|END}; entry: first node."""

    def __init__(self, entry: str, nodes: Dict[str, Callable], route: Dict[str, Callable], engine: str = "auto"):
        self.entry, self.nodes, self.route = entry, nodes, route
        self.engine = "simple"
        self.graph = None
        if engine in ("auto", "langgraph"):
            try:
                from typing import Any, TypedDict
                from langgraph.graph import END as LG_END, StateGraph

                class S(TypedDict):
                    ctx: Any

                g = StateGraph(S)
                for name, fn in nodes.items():
                    g.add_node(name, (lambda s, fn=fn: (fn(s["ctx"]), {"ctx": s["ctx"]})[1]))
                g.set_entry_point(entry)
                for name in nodes:
                    targets = {n: n for n in nodes}
                    targets[END] = LG_END
                    g.add_conditional_edges(name, (lambda s, name=name: route[name](s["ctx"])), targets)
                self.graph = g.compile()
                self.engine = "langgraph"
            except Exception:
                if engine == "langgraph":
                    raise

    def run(self, ctx: AgentContext) -> AgentContext:
        if self.graph is not None:
            self.graph.invoke({"ctx": ctx})
            return ctx
        name = self.entry
        while name != END:
            self.nodes[name](ctx)
            name = self.route[name](ctx)
        return ctx


class Orchestrator:
    def __init__(self, store: IncidentStore, publisher: Optional[Callable] = None, llm: Optional[LLMClient] = None,
                 classifier=None, severity_estimator=None, vlm_backend: Optional[str] = None, engine: Optional[str] = None):
        self.store, self.publisher = store, publisher
        self.llm = llm or LLMClient()
        self.verifier = VerifierAgent(classifier, vlm_backend)
        self.severity = SeverityAgent(severity_estimator)
        self.dispatcher = DispatcherAgent()
        self.clearance = TrafficClearanceAgent()
        self.reporter = ReportingAgent()
        self.guard = GuardrailAgent()
        self.fallback = FallbackSupervisor()
        self.max_retries = cfg("fallback")["max_agent_retries"]
        eng = engine or cfg("agents")["orchestrator"]["engine"]
        self.verify_graph = GraphRunner("verifier", {"verifier": self._n_verifier, "severity": self._n_severity},
                                        {"verifier": lambda c: END if c.halted else "severity", "severity": lambda c: END}, eng)
        self.response_graph = GraphRunner("dispatcher", {"dispatcher": self._n_dispatch, "clearance": self._n_clear, "reporting": self._n_report},
                                          {"dispatcher": lambda c: END if c.halted else "clearance",
                                           "clearance": lambda c: END if c.halted else "reporting", "reporting": lambda c: END}, eng)
        self.engine = self.verify_graph.engine

    # ------------------------------------------------------------ helpers
    def _ctx(self, iid: str, faults: Optional[Set[str]] = None, seeds=None) -> AgentContext:
        inc = self.store.get(iid)
        p = self.store.get_payload(iid)
        return AgentContext(store=self.store, incident=inc, candidate=p.get("candidate", {}), traffic=p.get("traffic", {}),
                            evidence_dir=p.get("evidence_dir"), faults=set(faults or ()), publisher=self.publisher, llm=self.llm, seeds=seeds)

    def _step(self, ctx: AgentContext, agent, key: str):
        last = None
        for _ in range(1 + self.max_retries):
            try:
                out = agent.run(ctx)
                g = self.guard.check(ctx, key, out)
                if g.passed:
                    agent.commit(ctx, out)
                    return out
                last = g.violations
            except Exception as e:                                # agent crash / timeout / invalid output
                last = repr(e)
                ctx.log(agent.name, "error", [], "exception", {"error": last})
        out = self.fallback.handle(ctx, key, last)
        g = self.guard.check(ctx, key, out)
        if g.passed:
            agent.commit(ctx, out)
            return out
        ctx.halted = True
        ctx.alert("critical", f"{key}: fallback also blocked by guardrail - operator must handle manually")
        return None

    # ------------------------------------------------------------ graph nodes
    def _n_verifier(self, ctx): self._step(ctx, self.verifier, "verifier")
    def _n_severity(self, ctx): self._step(ctx, self.severity, "severity")
    def _n_dispatch(self, ctx): self._step(ctx, self.dispatcher, "dispatcher")
    def _n_clear(self, ctx): self._step(ctx, self.clearance, "traffic_clearance")
    def _n_report(self, ctx): self._step(ctx, self.reporter, "reporting")

    # ------------------------------------------------------------ public API
    def verification_phase(self, iid: str, faults: Optional[Set[str]] = None) -> IncidentRecord:
        ctx = self._ctx(iid, faults)
        apply_transition(self.store, ctx.incident, IncidentStatus.UNDER_VERIFICATION, "agents/verifier_agent", "verification started", self.publisher)
        self.verify_graph.run(ctx)
        return self.store.get(iid)

    def approve(self, iid: str, operator: str) -> IncidentRecord:
        inc = self.store.get(iid)
        apply_transition(self.store, inc, IncidentStatus.OPERATOR_APPROVED, f"human:{operator}", "operator approved", self.publisher)
        return self.store.get(iid)

    def reject(self, iid: str, operator: str, reason: str = "operator rejected") -> IncidentRecord:
        inc = self.store.get(iid)
        inc.rejection_reason = reason
        apply_transition(self.store, inc, IncidentStatus.REJECTED, f"human:{operator}", reason, self.publisher)
        return self.store.get(iid)

    def response_phase(self, iid: str, faults: Optional[Set[str]] = None, seeds=None) -> IncidentRecord:
        ctx = self._ctx(iid, faults, seeds)
        if ctx.incident.status != IncidentStatus.OPERATOR_APPROVED:
            raise PermissionError("response phase requires OPERATOR_APPROVED status")
        self.response_graph.run(ctx)
        return self.store.get(iid)

    def close(self, iid: str, operator: str, note: str = "incident resolved") -> IncidentRecord:
        inc = self.store.get(iid)
        apply_transition(self.store, inc, IncidentStatus.CLOSED, f"human:{operator}", note, self.publisher)
        return self.store.get(iid)
