"""CLI for Electron Smart tab (JSON stdout)."""

from __future__ import annotations

import argparse
import json
import sys

from mango.smart.smart_brief import build_daily_brief
from mango.smart.smart_routines import list_routines_text
from mango.smart.smart_store import (
    add_inbox_item,
    delete_card,
    ensure_defaults,
    load_timeline_entries,
    smart_snapshot,
    upsert_card,
)

try:
    # Electron pipes stdout/stderr; force UTF-8 so Windows codepages do not crash
    # when smart payloads contain characters outside cp1252/charmap.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mango smart layer API")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("snapshot", help="Full smart state JSON")

    p_add = sub.add_parser("card-add")
    p_add.add_argument("--title", default="Note")
    p_add.add_argument("--content", required=True)
    p_add.add_argument("--category", default="fact")

    p_del = sub.add_parser("card-delete")
    p_del.add_argument("--id", required=True)

    p_inbox = sub.add_parser("inbox-add")
    p_inbox.add_argument("--text", required=True)

    sub.add_parser("brief")
    sub.add_parser("routines-list")
    sub.add_parser("timeline")

    args = parser.parse_args(argv)
    ensure_defaults()

    if args.cmd == "snapshot":
        print(json.dumps(smart_snapshot(), ensure_ascii=False))
        return 0
    if args.cmd == "card-add":
        card = upsert_card(title=args.title, content=args.content, category=args.category)
        print(json.dumps(card, ensure_ascii=False))
        return 0
    if args.cmd == "card-delete":
        ok = delete_card(args.id)
        print(json.dumps({"ok": ok}))
        return 0
    if args.cmd == "inbox-add":
        item = add_inbox_item(args.text)
        print(json.dumps(item, ensure_ascii=False))
        return 0
    if args.cmd == "brief":
        print(build_daily_brief())
        return 0
    if args.cmd == "routines-list":
        print(list_routines_text())
        return 0
    if args.cmd == "timeline":
        print(json.dumps(load_timeline_entries(100), ensure_ascii=False))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
