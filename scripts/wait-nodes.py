import sys
import time
import requests

pending = set(sys.argv[1:])
deadline = time.monotonic() + 300
while pending and time.monotonic() < deadline:
    for node in list(pending):
        try:
            response = requests.get(f"http://{node}:8000/health/ready", timeout=25)
            if response.status_code == 200:
                pending.remove(node)
        except requests.RequestException:
            pass
    if pending:
        time.sleep(3)
if pending:
    raise SystemExit(f"Nodes not ready before deadline: {sorted(pending)}")
