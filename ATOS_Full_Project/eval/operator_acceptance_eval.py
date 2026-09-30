"""Simulated-operator acceptance: an oracle operator approves only true accidents; acceptance = share of alerts shown to the
operator that were genuine (i.e. how much operator attention is wasted)."""
from eval.ablation_harness import two_stage
from eval.common import candidates_for_split
from workers.classifier_verify import ClassifierVerifier


def run(split="test"):
    clf, cache = ClassifierVerifier(), {}
    alerts = [c for c in candidates_for_split(split) if two_stage(c, True, clf, cache)]
    good = sum(1 for c in alerts if c["true_label"] == "accident")
    return {"alerts_shown_to_operator": len(alerts), "approved_by_oracle": good, "rejected_by_oracle": len(alerts) - good,
            "operator_acceptance_rate": round(good / max(1, len(alerts)), 3)}
