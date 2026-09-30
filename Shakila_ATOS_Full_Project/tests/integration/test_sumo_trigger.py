from tools.sumo import microsim


def test_treatment_beats_baseline():
    r = microsim.run_experiment(None, [1])
    s = microsim.summarize(r)
    assert s["improvement_pct"]["avg_delay_s"] > 0 and s["improvement_pct"]["emergency_arrival_s"] > 0
