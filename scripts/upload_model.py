
import argparse
import hashlib
import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

parser = argparse.ArgumentParser()
parser.add_argument("--file", required=True)
parser.add_argument("--version", default="v1")
args = parser.parse_args()

model_path = Path(args.file)
if not model_path.is_file():
    raise SystemExit(f"Model archive not found: {model_path}")

expected = {
    "v1": "3b098817b3ab49b30b44cd2b6086b71b1ef7645542451883d54dfcfebab47bfe",
    "v2": "47ce600a2c68fd4f36737ce09a1fbf719ced97cc6c9e388aa92c07af14b01117",
}

if args.version not in expected:
    raise SystemExit("Version must be v1 or v2")

print("Verifying model SHA-256...")
digest = hashlib.sha256()
with model_path.open("rb") as f:
    for chunk in iter(lambda: f.read(1024 * 1024), b""):
        digest.update(chunk)

actual = digest.hexdigest()
if actual != expected[args.version]:
    raise SystemExit(f"Checksum mismatch: {actual}")

print("Checksum verified.")

s3 = boto3.client(
    "s3",
    endpoint_url=os.getenv("S3_ENDPOINT", "http://localhost:8333"),
    aws_access_key_id="anonymous",
    aws_secret_access_key="anonymous",
    region_name="us-east-1",
)

bucket = "models"
key = f"{args.version}/{model_path.name}"

try:
    s3.head_bucket(Bucket=bucket)
except ClientError:
    s3.create_bucket(Bucket=bucket)

print(f"Uploading {model_path} to s3://{bucket}/{key}...")
s3.upload_file(str(model_path), bucket, key)

s3.head_object(Bucket=bucket, Key=key)
print(f"Upload verified: s3://{bucket}/{key}")

