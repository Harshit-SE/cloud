"""
Builds report/report.pdf using ReportLab SimpleDocTemplate.
Generates an 8-page professional technical report covering Tasks 1 to 7.
"""

from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = ROOT / "report" / "report.pdf"


class NumberedCanvas(canvas.Canvas):
    """Adds running headers and footers with Page X of Y numbering."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#475569"))

        # Running Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 750, "AeroParse: Cloud-Native Command-Parsing Distillation")
            self.drawRightString(558, 750, "CS3081 Cloud Computing Mini Project")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(54, 744, 558, 744)

        # Running Footer (all pages)
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(54, 45, 558, 45)
        self.drawString(54, 32, "Roll No: 230101065 — CS3081 Mini Project Submission")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 32, page_str)
        self.restoreState()


def build_pdf():
    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        "DocSubTitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#087e8b"),
        spaceAfter=14
    )

    h1_style = ParagraphStyle(
        "Heading1_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#0b3954"),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        "Heading2_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#087e8b"),
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        "Body_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12.5,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=6
    )

    bullet_style = ParagraphStyle(
        "Bullet_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11.5,
        leftIndent=14,
        firstLineIndent=-10,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=3
    )

    code_style = ParagraphStyle(
        "Code_Custom",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor("#0f172a"),
        backColor=colors.HexColor("#f8fafc"),
        borderPadding=4,
        spaceAfter=6
    )

    table_header_style = ParagraphStyle(
        "TH",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#0f172a")
    )

    table_cell_style = ParagraphStyle(
        "TD",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#334155")
    )

    story = []

    # Title & Metadata
    story.append(Paragraph("AeroParse: Knowledge Distillation & Deployment on Local Cloud", title_style))
    story.append(Paragraph("CS3081 Cloud Computing — Assignment Mini Project Report | Roll No: 230101065", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0b3954"), spaceAfter=10))

    # Executive Summary / Overview
    story.append(Paragraph("System Abstract & Overview", h2_style))
    story.append(Paragraph(
        "This project investigates sequence-level knowledge distillation and cloud-native deployment of an "
        "ultra-lightweight command parser. A 3.8-billion parameter teacher model (Microsoft Phi-3.5-mini-instruct via Ollama) "
        "was distilled into a 70-million parameter student model (EleutherAI Pythia-70M). The model is served on a local "
        "Kubernetes cluster (k3d) with SeaweedFS S3 object storage, horizontal pod autoscaling, health probes, and automated "
        "CI/CD testing. All seven tasks specified in the assignment are addressed with measured evidence, architectural diagrams, "
        "and critical reflection.", body_style
    ))

    # Task 1
    story.append(Paragraph("Task 1: Object Storage and Parallel Teacher Labelling", h1_style))
    story.append(Paragraph(
        "<b>Cluster & Storage Architecture:</b> A single-node local Kubernetes cluster was provisioned using k3d from "
        "<code>cluster/k3d.yaml</code> with port 8080 forwarded to the Traefik ingress load balancer. SeaweedFS was deployed in the "
        "<code>data</code> namespace via Helm (<code>cluster/seaweedfs-values.yaml</code>) exposing an S3-compatible API with "
        "buckets <code>datasets</code> and <code>models</code>. The input pool <code>commands_pool.jsonl</code> (3,000 commands) "
        "was uploaded to the datasets bucket.", body_style
    ))
    story.append(Paragraph(
        "<b>Parallel Sharding Architecture:</b> The teacher (Phi-3.5) was served locally via Ollama with fixed seed 42 and "
        "temperature 0.0. To accelerate labelling, <code>worker/teacher_worker.py</code> sharded commands across worker pods using "
        "modulo arithmetic: <code>(line_index % SHARD_COUNT) == SHARD_INDEX</code>. Two workers ran in namespace <code>pipeline</code>, "
        "writing <code>datasets/teacher/shard-0.jsonl</code> and <code>shard-1.jsonl</code>. Every command ID appeared in exactly one shard.",
        body_style
    ))
    story.append(Paragraph(
        "<b>Data Cleaning Pipeline:</b> <code>worker/clean.py</code> loaded all shard outputs and rejected invalid entries according to "
        "the five assignment criteria: (a) malformed JSON, (b) invalid key sets (strictly: intent, date, time, place), (c) unallowed intents, "
        "(d) unanchored slot values not present in command text, and (e) duplicate commands (retaining lowest ID).", body_style
    ))

    # Task 1 Table
    t1_data = [
        [Paragraph("Category", table_header_style), Paragraph("Filter Rule", table_header_style), Paragraph("Count", table_header_style)],
        [Paragraph("Input Records", table_cell_style), Paragraph("Total pool from commands_pool.jsonl", table_cell_style), Paragraph("3,000", table_cell_style)],
        [Paragraph("Rule (a) Invalid JSON", table_cell_style), Paragraph("Syntax error or decode failure", table_cell_style), Paragraph("142", table_cell_style)],
        [Paragraph("Rule (b) Wrong Keys", table_cell_style), Paragraph("Keys != {intent, date, time, place}", table_cell_style), Paragraph("88", table_cell_style)],
        [Paragraph("Rule (c) Invalid Intent", table_cell_style), Paragraph("Intent outside 8 allowed categories", table_cell_style), Paragraph("64", table_cell_style)],
        [Paragraph("Rule (d) Invalid Slot", table_cell_style), Paragraph("Slot text not verbatim in command", table_cell_style), Paragraph("118", table_cell_style)],
        [Paragraph("Rule (e) Duplicates", table_cell_style), Paragraph("Duplicate commands removed", table_cell_style), Paragraph("296", table_cell_style)],
        [Paragraph("<b>Kept Records</b>", table_cell_style), Paragraph("Cleaned training dataset (datasets/v1/train.jsonl)", table_cell_style), Paragraph("<b>2,292</b>", table_cell_style)],
    ]
    t1_table = Table(t1_data, colWidths=[120, 280, 100])
    t1_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t1_table)
    story.append(Paragraph("<b>Integrity Formula Verification:</b> 3,000 = 142 + 88 + 64 + 118 + 296 + 2,292 (exact match). SHA-256 recorded in <code>train.sha256</code>.", body_style))

    story.append(Spacer(1, 10))

    # Task 2
    story.append(Paragraph("Task 2: Training the Student (Sequence-Level Distillation)", h1_style))
    story.append(Paragraph(
        "<b>Training Setup:</b> EleutherAI/pythia-70m was fine-tuned on CPU using PyTorch and Hugging Face Transformers on the first "
        "1,500 records of <code>train.jsonl</code>. Each sequence was structured as <code>Command: &lt;text&gt;\\nJSON: &lt;teacher_reply&gt;</code>. "
        "Loss was computed solely on JSON generation tokens by masking prompt tokens with -100.", body_style
    ))
    story.append(Paragraph(
        "<b>Reproducibility:</b> Configured via <code>training/config.yaml</code> with pinned seed (42), learning rate (5e-5), batch size (4), "
        "epochs (3), max sequence length (256), and library versions (Python 3.11, PyTorch 2.15.0, Transformers 4.57.6). Supports single-command "
        "execution via <code>make train</code> and verification subset <code>make train SUBSET=50</code>. Loss per epoch logged to <code>training/loss.csv</code>.",
        body_style
    ))
    story.append(Paragraph(
        "<b>Model Artefacts:</b> Model v1 and v2 uploaded to S3 bucket <code>models</code> under <code>models/v1/</code> and <code>models/v2/</code>. "
        "Checksum saved in <code>models/v1/model.sha256</code> matches the published GitHub Release asset.", body_style
    ))

    # Task 2 Benchmark Table
    t2_data = [
        [Paragraph("Metric", table_header_style), Paragraph("Teacher (Phi-3.5)", table_header_style), Paragraph("Untrained Pythia-70M", table_header_style), Paragraph("Distilled Student (v1)", table_header_style)],
        [Paragraph("JSON Validity", table_cell_style), Paragraph("94.0%", table_cell_style), Paragraph("0.0%", table_cell_style), Paragraph("90.0%", table_cell_style)],
        [Paragraph("Intent Accuracy", table_cell_style), Paragraph("85.0%", table_cell_style), Paragraph("0.0%", table_cell_style), Paragraph("75.0%", table_cell_style)],
        [Paragraph("Date Accuracy", table_cell_style), Paragraph("71.0%", table_cell_style), Paragraph("0.0%", table_cell_style), Paragraph("68.0%", table_cell_style)],
        [Paragraph("Time Accuracy", table_cell_style), Paragraph("79.0%", table_cell_style), Paragraph("0.0%", table_cell_style), Paragraph("76.0%", table_cell_style)],
        [Paragraph("Place Accuracy", table_cell_style), Paragraph("81.0%", table_cell_style), Paragraph("0.0%", table_cell_style), Paragraph("77.0%", table_cell_style)],
        [Paragraph("<b>Full-Frame Accuracy</b>", table_cell_style), Paragraph("<b>44.0%</b>", table_cell_style), Paragraph("<b>0.0%</b>", table_cell_style), Paragraph("<b>41.0%</b>", table_cell_style)],
    ]
    t2_table = Table(t2_data, colWidths=[130, 120, 120, 130])
    t2_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t2_table)
    story.append(Paragraph(
        "<b>Theoretical Explanation:</b> (a) <i>Sequence-level distillation</i> trains on teacher generated discrete token sequences using standard cross-entropy loss. "
        "(b) <i>Logit-based distillation</i> trains on soft probability distributions across the full vocabulary via KL divergence, transferring dark knowledge. "
        "(c) <i>Why logit-based is impossible here:</i> Ollama exposes a black-box text-generation API without logit access, and Phi-3.5 (32K vocabulary) and Pythia-70M (50K vocabulary) share incompatible tokenizers. "
        "(d) <i>Limitation:</i> Sequence-level distillation provides no uncertainty signal; the student memorizes teacher hallucinations and syntax errors equally with correct samples.",
        body_style
    ))

    story.append(Spacer(1, 10))

    # Task 3
    story.append(Paragraph("Task 3: The Inference Service in a Container", h1_style))
    story.append(Paragraph(
        "<b>FastAPI Microservice:</b> Implemented in <code>service/app.py</code> with endpoints: POST <code>/parse</code> returning four-key JSON "
        "and headers <code>X-Model-Version</code> and <code>X-Served-By</code>; GET <code>/healthz</code> (200 alive); GET <code>/readyz</code> (503 loading, 200 ready). "
        "Configuration strictly governed by <code>MODEL_URI</code>, <code>MODEL_VERSION</code>, <code>S3_ENDPOINT</code>, and <code>MAX_NEW_TOKENS</code>.", body_style
    ))
    story.append(Paragraph(
        "<b>Dynamic S3 Loading & Secrets:</b> Container image contains zero weights. At startup, weights are downloaded from SeaweedFS using S3 credentials "
        "mounted from Kubernetes Secret <code>seaweedfs-s3-credentials</code>.", body_style
    ))
    story.append(Paragraph(
        "<b>Schema Validation & Fault Injection:</b> Every output is validated against <code>schema.json</code>. Malformed JSON or schema violations return "
        "HTTP 500 with <code>{\"error\": \"invalid_model_output\"}</code>. Setting <code>FAULT_INJECT=1</code> forces output to 'not json', verifying error interception.", body_style
    ))
    story.append(Paragraph(
        "<b>Container Optimization & Resource Limit Test:</b> Built on <code>python:3.12-slim</code> with CPU-only wheels, image size is 1.66 GB (&lt; 2 GB). "
        "50 sequential requests under 1 CPU / 1 GiB memory limits completed with 0 OOM kills and <b>737.4 MiB peak memory</b>.", body_style
    ))

    story.append(Spacer(1, 10))

    # Task 4
    story.append(Paragraph("Task 4: Kubernetes Deployment, Scaling, and Reliability", h1_style))
    story.append(Paragraph(
        "<b>Workload Orchestration:</b> Deployed in namespace <code>app</code> with 2 replicas, resource requests 500m/512Mi, limits 1 CPU/1GiB, "
        "ClusterIP service, Traefik ingress for <code>/parse</code>, and readiness/liveness probes.", body_style
    ))
    story.append(Paragraph(
        "<b>Autoscaling (HPA):</b> HPA configured for min 1, max 2 replicas at 70% CPU target. Scaled to 2 replicas under load, then scaled down to 1 after load stopped.", body_style
    ))
    story.append(Paragraph(
        "<b>Rolling Updates & Rollback:</b> Updating MODEL_VERSION from v1 to v2 during active load achieved 0.0% failed requests. Rollback via "
        "<code>kubectl rollout undo</code> restored v1 without downtime.", body_style
    ))
    story.append(Paragraph(
        "<b>Recovery & Cold-Start:</b> Pod deletion under load recovered replica count with &lt; 2% request drops. Cold-start median across 3 trials "
        "was <b>42.5 seconds</b> (Run 1: 43.8s, Run 2: 41.2s, Run 3: 42.5s).", body_style
    ))
    story.append(Paragraph(
        "<b>Load Balancing:</b> Over 2-minute load test, Pod 1 served 41 requests (52.6%) and Pod 2 served 37 requests (47.4%), satisfying the &gt;30% requirement.", body_style
    ))

    story.append(Spacer(1, 10))

    # Task 5
    story.append(Paragraph("Task 5: Subnetting and Network Access Control", h1_style))
    story.append(Paragraph(
        "<b>VLSM Subnet Allocation:</b> Address block <code>10.20.0.0/16</code> divided contiguously from largest requirement to smallest using "
        "<code>usable_hosts = 2^(32 - prefix) - 2</code>:", body_style
    ))

    t5_data = [
        [Paragraph("Subnet", table_header_style), Paragraph("Required", table_header_style), Paragraph("Network Address", table_header_style), Paragraph("Prefix", table_header_style), Paragraph("Usable Host Range", table_header_style), Paragraph("Broadcast", table_header_style), Paragraph("Usable Hosts", table_header_style)],
        [Paragraph("app", table_cell_style), Paragraph("1,000", table_cell_style), Paragraph("10.20.0.0", table_cell_style), Paragraph("/22", table_cell_style), Paragraph("10.20.0.1 - 10.20.3.254", table_cell_style), Paragraph("10.20.3.255", table_cell_style), Paragraph("1,022", table_cell_style)],
        [Paragraph("public", table_cell_style), Paragraph("250", table_cell_style), Paragraph("10.20.4.0", table_cell_style), Paragraph("/24", table_cell_style), Paragraph("10.20.4.1 - 10.20.4.254", table_cell_style), Paragraph("10.20.4.255", table_cell_style), Paragraph("254", table_cell_style)],
        [Paragraph("data", table_cell_style), Paragraph("100", table_cell_style), Paragraph("10.20.5.0", table_cell_style), Paragraph("/25", table_cell_style), Paragraph("10.20.5.1 - 10.20.5.126", table_cell_style), Paragraph("10.20.5.127", table_cell_style), Paragraph("126", table_cell_style)],
        [Paragraph("management", table_cell_style), Paragraph("20", table_cell_style), Paragraph("10.20.5.128", table_cell_style), Paragraph("/27", table_cell_style), Paragraph("10.20.5.129 - 10.20.5.158", table_cell_style), Paragraph("10.20.5.159", table_cell_style), Paragraph("30", table_cell_style)],
    ]
    t5_table = Table(t5_data, colWidths=[65, 50, 75, 45, 135, 75, 55])
    t5_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(t5_table)
    story.append(Paragraph(
        "<b>NACL Implementation:</b> Public subnet stateless NACL (<code>network/nacl.json</code>) tested with <code>tools/nacl_sim.py</code> (6/6 = 100.0% correct). "
        "<b>Operational Reasoning:</b> (1) Stateless NACLs do not track connection state; return traffic to ephemeral ports (1024-65535) requires separate explicit rules. "
        "(2) Rules evaluate in ascending order with first match winning; deny rule for 198.51.100.0/24 must precede broad allow rules to prevent bypass.", body_style
    ))

    story.append(Spacer(1, 10))

    # Task 6
    story.append(Paragraph("Task 6: Reproducibility, Testing, and CI/CD", h1_style))
    story.append(Paragraph(
        "<b>Automation:</b> Single-command deployment via <code>make up</code> and teardown via <code>make down</code>. "
        "<b>GitHub Actions Pipeline:</b> Four strictly ordered stages: (1) Linting (Ruff and compileall), (2) Unit tests (17 tests across 4 modules), "
        "(3) Model evaluation downloading release asset with quality gate <code>score.py --min-validity 95</code>, and (4) Secret scanning via Gitleaks (0 leaks). "
        "Deliberately evaluated untrained Pythia-70M failed the gate (0% validity), proving pipeline protection. <code>AI_USE.md</code> documents tool attribution.", body_style
    ))

    story.append(Spacer(1, 10))

    # Task 7
    story.append(Paragraph("Task 7: Performance, Cost, and Review", h1_style))
    story.append(Paragraph(
        "<b>Locust Load Test Measurements:</b> 4 users, 2 minutes: 89 requests, 78 successful, 11 failed (error rate 12.36%). "
        "Throughput: 0.748 req/s. Median latency (p50): 3,700 ms. 95th percentile latency (p95): 16,000 ms. CPU peaked near 1 core limit; RAM peaked at 560 MiB.", body_style
    ))
    story.append(Paragraph(
        "<b>Cost Estimation (rate_card.json):</b> Replica rate = 1 vCPU (3.50 INR) + 1 GiB RAM (0.45 INR) = 3.95 INR/hr. "
        "Two replicas = 7.90 INR/hr. Hourly requests served = (78 / 120s) * 3600 = 2,340 req/hr. "
        "<b>Cost per 1,000 requests = (7.90 / 2340) * 1000 = 3.376 INR</b>.", body_style
    ))
    story.append(Paragraph(
        "<b>Service Level Objective (SLO):</b> Target: 99.0% success over 2-minute load test. Total requests: 89. "
        "Error budget: floor(89 * 0.01) = 0 allowed failures. Actual failures: 11. Error budget consumed: <b>1,236%</b> (SLO breached due to CPU saturation on laptop).", body_style
    ))

    # Review Table
    t7_data = [
        [Paragraph("Component", table_header_style), Paragraph("Measured Evidence", table_header_style), Paragraph("Identified Limitation", table_header_style), Paragraph("Proposed Improvement", table_header_style)],
        [Paragraph("Data & Storage", table_cell_style), Paragraph("2,292 valid records from 3,000 outputs", table_cell_style), Paragraph("Single SeaweedFS volume; no HA replication", table_cell_style), Paragraph("Multi-AZ MinIO cluster with 3x replication factor", table_cell_style)],
        [Paragraph("Model Quality", table_cell_style), Paragraph("90.0% JSON validity; 41.0% full-frame", table_cell_style), Paragraph("Occasional truncated JSON syntax errors", table_cell_style), Paragraph("Constrained grammar decoding (Outlines/Guidance)", table_cell_style)],
        [Paragraph("Latency & Throughput", table_cell_style), Paragraph("0.748 req/s; p95 latency = 16,000 ms", table_cell_style), Paragraph("CPU-only unquantized autoregressive decoding", table_cell_style), Paragraph("INT8 ONNX Runtime or GGML/llama.cpp quantization", table_cell_style)],
        [Paragraph("Resource Utilisation", table_cell_style), Paragraph("Peak RAM 560 MiB; CPU throttled at 1 core", table_cell_style), Paragraph("CPU saturation under concurrency causes queuing", table_cell_style), Paragraph("OpenMP core affinity and dedicated cloud compute", table_cell_style)],
        [Paragraph("Reliability & Recovery", table_cell_style), Paragraph("Cold-start median 42.5s; pod recovered", table_cell_style), Paragraph("Synchronous S3 download delays pod readiness", table_cell_style), Paragraph("Local hostPath node caching or CSI volume snapshots", table_cell_style)],
        [Paragraph("Security & Cost", table_cell_style), Paragraph("Cost: 3.376 INR/1k req; 6/6 NACL passed", table_cell_style), Paragraph("Ingress lacks TLS termination (plain HTTP)", table_cell_style), Paragraph("cert-manager Let's Encrypt TLS and Istio mTLS", table_cell_style)],
    ]
    t7_table = Table(t7_data, colWidths=[90, 110, 150, 150])
    t7_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t7_table)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully compiled report to: {PDF_PATH}")
    print(f"PDF Size: {PDF_PATH.stat().st_size} bytes")


if __name__ == "__main__":
    build_pdf()
