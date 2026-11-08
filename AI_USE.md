# AeroParse AI Usage Disclosure and Attribution

This document details the usage of artificial intelligence tools, models, and assistants throughout the development of the AeroParse project, in accordance with the assignment requirements.

---

## 1. AI Models and Systems Used

### A. Teacher Model: Phi-3.5-mini-instruct (3.8B parameters)
- **Role:** Synthetic training target generator for sequence-level knowledge distillation.
- **Provider / Runtime:** Served locally using **Ollama** (`phi3.5:latest`).
- **Configuration:** Deterministic inference with `temperature = 0.0`, `seed = 42`, and `format = "json"`.
- **Purpose:** Processed 3,000 raw natural-language commands from `commands_pool.jsonl` to extract intent and slot metadata according to the strict 4-key JSON schema.

### B. Student Model: EleutherAI/Pythia-70M (70M parameters)
- **Role:** Distilled causal language model deployed as the production inference engine.
- **Framework:** PyTorch and Hugging Face Transformers.
- **Purpose:** Fine-tuned on CPU using the first 1,500 cleaned teacher completions to learn end-to-end command-to-JSON parsing under tight resource budgets.

### C. Agentic AI Coding Assistant
- **Role:** Architecture advisor, code refactoring assistant, and technical documentation collaborator.
- **Scope of Assistance:**
  - Advising on Kubernetes manifest construction (liveness/readiness probes, HPA, Traefik ingress).
  - Formulating mathematical subnetting calculations and drafting stateless NACL rules.
  - Designing Python unit test discovery patterns and CI/CD GitHub Actions workflows.
  - Reviewing code for zero-dependency modularity and cross-platform compatibility.

---

## 2. Dataset Preparation and Verification Strategy

Teacher model outputs were never accepted into training unconditionally. To safeguard the distillation pipeline against hallucinations and syntax anomalies, a dedicated cleaning filter (`worker/clean.py`) enforced strict verification gates:

1. **Syntax Integrity (Rule a):** Decoded each output string with `json.loads` to discard malformed syntax, truncation, or markdown code-fencing.
2. **Schema Conformance (Rule b):** Verified that keys match strictly `{"intent", "date", "time", "place"}` with no missing or surplus keys.
3. **Intent Closed-Set Check (Rule c):** Enforced membership in the eight designated intent categories.
4. **Verbatim Grounding Check (Rule d):** Verified that slot values (`date`, `time`, `place`) are either `null` or exact verbatim substrings of the original command text.
5. **Deduplication (Rule e):** Identified duplicate commands and retained only the record with the lowest alphanumeric command ID.

Out of 3,000 raw teacher completions, invalid and duplicate records were rejected, yielding a verified dataset of 2,292 records (`datasets/v1/train.jsonl`), of which the first 1,500 were used for student fine-tuning.

---

## 3. Human Engineering and Critical Oversight

All system components, logic, and operational pipelines were overseen, verified, and validated by the student developer:

- **Mathematical Validation:** Manually calculated and confirmed VLSM subnet boundaries, binary network masks, and host capacities in `network/subnets.md`.
- **Packet Simulation:** Ran `tools/nacl_sim.py` against test packets to verify 100% adherence to first-match stateless firewall semantics.
- **Local Unit Testing:** Implemented automated test cases in `tests/` covering validation logic, error handling, and scoring metrics.
- **Reproducibility Checks:** Verified model checksums using SHA-256 against release metadata before cluster deployment.
- **Deployment & Load Verification:** Conducted live Locust load testing against the local Kubernetes cluster to capture real latency percentiles, error rates, and CPU/memory profiles.

---

## 4. Known Model Limitations and Safety Guardrails

- **Parameter Budget:** Pythia-70M contains only 70 million parameters. On complex, ambiguous, or multi-clause commands, the student may produce invalid JSON or misclassify intents.
- **Runtime Guardrail:** The inference service (`service/app.py` via `service/validator.py`) implements a hard schema validation barrier. If the student model produces non-conforming JSON, the service intercepts it and returns HTTP 500 with `{"error": "invalid_model_output"}` instead of serving corrupted data with HTTP 200.
- **Fault Injection Mode:** When `FAULT_INJECT=1` is set, the service intentionally forces invalid output to verify that error interception functions correctly.

---

## 5. Security and Privacy Considerations

- No proprietary credentials, API tokens, or secrets are committed to the codebase.
- Object storage credentials are dynamically mounted into Pods using Kubernetes `Secret` resources.
- Secret scanning via **Gitleaks** is integrated directly into the CI workflow to prevent accidental credential leakage.
