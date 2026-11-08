#!/usr/bin/env bash
# ==============================================================================
# AeroParse Automated Deployment Workflow
# Orchestrates k3d cluster creation, SeaweedFS deployment, model provisioning,
# container compilation, and Kubernetes rollout.
# ==============================================================================
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CLUSTER="aeroparse-cluster"
MODEL_VERSION="${MODEL_VERSION:-v1}"
MODEL_DIR=".cache/models"

case "$MODEL_VERSION" in
  v1)
    MODEL_FILE="pythia-70m-v1.tar.gz"
    ;;
  v2)
    MODEL_FILE="pythia-70m-v2.tar.gz"
    ;;
  *)
    echo "[-] Error: Unsupported MODEL_VERSION: $MODEL_VERSION (must be v1 or v2)"
    exit 1
    ;;
esac

# Preflight requirements check
for tool in docker k3d kubectl helm curl python3; do
  command -v "$tool" >/dev/null || {
    echo "[-] Missing prerequisite tool: $tool"
    exit 1
  }
done

docker info >/dev/null 2>&1 || {
  echo "[-] Docker daemon is not running. Please start Docker and retry."
  exit 1
}

echo "=========================================================="
echo "          AeroParse Cluster Provisioning                  "
echo "=========================================================="

echo "==> Step 1: Initializing local k3d cluster"
if ! k3d cluster list | grep -q "$CLUSTER"; then
  k3d cluster create --config cluster/k3d.yaml
else
  echo "[*] Cluster '$CLUSTER' already exists. Reusing existing instance."
fi

kubectl config use-context "k3d-$CLUSTER"
kubectl wait --for=condition=Ready nodes --all --timeout=180s

echo "==> Step 2: Deploying SeaweedFS Object Storage in namespace 'data'"
helm repo add seaweedfs https://seaweedfs.github.io/seaweedfs/helm --force-update
helm repo update

kubectl create namespace data --dry-run=client -o yaml | kubectl apply -f -

if helm status seaweedfs -n data >/dev/null 2>&1; then
  helm upgrade seaweedfs seaweedfs/seaweedfs \
    --version 4.51.0 -n data -f cluster/seaweedfs-values.yaml \
    --timeout 15m --wait
else
  helm install seaweedfs seaweedfs/seaweedfs \
    --version 4.51.0 -n data -f cluster/seaweedfs-values.yaml \
    --timeout 15m --wait
fi

kubectl rollout status deployment/seaweedfs-s3 -n data --timeout=300s
kubectl rollout status statefulset/seaweedfs-master -n data --timeout=300s
kubectl rollout status statefulset/seaweedfs-volume -n data --timeout=300s
kubectl rollout status statefulset/seaweedfs-filer -n data --timeout=300s

echo "==> Step 3: Resolving model release artifact"
mkdir -p "$MODEL_DIR"
MODEL_PATH="$MODEL_DIR/$MODEL_FILE"

if [ ! -f "$MODEL_PATH" ]; then
  # Fallback to local release asset or remote source
  DOWNLOAD_URL="${MODEL_RELEASE_URL:-https://github.com/rahul-singh92/NanoParse/releases/download/v1.0/$MODEL_FILE}"
  echo "[*] Downloading model artifact from: $DOWNLOAD_URL"
  curl -fL "$DOWNLOAD_URL" -o "$MODEL_PATH"
fi

echo "==> Step 4: Establishing temporary S3 port-forward for model upload"
S3_PORT=8334
if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:$S3_PORT -sTCP:LISTEN >/dev/null 2>&1; then
  S3_PORT=8335
fi

kubectl port-forward -n data svc/seaweedfs-s3 "$S3_PORT:8333" \
  > /tmp/aeroparse-s3-portforward.log 2>&1 &
PF_PID=$!

cleanup() {
  kill "$PF_PID" 2>/dev/null || true
}
trap cleanup EXIT

for i in $(seq 1 30); do
  if curl -s "http://localhost:$S3_PORT/" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "==> Step 5: Uploading model weights to SeaweedFS S3 bucket 'models'"
if [ ! -x ".venv-deploy/bin/python" ]; then
  python3 -m venv .venv-deploy
fi
.venv-deploy/bin/python -m pip install --quiet boto3==1.38.18

S3_ENDPOINT="http://localhost:$S3_PORT" \
  .venv-deploy/bin/python scripts/upload_model.py \
    --file "$MODEL_PATH" \
    --version "$MODEL_VERSION"

echo "==> Step 6: Creating namespace 'app' and S3 credentials Secret"
kubectl create namespace app --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic seaweedfs-s3-credentials \
  -n app \
  --from-literal=access-key=anonymous \
  --from-literal=secret-key=anonymous \
  --dry-run=client -o yaml | kubectl apply -f -

echo "==> Step 7: Building and importing inference service container"
IMAGE_TAG="aeroparse-service:$MODEL_VERSION"
docker build -t "$IMAGE_TAG" service/
k3d image import "$IMAGE_TAG" -c "$CLUSTER"

echo "==> Step 8: Deploying AeroParse workload manifests"
kubectl apply -f k8s/task4.yaml
kubectl rollout status deployment/aeroparse -n app --timeout=600s

echo "=========================================================="
echo "          AeroParse Deployment Successful!                "
echo "=========================================================="
kubectl get pods -n data
kubectl get pods -n app
echo ""
echo "API Endpoint available at: http://localhost:8080/parse"
