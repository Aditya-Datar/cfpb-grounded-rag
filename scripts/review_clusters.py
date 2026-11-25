"""Second-model review of the proposed cluster members (docs/CLUSTER_SCORING_PROTOCOL.md, Sec. 5).

    .venv/Scripts/python.exe scripts/review_clusters.py [--workers 4]

Reviewer: mistralai/mistral-large-4-1t-a52b through the NVIDIA API (the judge
benchmarked in H4), temperature 0, reasoning_effort "low" (default effort took about
3 minutes per call on 2026-11-19), responses cached in outputs/retrieval/llm_cache.
For each proposed member it sees ONLY: the cluster key (CFPB issue, sub-issues,
products, gold section and its heading), the member section's text around the
builder's duty quote, and the quote. It does not see the builder's other members
or its link evidence. It answers accept or reject against the five membership
tests of the protocol (Sec. 4).

Controls: for every cluster the definitions section of the gold's law (1005.2,
1006.2, 1022.3 or 1022.41, 1026.2, 1681a) is also put to the reviewer. The
protocol excludes definitions, so a sound reviewer rejects them; the control
rejection rate is reported beside the member acceptance rate. Builder-reviewer
kappa is undefined (the builder proposes only members it accepts), so these two
rates are reported instead.

Writes annotation/clusters_review_mistral.jsonl.

--reviewer gpt (added 2026-11-20 at Aditya's request): the same prompts go to
gpt-5.6-sol through the Codex CLI on Aditya's ChatGPT Edu login (codex exec,
read-only sandbox, run from an empty scratch directory so it cannot see the repo,
told not to run commands). Answers are cached in outputs/retrieval/codex_cache.
Writes annotation/clusters_review_gpt.jsonl. Same blindness: it sees one item at a
time and never Claude's other members, link evidence or Mistral's answers.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cfpb.pipeline.corpus import load_corpus  # noqa: E402
from cfpb.retrieval.llm_rerank import post  # noqa: E402

REVIEWER = "mistralai/mistral-large-4-1t-a52b"
GPT = "gpt-5.6-sol"
CODEX_CACHE = ROOT / "outputs" / "retrieval" / "codex_cache"
REASONING_EFFORT = "low"  # default effort took ~3 min per call (2026-11-19); low answers in seconds
DEFINITIONS = {"E": "1005.2", "F": "1006.2", "V": "1022.41", "Z": "1026.2", "FCRA": "1681a"}

PROMPT = """You are reviewing an evaluation label for a research project on US consumer-finance complaints. This is not legal advice.

A group of consumer complaints shares this CFPB complaint issue and this governing ("gold") section:
- CFPB issue: {issue}
- Sub-issues seen: {sub_issues}
- Products: {products}
- Companies complained about: {companies}
- Gold section: {gold_label} ({gold_heading})

Question: should the candidate section below ALSO count as a correct citation in a response to these complaints? Accept it only if ALL five tests hold:
1. It imposes a duty (or prohibition) on the kind of company complained about.
2. That duty is triggered by facts typical of this issue (for example a dispute, an error notice, an identity-theft report, a validation request, a payment).
3. It is in the corpus (Regulations E, F, V, Z or the FCRA). Assume this holds.
4. It is NOT a definitions, scope, effective-date, general-provision or model-form section.
5. The quoted sentence below really is in the candidate's text and creates that duty.

Candidate section: {cand_label} ({cand_heading})
Quoted duty sentence: "{quote}"
Candidate text (excerpt):
{excerpt}

Answer with JSON only: {{"decision": "accept" or "reject", "failed_test": null or the number of the first test that fails, "reason": "one sentence"}}"""


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("’", "'")).strip()


def label(sec: str) -> str:
    return f"15 U.S.C. {sec}" if sec.startswith("1681") else f"12 CFR {sec}"


def ask_codex(prompt: str) -> str:
    """One codex exec call from an empty directory; cached by prompt hash."""
    CODEX_CACHE.mkdir(parents=True, exist_ok=True)
    f = CODEX_CACHE / (hashlib.sha1((GPT + prompt).encode()).hexdigest() + ".txt")
    if f.exists():
        return f.read_text(encoding="utf-8")
    full = prompt + "\n\nDo not run any commands or read any files; everything you need is above."
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "answer.txt"
        r = subprocess.run(["codex", "exec", "--skip-git-repo-check", "--ephemeral", "-s", "read-only", "-m", GPT,
                            "-o", str(out), "-"], input=full, cwd=d, capture_output=True, text=True,
                           encoding="utf-8", timeout=600, shell=sys.platform == "win32")
        ans = out.read_text(encoding="utf-8") if out.exists() else ""
    if r.returncode != 0 or not ans.strip():
        raise RuntimeError(f"codex exit {r.returncode}")
    f.write_text(ans, encoding="utf-8")
    return ans


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--reviewer", choices=["mistral", "gpt"], default="mistral")
    ap.add_argument("--limit", type=int, default=None, help="first N jobs only (smoke test)")
    args = ap.parse_args()
    corpus = load_corpus([str(ROOT / "chunking" / "data" / "processed" / "chunks.jsonl")])
    text, heading = {}, {}
    for c in corpus.chunks:
        text.setdefault(c.section, []).append(c.text)
        heading.setdefault(c.section, c.heading)
    text = {s: norm(" ".join(t)) for s, t in text.items()}
    keys = {json.loads(l)["key"]: json.loads(l) for l in open(ROOT / "annotation" / "cluster_keys.jsonl", encoding="utf-8")}
    clusters = [json.loads(l) for l in open(ROOT / "annotation" / "clusters_claude.jsonl", encoding="utf-8")]

    jobs = []
    for cl in clusters:
        for m in cl["members"][1:]:
            jobs.append((cl, m["section"], m["duty_quote"], "member"))
        d = DEFINITIONS[cl["gold_regulation"]]
        jobs.append((cl, d, text[d].split(". ")[0][:300], "control"))

    def one(job):
        cl, sec, quote, kind = job
        k = keys[cl["key"]]
        t = text[sec]
        i = max(0, t.find(norm(quote)))
        words_before = t[:i].split()[-120:]
        excerpt = " ".join(words_before + t[i:].split()[:180])
        prompt = PROMPT.format(
                    issue=k["issue"], sub_issues="; ".join(k["sub_issues"]) or "none", products="; ".join(k["products"]),
                    companies="; ".join(k["companies"][:4]), gold_label=label(k["gold_section"]),
                    gold_heading=heading.get(k["gold_section"], ""), cand_label=label(sec),
                    cand_heading=heading.get(sec, ""), quote=quote, excerpt=excerpt)
        body = {"model": REVIEWER, "temperature": 0, "max_tokens": 4096, "reasoning_effort": REASONING_EFFORT,
                "messages": [{"role": "user", "content": PROMPT.format(
                    issue=k["issue"], sub_issues="; ".join(k["sub_issues"]) or "none", products="; ".join(k["products"]),
                    companies="; ".join(k["companies"][:4]), gold_label=label(k["gold_section"]),
                    gold_heading=heading.get(k["gold_section"], ""), cand_label=label(sec),
                    cand_heading=heading.get(sec, ""), quote=quote, excerpt=excerpt)}]}
        try:
            if args.reviewer == "gpt":
                content = ask_codex(prompt)
            else:
                msg = post("/chat/completions", body)["choices"][0]["message"]
                content = re.sub(r"<think>.*?</think>", "", msg.get("content") or "", flags=re.S)
            m = re.search(r"\{.*\}", content, re.S)
            ans = json.loads(m.group(0)) if m else {}
        except Exception as e:  # recorded, not silently accepted
            ans = {"decision": None, "reason": f"error: {type(e).__name__}"}
        dec = str(ans.get("decision", "")).lower()
        return {"key": cl["key"], "section": sec, "kind": kind,
                "decision": dec if dec in ("accept", "reject") else None,
                "failed_test": ans.get("failed_test"), "reason": ans.get("reason"),
                "reviewer": GPT + " (codex cli)" if args.reviewer == "gpt" else REVIEWER,
                "reasoning_effort": "codex default" if args.reviewer == "gpt" else REASONING_EFFORT}

    jobs = jobs[:args.limit] if args.limit else jobs
    with ThreadPoolExecutor(args.workers) as ex:
        rows = list(ex.map(one, jobs))
    out = ROOT / "annotation" / f"clusters_review_{args.reviewer}.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    mem = [r for r in rows if r["kind"] == "member"]
    ctl = [r for r in rows if r["kind"] == "control"]
    print(f"wrote {out}")
    print(f"members: {len(mem)}, accepted {sum(r['decision'] == 'accept' for r in mem)}, "
          f"rejected {sum(r['decision'] == 'reject' for r in mem)}, no answer {sum(r['decision'] is None for r in mem)}")
    print(f"controls (definitions): {len(ctl)}, rejected {sum(r['decision'] == 'reject' for r in ctl)}, "
          f"no answer {sum(r['decision'] is None for r in ctl)}")


if __name__ == "__main__":
    main()
