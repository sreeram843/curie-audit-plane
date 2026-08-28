from __future__ import annotations

from collections.abc import Mapping
from html import escape

FIGURE_METRICS = (
    ("audit_reconstruction_completeness", "Audit Reconstruction Completeness"),
    ("independently_verified_arc", "Independent Verification"),
    ("required_event_completeness", "Required Events"),
    ("evidence_attribution_coverage", "Evidence Attribution"),
    ("human_action_capture_completeness", "Human Action Capture"),
)


def _number(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def render_cohort_metrics_svg(study: Mapping[str, object]) -> str:
    """Return a self-contained vector figure for the cohort fraction metrics."""
    metrics = study.get("metrics", {})
    if not isinstance(metrics, Mapping):
        metrics = {}
    selected = [
        (key, label, metrics[key])
        for key, label in FIGURE_METRICS
        if isinstance(metrics.get(key), Mapping) and metrics[key].get("mean") is not None
    ]
    width, height = 1000, 560
    left, top, plot_width, plot_height = 270, 110, 650, 330
    row_height = plot_height / max(len(selected), 1)
    encounter_count = escape(str(study.get("encounter_count", "")))
    repetitions = escape(str(study.get("repetitions", "")))
    observation_count = study.get("observation_count")
    if observation_count is None:
        observation_count = _number(study.get("encounter_count")) * _number(study.get("repetitions"))
        observation_count = int(observation_count)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Curie Audit Plane synthetic cohort evaluation</title>',
        '<desc id="desc">Mean completeness metrics with 95 percent confidence intervals.</desc>',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<text x="60" y="52" font-family="Arial, sans-serif" font-size="25" '
        'font-weight="700" fill="#0f172a">Synthetic cohort evaluation</text>',
        f'<text x="60" y="80" font-family="Arial, sans-serif" font-size="15" '
        f'fill="#475569">Curie Audit Plane · encounters={encounter_count} · repetitions={repetitions} · n={observation_count}</text>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#94a3b8"/>',
        f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" '
        f'y2="{top + plot_height}" stroke="#94a3b8"/>',
    ]
    for tick in range(0, 6):
        x = left + plot_width * tick / 5
        value = tick / 5
        parts.append(
            f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_height}" '
            'stroke="#e2e8f0"/> '
            f'<text x="{x:.1f}" y="{top + plot_height + 28}" text-anchor="middle" '
            f'font-family="Arial, sans-serif" font-size="13" fill="#64748b">{value:.1f}</text>'
        )
    for index, (_, label, metric) in enumerate(selected):
        center_y = top + row_height * (index + 0.5)
        mean = max(0.0, min(1.0, _number(metric.get("mean"))))
        low = max(0.0, min(mean, _number(metric.get("ci95_low"), mean)))
        high = max(mean, min(1.0, _number(metric.get("ci95_high"), mean)))
        bar_width = plot_width * mean
        error_x_low = left + plot_width * low
        error_x_high = left + plot_width * high
        parts.extend(
            [
                f'<text x="{left - 18}" y="{center_y + 5:.1f}" text-anchor="end" '
                f'font-family="Arial, sans-serif" font-size="15" fill="#334155">{escape(label)}</text>',
                f'<rect x="{left}" y="{center_y - 17:.1f}" width="{bar_width:.1f}" height="34" '
                'rx="5" fill="#0f766e"/>',
                f'<line x1="{error_x_low:.1f}" y1="{center_y:.1f}" x2="{error_x_high:.1f}" '
                f'y2="{center_y:.1f}" stroke="#0f172a" stroke-width="3"/>',
                f'<line x1="{error_x_low:.1f}" y1="{center_y - 8:.1f}" x2="{error_x_low:.1f}" '
                f'y2="{center_y + 8:.1f}" stroke="#0f172a" stroke-width="2"/>',
                f'<line x1="{error_x_high:.1f}" y1="{center_y - 8:.1f}" x2="{error_x_high:.1f}" '
                f'y2="{center_y + 8:.1f}" stroke="#0f172a" stroke-width="2"/>',
                f'<text x="{left + plot_width + 18}" y="{center_y + 5:.1f}" '
                f'font-family="Arial, sans-serif" font-size="14" fill="#334155">{mean:.3f}</text>',
            ]
        )
    parts.extend(
        [
            f'<text x="{left + plot_width / 2}" y="{top + plot_height + 58}" text-anchor="middle" '
            'font-family="Arial, sans-serif" font-size="14" fill="#475569">Mean fraction (bars) · 95% CI (whiskers)</text>',
            '<text x="60" y="520" font-family="Arial, sans-serif" font-size="13" fill="#64748b">'
            'Synthetic data; scripted reviewer proxy; not clinical efficacy evidence.</text>',
            '</svg>',
        ]
    )
    return "".join(parts)
