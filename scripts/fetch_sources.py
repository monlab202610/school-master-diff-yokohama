#!/usr/bin/env python3
"""Fetch exactly three pinned public CSV files, serially; no ongoing crawl."""
import argparse
import hashlib
import time
import urllib.error
import urllib.request
from pathlib import Path
from build_sample import SOURCES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    last_request = None
    for spec in SOURCES:
        target = args.output / spec["filename"]
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != spec["sha256"]:
                parser.exit(2, "existing source differs; do not overwrite: " + target.name + "\n")
            print("cached: " + target.name)
            continue
        if last_request is not None:
            time.sleep(max(0, 2 - (time.monotonic() - last_request)))
        url = "https://www.mext.go.jp/content/" + spec["filename"]
        last_request = time.monotonic()
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "monlab-school-master-sample/0.1"})
            with urllib.request.urlopen(request, timeout=30) as response:
                if response.status != 200:
                    raise ValueError("unexpected HTTP status")
                content = response.read(8_000_001)
                if not response.geturl().startswith("https://www.mext.go.jp/"):
                    raise ValueError("unexpected redirect destination")
            if len(content) > 8_000_000 or hashlib.sha256(content).hexdigest() != spec["sha256"]:
                raise ValueError("source changed or size exceeded; review edition before continuing")
            target.write_bytes(content)
        except (urllib.error.URLError, ValueError) as exc:
            parser.exit(2, "fetch stopped: " + str(exc) + "\n")
        print("verified: " + target.name)


if __name__ == "__main__":
    main()
