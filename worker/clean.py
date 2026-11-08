"""
AeroParse Data Cleaning and Validation Pipeline
Filters teacher-generated dataset shards according to strict JSON validation rules:
  (a) Malformed JSON syntax
  (b) Extraneous or missing keys (strictly: intent, date, time, place)
  (c) Invalid intent outside the 8 allowed categories
  (d) Hallucinated slots (must be null or exact verbatim substring in command)
  (e) Duplicate commands (preserves first occurrence by lowest command ID)
"""

import os
import sys
import json
import hashlib
import argparse
import requests
from pathlib import Path
from collections import Counter
from typing import Dict, List, Tuple, Optional, Any

# Closed sets and schema rules
ALLOWED_INTENTS = {
    "alarm_set",
    "alarm_query",
    "calendar_set",
    "calendar_query",
    "calendar_remove",
    "weather_query",
    "datetime_query",
    "recommendation_events"
}

REQUIRED_KEYS = {"intent", "date", "time", "place"}


def fetch_shard_records(s3_url: str, shard_names: List[str]) -> List[str]:
    """Retrieve raw lines from local disk if present, else fallback to S3 endpoint."""
    all_lines: List[str] = []

    for shard in shard_names:
        local_path = Path("checkpoints") / Path(shard).name
        if local_path.is_file():
            print(f"[*] Reading shard from local checkpoint: {local_path}")
            all_lines.extend(local_path.read_text(encoding="utf-8").splitlines())
            continue

        local_datasets = Path(shard)
        if local_datasets.is_file():
            print(f"[*] Reading shard from local path: {local_datasets}")
            all_lines.extend(local_datasets.read_text(encoding="utf-8").splitlines())
            continue

        endpoint = f"{s3_url.rstrip('/')}/{shard.lstrip('/')}"
        print(f"[*] Fetching shard from remote storage: {endpoint}")
        resp = requests.get(endpoint, timeout=60)
        resp.raise_for_status()
        all_lines.extend(resp.text.splitlines())

    return [line.strip() for line in all_lines if line.strip()]


def validate_teacher_reply(raw_text: str, command_text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Validates teacher output against constraints (a), (b), (c), and (d).
    Returns (parsed_dict, None) if valid, or (None, rejection_reason).
    """
    # (a) JSON validity
    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        return None, "invalid_json"

    # (b) Key integrity: exactly the four keys
    if not isinstance(data, dict) or set(data.keys()) != REQUIRED_KEYS:
        return None, "wrong_keys"

    # (c) Intent taxonomy: must be in the closed set
    if not isinstance(data["intent"], str) or data["intent"] not in ALLOWED_INTENTS:
        return None, "invalid_intent"

    # (d) Slot grounding: must be null or verbatim substring of command
    for slot in ("date", "time", "place"):
        val = data[slot]
        if val is not None:
            if not isinstance(val, str) or val not in command_text:
                return None, "invalid_slot"

    return data, None


def deduplicate_records(records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """
    Rule (e): Deduplicate commands. If multiple records share the same command text,
    retain the one with the smallest lexical command ID.
    """
    unique_map: Dict[str, Dict[str, Any]] = {}
    duplicates_count = 0

    for rec in records:
        text = rec["text"]
        if text not in unique_map:
            unique_map[text] = rec
        else:
            duplicates_count += 1
            if rec["id"] < unique_map[text]["id"]:
                unique_map[text] = rec

    retained = sorted(unique_map.values(), key=lambda r: r["id"])
    return retained, duplicates_count


def clean_dataset(
    shard_files: List[str],
    output_dir: Path,
    s3_endpoint: str
) -> Dict[str, Any]:
    raw_lines = fetch_shard_records(s3_endpoint, shard_files)
    print(f"[*] Total raw records read: {len(raw_lines)}")

    stats = Counter()
    validated_records: List[Dict[str, Any]] = []

    for line in raw_lines:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            stats["invalid_json"] += 1
            continue

        if not isinstance(item, dict) or set(item.keys()) != {"id", "text", "teacher_raw"}:
            stats["wrong_keys"] += 1
            continue

        parsed, error = validate_teacher_reply(item["teacher_raw"], item["text"])
        if error:
            stats[error] += 1
            continue

        validated_records.append({
            "id": item["id"],
            "text": item["text"],
            "intent": parsed["intent"],
            "date": parsed["date"],
            "time": parsed["time"],
            "place": parsed["place"],
        })

    # Deduplication
    clean_records, dup_count = deduplicate_records(validated_records)
    stats["duplicates"] = dup_count
    stats["kept"] = len(clean_records)
    stats["total_input"] = len(raw_lines)

    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / "train.jsonl"

    # Write deterministically with newline='\n' to guarantee consistent cross-platform SHA-256
    with out_file.open("w", encoding="utf-8", newline="\n") as f:
        for rec in clean_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    sha256_hash = hashlib.sha256(out_file.read_bytes()).hexdigest()
    sha_file = output_dir / "train.sha256"
    sha_file.write_text(f"{sha256_hash}  train.jsonl\n", encoding="utf-8", newline="\n")

    return {
        "stats": stats,
        "output_file": str(out_file),
        "sha256": sha256_hash,
    }


def main():
    parser = argparse.ArgumentParser(description="Clean and validate teacher-generated training shards.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("datasets/v1"),
        help="Directory where cleaned train.jsonl and train.sha256 will be saved."
    )
    parser.add_argument(
        "--s3-endpoint",
        type=str,
        default=os.environ.get("S3_URL", "http://localhost:8333"),
        help="SeaweedFS S3 endpoint"
    )
    parser.add_argument(
        "--shards",
        nargs="+",
        default=["datasets/teacher/shard-0.jsonl", "datasets/teacher/shard-1.jsonl"],
        help="List of shard paths or object keys"
    )

    args = parser.parse_args()
    summary = clean_dataset(args.shards, args.output_dir, args.s3_endpoint)
    s = summary["stats"]

    print("\n==========================================")
    print("      AeroParse Cleaning Pipeline         ")
    print("==========================================")
    print(f"Total input records:      {s['total_input']}")
    print(f"(a) Invalid JSON:         {s['invalid_json']}")
    print(f"(b) Wrong keys:           {s['wrong_keys']}")
    print(f"(c) Invalid intent:       {s['invalid_intent']}")
    print(f"(d) Invalid slot:         {s['invalid_slot']}")
    print(f"(e) Duplicate commands:   {s['duplicates']}")
    print(f"Kept records:             {s['kept']}")
    print("------------------------------------------")
    print(f"Output File: {summary['output_file']}")
    print(f"SHA-256:     {summary['sha256']}")
    print("==========================================\n")


if __name__ == "__main__":
    main()
