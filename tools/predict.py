import argparse
import json
from pathlib import Path

import torch
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--output", default="predictions.jsonl")
    parser.add_argument("--validation", default="data/validation.jsonl")
    parser.add_argument(
        "--random-init",
        action="store_true",
        help="Initialize random model weights instead of loading trained weights",
    )
    args = parser.parse_args()

    torch.manual_seed(42)
    model_dir = Path(args.model_dir)

    records = [
        json.loads(line)
        for line in Path(args.validation).read_text().splitlines()
        if line.strip()
    ]

    tokenizer = AutoTokenizer.from_pretrained(
        str(model_dir), local_files_only=True
    )

    if args.random_init:
        config = AutoConfig.from_pretrained(
            str(model_dir), local_files_only=True
        )
        model = AutoModelForCausalLM.from_config(
            config, dtype=torch.float32
        )
        print("Using randomly initialized, untrained model", flush=True)
    else:
        model = AutoModelForCausalLM.from_pretrained(
            str(model_dir),
            local_files_only=True,
            dtype=torch.float32,
        )

    model.to("cpu")
    model.eval()

    predictions = []

    for index, record in enumerate(records, 1):
        prompt = f"Command: {record['text']}\nJSON:"
        inputs = tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=256,
        )

        with torch.inference_mode():
            output = model.generate(
                **inputs,
                max_new_tokens=100,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )

        generated = output[0][inputs["input_ids"].shape[1]:]
        raw = tokenizer.decode(generated, skip_special_tokens=True)

        predictions.append({
            "id": record["id"],
            "prediction": raw,
        })

        print(f"Predicted {index}/{len(records)}", flush=True)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        for prediction in predictions:
            file.write(json.dumps(prediction, ensure_ascii=False) + "\n")

    print(f"Saved {len(predictions)} predictions to {output_path}")


if __name__ == "__main__":
    main()
