"""
AeroParse Inference Microservice
FastAPI service exposing /parse, /healthz, and /readyz endpoints.
Loads distilled Pythia-70M model directly from S3-compatible object storage (SeaweedFS).
"""

import os
import sys
import json
import socket
import tarfile
import logging
import threading
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from transformers import AutoTokenizer, AutoModelForCausalLM

from service.validator import validate_against_schema

# Set up structured logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("aeroparse")

# Mandatory environment variables per assignment specification
MODEL_URI = os.environ.get("MODEL_URI", "s3://models/v1/pythia-70m-v1.tar.gz")
MODEL_VERSION = os.environ.get("MODEL_VERSION", "v1")
S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://seaweedfs-s3.data.svc.cluster.local:8333")
MAX_NEW_TOKENS = int(os.environ.get("MAX_NEW_TOKENS", "100"))

# Optional / runtime flags
FAULT_INJECT = os.environ.get("FAULT_INJECT", "0") == "1"
POD_NAME = os.environ.get("POD_NAME", socket.gethostname())

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.json"
MODEL_LOCAL_DIR = Path("/tmp/aeroparse-model")

# Service state
is_ready: bool = False
model_instance: Optional[Any] = None
tokenizer_instance: Optional[Any] = None
model_mutex = threading.Lock()


class ParsePayload(BaseModel):
    text: str = Field(..., description="Natural language command to parse into structured slots")


def retrieve_model_artifact(s3_uri: str, local_destination: Path) -> None:
    """Fetch model tar.gz from SeaweedFS S3 storage and unpack securely."""
    parsed = urlparse(s3_uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError(f"Invalid MODEL_URI scheme or bucket: {s3_uri}")

    bucket_name = parsed.netloc
    object_key = parsed.path.lstrip("/")

    # Credentials passed from Kubernetes Secret via environment variables
    aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID", "anonymous")
    aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "anonymous")

    logger.info(f"Connecting to S3 at {S3_ENDPOINT} (bucket={bucket_name}, key={object_key})")
    import boto3
    s3_client = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name="us-east-1"
    )

    archive_temp = Path("/tmp/model_archive.tar.gz")
    logger.info(f"Downloading model artifact from {s3_uri}...")
    s3_client.download_file(bucket_name, object_key, str(archive_temp))

    local_destination.mkdir(parents=True, exist_ok=True)
    logger.info(f"Extracting model archive to {local_destination}...")

    # Path traversal protection
    with tarfile.open(archive_temp, "r:gz") as tar:
        base_dir = local_destination.resolve()
        for member in tar.getmembers():
            dest_path = (local_destination / member.name).resolve()
            if dest_path != base_dir and base_dir not in dest_path.parents:
                raise ValueError("Detected insecure relative path in tar archive")
        tar.extractall(local_destination)

    archive_temp.unlink(missing_ok=True)
    logger.info("Extraction complete.")


def initialize_model_worker() -> None:
    """Background startup task to load weights and mark service ready."""
    global is_ready, model_instance, tokenizer_instance
    try:
        retrieve_model_artifact(MODEL_URI, MODEL_LOCAL_DIR)

        logger.info(f"Initializing tokenizer and weights from {MODEL_LOCAL_DIR}...")
        tokenizer_instance = AutoTokenizer.from_pretrained(str(MODEL_LOCAL_DIR), local_files_only=True)
        model_instance = AutoModelForCausalLM.from_pretrained(
            str(MODEL_LOCAL_DIR),
            local_files_only=True,
            dtype=torch.float32
        )
        model_instance.to("cpu")
        model_instance.eval()

        is_ready = True
        logger.info(f"[READY] AeroParse service initialized with MODEL_VERSION={MODEL_VERSION}")
    except Exception as err:
        logger.error(f"[FATAL] Failed to load model artifact: {err}", exc_info=True)


@asynccontextmanager
async def lifespan_handler(app: FastAPI):
    # Asynchronously kick off model loading in background thread so /healthz responds immediately
    loader_thread = threading.Thread(target=initialize_model_worker, daemon=True)
    loader_thread.start()
    yield


app = FastAPI(
    title="AeroParse Command Parser Service",
    description="Lightweight knowledge-distilled command parsing service deployed on local Kubernetes.",
    lifespan=lifespan_handler
)





def run_inference(command_input: str) -> str:
    """Generate parsed JSON sequence using distilled causal language model."""
    prompt = f"Command: {command_input}\nJSON:"
    tokens = tokenizer_instance(prompt, return_tensors="pt")

    with model_mutex, torch.inference_mode():
        generated_tokens = model_instance.generate(
            **tokens,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            pad_token_id=tokenizer_instance.eos_token_id,
            eos_token_id=tokenizer_instance.eos_token_id
        )

    # Decode only the generated continuation
    target_tokens = generated_tokens[0][tokens["input_ids"].shape[1]:]
    return tokenizer_instance.decode(target_tokens, skip_special_tokens=True).strip()


@app.get("/healthz", status_code=status.HTTP_200_OK)
def liveness_check():
    """Liveness probe: returns 200 as long as the process is alive."""
    return {"status": "alive"}


@app.get("/readyz")
def readiness_check():
    """Readiness probe: returns 503 until model weights are loaded and ready."""
    if not is_ready:
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"status": "initializing"})
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ready"})


@app.post("/parse")
def parse_command(payload: ParsePayload):
    """Parses natural-language commands into structured 4-key JSON."""
    if not is_ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "model_not_ready"}
        )

    headers = {
        "X-Model-Version": MODEL_VERSION,
        "X-Served-By": POD_NAME,
    }

    # Task 3 requirement: FAULT_INJECT replaces output with 'not json'
    raw_output = "not json" if FAULT_INJECT else run_inference(payload.text)
    validated_frame = validate_against_schema(raw_output)

    if validated_frame is None:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "invalid_model_output"},
            headers=headers
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=validated_frame,
        headers=headers
    )
