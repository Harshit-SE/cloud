import json
import requests
import torch
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForCausalLM

ROOT = Path(__file__).resolve().parent.parent
VALIDATION = ROOT / "data/validation.jsonl"
PROMPT_FILE = ROOT / "prompts/teacher_prompt.txt"
RESULTS = ROOT / "results"

RESULTS.mkdir(exist_ok=True)

records = [
    json.loads(line)
    for line in VALIDATION.read_text().splitlines()
    if line.strip()
]

def save_predictions(name, predictions):
    path = RESULTS / f"{name}_predictions.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for item in predictions:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"Saved {len(predictions)} predictions: {path}")

# 1. Teacher: same Ollama model and settings used in Task 1
def evaluate_teacher():
    prompt = PROMPT_FILE.read_text()
    predictions = []

    for i, record in enumerate(records, 1):
        payload = {
            "model": "phi3.5",
            "prompt": prompt + "\n" + record["text"],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0,
                "seed": 42,
                "num_predict": 100
            }
        }

        response = requests.post(
            "http://localhost:11434/api/generate",
            json=payload,
            timeout=180
        )
        response.raise_for_status()

        raw = response.json()["response"]
        predictions.append({
            "id": record["id"],
            "prediction": raw
        })

        print(f"Teacher: {i}/{len(records)}", flush=True)

    save_predictions("teacher", predictions)

# 2. Original and fine-tuned Pythia
def evaluate_pythia(model_name, output_name):
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        dtype=torch.float32
    )
    model.to("cpu")
    model.eval()

    predictions = []

    for i, record in enumerate(records, 1):
        prompt = f"Command: {record['text']}\nJSON:"
        inputs = tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=256
        )

        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=100,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id
            )

        generated = output[0][inputs["input_ids"].shape[1]:]
        raw = tokenizer.decode(generated, skip_special_tokens=True)

        predictions.append({
            "id": record["id"],
            "prediction": raw
        })

        print(f"{output_name}: {i}/{len(records)}", flush=True)

    save_predictions(output_name, predictions)

if __name__ == "__main__":
    print("Evaluating teacher...")
    evaluate_teacher()

    print("\nEvaluating original Pythia-70M...")
    evaluate_pythia("EleutherAI/pythia-70m", "baseline")

    print("\nEvaluating fine-tuned Pythia-70M v1...")
    evaluate_pythia(str(ROOT / "training/output/v1"), "student")
