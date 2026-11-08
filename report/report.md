# AeroParse: Knowledge Distillation and Cloud-Native Deployment of a Lightweight Command-Parsing Language Model

**Roll Number:** 230101065  
**Course:** CS3081 Cloud Computing — Mini Project  
**System Repository:** AeroParse  
**Target Architecture:** Kubernetes (k3d), SeaweedFS, PyTorch CPU, FastAPI, Locust  

---

## Abstract
This report presents the design, distillation, containerization, and cloud orchestration of **AeroParse**, an ultra-lightweight natural language command parsing system. Using sequence-level knowledge distillation, command understanding capabilities were transferred from a 3.8-billion-parameter teacher model (Microsoft Phi-3.5-mini-instruct) into an efficient 70-million-parameter student model (EleutherAI Pythia-70M). The model is served via a containerized FastAPI application on a local Kubernetes cluster (k3d) backed by S3-compatible object storage (SeaweedFS). The service implements automated health checking, horizontal pod autoscaling (HPA), zero-downtime rolling updates, and strict output schema validation. A comprehensive evaluation analyzes JSON validity, full-frame extraction accuracy, CPU latency percentiles, error budget consumption under an SLO framework, and hypothetical cloud operational costs.

---

## Section 1: Task 1 — Object Storage and Parallel Teacher Labelling

### 1.1 Cluster Initialization and Storage Topology
A lightweight, reproducible local cloud environment was provisioned using **k3d** based on declarative manifests stored at `cluster/k3d.yaml`. The cluster exposes host port `8080` bound to the internal Traefik Ingress controller load balancer.

Within the dedicated `data` namespace, **SeaweedFS** was deployed via Helm (`cluster/seaweedfs-values.yaml`) to deliver an S3-compatible distributed object storage layer with Master, Volume, Filer, and S3 gateway components. Two primary buckets were provisioned:
- `datasets`: Houses raw training pools (`commands_pool.jsonl`), teacher worker shards, and cleaned training corpora.
- `models`: Stores versioned distilled model weights (`v1/` and `v2/`) along with their cryptographic SHA-256 verification manifests.

### 1.2 Teacher Model Serving & Parallel Sharding
The teacher model selected for distillation is **Phi-3.5-mini-instruct** (3.8B parameters), served locally using Ollama. To enforce deterministic generation across all runs, the generation parameters were fixed to:
- `temperature = 0.0`
- `seed = 42`
- `format = "json"`

The system prompt in `prompts/teacher_prompt.txt` strictly confines the model to output a single JSON object with exactly four keys: `intent`, `date`, `time`, and `place`, selecting from an eight-intent closed taxonomy.

To overcome CPU inference bottlenecks across 3,000 raw input commands, a distributed worker architecture was implemented in `worker/teacher_worker.py`. Commands were partitioned across concurrent worker pods in the `pipeline` namespace using modulo sharding:
$$\text{Assigned if } (\text{Line Index} \pmod{\text{SHARD\_COUNT}}) = \text{SHARD\_INDEX}$$

Two parallel workers (`SHARD_COUNT=2`, indices 0 and 1) were executed concurrently. Each worker tracked processing progress with local state checkpoints and synced intermediate outputs to `datasets/teacher/shard-0.jsonl` and `shard-1.jsonl` in SeaweedFS. Every command ID in `commands_pool.jsonl` appeared in exactly one worker shard without gaps or duplicates.

### 1.3 Data Cleaning and Filtering Pipeline
Teacher completions cannot be assumed to be 100% syntactically or semantically sound. The pipeline `worker/clean.py` implemented a deterministic 5-stage filter:
1. **Rule (a) - Malformed JSON Syntax:** Discarded outputs failing `json.loads`.
2. **Rule (b) - Schema Key Discrepancies:** Discarded objects whose key set differed from `{"intent", "date", "time", "place"}`.
3. **Rule (c) - Out-of-Vocabulary Intents:** Filtered intents outside the designated eight categories.
4. **Rule (d) - Unanchored / Hallucinated Slots:** Verified that every non-null slot string appeared as a verbatim substring in the source command.
5. **Rule (e) - Command Deduplication:** For identical command texts appearing under multiple IDs, retained only the instance with the lexicographically smallest ID.

#### Data Cleaning Accounting Table
$$\text{Input Records} = 3,000$$
$$\text{Cleaned Corpus Size} = 2,292$$
$$\text{Integrity Check:} \quad 3,000 = (a) + (b) + (c) + (d) + \text{Duplicates} + \text{Kept} \quad (3,000 = 708 + 2,292)$$

The final corpus was written to `datasets/v1/train.jsonl` with Unix line-endings (`\n`), yielding a deterministic SHA-256 checksum matching `datasets/v1/train.sha256`.

---

## Section 2: Task 2 — Student Training (Sequence-Level Knowledge Distillation)

### 2.1 Distillation Methodology & Objective
Rather than training a miniature model from scratch on small human annotations, **sequence-level knowledge distillation** (Kim & Rush, 2016) uses the teacher model as a high-capacity label generator. The first 1,500 records of `datasets/v1/train.jsonl` formed the training set.

Each training pair was formatted as:
```text
Command: <natural language command>
JSON: {"intent": "...", "date": ..., "time": ..., "place": ...}
```
During autoregressive training, prompt tokens were masked with label `-100`, forcing the PyTorch cross-entropy loss to evaluate gradients exclusively on the JSON target sequence.

### 2.2 Sequence-Level vs. Logit-Based Distillation
- **Sequence-Level Distillation:** Optimizes standard cross-entropy loss over hard target token sequences emitted by the teacher:
  $$\mathcal{L}_{\text{seq}} = - \sum_{t=1}^T \log P_S(y_t \mid y_{<t}, x)$$
- **Logit-Based Distillation:** Minimizes Kullback-Leibler (KL) divergence between teacher and student softened probability distributions across the entire vocabulary:
  $$\mathcal{L}_{\text{logit}} = \tau^2 \, D_{\text{KL}}(P_T^\tau \parallel P_S^\tau)$$
  where $\tau$ is a temperature hyperparameter.
- **Infeasibility in this Setting:** Logit-based distillation was technically impossible because:
  1. Ollama's HTTP API is an opaque black box returning only generated text strings, omitting intermediate hidden states and vocabulary logits.
  2. Phi-3.5 (32K vocabulary) and Pythia-70M (50,304 vocabulary) utilize incompatible tokenizers; token logits cannot be directly aligned without custom projection layers.
- **Limitation:** Sequence-level distillation transfers hard labels without uncertainty estimates. The student cannot differentiate between high-confidence teacher predictions and near-random guesses, and consequently memorizes teacher errors and hallucinations.

### 2.3 Training Configuration and Reproducibility
All hyperparameters were pinned in `training/config.yaml`:
- Architecture: `EleutherAI/pythia-70m` (70M parameters)
- Epochs: 3 | Batch Size: 4 | Learning Rate: $5 \times 10^{-5}$ (AdamW, weight decay 0.01)
- Seed: 42 | Target: CPU | Sequence Length: 256 tokens

Training is executed via `make train`, supporting `SUBSET=50` for rapid sanity checking. Epoch loss was logged to `training/loss.csv`. Two versions were produced: `v1` (baseline 3 epochs) and `v2` (extended epoch schedule). Checksums were logged in `models/v1/model.sha256` and released via GitHub Releases.

### 2.4 Model Benchmark Comparison

Evaluation was conducted against `data/validation.jsonl` (100 labelled test commands) using `tools/score.py`:

| Evaluation Metric | Teacher (Phi-3.5) | Untrained Pythia-70M | Distilled Student (v1) |
| :--- | :---: | :---: | :---: |
| **JSON Validity** | 94.0% | 0.0% | **90.0%** |
| **Intent Accuracy** | 85.0% | 0.0% | **75.0%** |
| **Date Accuracy** | 71.0% | 0.0% | **68.0%** |
| **Time Accuracy** | 79.0% | 0.0% | **76.0%** |
| **Place Accuracy** | 81.0% | 0.0% | **77.0%** |
| **Full-Frame Accuracy** | **44.0%** | **0.0%** | **41.0%** |

The fine-tuned student achieved **90.0% JSON validity** and **41.0% full-frame accuracy**—retaining **93.2% of the teacher's full-frame accuracy** while operating with **54x fewer parameters**.

---

## Section 3: Task 3 — Containerized Inference Microservice

### 3.1 Service Architecture & Endpoints
The inference service in `service/app.py` exposes three primary HTTP endpoints on port 8000:
- `POST /parse`: Accepts `{"text": "..."}` and returns the parsed four-key JSON frame with response headers `X-Model-Version` and `X-Served-By` (Pod hostname).
- `GET /healthz`: Immediate liveness check returning HTTP 200.
- `GET /readyz`: Readiness check returning HTTP 503 during startup and S3 model loading, transitioning to HTTP 200 once weights are in memory.

### 3.2 Configuration, Validation Guardrail, and Fault Injection
- **Environment Driven:** Configured solely through `MODEL_URI`, `MODEL_VERSION`, `S3_ENDPOINT`, and `MAX_NEW_TOKENS`.
- **Dynamic Startup Retrieval:** Weights are downloaded from SeaweedFS on container boot using S3 credentials supplied via Kubernetes Secrets (`seaweedfs-s3-credentials`). Model binaries are excluded from the Docker image.
- **Strict Schema Interception:** Every raw model generation is validated by `service/validator.py` against `data/schema.json`. If the output contains invalid JSON, extra keys, or illegal intents, the service responds with HTTP 500: `{"error": "invalid_model_output"}`.
- **Fault Injection (`FAULT_INJECT=1`):** Overrides generation with `"not json"`, verifying that malformed outputs are caught and return HTTP 500.

### 3.3 Resource Profiling Under Limits
The container was built using `python:3.12-slim` and CPU-only PyTorch wheels, keeping image size at **1.66 GB** (well below the 2.0 GB limit).

When tested under hard container limits of **1 CPU core** and **1 GiB memory**:
- 50 sequential requests completed with 100% success (0 OOM kills).
- Peak memory reached **737.4 MiB** (773,095,424 bytes), demonstrating safe operation within the 1 GiB allocation.

---

## Section 4: Task 4 — Kubernetes Orchestration, Scaling & Reliability

### 4.1 Deployment Topology
Workloads were deployed in the `app` namespace:
- **Deployment:** 2 replicas of `aeroparse-service:v1`, resource requests `500m CPU / 512Mi RAM`, limits `1 CPU / 1Gi RAM`.
- **Service & Ingress:** ClusterIP service mapped to Traefik Ingress routing path `/parse`.
- **Probes:** Liveness probe on `/healthz` (delay 20s); Readiness probe on `/readyz` (delay 5s, failureThreshold 120), preventing traffic ingress before weights are loaded.

### 4.2 Horizontal Pod Autoscaling (HPA)
An HPA was configured with minReplicas 1, maxReplicas 2, and target CPU utilization 70%. Under sustained Locust load, metrics-server triggered scale-up to 2 replicas, and scaled down to 1 replica after load cessation. Local cluster limitation: on single-node laptop virtualization, all pods share the same host physical cores, causing thermal throttling rather than physical distributed scaling.

### 4.3 Resilience, Rollouts & Cold-Start Measurements
- **Rolling Update:** Transitioning `MODEL_VERSION` from `v1` to `v2` during active load achieved zero failed requests (0.0% failure rate) due to `maxSurge: 1, maxUnavailable: 0`. Rolling back via `kubectl rollout undo` restored `v1` headers.
- **Pod Recovery:** Terminating an active pod under load resulted in Kubernetes immediately spinning up a replacement replica with $< 2\%$ request drop.
- **Cold-Start Latency:** Three consecutive pod eviction trials recorded S3 download and initialization times:
  - Run 1: 43.8s | Run 2: 41.2s | Run 3: 42.5s $\implies$ **Median: 42.5 seconds**.
- **Load Balancing:** Over a 2-minute Locust benchmark, Pod 1 served 41 requests (52.6%) and Pod 2 served 37 requests (47.4%), confirming equitable load balancing ($> 30\%$ per replica).

---

## Section 5: Task 5 — Subnetting and Stateless Network Access Control

### 5.1 VLSM Subnet Allocation (`10.20.0.0/16`)
Subnets were allocated contiguously from largest to smallest requirement:
1. `app` (1,000 hosts): `/22` $\implies$ `10.20.0.0/22`, range `10.20.0.1`–`10.20.3.254`, broadcast `10.20.3.255`, 1,022 usable hosts.
2. `public` (250 hosts): `/24` $\implies$ `10.20.4.0/24`, range `10.20.4.1`–`10.20.4.254`, broadcast `10.20.4.255`, 254 usable hosts.
3. `data` (100 hosts): `/25` $\implies$ `10.20.5.0/25`, range `10.20.5.1`–`10.20.5.126`, broadcast `10.20.5.127`, 126 usable hosts.
4. `management` (20 hosts): `/27` $\implies$ `10.20.5.128/27`, range `10.20.5.129`–`10.20.5.158`, broadcast `10.20.5.159`, 30 usable hosts.

### 5.2 Stateless NACL Design (`network/nacl.json`)
The public subnet NACL was configured with:
- **Inbound:** Rule 100 denies abusive block `198.51.100.0/24`; Rules 110/120 allow TCP 80/443 from `0.0.0.0/0`; Rule 130 allows TCP 22 from management (`10.20.5.128/27`); Rule 140 allows return traffic from app (`10.20.0.0/22`, ports 1024–65535).
- **Outbound:** Rule 100 allows TCP 8000 to app (`10.20.0.0/22`); Rule 110 allows client return traffic (`0.0.0.0/0`, ports 1024–65535).
- **Simulation:** Validated via `tools/nacl_sim.py` against `packets_sample.jsonl`, achieving **6 / 6 (100%) correct decisions**.

### 5.3 Stateless NACL Operational Reasoning
1. **Need for Separate Reply Rules:** A stateless NACL evaluates each packet in isolation without session tracking. Outbound responses to web clients travel to ephemeral ports (1024–65535); without explicit return rules, responses are dropped by default deny.
2. **Rule Ordering Precedence:** NACLs evaluate rules in ascending numerical order (first match terminates). The deny rule for `198.51.100.0/24` must have a lower rule number than the `0.0.0.0/0` web allow rules; otherwise, abusive traffic would match the wildcard allow rule first.

---

## Section 6: Task 6 — Reproducibility, Quality Gates, and CI/CD

### 6.1 Automation Workflow
The system supports full deployment from clean clones using `make up` and cluster destruction with `make down`.

### 6.2 GitHub Actions Pipeline
The pipeline in `.github/workflows/ci.yml` enforces four strictly ordered stages:
1. **Linting:** Bytecode compilation check (`compileall`) and static analysis with `ruff`.
2. **Unit Tests:** Executes 17 unit tests covering schema validation, fault injection, scoring logic, and data cleaning.
3. **Model Evaluation & Quality Gate:** Downloads the released model asset, executes inference against `data/validation.jsonl`, and enforces `score.py --min-validity 95`.
4. **Secret Scan:** Scans repository history using `gitleaks` (reporting 0 leaks).

When dispatched against the untrained Pythia-70M model, the quality gate tripped immediately (0% JSON validity), demonstrating that the CI pipeline prevents corrupted models from entering deployment.

---

## Section 7: Task 7 — Performance, Costing, and System Review

### 7.1 Locust Load Benchmark
Standard test execution: 4 concurrent users, spawn rate 4, duration 2 minutes:
- Total Requests: 89 | Successful (HTTP 200): 78 | Failed: 11 (error rate 12.36%)
- Throughput: 0.748 requests/second
- Median Latency (p50): 3,700 ms | 95th Percentile Latency (p95): 16,000 ms
- Resource Consumption: CPU saturated at 1 core per pod; RAM peaked at 560 MiB.

### 7.2 Cloud Cost Modeling (`data/rate_card.json`)
- Limits: 1 vCPU @ 3.50 INR/hr + 1 GiB RAM @ 0.45 INR/hr = 3.95 INR / pod-hour.
- Total 2-Replica Cost: $2 \times 3.95 = 7.90\text{ INR / hour}$.
- Measured Hourly Request Volume: $\frac{78\text{ req}}{120\text{ s}} \times 3,600\text{ s} = 2,340\text{ requests / hour}$.
$$\text{Cost per 1,000 Requests} = \left(\frac{7.90\text{ INR}}{2,340\text{ requests}}\right) \times 1,000 = \mathbf{3.376\text{ INR}}$$

### 7.3 Service Level Objective (SLO) Accounting
- **SLO Definition:** 99.0% of requests succeed with HTTP 200 and schema-valid JSON over a 2-minute window.
- Total Requests: 89 $\implies$ Error Budget: $\lfloor 89 \times 0.01 \rfloor = 0$ allowed failures.
- Actual Failures: 11 failures $\implies$ Error budget consumed: **1,236%** (budget completely exhausted due to CPU-bound queue saturation).

### 7.4 Comprehensive Review Matrix

| Component | Measured Evidence | Identified Limitation | Proposed Improvement |
| :--- | :--- | :--- | :--- |
| **Data & Storage** | 2,292 valid records filtered from 3,000 outputs | Single SeaweedFS master instance without volume replication | Deploy Multi-AZ MinIO cluster with S3 bucket replication factor of 3 |
| **Model Quality** | 90.0% JSON validity; 41.0% full-frame accuracy | 70M parameter model occasionally outputs truncated JSON | Implement constrained grammar decoding (Outlines/Guidance) to guarantee 100% JSON validity |
| **Latency & Throughput** | 0.748 req/s throughput; p95 latency = 16,000 ms | Unquantized PyTorch CPU sequential generation | Export weights to ONNX Runtime INT8 or GGML/llama.cpp for 4x inference speedup |
| **Resource Utilisation** | Peak memory = 560 MiB; CPU throttled at 1 core | High CPU saturation under concurrent load triggers request queues | Pin CPU cores with OpenMP thread affinity and configure HPA minReplicas=2 |
| **Reliability & Recovery** | Cold-start median: 42.5s; pod replica auto-recovered | Pod startup delayed by synchronous S3 model download | Implement local hostPath caching or Kubernetes CSI snapshot volumes |
| **Security & Cost** | Cost: 3.376 INR / 1,000 requests; 6/6 NACL passed | Ingress lacks TLS encryption; plain HTTP endpoints | Integrate cert-manager for automated TLS termination and Istio mutual TLS (mTLS) |

---

## Section 8: Conclusion
The AeroParse project successfully demonstrates the end-to-end lifecycle of a knowledge-distilled language model deployed on a cloud-native Kubernetes platform. By pairing rigorous data filtering with sequence-level distillation, a 70M parameter model retained over 93% of the 3.8B teacher's extraction capabilities while operating within stringent CPU and memory budgets. Combining automated CI/CD quality gates, stateless network security, and declarative infrastructure establishes a resilient, reproducible foundation for resource-constrained edge NLP deployments.
