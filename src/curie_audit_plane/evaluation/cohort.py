from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

MIN_COHORT_SIZE = 1
MAX_COHORT_SIZE = 1000


def _rewrite(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _rewrite(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_rewrite(item, replacements) for item in value]
    if isinstance(value, str):
        result = value
        for source, target in replacements.items():
            result = result.replace(source, target)
        return result
    return value


def _cohort_bundle(base: dict[str, Any], index: int) -> dict[str, Any]:
    identifier = f"TEST-{index:05d}"
    replacements = {
        "TEST-00001": identifier,
        "test-00001": f"test-{index:05d}",
    }
    bundle = _rewrite(base, replacements)
    timestamp = bundle.get("timestamp")
    if isinstance(timestamp, str):
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        bundle["timestamp"] = (parsed + timedelta(days=index - 1)).isoformat().replace("+00:00", "Z")
    return bundle


def generate_synthetic_cohort(
    base_path: str | Path,
    output_dir: str | Path,
    *,
    count: int,
) -> list[Path]:
    if not MIN_COHORT_SIZE <= count <= MAX_COHORT_SIZE:
        raise ValueError("cohort size must be between 1 and 1000")
    base = json.loads(Path(base_path).read_text(encoding="utf-8"))
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for index in range(1, count + 1):
        path = destination / f"encounter-{index:05d}.json"
        path.write_text(
            json.dumps(_cohort_bundle(base, index), indent=2) + "\n",
            encoding="utf-8",
        )
        paths.append(path)
    return paths
