# HANDWRITTEN REFLECTION NOTES REFERENCE
## File to Scan: `230101065.pdf` (Strictly 3 Pages Maximum)

> **Instructions for the Student:**
> Write the following content across **exactly three physical sheets of A4 paper** in your neat handwriting.
> Ensure your **Name**, **Roll Number (230101065)**, and **GitHub Repo Link** are written clearly at the top of Page 1.
> After writing, use a document scanner app (such as Adobe Scan or CamScanner) to scan the 3 pages into a single PDF file and name it strictly:
> **`230101065.pdf`**

---

### ==================== PAGE 1 ====================

**STUDENT DETAILS:**
- **Name:** [Your Full Name]
- **Roll Number:** 230101065
- **Course:** CS3081 Cloud Computing — Mini Project
- **Project Title:** AeroParse: Knowledge Distillation & Deployment of a Command Parser on Local Cloud
- **GitHub Repository Link:** https://github.com/[your-github-username]/AeroParse

---

#### 1. Executive Summary & Objective
In this mini project, I designed, trained, evaluated, and deployed a cloud-native command parsing service. The objective was to take a relatively capable teacher model (Microsoft Phi-3.5-mini-instruct, 3.8B parameters) and distill its command-to-JSON reasoning into an ultra-compact student model (EleutherAI Pythia-70M, 70M parameters), deploy it as a containerized microservice on a local Kubernetes cluster (k3d), and evaluate it under realistic cloud operational conditions.

#### 2. What I Learnt
Through this end-to-end project, I gained deep practical understanding across several core cloud computing and NLP engineering concepts:
1. **Sequence-Level Knowledge Distillation:** I learnt how smaller language models can be supervised by treating teacher-generated outputs as target sequences (Kim & Rush, 2016). By masking the input prompt tokens with label `-100`, the student computes cross-entropy loss strictly over target JSON tokens, effectively acting as an automated sequence translator.
2. **Local Cloud & Object Storage Decoupling:** I learnt how modern 12-factor cloud applications decouple stateless compute from stateful storage. By provisioning SeaweedFS inside the `data` namespace and downloading model weights dynamically at pod startup via S3 APIs, container images remained lightweight (1.66 GB) without baking heavy model weights into Docker layers.
3. **Stateless vs Stateful Network Security:** I gained hands-on experience designing Network Access Control Lists (NACLs). I learnt that because stateless packet filters evaluate every packet independently without session tracking, outbound replies to clients require explicit ephemeral port allow rules (ports 1024–65535).
4. **Resilience, Health Probes & Autoscaling:** I understood the vital distinction between liveness (`/healthz`) and readiness (`/readyz`) probes. The readiness probe successfully prevented Kubernetes from routing traffic to pods while model weights were still streaming from S3 into memory.

#### 3. Technical Discoveries on Model Architectures
- **Pythia-70M Suitability:** A 70-million-parameter causal language model is small enough to train and run CPU inference on a commodity laptop with under 1 GiB RAM. However, its compressed representation makes it vulnerable to syntax degradation and repetition loops without careful temperature and sequence length constraints.
- **Teacher Bottleneck:** Generating labels with Phi-3.5 locally via Ollama across 3,000 commands required parallelization. Modulo sharding across worker pods (`line_index % SHARD_COUNT`) taught me how batch inference workloads scale linearly across cloud worker pools.

---

### ==================== PAGE 2 ====================

#### 4. Engineering Challenges Faced & Solutions Implemented

**Challenge 1: Teacher Model Hallucinations and Inconsistent JSON Outputs**
- *Problem:* Despite setting temperature=0 and seed=42, Phi-3.5 occasionally emitted invalid JSON syntax, markdown fences (` ```json `), illegal intent categories, and hallucinated slot values not present in the user's spoken command.
- *Solution:* I built a strict, five-stage validation pipeline in `worker/clean.py` that enforced assignment rules (a) through (e). The cleaner verified exact JSON syntax, strictly verified the four required keys (`intent`, `date`, `time`, `place`), verified the closed set of 8 intents, and checked verbatim slot substrings in the command text. It discarded 708 invalid/duplicate records, yielding a clean dataset of 2,292 records (`datasets/v1/train.jsonl`).

**Challenge 2: Infeasibility of Logit-Based Distillation**
- *Problem:* The project explored whether logit-based distillation (Hinton et al., 2015) could transfer richer probability distributions than sequence-level distillation.
- *Solution & Analysis:* I proved that logit-based distillation was technically impossible in this setup:
  1. *Ollama Interface:* Ollama only exposes a text generation endpoint (`/api/generate`) and does not expose vocabulary logits or forward activations.
  2. *Tokenizer Mismatch:* Phi-3.5 uses a 32,064-token SentencePiece tokenizer, whereas Pythia-70M uses a 50,304-token GPT-NeoX BPE tokenizer. Without an aligned projection matrix, token-level KL divergence cannot be computed. Therefore, sequence-level distillation was the optimal, viable approach.

**Challenge 3: Stateless NACL Asymmetric Traffic Dropping**
- *Problem:* Initial public subnet NACL configurations dropped legitimate HTTP/S responses returning to external clients, as well as backend responses returning from the `app` subnet.
- *Solution:* I diagnosed that stateless NACLs do not track connection handshakes. When an external client sends an HTTP request, the response packet travels outbound to a dynamically chosen client ephemeral port (1024–65535). By adding Rule 110 outbound (`0.0.0.0/0`, ports 1024–65535) and Rule 140 inbound (`10.20.0.0/22`, ports 1024–65535), packet flow was fully restored, achieving 100% (6/6) in `tools/nacl_sim.py`.

**Challenge 4: Strict Container Resource Constraints (1 CPU, 1 GiB RAM)**
- *Problem:* PyTorch applications easily exceed 1 GiB memory and crash with `OOMKilled` when running concurrent inferences.
- *Solution:* In `service/app.py`, I implemented `torch.inference_mode()`, loaded weights with `float32` CPU tensors, and guarded inference with a thread mutex (`model_mutex`). Sequential testing with 50 requests under hard container limits (1 CPU, 1 GiB) finished with 0 OOM kills and a measured peak memory of 737.4 MiB.

---

### ==================== PAGE 3 ====================

#### 5. Empirical Findings & Benchmarking Results

**Model Quality Comparison (on 100 Gold Validation Examples):**
- *JSON Validity:* Teacher: 94.0% | Untrained Pythia-70M: 0.0% | **Distilled Student (v1): 90.0%**
- *Intent Accuracy:* Teacher: 85.0% | Untrained: 0.0% | **Distilled Student: 75.0%**
- *Full-Frame Accuracy:* Teacher: 44.0% | Untrained: 0.0% | **Distilled Student: 41.0%**
- *Finding:* The distilled 70M model retained **93.2% of the teacher's full-frame accuracy** ($41\% / 44\%$) while operating with **54x fewer parameters** ($70\text{M}$ vs $3.8\text{B}$).

**Locust Load Test Measurements (4 Concurrent Users, 2 Minutes):**
- Total Requests: 89 | Successful: 78 | Failed: 11 (12.36% error rate)
- Throughput: 0.748 requests/second | Median Latency (p50): 3,700 ms | 95th Percentile Latency (p95): 16,000 ms
- Load Balancing: Pod 1 served 41 requests (52.6%); Pod 2 served 37 requests (47.4%). Both replicas served $> 30\%$ of total traffic.
- Cold-Start Time: Three pod restart trials yielded 43.8s, 41.2s, 42.5s $\implies$ **Median: 42.5s**.

**Hypothetical Cloud Cost Modeling (from `rate_card.json`):**
- 1 Replica = 1 vCPU (3.50 INR) + 1 GiB RAM (0.45 INR) = 3.95 INR / hour.
- 2 Replicas = $2 \times 3.95 = 7.90$ INR / hour.
- Hourly throughput = $(78 / 120\text{s}) \times 3600\text{s} = 2,340$ requests/hour.
$$\text{Cost per 1,000 Requests} = \left(\frac{7.90\text{ INR}}{2,340\text{ requests}}\right) \times 1,000 = \mathbf{3.376\text{ INR}}$$

**Service Level Objective (SLO) Accounting:**
- Objective: 99.0% request success over a 2-minute window.
- Error Budget for 89 requests: $\lfloor 89 \times 0.01 \rfloor = 0$ allowable failures.
- Actual failures: 11 failures $\implies$ **1,236% error budget consumed** (SLO breached due to CPU-bound inference saturation on laptop hardware).

#### 6. Critical Limitations & Proposed Engineering Improvements
1. **Model Syntax Errors:** Although JSON validity reached 90%, 10% of outputs failed schema checks. *Improvement:* Implement constrained grammar decoding (e.g., using Outlines or Guidance) to mathematically force the model to output valid JSON transitions only.
2. **CPU Inference Latency:** Unquantized autoregressive decoding on CPU caused high p95 latency (16s). *Improvement:* Quantize model weights to INT8 or INT4 using ONNX Runtime or GGML/llama.cpp, yielding an estimated 3x–4x latency reduction.
3. **Storage Resilience:** SeaweedFS ran on a single volume with no HA replication. *Improvement:* Deploy a multi-AZ MinIO cluster with cross-region replication.
4. **Transport Security:** Cluster Ingress handled unencrypted HTTP traffic. *Improvement:* Integrate `cert-manager` with Let's Encrypt for automatic TLS termination and mutual TLS (mTLS) via Istio.

#### 7. Final Reflections
This project gave me invaluable end-to-end exposure to how modern AI microservices are developed and operationalized. I learned that deploying machine learning models in production requires far more than training loss optimization; it demands robust data hygiene, strict schema guardrails, container optimization, declarative Kubernetes scaling, and rigorous network access policies.

**Student Signature:** ___________________________  
**Date:** November 2026
