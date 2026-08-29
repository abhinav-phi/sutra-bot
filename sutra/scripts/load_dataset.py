#!/usr/bin/env python3
"""Push the expanded dataset into a running Sutra bot (warmup rehearsal).

Usage:
    python dataset/generate_dataset.py --seed-dir dataset --out expanded   # repo root
    python sutra/scripts/load_dataset.py --dir expanded --url http://localhost:8080
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path


def post(url: str, body: dict) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="expanded", help="expanded/ output dir")
    ap.add_argument("--url", default="http://127.0.0.1:8081", help="bot base URL")
    args = ap.parse_args()

    root = Path(args.dir)
    if not root.exists():
        print(f"missing {root}; run generate_dataset.py first");  return 1

    counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
    plan = ([("category", root / "categories", lambda p: p.stem)],
            [("merchant", root / "merchants",
              lambda p: json.loads(p.read_text(encoding="utf-8"))["merchant_id"]),
             ("customer", root / "customers",
              lambda p: json.loads(p.read_text(encoding="utf-8"))["customer_id"]),
             ("trigger", root / "triggers",
              lambda p: json.loads(p.read_text(encoding="utf-8"))["id"])])

    for groups in plan:
        for scope, folder, cid_of in groups:
            if not folder.exists():
                continue
            for f in sorted(folder.glob("*.json")):
                payload = json.loads(f.read_text(encoding="utf-8"))
                status, resp = post(f"{args.url}/v1/context", {
                    "scope": scope, "context_id": cid_of(f), "version": 1,
                    "payload": payload})
                counts[scope] += 1
                if status != 200:
                    print(f"  !! {scope}/{f.name} -> {status} {resp}")
        print(f"pushed {counts}")

    print("done. healthz:")
    with urllib.request.urlopen(f"{args.url}/v1/healthz", timeout=5) as r:
        print(json.dumps(json.loads(r.read()), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
