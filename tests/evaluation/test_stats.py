from curie_audit_plane.evaluation.stats import rate_summary, wilson_interval


def test_wilson_interval_is_not_degenerate_at_boundary():
    low, high = wilson_interval(6, 6)
    assert high == 1.0
    assert 0.0 < low < 1.0


def test_rate_summary_records_wilson_method():
    summary = rate_summary(6, 6)
    assert summary["mean"] == 1.0
    assert summary["interval"] == "wilson"
    assert summary["ci95_high"] == 1.0
    assert summary["ci95_low"] < 1.0
