#!/usr/bin/env python3
"""Offline lookup of one school code in the included sample."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("school_code")
    parser.add_argument("--data", type=Path, default=Path(__file__).resolve().parents[1] / "data/after.json")
    args = parser.parse_args()
    rows = json.loads(args.data.read_text(encoding="utf-8"))
    matches = [row for row in rows if row["school_code"] == args.school_code]
    if not matches:
        parser.exit(1, "not in this Yokohama sample (not proof of a nonexistent school)\n")
    print(json.dumps(matches[0], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
