import json
from pathlib import Path

CONTRACT = Path(__file__).resolve().parents[2] / "contracts" / "event-stages.json"


def load_event_stages() -> dict[str, str]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


EVENT_STAGES = load_event_stages()


def stage_for(event_type: str) -> str:
    return EVENT_STAGES.get(event_type, "transaction")
