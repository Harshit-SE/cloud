import json
import hashlib
import re
from pathlib import Path

SOURCE = Path("datasets/v1/train.jsonl")
OUTPUT_DIR = Path("datasets/v2")

DATE_PATTERNS = [
    r"\bthe entire week\b",
    r"\bthis weekend\b",
    r"\bnext weekend\b",
    r"\bthe weekend after next\b",
    r"\bnext week\b",
    r"\bthis week\b",
    r"\bwhole week\b",
    r"\ball week\b",
]

def extract_date(text):
    matches = []

    for pattern in DATE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            matches.append(match)

    if not matches:
        return None

    # Prefer the longest explicit expression.
    matches.sort(key=lambda m: (-(m.end() - m.start()), m.start()))
    return matches[0].group(0)

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    corrected = []
    audit = []
    changed = 0

    with SOURCE.open(encoding="utf-8") as source:
        for line in source:
            record = json.loads(line)

            if record["date"] is None:
                extracted = extract_date(record["text"])

                if extracted is not None:
                    audit.append({
                        "id": record["id"],
                        "text": record["text"],
                        "old_date": None,
                        "new_date": extracted,
                    })
                    record["date"] = extracted
                    changed += 1

            corrected.append(record)

    output_file = OUTPUT_DIR / "train.jsonl"
    with output_file.open("w", encoding="utf-8") as output:
        for record in corrected:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")

    audit_file = OUTPUT_DIR / "corrections.jsonl"
    with audit_file.open("w", encoding="utf-8") as output:
        for item in audit:
            output.write(json.dumps(item, ensure_ascii=False) + "\n")

    checksum = hashlib.sha256(output_file.read_bytes()).hexdigest()
    (OUTPUT_DIR / "train.sha256").write_text(
        f"{checksum}  train.jsonl\n",
        encoding="utf-8",
    )

    print(f"Original records: {len(corrected)}")
    print(f"Date labels corrected: {changed}")
    print(f"Audit entries: {len(audit)}")
    print(f"Output: {output_file}")
    print(f"SHA-256: {checksum}")

if __name__ == "__main__":
    main()
