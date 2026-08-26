#!/usr/bin/env python3
"""Canonical stage 1: research, independent automated challenge, score and render."""

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP1 = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

import vendors as V


def vendor_family(vendor):
    return str(vendor or "").split("/", 1)[0].strip()


def independent_reviewer(primary):
    primary_family = vendor_family(primary)
    for family in ("openai", "anthropic", "gemini"):
        if family != primary_family and V._MODEL_PREFS.get(family):
            return f"{family}/{V._MODEL_PREFS[family][0]}"
    raise ValueError("no configured vendor family can independently challenge the primary")


def run_command(argv):
    completed = subprocess.run(argv, cwd=HERE)
    if completed.returncode:
        raise RuntimeError(
            f"{os.path.basename(argv[1])} exited with code {completed.returncode}"
        )


def build_source_inventory(research):
    inventory = {}
    for record in research.values() if isinstance(research, dict) else []:
        if not isinstance(record, dict):
            continue
        answer = record.get("answer") or {}
        url = str(answer.get("source_url") or "").strip()
        title = str(answer.get("source_title") or "").strip()
        if not url and not title:
            continue
        inventory.setdefault(url or title.casefold(), {
            "source_name": title,
            "source_url": url,
            "tier": answer.get("proposed_tier") or "",
            "published_year": answer.get("year"),
            "verified_quote": answer.get("quote") or "",
            "indicator_ids": [],
        })["indicator_ids"].append(record.get("id") or "")
    return list(inventory.values())


def checkpoint_combined_spend(out):
    """Publish every known Stage 1 charge, including a failed child attempt."""
    totals = []
    source_ledgers = []
    for suffix in ("spend", "g2_spend"):
        name = f"{out}_{suffix}.json"
        path = os.path.join(LOOP1, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
        total = (value.get("summary") or {}).get("total")
        if isinstance(total, bool) or not isinstance(total, (int, float)) or total < 0:
            raise ValueError(f"spend ledger {path} has no valid summary.total")
        totals.append(float(total))
        source_ledgers.append(name)
    combined_spend = {
        "schema_version": "damm.stage-spend/v1",
        "summary": {"total": round(sum(totals), 8)},
        "source_ledgers": source_ledgers,
    }
    checkpoint_identity = os.environ.get("DAMM_CHECKPOINT_BINDING_SHA256")
    if checkpoint_identity:
        combined_spend["checkpoint_identity_sha256"] = checkpoint_identity
    spend_path = os.path.join(LOOP1, f"{out}_diagnostic_stage_spend.json")
    V.atomic_write_json(spend_path, combined_spend)
    return spend_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--country", required=True)
    parser.add_argument("--iso", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--ceiling", type=float, default=500.0)
    parser.add_argument("--vendor", default="anthropic/claude-opus-5")
    parser.add_argument("--reviewer-vendor")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    reviewer = args.reviewer_vendor or independent_reviewer(args.vendor)
    if vendor_family(reviewer) == vendor_family(args.vendor):
        print("!! automated challenge vendor must be independent of the research vendor")
        return 1

    common = ["--country", args.country, "--iso", args.iso,
              "--ceiling", str(args.ceiling)]
    commands = [
        [sys.executable, os.path.join(HERE, "research_orchestrator.py"),
         *common, "--out", args.out, "--vendor", args.vendor],
        [sys.executable, os.path.join(HERE, "gate2.py"),
         *common, "--run", args.out, "--vendor", reviewer],
        [sys.executable, os.path.join(HERE, "diagnostic.py"),
         *common, "--out", args.out],
    ]
    if args.resume:
        for command in commands:
            command.append("--resume")
    try:
        for command in commands:
            run_command(command)
    except (OSError, RuntimeError, ValueError) as error:
        try:
            checkpoint_combined_spend(args.out)
        except (OSError, ValueError, json.JSONDecodeError) as spend_error:
            print(f"!! DAMM diagnostic spend checkpoint failed: {spend_error}")
        print(f"!! DAMM diagnostic stage failed: {error}")
        return 1

    required = {
        "damm_observations": f"{args.out}_input.json",
        "automated_challenge": f"{args.out}_g2_findings.json",
        "engine_input": f"{args.out}_g2_input.json",
        "scored_assessment": f"{args.out}_v17.json",
        "diagnostic_report": f"{args.out}_diagnostic.html",
        "source_inventory": f"{args.out}_research.json",
    }
    missing = [key for key, name in required.items()
               if not os.path.isfile(os.path.join(LOOP1, name))]
    if missing:
        print("!! DAMM diagnostic stage is missing: " + ", ".join(missing))
        return 1

    research_path = os.path.join(LOOP1, f"{args.out}_research.json")
    sources_path = os.path.join(LOOP1, f"{args.out}_diagnostic_sources.json")
    with open(research_path) as handle:
        inventory = build_source_inventory(json.load(handle))
    if not inventory:
        print("!! DAMM diagnostic source inventory is empty")
        return 1
    with open(sources_path, "w") as handle:
        json.dump(inventory, handle, indent=2)
    required["source_inventory"] = os.path.basename(sources_path)

    try:
        checkpoint_combined_spend(args.out)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"!! DAMM diagnostic stage could not write its spend ledger: {error}")
        return 1
    print(json.dumps({
        "schema_version": "damm.workflow-event/v1",
        "event": "diagnostic_stage_complete",
        "primary_vendor": args.vendor,
        "reviewer_vendor": reviewer,
        "artifacts": required,
    }, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
