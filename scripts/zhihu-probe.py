"""One bounded readonly probe; no retries after an access denial."""

import argparse
import importlib.metadata
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from services.api.zhihu import AccessBlocked, LibraryTransport, collect_history, normalize_target

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("target")
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.limit <= 10:
        parser.error("--limit must be 1..10")
    try:
        result = collect_history(
            LibraryTransport(),
            normalize_target(args.target),
            max_items=args.limit,
            max_pages=1,
            kinds=["answer"],
        )
        print(
            json.dumps(
                {
                    "ok": True,
                    "profile": result["profile"],
                    "coverage": result["coverage"],
                    "documents": [
                        {
                            "url": d["url"],
                            "title": d["title"],
                            "characters": len(d["text"]),
                            "published_at": d["published_at"],
                            "edited_at": d["edited_at"],
                        }
                        for d in result["documents"]
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    except AccessBlocked as error:
        print(
            json.dumps(
                {"ok": False, "code": error.code, "message": str(error), "captured": 0},
                ensure_ascii=False,
                indent=2,
            )
        )
        sys.exit(2)
