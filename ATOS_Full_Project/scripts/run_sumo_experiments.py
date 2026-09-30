"""python -m scripts.run_sumo_experiments  -> baseline vs treatment table (mean +- std over seeds)"""
import json

from config import path
from eval import sumo_eval
from tools.sumo.analyze_results import to_markdown

if __name__ == "__main__":
    s = sumo_eval.run()
    md = to_markdown(s)
    print(md)
    (path("eval", "reports") / "sumo_report.md").write_text(md, encoding="utf-8")
    json.dump({k: v for k, v in s.items() if k != "queue_series"}, open(path("eval", "reports", "sumo_results.json"), "w"), indent=2)
