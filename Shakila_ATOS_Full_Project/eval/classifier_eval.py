import json

from config import cfg, path


def run():
    return json.load(open(path(cfg("classifier")["metrics_path"])))
