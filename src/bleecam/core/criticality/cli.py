# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""CLI to view the criticality library and (re)generate its catalog.

  bleecam-lib list                 # summaries, by family
  bleecam-lib describe <id>        # one constraint's scope/meaning/parameters
  bleecam-lib docs [--write PATH]  # generate the documentation catalog
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .catalog import generate_catalog
from .registry import all_constraints, describe


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="bleecam-lib",
        description="View the BLEECAM criticality constraint library (use these ids in a scenario YAML).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list all available criticality constraints")
    d = sub.add_parser("describe", help="show one constraint's scope, meaning, and parameters")
    d.add_argument("id", help="constraint id (see `list`)")
    dd = sub.add_parser("docs", help="generate the documentation catalog (Markdown)")
    dd.add_argument("--write", default=None, help="write to this path instead of stdout")
    args = parser.parse_args()

    if args.cmd == "list":
        family = None
        print("BLEECAM criticality constraint library:")
        for c in all_constraints():
            if c.family != family:
                family = c.family
                print(f"\n  [{family}]")
            print(f"    {c.id:24} {c.summary}")
        print("\nUse an id in a scenario YAML under `constraints:` and run `bleecam-run scenario.yaml`.")
    elif args.cmd == "describe":
        print(describe(args.id))
    elif args.cmd == "docs":
        md = generate_catalog()
        if args.write:
            Path(args.write).write_text(md)
            print(f"wrote {args.write} ({len(all_constraints())} constraints)")
        else:
            print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
