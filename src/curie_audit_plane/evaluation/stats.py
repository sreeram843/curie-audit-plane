from __future__ import annotations

from math import sqrt
from statistics import mean, median, stdev


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    p = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denom
    margin = (z * sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n)) / denom
    low = max(0.0, center - margin)
    high = min(1.0, center + margin)
    if successes == n:
        high = 1.0
    if successes == 0:
        low = 0.0
    return low, high


def paired_mean_ci(deltas: list[float], z: float = 1.96) -> dict[str, float | int | str]:
    average = mean(deltas)
    margin = 0.0 if len(deltas) < 2 else z * stdev(deltas) / len(deltas) ** 0.5
    return {
        "mean": average,
        "ci95_low": average - margin,
        "ci95_high": average + margin,
        "n": len(deltas),
        "method": "paired-normal",
    }


def rate_summary(successes: int, n: int, unit: str = "fraction") -> dict[str, float | int | str]:
    low, high = wilson_interval(successes, n)
    return {
        "mean": (successes / n) if n else 0.0,
        "median": median(([1.0] * successes) + ([0.0] * (n - successes))) if n else 0.0,
        "ci95_low": low,
        "ci95_high": high,
        "n": n,
        "numerator": successes,
        "denominator": n,
        "unit": unit,
        "status": "MEASURED",
        "interval": "wilson",
    }


def numeric_summary(values: list[float], unit: str) -> dict[str, float | int | str]:
    average = mean(values)
    margin = 0.0 if len(values) < 2 else 1.96 * stdev(values) / len(values) ** 0.5
    return {
        "mean": average,
        "median": median(values) if values else 0.0,
        "ci95_low": average - margin,
        "ci95_high": average + margin,
        "n": len(values),
        "unit": unit,
        "status": "MEASURED",
        "interval": "normal",
    }


def summarize_values(values: list[float], unit: str) -> dict[str, float | int | str]:
    if values and all(value in (0.0, 1.0) for value in values):
        return rate_summary(int(round(sum(values))), len(values), unit)
    return numeric_summary(values, unit)
