"""Read-only ring probe. Run inside the Compose network with a node IPv4."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "distributed"), str(ROOT)]
from chord.reference import ChordNodeReference

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ip")
    args = parser.parse_args()
    node = ChordNodeReference(args.ip)
    print(f"Successor: {node.succ}; predecessor: {node.pred}")
