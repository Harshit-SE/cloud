"""
AeroParse Teacher Shard Worker
Executes parallel teacher inference using Ollama (Phi-3.5) across sharded dataset partitions.
"""

import os
import sys
import json
import argparse
import requests
from pathlib import Path
from typing import Dict, List, Any

# Environment configuration
SHARD_INDEX = int(os.environ.get("SHARD_INDEX", "0"))
SHARD_COUNT = int(os.environ.get("SHARD_COUNT", "2"))
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
S3_URL = os.environ.get("S3_URL", "http://seaweedfs-s3.data.svc.cluster.local:8333")
MODEL_NAME = os.environ.get("TEACHER_MODEL", "phi3.5")

CHECKPOINT_DIR = Path("checkpoints")


def fetch_pool_commands() -> List[Dict[str, str]]:
    """Retrieve full command pool from SeaweedFS S3 storage."""
    url = f"{S3_URL}/datasets/commands_pool.jsonl"
    print(f"[*] Fetching commands from: {url}")
    response = requests.get(url, timeout=45)
    response.raise_for_status()

    records = [
        json.loads(line)
        for line in response.text.splitlines()
        if line.strip()
    ]
    return records


def partition_commands(commands: List[Dict[str, str]], index: int, count: int) -> List[Dict[str, str]]:
    """Select commands assigned to this shard index using round-robin partitioning."""
    return [
        cmd for idx, cmd in enumerate(commands)
        if idx % count == index
    ]


def load_checkpoint(shard_index: int) -> List[Dict[str, Any]]:
    """Load local checkpoint records if available."""
    checkpoint_file = CHECKPOINT_DIR / f"shard-{shard_index}.jsonl"
    if not checkpoint_file.exists():
        return []

    records = []
    with checkpoint_file.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def save_checkpoint(results: List[Dict[str, Any]], shard_index: int) -> None:
    """Save progress to local checkpoint directory."""
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint_file = CHECKPOINT_DIR / f"shard-{shard_index}.jsonl"
    with checkpoint_file.open("w", encoding="utf-8") as f:
        for item in results:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def sync_to_storage(results: List[Dict[str, Any]], shard_index: int) -> None:
    """Upload completed shard JSONL to SeaweedFS datasets bucket."""
    target_url = f"{S3_URL}/datasets/teacher/shard-{shard_index}.jsonl"
    payload = "\n".join(
        json.dumps(rec, ensure_ascii=False) for rec in results
    ) + "\n"

    response = requests.put(
        target_url,
        data=payload.encode("utf-8"),
        headers={"Content-Type": "application/jsonlines"},
        timeout=120
    )
    response.raise_for_status()
    print(f"[+] Synced {len(results)} records to {target_url}")


def query_teacher(command_text: str, system_prompt: str) -> str:
    """Invoke Phi-3.5 via Ollama with fixed seed and temperature=0."""
    payload = {
        "model": MODEL_NAME,
        "prompt": f"{system_prompt.strip()}\n\n{command_text}",
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.0,
            "seed": 42,
            "num_predict": 128
        }
    }

    resp = requests.post(OLLAMA_URL, json=payload, timeout=180)
    resp.raise_for_status()
    data = resp.json()
    return data.get("response", "").strip()


def run_worker():
    if SHARD_COUNT <= 0 or not (0 <= SHARD_INDEX < SHARD_COUNT):
        raise ValueError(f"Invalid shard parameters: index={SHARD_INDEX}, count={SHARD_COUNT}")

    prompt_path = Path("prompts/teacher_prompt.txt")
    if not prompt_path.is_file():
        raise FileNotFoundError(f"Missing prompt file at {prompt_path}")
    prompt = prompt_path.read_text(encoding="utf-8")

    print(f"=== AeroParse Worker Node: Shard {SHARD_INDEX + 1}/{SHARD_COUNT} ===")
    all_commands = fetch_pool_commands()
    assigned = partition_commands(all_commands, SHARD_INDEX, SHARD_COUNT)
    print(f"[*] Total pool: {len(all_commands)} | Assigned to shard: {len(assigned)}")

    existing_results = load_checkpoint(SHARD_INDEX)
    completed_ids = {r["id"] for r in existing_results}
    results = list(existing_results)
    print(f"[*] Resuming from checkpoint: {len(completed_ids)} already processed")

    for i, cmd in enumerate(assigned, start=1):
        cmd_id = cmd["id"]
        if cmd_id in completed_ids:
            continue

        try:
            raw_output = query_teacher(cmd["text"], prompt)
        except Exception as e:
            print(f"[!] Error labelling command {cmd_id}: {e}", file=sys.stderr)
            continue

        record = {
            "id": cmd_id,
            "text": cmd["text"],
            "teacher_raw": raw_output
        }
        results.append(record)
        completed_ids.add(cmd_id)

        if len(results) % 25 == 0:
            save_checkpoint(results, SHARD_INDEX)
            try:
                sync_to_storage(results, SHARD_INDEX)
            except Exception as e:
                print(f"[!] Warning: intermediate storage sync failed: {e}")

        print(f"[Shard {SHARD_INDEX}] Progress: {len(completed_ids)}/{len(assigned)} ({(len(completed_ids)/len(assigned))*100:.1f}%)")

    # Final persist
    save_checkpoint(results, SHARD_INDEX)
    sync_to_storage(results, SHARD_INDEX)
    print(f"[SUCCESS] Shard {SHARD_INDEX} completed successfully. Total processed: {len(results)}")


if __name__ == "__main__":
    run_worker()
