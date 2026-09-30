"""Helper used by docs/notebooks: run N synthetic lifecycles and return statuses."""
from eval.agent_success_eval import _lifecycle


def run(n=3):
    return [_lifecycle(i, set())[1].status.value for i in range(n)]
