"""
AeroParse Schema and Output Validation Logic
Zero-dependency validator for model-generated command JSON frames.
"""

import json
from pathlib import Path
from typing import Dict, Optional, Any

SCHEMA_FILE = Path(__file__).resolve().parent / "schema.json"

DEFAULT_KEYS = {"intent", "date", "time", "place"}
DEFAULT_INTENTS = {
    "alarm_set",
    "alarm_query",
    "calendar_set",
    "calendar_query",
    "calendar_remove",
    "weather_query",
    "datetime_query",
    "recommendation_events"
}


def validate_against_schema(raw_text: str, schema_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """
    Validates that raw_text is valid JSON conforming strictly to schema.json:
    - Exactly the four keys: intent, date, time, place
    - Intent belongs to the 8 allowed intents
    - Slot values are either null or strings
    Returns parsed dict on success, None on failure.
    """
    try:
        data = json.loads(raw_text)
        if not isinstance(data, dict):
            return None

        target_schema = schema_path or SCHEMA_FILE
        if target_schema.is_file():
            schema_meta = json.loads(target_schema.read_text(encoding="utf-8"))
            allowed_keys = set(schema_meta.get("keys", DEFAULT_KEYS))
            allowed_intents = set(schema_meta.get("intents", DEFAULT_INTENTS))
        else:
            allowed_keys = DEFAULT_KEYS
            allowed_intents = DEFAULT_INTENTS

        # Key verification: must match exactly
        if set(data.keys()) != allowed_keys:
            return None

        # Intent verification: must belong to allowed set
        if data.get("intent") not in allowed_intents:
            return None

        # Slot verification: string or null
        for slot in ("date", "time", "place"):
            val = data.get(slot)
            if val is not None and not isinstance(val, str):
                return None

        return data
    except Exception:
        return None
