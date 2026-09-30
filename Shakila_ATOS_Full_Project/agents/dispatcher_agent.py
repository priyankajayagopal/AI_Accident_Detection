"""Dispatcher agent (runs only AFTER human approval): which emergency services, priority, ETAs. Advisory only."""
import time

from agents.agent_state import AgentContext
from agents.tools import routing_tools
from agents.tools.incident_tools import apply_transition
from config import camera, cfg
from schemas.incident import IncidentStatus


class DispatcherAgent:
    name = "dispatcher_agent"

    def run(self, ctx: AgentContext) -> dict:
        t0 = time.perf_counter()
        if "dispatcher_error" in ctx.faults:
            raise RuntimeError("injected dispatcher failure")
        inc = ctx.incident
        lvl = inc.estimated_severity.level.value
        a = cfg("agents")["dispatcher"]
        services = list(a["service_rules"].get(lvl, ["police"]))
        edge = camera(inc.location.camera_id).get("corridor_edge", "J2-J3")
        eta = {}
        for s in services:
            _, sec = routing_tools.emergency(s, edge)
            eta[s] = round(sec, 1)
        facts = {"severity": lvl, "services": services, "eta_s": eta, "vehicles": inc.vehicles_involved, "blocked_lanes": inc.blocked_lanes}
        tmpl = (f"{lvl.capitalize()} severity incident with {inc.vehicles_involved} vehicle(s) and {inc.blocked_lanes} blocked lane(s). "
                f"Recommend {', '.join(services)} (priority {a['base_priority'][lvl]}); fastest ETA {min(eta.values()):.0f}s from the nearest station.")
        out = {"services": services, "priority": a["base_priority"].get(lvl, "P3"), "eta_s": eta,
               "rationale": ctx.llm.explain("dispatcher", facts, tmpl) if ctx.llm else tmpl, "advisory_only": True, "used_fallbacks": []}
        ctx.log(self.name, "dispatch_plan", ["routing_tools.emergency"], f"{out['priority']}: {','.join(services)}", {"eta_s": eta}, t0)
        return out

    def commit(self, ctx: AgentContext, out: dict):
        ctx.incident.dispatch = out
        ctx.fallbacks_used += out.get("used_fallbacks", [])
        apply_transition(ctx.store, ctx.incident, IncidentStatus.DISPATCH_RECOMMENDED, self.name, out["priority"], ctx.publisher)
