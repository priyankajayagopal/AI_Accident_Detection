import json

from config import cfg, path


def run():
    m = json.load(open(path(cfg("severity")["metrics_path"])))
    return {"val": m["val"], "test": {k: v for k, v in m["test"].items() if k != "report"}}
