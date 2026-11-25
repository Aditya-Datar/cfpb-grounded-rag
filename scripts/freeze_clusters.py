"""Merge builder and reviewer, then freeze the clusters (docs/CLUSTER_SCORING_PROTOCOL.md, Sec. 5-6).

    .venv/Scripts/python.exe scripts/freeze_clusters.py

A proposed member enters the frozen cluster only if the reviewer accepted it
(the builder proposed it, so both models accept). A missing or unparseable
review counts as a rejection. The gold section is always a member.

Writes annotation/clusters_frozen.jsonl and results/cluster_freeze.json (SHA-256
of the frozen file, counts, member acceptance and control rejection rates).
scripts/score_clusters.py refuses to run if the hash no longer matches.
"""
import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    clusters = [json.loads(l) for l in open(ROOT / "annotation" / "clusters_claude.jsonl", encoding="utf-8")]
    review = [json.loads(l) for l in open(ROOT / "annotation" / "clusters_review_mistral.jsonl", encoding="utf-8")]
    dec = {(r["key"], r["section"]): r for r in review if r["kind"] == "member"}
    ctl = [r for r in review if r["kind"] == "control"]

    rows, rejected = [], []
    for cl in clusters:
        kept = [cl["members"][0]]
        for m in cl["members"][1:]:
            r = dec.get((cl["key"], m["section"]))
            if r and r["decision"] == "accept":
                kept.append(m)
            else:
                rejected.append({"key": cl["key"], "section": m["section"], "tier": m["tier"],
                                 "reason": (r or {}).get("reason"), "decision": (r or {}).get("decision")})
        rows.append({"key": cl["key"], "issue": cl["issue"], "gold_section": cl["gold_section"],
                     "gold_regulation": cl["gold_regulation"], "members": kept})
    out = ROOT / "annotation" / "clusters_frozen.jsonl"
    data = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    out.write_text(data, encoding="utf-8")

    proposed = sum(len(c["members"]) - 1 for c in clusters)
    accepted = sum(len(r["members"]) - 1 for r in rows)
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    info = {
        "frozen_file": "annotation/clusters_frozen.jsonl",
        "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        "frozen_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_head_at_freeze": commit, "committed": False,
        "builder": "llm:claude-opus-5-5 (regulation-annotator skill)", "reviewer": review[0]["reviewer"] if review else None,
        "rule": "member kept only if both builder and reviewer accept; no answer counts as reject",
        "n_clusters": len(rows), "proposed_members": proposed, "accepted_members": accepted,
        "member_acceptance_rate": accepted / proposed if proposed else None,
        "accepted_by_tier": dict(Counter(m["tier"] for r in rows for m in r["members"][1:])),
        "reviewer_no_answer": sum(1 for r in review if r["decision"] is None),
        "controls": {"n": len(ctl), "rejected": sum(r["decision"] == "reject" for r in ctl),
                     "accepted": sum(r["decision"] == "accept" for r in ctl)},
        "kappa": "undefined: the builder proposes only members it accepts; see acceptance and control rates",
        "label_status": "silver (LLM-built, LLM-reviewed); no human review by decision of Aditya, 2026-11-19",
        "rejected_members": rejected,
    }
    (ROOT / "results" / "cluster_freeze.json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"froze {len(rows)} clusters: {accepted}/{proposed} proposed members accepted; controls rejected "
          f"{info['controls']['rejected']}/{info['controls']['n']}; sha256 {info['sha256'][:12]}")


if __name__ == "__main__":
    main()
