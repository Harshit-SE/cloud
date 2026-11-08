#!/usr/bin/env bash
# ==============================================================================
# AeroParse Cluster Teardown Workflow
# ==============================================================================
set -Eeuo pipefail

CLUSTER="aeroparse-cluster"

echo "==> Tearing down AeroParse Kubernetes cluster: $CLUSTER"

if k3d cluster list | grep -q "$CLUSTER"; then
  k3d cluster delete "$CLUSTER"
  echo "[+] Cluster '$CLUSTER' successfully deleted."
else
  echo "[*] Cluster '$CLUSTER' does not exist. No teardown required."
fi

echo "[+] AeroParse cleanup completed successfully."
