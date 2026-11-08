# AeroParse: Lightweight Cloud Command-Parsing Language Engine

**Student Roll Number:** 230101065  
**Course:** CS3081 Cloud Computing — Mini Project  
**Repository:** https://github.com/Harshit-SE/cloud  

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Kubernetes](https://img.shields.io/badge/kubernetes-k3d-326CE5.svg)](https://k3d.io/)
[![Model](https://img.shields.io/badge/model-Pythia--70M-orange.svg)](https://huggingface.co/EleutherAI/pythia-70m)

**AeroParse** is a cloud-native, sequence-level knowledge-distilled command parsing engine designed for edge and low-resource cloud environments. It distills conversational command parsing knowledge from a large teacher model (Microsoft Phi-3.5-mini-instruct, 3.8B) into an ultra-compact student model (EleutherAI Pythia-70M), and serves inference requests through a resilient, autoscaling FastAPI microservice deployed on a local Kubernetes cluster.

---

## 1. System Architecture

```
                                [ External Client / Ingress Controller ]
                                                   │
                                          HTTP POST /parse (:8080)
                                                   ▼
┌────────────────────────────────────── Kubernetes Namespace: app ──────────────────────────────────────┐
│                                                                                                       │
│                       ┌──────────────────── Traefik Ingress ────────────────────┐                      │
│                       └────────────────────────────┬────────────────────────────┘                      │
│                                                    ▼                                                  │
│                                      ┌────── ClusterIP Service ──────┐                                │
│                                      └─────────────┬─────────────────┘                                │
│                                                    │                                                  │
│                         ┌──────────────────────────┴──────────────────────────┐                       │
│                         ▼                                                     ▼                       │
│             ┌───────────────────────┐                             ┌───────────────────────┐           │
│             │ Pod: aeroparse-rep-1  │                             │ Pod: aeroparse-rep-2  │           │
│             │  ├── FastAPI Core     │                             │  ├── FastAPI Core     │           │
│             │  ├── Pythia-70M (CPU) │                             │  ├── Pythia-70M (CPU) │           │
│             │  └── Schema Validator │                             │  └── Schema Validator │           │
│             └───────────┬───────────┘                             └───────────┬───────────┘           │
└─────────────────────────┼─────────────────────────────────────────────────────┼───────────────────────┘
                          │                                                     │
                          │        Download Weights (S3 Protocol on Startup)     │
                          └──────────────────────────┬──────────────────────────┘
                                                     ▼
┌────────────────────────────────────── Kubernetes Namespace: data ─────────────────────────────────────┐
│                                                                                                       │
│                            ┌───────────── SeaweedFS S3 Gateway ────────────┐                          │
│                            │   s3://models/v1/pythia-70m-v1.tar.gz         │                          │
│                            │   s3://datasets/commands_pool.jsonl           │                          │
│                            └───────────────────────────────────────────────┘                          │
└───────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Technology Stack

- **Student Language Model:** EleutherAI Pythia-70M (Causal LM, 70M parameters)
- **Teacher Language Model:** Microsoft Phi-3.5-mini-instruct (3.8B parameters via Ollama)
- **Machine Learning Framework:** PyTorch & Hugging Face Transformers
- **Web Service Framework:** FastAPI & Uvicorn ASGI
- **Object Storage:** SeaweedFS (S3-compatible distributed storage)
- **Containerization:** Docker (Debian Slim Python base, multi-stage, < 2 GB)
- **Orchestration:** Kubernetes using k3d (lightweight K3s in Docker)
- **Load Testing & Benchmarking:** Locust
- **CI/CD & Verification:** GitHub Actions, Ruff, Python unittest, Gitleaks

---

## 3. Directory Layout

```
├── .github/workflows/        # Automated CI/CD pipeline (lint, test, eval, secret scan)
├── cluster/                  # Local cluster definitions (k3d.yaml, seaweedfs-values.yaml)
├── data/                     # Schema rules, evaluation datasets, and rate card
│   ├── commands_pool.jsonl   # 3,000 raw input commands
│   ├── validation.jsonl      # 100 gold-labelled validation examples
│   ├── schema.json           # 4-key JSON schema and intent taxonomy
│   └── rate_card.json        # Hypothetical cloud billing rates
├── datasets/                 # Cleaned datasets and SHA-256 verification hashes
│   └── v1/train.jsonl        # Verified training set (2,292 examples)
├── k8s/                      # Kubernetes manifests (Deployment, Service, Ingress, HPA)
├── models/                   # Model checksums and release metadata
├── network/                  # Subnet designs, stateless NACL rules, and explanations
├── prompts/                  # Teacher extraction prompt
├── results/                  # Locust reports, scoring benchmarks, and explanations
├── scripts/                  # Shell automation (deploy.sh, destroy.sh, upload_model.py)
├── service/                  # FastAPI inference microservice and Dockerfile
├── tests/                    # Comprehensive unit test suite (17 tests)
├── tools/                    # Scoring, prediction, NACL simulation, and Locust load testing
├── training/                 # PyTorch sequence-level distillation trainer & config
├── AI_USE.md                 # AI usage disclosure and attribution
├── Makefile                  # Automated build and operation targets
└── README.md                 # Project documentation
```

---

## 4. Quickstart: Building & Deploying the System

### Prerequisites
Ensure the following tools are installed on your host machine:
- Docker Engine
- k3d (`curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash`)
- kubectl
- Helm 3
- Python 3.11+
- Make

### One-Command Deployment (`make up`)
To create the cluster, install object storage, provision the model weights, build the service container, and launch all workloads:

```bash
make up MODEL_VERSION=v1
```

Once deployment completes, the service ingress is accessible at:
```
http://localhost:8080/parse
```

### Verification and Health Check
```bash
# Check liveness
curl http://localhost:8080/healthz

# Check readiness (model loaded)
curl http://localhost:8080/readyz

# Send sample command
curl -X POST http://localhost:8080/parse \
  -H "Content-Type: application/json" \
  -d '{"text": "set an alarm for seven am tomorrow"}'
```

Expected JSON response:
```json
{
  "intent": "alarm_set",
  "date": "tomorrow",
  "time": "seven am",
  "place": null
}
```

Response headers will include:
- `X-Model-Version: v1`
- `X-Served-By: <pod-name>`

### One-Command Cluster Teardown (`make down`)
To completely delete the k3d cluster and free all resources:

```bash
make down
```

---

## 5. Model Distillation & Training

AeroParse trains `EleutherAI/pythia-70m` using **sequence-level knowledge distillation** on CPU.

### Configuration
All training parameters are configured in [`training/config.yaml`](training/config.yaml):
- **Base Model:** `EleutherAI/pythia-70m`
- **Training Samples:** First 1,500 records from `datasets/v1/train.jsonl`
- **Seed:** `42`
- **Learning Rate:** `5e-5` (AdamW, weight decay 0.01)
- **Batch Size:** `4`
- **Epochs:** `3`
- **Max Sequence Length:** `256` tokens

### Training Execution
To train on the full 1,500 examples:
```bash
make train
```

To run a fast verification pass on 50 records:
```bash
make train SUBSET=50
```

Epoch-by-epoch loss is saved automatically to [`training/loss.csv`](training/loss.csv).

---

## 6. Model Evaluation Benchmarks

The model is evaluated using [`tools/score.py`](tools/score.py) against the 100 gold validation records in [`data/validation.jsonl`](data/validation.jsonl):

```bash
python tools/score.py \
  results/student_predictions.jsonl \
  data/validation.jsonl \
  --out results/student_validation.json
```

### Performance Comparison

| Metric | Teacher (Phi-3.5) | Untrained Pythia-70M | Distilled Student (AeroParse v1) |
| :--- | :---: | :---: | :---: |
| **JSON Validity** | 94.0% | 0.0% | **90.0%** |
| **Intent Accuracy** | 85.0% | 0.0% | **75.0%** |
| **Date Accuracy** | 71.0% | 0.0% | **68.0%** |
| **Time Accuracy** | 79.0% | 0.0% | **76.0%** |
| **Place Accuracy** | 81.0% | 0.0% | **77.0%** |
| **Full-Frame Accuracy** | 44.0% | 0.0% | **41.0%** |

The distilled 70M model retains **93.2%** of the teacher's full-frame accuracy ($41.0\% / 44.0\%$) despite having **54x fewer parameters** ($70\text{M}$ vs $3.8\text{B}$).

---

## 7. Automated Testing & CI/CD Pipeline

The test suite runs 17 automated unit tests covering schema validation, fault injection, packet filtering, and data cleaning:

```bash
# Execute local unit tests
make test
```

### GitHub Actions Pipeline
The automated workflow ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) executes four sequential stages:
1. **Lint:** Code syntax validation with `compileall` and `ruff`.
2. **Unit Tests:** Automated discovery across `tests/`.
3. **Model Evaluation:** Downloads released weights, runs inference on validation data, and scores accuracy.
4. **Secret Scan:** Scans commit history with `gitleaks` to guarantee zero committed credentials.

---

## 8. Network Subnetting & Stateless NACL

- **Subnet Allocation:** [`network/subnets.md`](network/subnets.md) details the VLSM division of `10.20.0.0/16` into four contiguous subnets (`app` /22, `public` /24, `data` /25, and `management` /27).
- **Network ACL:** [`network/nacl.json`](network/nacl.json) defines stateless packet filtering rules for the public subnet housing the ingress load balancer.
- **Simulation Verification:**
  ```bash
  python tools/nacl_sim.py network/nacl.json network/packets_sample.jsonl --check
  ```
  *Result: 6 / 6 test packets verified (100.0% accuracy).*

---

## 9. Performance, Load Testing & Cost Analysis (Task 7)

### Locust Load Test
Standard load test configuration: 4 concurrent users, spawn rate of 4, duration 2 minutes:
```bash
locust -f tools/locustfile.py \
  --headless \
  --users 4 \
  --spawn-rate 4 \
  --run-time 2m \
  --host http://localhost:8080 \
  --csv results/task7/loadtest
```

### Key Measured Metrics
- **Total Requests:** 89
- **Successful Requests (HTTP 200):** 78
- **Failed Requests:** 11
- **Throughput:** 0.748 requests/second
- **Median Latency (p50):** 3,700 ms
- **95th Percentile Latency (p95):** 16,000 ms
- **Replica Load Distribution:**
  - Pod 1: 41 requests (52.6%)
  - Pod 2: 37 requests (47.4%)
  *(Both replicas served > 30% of total load).*

### Cost Estimation (rate_card.json)
- **vCPU Rate:** 3.50 INR / hour
- **GiB Memory Rate:** 0.45 INR / hour
- **Per Replica Limit:** 1 vCPU, 1 GiB RAM $\implies 3.50 + 0.45 = 3.95$ INR / hour.
- **2 Replicas Total Hourly Cost:** $2 \times 3.95 = 7.90$ INR / hour.
- **Hourly Throughput:** $\frac{78\text{ requests}}{120\text{ seconds}} \times 3,600\text{ seconds} = 2,340\text{ requests / hour}$.
- **Cost per 1,000 Requests:**
  $$\text{Cost} = \left(\frac{7.90\text{ INR}}{2,340\text{ requests}}\right) \times 1,000 = \mathbf{3.376\text{ INR}}$$

---

## 10. Service Level Objective (SLO)

- **Objective Target:** 99.0% of requests succeed with HTTP 200 and valid JSON over a 2-minute load-test window.
- **Total Requests Evaluated:** 89
- **Error Budget (1.0% allowable failures):** $\lfloor 89 \times 0.01 \rfloor = 0$ requests allowed to fail.
- **Actual Failures Incurred:** 11 requests
- **Budget Consumed:** $11 / 0.89 = 1,236\%$ of error budget consumed (SLO breached due to CPU saturation on local laptop hardware).

---

## 11. Component Review & Improvement Matrix

| Component | Measured Evidence | Identified Limitation | Proposed Engineering Improvement |
| :--- | :--- | :--- | :--- |
| **Data & Storage** | 2,292 valid records filtered from 3,000 teacher outputs | Single SeaweedFS master instance without volume replication | Deploy Multi-AZ MinIO or Ceph cluster with S3 object versioning and replication factor of 3 |
| **Model Quality** | 90.0% JSON validity; 41.0% full-frame accuracy | 70M parameter model occasionally outputs truncated or invalid JSON | Employ constrained grammar sampling (Outlines / Guidance) to guarantee 100% valid JSON syntax |
| **Latency & Throughput** | 0.748 req/s throughput; p95 latency = 16,000 ms | PyTorch CPU-only sequential autoregressive decoding | Quantize weights to INT8/INT4 using ONNX Runtime or GGML/llama.cpp for 4x CPU speedup |
| **Resource Utilisation** | Peak memory = 560 MiB per pod; CPU throttled at 1 core | High CPU saturation under concurrent load triggers request queues | Optimize CPU thread affinities with OpenMP and set higher CPU limits on dedicated cluster nodes |
| **Reliability & Recovery** | Cold-start median: 42s; Replica count restored upon pod deletion | Pod initialization delayed by synchronous S3 model tarball download | Implement Kubernetes `initContainer` caching or persistent local node storage volume mounts |
| **Security & Cost** | Estimated cost: 3.376 INR per 1,000 requests; 6/6 NACL packets passed | Cluster ingress lacks TLS termination; plain HTTP communication | Integrate cert-manager with Let's Encrypt for automated TLS encryption and mutual TLS (mTLS) via Istio |

---

## 12. Licensing

The dataset is derived from SLURP under the Creative Commons Attribution 4.0 International License (CC BY 4.0).
EleutherAI Pythia-70M is released under the Apache 2.0 License.
AeroParse software and manifests are provided for academic research and educational demonstration.
