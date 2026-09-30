"""Run every evaluation and write eval/reports/*.md  (python -m scripts.run_evaluation [--quick])"""
import argparse
import json
import time

from config import cfg, path
from eval import (ablation_harness, agent_success_eval, classifier_eval, detector_benchmark, false_alarms_per_hour,
                  operator_acceptance_eval, proposal_eval, severity_eval, sumo_eval, tracker_benchmark, vlm_eval)
from tools.sumo.analyze_results import to_markdown

R = path("eval", "reports")


def md_table(d: dict, title: str) -> str:
    out = [f"# {title}", ""]
    def rec(x, ind=0):
        for k, v in x.items():
            if isinstance(v, dict):
                out.append("  " * ind + f"- **{k}**"); rec(v, ind + 1)
            else:
                out.append("  " * ind + f"- {k}: `{v}`")
    rec(d)
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--quick", action="store_true"); a = ap.parse_args()
    t = cfg("evaluation")["targets"]
    res = {}
    steps = [("detector", "detector_report.md", lambda: detector_benchmark.run(max_videos=4 if a.quick else 8)),
             ("tracker", "tracker_report.md", lambda: tracker_benchmark.run(max_videos=4 if a.quick else 8)),
             ("proposal", None, proposal_eval.run), ("classifier", None, classifier_eval.run),
             ("vlm", "vlm_report.md", vlm_eval.run), ("severity", "severity_report.md", severity_eval.run),
             ("ablation", "ablation_table.md", ablation_harness.run), ("false_alarms", None, false_alarms_per_hour.run),
             ("operator_acceptance", None, operator_acceptance_eval.run),
             ("agents", None, lambda: agent_success_eval.run(2 if a.quick else 3)),
             ("sumo", "sumo_report.md", lambda: sumo_eval.run([1, 2, 3] if a.quick else None))]
    for name, fname, fn in steps:
        t0 = time.time(); res[name] = fn()
        print(f"{name:20s} done in {time.time() - t0:5.1f}s")
        if fname:
            (R / fname).write_text(to_markdown(res[name]) if name == "sumo" else md_table(res[name], name.title() + " evaluation"), encoding="utf-8")
    ab = res["ablation"]["D_full two-stage (classifier + VLM)"]
    sm = [
        ("Accident detection F1 (full system)", f">= {t['accident_f1']}", ab["f1"], ab["f1"] >= t["accident_f1"]),
        ("False-positive rate (candidate level)", f"< {t['accident_fpr']}", ab["fpr_candidate"], ab["fpr_candidate"] < t["accident_fpr"]),
        ("Pipeline FPS", f">= {t['fps']}", res["detector"]["detector_fps"], res["detector"]["detector_fps"] >= t["fps"]),
        ("Tracking MOTA", f">= {t['mota']}", res["tracker"]["MOTA"], res["tracker"]["MOTA"] >= t["mota"]),
        ("Severity macro-F1", f">= {t['severity_macro_f1']}", res["severity"]["test"]["macro_f1"], res["severity"]["test"]["macro_f1"] >= t["severity_macro_f1"]),
        ("Delay reduction (simulation)", f">= {int(t['sumo_delay_reduction']*100)}%", f"{res['sumo']['improvement_pct']['avg_delay_s']}%", res["sumo"]["improvement_pct"]["avg_delay_s"] >= t["sumo_delay_reduction"] * 100),
        ("Detection-to-proposal latency (s)", f"< {t['alert_latency_s']}", res["proposal"]["latency_s_max"], (res["proposal"]["latency_s_max"] or 99) < t["alert_latency_s"]),
        ("Agent task success", f">= {t['agent_task_success']}", res["agents"]["task_success_rate"], res["agents"]["task_success_rate"] >= t["agent_task_success"]),
    ]
    lines = ["# Evaluation summary (synthetic CCTV-style data - see docs/limitations.md)", "", "| Metric | Target | Result | Met |", "|---|---|---|---|"]
    lines += [f"| {m} | {tg} | {r} | {'YES' if ok else 'no'} |" for m, tg, r, ok in sm]
    (R / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    json.dump(res, open(R / "all_results.json", "w"), indent=2, default=str)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
