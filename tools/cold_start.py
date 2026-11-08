import json
import subprocess
import time
from datetime import datetime

def kubectl(*args):
    return subprocess.check_output(
        ["kubectl", *args], text=True
    )

def measure(run):
    print(f"\nCold-start run {run}")

    kubectl("delete", "pods", "-n", "app", "-l", "app=nanoparse")

    while True:
        pods = json.loads(kubectl(
            "get", "pods", "-n", "app",
            "-l", "app=nanoparse", "-o", "json"
        ))["items"]

        ready = [
            p for p in pods
            if any(
                c["type"] == "Ready" and c["status"] == "True"
                for c in p.get("status", {}).get("conditions", [])
            )
        ]

        if len(ready) >= 2:
            break

        time.sleep(1)

    durations = []
    for pod in ready:
        created = datetime.fromisoformat(
            pod["metadata"]["creationTimestamp"].replace("Z", "+00:00")
        )
        ready_time = next(
            c["lastTransitionTime"]
            for c in pod["status"]["conditions"]
            if c["type"] == "Ready" and c["status"] == "True"
        )
        ready_at = datetime.fromisoformat(
            ready_time.replace("Z", "+00:00")
        )
        durations.append((ready_at - created).total_seconds())

    print("Pod startup times:", durations)
    return durations

results = []
for run in range(1, 4):
    results.extend(measure(run))

print("\nAll pod startup times:", results)

if results:
    values = sorted(results)
    n = len(values)
    median = values[n // 2] if n % 2 else (
        values[n // 2 - 1] + values[n // 2]
    ) / 2
    print("Median startup time:", median, "seconds")
