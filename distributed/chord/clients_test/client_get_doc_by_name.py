"""Retrieve a disposable document using the current JSON protocol."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "client"), str(ROOT)]
from api import download_file

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("title")
    args = parser.parse_args()
    print(download_file(args.title))
