import concurrent.futures
import json
import time
import urllib.request
from collections import Counter

URL = "http://localhost:8080/parse"
DURATION = 120
WORKERS = 4
counts = Counter()
start = time.time()

def send_requests():
    local = Counter()
    while time.time() - start < DURATION:
        req = urllib.request.Request(
            URL,
            data=json.dumps({
                "text": "Set an alarm for seven am tomorrow"
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                local[str(response.status)] += 1
        except Exception as exc:
            local["ERROR"] += 1
    return local

with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
    for result in pool.map(lambda _: send_requests(), range(WORKERS)):
        counts.update(result)

print("Load test duration:", round(time.time() - start, 2), "seconds")
print("Results:", dict(counts))
print("Total requests:", sum(counts.values()))
