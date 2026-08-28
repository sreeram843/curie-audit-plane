from curie_audit_plane.evaluation.figure import render_cohort_metrics_svg


def test_cohort_figure_is_vector_and_contains_metric_labels():
    study = {
        "encounter_count": 50,
        "repetitions": 1,
        "metrics": {
            "audit_reconstruction_completeness": {
                "mean": 1.0,
                "ci95_low": 1.0,
                "ci95_high": 1.0,
                "unit": "fraction",
            },
            "independently_verified_arc": {
                "mean": 1.0,
                "ci95_low": 1.0,
                "ci95_high": 1.0,
                "unit": "fraction",
            },
        },
    }

    svg = render_cohort_metrics_svg(study)

    assert svg.startswith("<svg ")
    assert 'role="img"' in svg
    assert "Audit Reconstruction Completeness" in svg
    assert "Independent Verification" in svg
    assert "n=50" in svg
