"""Isolated Docker integration gate, including restart/failure/recovery.

No volume deletion. Each invocation has a fresh, namespaced project.
"""
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "infochord-test-" + uuid.uuid4().hex[:10]
BASE = ["docker", "compose", "-p", PROJECT, "-f", "docker-compose.yml", "-f", "compose.test.yml"]


def run(*args, timeout=600):
    print("Gate step: " + " ".join(args), flush=True)
    subprocess.run(BASE + list(args), cwd=ROOT, check=True, timeout=timeout)


def scenario(stage, nodes="node1,node2,node3"):
    run("run", "--rm", "--no-deps", "-e", f"TEST_NODES={nodes}", "test-runner",
        "python", "tests/integration/test_cluster.py", stage)


def ready(*nodes):
    # Compose --wait on restarted services waits for their readiness healthchecks.
    run("up", "-d", "--wait", "--wait-timeout", "300", *nodes)


if __name__ == "__main__":
    print(f"Isolated test project: {PROJECT}", flush=True)
    try:
        run("config", "--quiet", timeout=60)
        run("build", "node1", timeout=1800)
        run("run", "--rm", "--no-deps", "node1", "python", "-m", "unittest", "discover", "-s", "tests", "-v")
        ready("node1", "node2", "node3", "ui")
        scenario("initial")
        run("restart", "node1", "node2", "node3")
        ready("node1", "node2", "node3")
        scenario("restart")
        run("stop", "node1")
        # Health state is polled by the dedicated waiter without starting node1.
        run("run", "--rm", "--no-deps", "test-runner", "python", "scripts/wait-nodes.py", "node2", "node3")
        scenario("failure", "node2,node3")
        ready("node1", "node2", "node3")
        scenario("recovery")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"Gate FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        # Diagnostics/cleanup must not mask the original gate failure.
        for args, timeout in [(("ps", "--all"), 30),
                              (("logs", "--no-color", "--tail", "100"), 60),
                              (("down", "--timeout", "20"), 90)]:
            try:
                run(*args, timeout=timeout)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                print(f"Diagnostics/stop could not complete for {PROJECT}: {type(exc).__name__}", file=sys.stderr)
        print(f"Test project {PROJECT}: volumes were not deleted. Check status if Docker was unavailable.", flush=True)
