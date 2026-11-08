"""
AeroParse Student Model Distillation Trainer
Fine-tunes EleutherAI/pythia-70m on teacher-generated (Phi-3.5) command-to-JSON pairs.
Runs sequence-level knowledge distillation exclusively on CPU.
"""

import os
import csv
import json
import random
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Any

import yaml
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, AutoModelForCausalLM

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "training" / "config.yaml"


def initialize_seed(seed: int) -> None:
    """Set deterministic seeds across Python and PyTorch."""
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_configuration() -> Dict[str, Any]:
    """Load configuration from training/config.yaml."""
    if not CONFIG_PATH.is_file():
        raise FileNotFoundError(f"Configuration file not found: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_training_records(config: Dict[str, Any], subset: int = 0) -> List[Dict[str, Any]]:
    """Load command records up to max_train_samples or specified subset limit."""
    data_path = PROJECT_ROOT / config["train_file"]
    limit = subset if (subset and subset > 0) else config.get("max_train_samples", 1500)

    records: List[Dict[str, Any]] = []
    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
            if len(records) >= limit:
                break

    if not records:
        raise ValueError(f"No records found in training dataset: {data_path}")
    return records


def format_sequence_pair(record: Dict[str, Any]) -> Tuple[str, str]:
    """
    Format example for sequence-level distillation:
    Input: Command: <text>\nJSON:
    Target: {"intent": "...", "date": ..., "time": ..., "place": ...}
    """
    prompt = f"Command: {record['text']}\nJSON:"
    target_payload = {
        "intent": record["intent"],
        "date": record["date"],
        "time": record["time"],
        "place": record["place"]
    }
    response = " " + json.dumps(target_payload, separators=(",", ":"), ensure_ascii=False)
    return prompt, response


class DistillationDataset(Dataset):
    """
    Sequence-level distillation dataset.
    Prompt tokens are masked with -100 so loss is computed solely on JSON generation tokens.
    """
    def __init__(self, records: List[Dict[str, Any]], tokenizer: Any, max_len: int):
        self.samples: List[Tuple[List[int], List[int]]] = []
        eos_id = tokenizer.eos_token_id

        for rec in records:
            prompt_str, target_str = format_sequence_pair(rec)

            prompt_toks = tokenizer(
                prompt_str,
                add_special_tokens=True,
                truncation=True,
                max_length=max_len
            )["input_ids"]

            target_toks = tokenizer(
                target_str,
                add_special_tokens=False
            )["input_ids"]

            full_ids = prompt_toks + target_toks + [eos_id]
            if len(full_ids) > max_len:
                full_ids = full_ids[:max_len]

            # Mask prompt tokens with -100
            labels = [-100] * len(prompt_toks) + target_toks + [eos_id]
            labels = labels[:len(full_ids)]

            # Only retain if there are valid unmasked target tokens
            if any(token != -100 for token in labels):
                self.samples.append((full_ids, labels))

        if not self.samples:
            raise ValueError("No valid tokenized sequences produced for training.")

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Tuple[List[int], List[int]]:
        return self.samples[idx]


def collate_fn_padded(batch: List[Tuple[List[int], List[int]]], pad_id: int) -> Dict[str, torch.Tensor]:
    """Dynamic padding for input_ids, attention_mask, and labels."""
    batch_max = max(len(item[0]) for item in batch)
    padded_inputs, padded_masks, padded_labels = [], [], []

    for ids, labels in batch:
        pad_len = batch_max - len(ids)
        padded_inputs.append(ids + [pad_id] * pad_len)
        padded_masks.append([1] * len(ids) + [0] * pad_len)
        padded_labels.append(labels + [-100] * pad_len)

    return {
        "input_ids": torch.tensor(padded_inputs, dtype=torch.long),
        "attention_mask": torch.tensor(padded_masks, dtype=torch.long),
        "labels": torch.tensor(padded_labels, dtype=torch.long)
    }


def execute_training() -> None:
    parser = argparse.ArgumentParser(description="AeroParse Pythia-70M Distillation Training")
    parser.add_argument("--subset", type=int, default=0, help="Subset size (0 uses full limit)")
    parser.add_argument("--version", type=str, default="v1", help="Target model version (v1 or v2)")
    parser.add_argument("--seed", type=int, default=None, help="Override random seed")
    parser.add_argument("--data", type=str, default=None, help="Custom dataset file path")
    args = parser.parse_args()

    config = load_configuration()
    active_seed = args.seed if args.seed is not None else config.get("seed", 42)
    initialize_seed(active_seed)

    if args.data:
        config["train_file"] = args.data

    device = torch.device(config.get("device", "cpu"))
    print(f"=== Starting AeroParse Training [{args.version.upper()}] ===")
    print(f"[*] Hardware device: {device}")
    print(f"[*] Base seed:       {active_seed}")

    records = load_training_records(config, args.subset)
    print(f"[*] Loaded training samples: {len(records)}")

    model_id = config.get("model_name", "EleutherAI/pythia-70m")
    print(f"[*] Loading student architecture: {model_id}")
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(model_id, dtype=torch.float32)
    model.to(device)
    model.train()

    dataset = DistillationDataset(records, tokenizer, config.get("max_seq_length", 256))
    loader_generator = torch.Generator()
    loader_generator.manual_seed(active_seed)

    train_loader = DataLoader(
        dataset,
        batch_size=config.get("batch_size", 4),
        shuffle=True,
        generator=loader_generator,
        collate_fn=lambda b: collate_fn_padded(b, tokenizer.pad_token_id)
    )

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(config.get("learning_rate", 5e-5)),
        weight_decay=float(config.get("weight_decay", 0.01))
    )

    total_epochs = config.get("epochs", 3)
    loss_csv_filename = "loss.csv" if args.version == "v1" else f"loss_{args.version}.csv"
    loss_path = PROJECT_ROOT / "training" / loss_csv_filename

    loss_history: List[Tuple[int, float]] = []

    print(f"[*] Training for {total_epochs} epochs with {len(train_loader)} batches/epoch...")
    for epoch in range(1, total_epochs + 1):
        running_loss = 0.0
        total_batches = 0

        for step, batch in enumerate(train_loader, start=1):
            inputs = {k: v.to(device) for k, v in batch.items()}
            optimizer.zero_grad()

            outputs = model(**inputs)
            loss = outputs.loss
            loss.backward()

            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            running_loss += loss.item()
            total_batches += 1

        avg_loss = running_loss / max(1, total_batches)
        loss_history.append((epoch, avg_loss))
        print(f" -> Epoch [{epoch}/{total_epochs}] Finished | Average Loss: {avg_loss:.6f}")

    # Persist loss history
    with open(loss_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["epoch", "average_loss"])
        for ep, loss_val in loss_history:
            writer.writerow([ep, f"{loss_val:.6f}"])
    print(f"[+] Loss history written to: {loss_path}")

    # Save model and tokenizer
    out_dir = PROJECT_ROOT / "training" / "output" / args.version
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[*] Saving distilled weights to: {out_dir}")
    model.save_pretrained(out_dir)
    tokenizer.save_pretrained(out_dir)
    print(f"[SUCCESS] AeroParse student model {args.version} successfully distilled and saved.")


if __name__ == "__main__":
    execute_training()
