"""Disposable document insertion probe; use the automated gate for validation."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "client"), str(ROOT)]
from api import insert_document

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("title")
    parser.add_argument("text")
    args = parser.parse_args()
    print(insert_document(args.title, args.text))
