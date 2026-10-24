"""Delete probe requiring explicit confirmation; disposable demo data only."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "client"), str(ROOT)]
from api import delete_document

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("title")
    parser.add_argument("--confirm", action="store_true", required=True)
    args = parser.parse_args()
    print(delete_document(args.title))
