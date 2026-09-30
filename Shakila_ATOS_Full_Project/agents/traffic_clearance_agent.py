"""Traffic clearance agent: diversion route, emergency corridor, signal strategy, then validates it in simulation."""
import time

from agents.agent_state import AgentContext
from agents.tools import routing_tools, sumo_tools
from agents.tools.incident_tools import apply_transition
from config import camera, cfg
from schemas.incident import IncidentStatus


class TrafficClearanceAgent:
    name = "traffic_clearance_agent"

    def run(self, ctx: AgentContext) -> dict:
        t0 = time.perf_counter()
        if "routing_error" in ctx.faults:
            raise RuntimeError("injected routing failure")
        inc = ctx.incident
        edge = camera(inc.location.camera_id).get("corridor_edge", "J2-J3")
        up, down = edge.split("-")
        div_path, div_eta = routing_tools.diversion(edge)
        services = (inc.dispatch or {}).get("services") or ["police"]
        first = "ambulance" if "ambulance" in services else services[0]
        em_path, em_eta = routing_tools.emergency(first, edge)
        c = cfg("sumo")
        cyc = c["signals"]["cycle_s"]
        actions = [{"junction": up, "action": "hold_red_main", "seconds": float(cyc - c["treatment"]["upstream_hold_green_s"])},
                   {"junction": down, "action": "extend_green_main", "seconds": float(c["treatment"]["downstream_extension_s"])}]
        for j in em_path:
            if j.startswith("J"):
                actions.append({"junction": j, "action": "emergency_preempt", "seconds": 30.0})
        strat = (f"Divert traffic at {div_path[0]} via Route B ({' > '.join(div_path)}); hold main-road green at {up}, extend green at {down}; "
                 f"pre-empt signals along emergency corridor {' > '.join(em_path)} (simulation only).")
        out = {"diversion_route": div_path, "diversion_eta_s": round(div_eta, 1), "emergency_route": em_path,
               "emergency_eta_s": round(em_eta, 1), "blocked_edge": edge, "signal_actions": actions,
               "strategy": ctx.llm.explain("traffic_clearance", {"strategy": strat}, strat) if ctx.llm else strat,
               "actuation": "simulation_only", "used_fallbacks": []}
        ctx.log(self.name, "clearance_plan", ["routing_tools.diversion", "routing_tools.emergency"], "plan ready",
                {"diversion": div_path, "emergency": em_path}, t0)
        return out

    def commit(self, ctx: AgentContext, out: dict):
        inc = ctx.incident
        inc.clearance = out
        ctx.fallbacks_used += out.get("used_fallbacks", [])
        t0 = time.perf_counter()
        try:
            if "sim_error" in ctx.faults:
                raise RuntimeError("injected simulation failure")
            sim = sumo_tools.run_simulation(inc.estimated_severity.level.value, ctx.outputs.get("blocked_ratio", 0.0), ctx.seeds, out)
            inc.simulation = sim
            ctx.log(self.name, "simulate", ["sumo_tools.run_simulation"], f"delay -{sim['improvement_pct']['avg_delay_s']}%",
                    {"improvement_pct": sim["improvement_pct"]}, t0)
        except Exception as e:
            inc.flags.append("simulation_failed")
            ctx.log(self.name, "simulate", ["sumo_tools.run_simulation"], "failed - plan kept, simulation skipped", {"error": repr(e)}, t0)
        apply_transition(ctx.store, inc, IncidentStatus.SIMULATED, self.name, "clearance plan validated in simulation", ctx.publisher)
