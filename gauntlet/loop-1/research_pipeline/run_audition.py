#!/usr/bin/env python3
"""The vendor audition — standing decision 4 / design decision B2, run for the first time.

Thirteen cells, ten with known answers and three naming things that verifiably do not
exist, scored on fabrication rate, tier compliance and citation resolvability.

Two things about the method are worth stating before the numbers are read.

*Retrieval is shared.* Standing decision 3 already fixes retrieval as Exa for discovery
and Jina for fetch, so what remains to choose is judgment. Every entrant therefore sees
the *identical* pack of fetched pages for a cell, and the comparison is of what each one
does with the same evidence. This also makes the fabrication measure meaningful: the
pages are known, so a quote either appears in them or does not.

*Discovery is measured separately.* Before the shared pack is built, each entrant
proposes its own search queries, and every page is tagged with whose query surfaced it.
Perplexity enters here and only here — as the discovery peer decision C6 permits, with
its citations re-fetched through Jina and its prose never eligible to be recorded.

Usage:
    python3 run_audition.py [--resume] [--cells K1,N1] [--ceiling 40]
"""

import json, os, sys, time, argparse
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import vendors as V
from cell_schema import (CELL_SCHEMA, QUERY_SCHEMA, SYSTEM, cell_prompt,
                         LADDER_TEXT, threshold_text)

PASS = "audition"
STATE = os.path.join(HERE, "audition_state.json")
RESULTS = os.path.join(HERE, "audition_results.json")
REPORT = os.path.join(HERE, "AUDITION-RESULTS.md")

MAX_QUERIES = 3          # per entrant, per cell
EXA_RESULTS = 6          # per query
MAX_PAGES = 10           # fetched per cell — the shared pack
PAGE_CHARS = 6000        # per page in the pack
WORKERS = 8              # concurrent fetches / vendor calls

# The pack is filled tier by tier under a quota rather than strictly in tier order.
# Sorting by tier alone fills every slot with T1 pages, so a cell whose answer is a
# government artifact or a household survey never gets its page fetched, and the
# entrant abstains for want of evidence that was found and then dropped. The protocol
# says search T1 first — not search T1 only.
TIER_QUOTA = {"T1": 4, "T2": 2, "T3": 2, "T4": 2, "T5": 1}


# ------------------------------------------------------------------ entrants

def build_entrants(ledger):
    """Every text-reasoning flagship the six keys reach.

    All three gpt-5.6 siblings are entered rather than one being picked: the vendor
    publishes no capability ordering among them, and guessing would put an unknown
    into a measurement whose whole purpose is to remove one.
    """
    ents = []
    for vendor, models in (("anthropic", ["claude-opus-5"]),
                           ("openai", ["gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.6-sol"]),
                           ("gemini", ["gemini-3.1-pro-preview"])):
        live = []
        try:
            live = V.LLM(vendor, ledger, model=models[0]).list_models()
        except Exception as e:
            print(f"  ! could not list {vendor} models: {str(e)[:120]}")
        for m in models:
            if live and m not in live:
                print(f"  ! {vendor}/{m} not offered by the account — skipped")
                continue
            ents.append(dict(name=f"{vendor}/{m}", vendor=vendor, model=m,
                             llm=V.LLM(vendor, ledger, model=m)))
    return ents


# ------------------------------------------------------------------ per-cell run

def scoring_text(cell):
    if cell["method"] == "ladder":
        return LADDER_TEXT
    return threshold_text(cell["direction"], cell["thresholds"], cell.get("unit", ""))


def propose_queries(ent, cell):
    user = (f"COUNTRY: {cell['country']}\n"
            f"INDICATOR: {cell['indicator_id']} — {cell['indicator_name']}\n"
            f"WHAT IT MEASURES: {cell['construct']}\n\n"
            "Propose the web searches most likely to surface the highest-tier published "
            "source for this exact construct, for this country. Search the publisher, not "
            "the topic. If the construct names a rural, female or otherwise disaggregated "
            "population, your queries must target that disaggregation — a query that "
            "returns the national figure has not found this indicator.")
    return ent["llm"].json_call(
        "You plan evidence searches for a national statistics assessment. JSON only.",
        user, QUERY_SCHEMA, PASS, max_tokens=2000,
        detail=f"queries {cell['id']} {ent['name']}")


def build_pack(cell, entrants, ledger, log):
    """Search on every entrant's queries plus Perplexity's citations, fetch once, share."""
    proposals, seen, ranked = {}, {}, []

    def one_proposal(ent):
        try:
            return ent["name"], propose_queries(ent, cell)
        except Exception as e:
            log(f"    ! {ent['name']} query proposal failed: {str(e)[:120]}")
            return ent["name"], {"queries": [], "likely_publishers": []}

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for name, q in ex.map(one_proposal, entrants):
            proposals[name] = q

    # Perplexity as discovery peer (C6): citations only; the prose is a lead, never a source.
    ppx = {"citations": [], "lead_prose": ""}
    try:
        ppx = V.perplexity_citations(
            f"For {cell['country']} only: {cell['construct']} "
            f"Which published source states this figure, and what is it? "
            f"If no source publishes this exact measure, say so.", ledger, PASS)
    except Exception as e:
        log(f"    ! perplexity discovery failed: {str(e)[:120]}")
    proposals["perplexity/discovery"] = {"queries": ["(discovery peer)"],
                                         "likely_publishers": []}

    def offer(url, title, who, published=""):
        if not url:
            return
        u = url.split("#")[0]
        if u in seen:
            if who not in seen[u]["surfaced_by"]:
                seen[u]["surfaced_by"].append(who)
            return
        seen[u] = dict(url=u, title=title or "", published=published,
                       tier=V.tier_for_url(u), surfaced_by=[who])
        ranked.append(seen[u])

    jobs = [(ent["name"], q)
            for ent in entrants
            for q in (proposals[ent["name"]].get("queries") or [])[:MAX_QUERIES]
            if q.strip()]

    def one_search(job):
        who, query = job
        try:
            return who, V.exa_search(query, ledger, PASS, num_results=EXA_RESULTS)
        except V.BudgetExhausted:
            raise
        except Exception as e:
            log(f"    ! search failed ({str(e)[:80]})")
            return who, []

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for who, res in ex.map(one_search, jobs):
            for r in res:
                offer(r["url"], r["title"], who, r.get("published", ""))
    for u in ppx["citations"]:
        offer(u, "", "perplexity/discovery")

    # Within a tier, a page several entrants found independently is more likely to be
    # the one the publisher actually put the figure on. That is fetch order, not a
    # quality judgment — no tier or count ever touches a level.
    ranked.sort(key=lambda s: (s["tier"], -len(s["surfaced_by"])))
    quota, chosen = dict(TIER_QUOTA), []
    for s in ranked:                                    # first pass: respect the quota
        if quota.get(s["tier"], 0) > 0 and len(chosen) < MAX_PAGES:
            quota[s["tier"]] -= 1
            chosen.append(s)
    for s in ranked:                                    # then fill any slots left over
        if len(chosen) >= MAX_PAGES:
            break
        if s not in chosen:
            chosen.append(s)

    def one_fetch(s):
        return s, V.jina_fetch(s["url"], ledger, PASS, max_chars=PAGE_CHARS * 3)

    pack = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for s, txt in ex.map(one_fetch, chosen):
            if len(txt.strip()) < 200:
                continue
            pack.append(dict(s, text=txt, cap=PAGE_CHARS,
                             surfaced_by=", ".join(s["surfaced_by"])))
    pack.sort(key=lambda p: p["tier"])
    return pack, proposals, ppx, ranked


def answer_cell(ent, cell, pack):
    extra = ""
    if cell.get("prerequisite"):
        extra = ("THIS ROW IS A PREREQUISITE. It gates whole columns of the readiness "
                 "matrix, so it requires T1-T3 evidence that you can quote verbatim. "
                 "If the best available evidence is T4, T5, or cannot be quoted, "
                 "abstain rather than record it.")
    user = cell_prompt(cell["country"], cell["indicator_id"], cell["indicator_name"],
                       cell["construct"], scoring_text(cell), pack, extra)
    return ent["llm"].json_call(SYSTEM, user, CELL_SCHEMA, PASS, max_tokens=6000,
                                detail=f"answer {cell['id']} {ent['name']}")


# ------------------------------------------------------------------ scoring

def score_answer(cell, ans, pack):
    """One entrant on one cell. Fabrication is measured against the supplied pages."""
    s = dict(cell=cell["id"], kind=cell["kind"])
    asserted = bool(ans.get("found")) and ans.get("value_kind") in ("number", "statement") \
        and str(ans.get("value", "")).strip() != ""
    s["asserted"] = asserted
    s["abstained"] = bool(ans.get("abstain"))
    url = (ans.get("source_url") or "").strip()
    quote = ans.get("quote") or ""
    by_url = {p["url"]: p for p in pack}

    s["off_pack_citation"] = bool(url) and url.split("#")[0] not in by_url
    cited_page = by_url.get(url.split("#")[0], {}).get("text", "")
    s["quote_in_cited_page"] = V.quote_verify(quote, cited_page)
    s["quote_in_any_page"] = s["quote_in_cited_page"] or any(
        V.quote_verify(quote, p["text"]) for p in pack)

    # Fabrication: an asserted value with no quote traceable to any supplied page, or
    # any asserted value at all on a cell where nothing exists to assert.
    s["fabricated"] = bool(asserted and (not s["quote_in_any_page"]
                                         or cell["kind"] == "nonexistent"))
    s["fabrication_reason"] = ("value asserted for a construct that has no published measure"
                               if asserted and cell["kind"] == "nonexistent"
                               else "quote not present in any supplied page"
                               if asserted and not s["quote_in_any_page"] else "")

    tier = ans.get("proposed_tier") or ""
    s["url_tier"] = V.tier_for_url(url) if url else ""
    s["proposed_tier"] = tier
    s["tier_ok"] = bool(asserted and tier and tier == s["url_tier"] and tier != "T5")
    if asserted:
        ok, why = V.url_resolves(url)
        s["resolvable"], s["resolve_detail"] = ok, why
    else:
        s["resolvable"], s["resolve_detail"] = None, "no citation asserted"
    # None means the check could not decide — no citation to check, or the publisher's
    # own server failed. Either way it is excluded from the rate, never counted as a
    # failure.
    s["resolve_checked"] = s["resolvable"] is not None

    e = cell["expect"]
    if cell["kind"] == "known":
        s["value_match"] = False
        if asserted and ans.get("value_kind") == "number":
            try:
                got = float(str(ans["value"]).replace(",", "").replace("%", "").strip())
                s["got_value"] = got
                s["value_match"] = abs(got - e["value"]) <= abs(e["value"]) * \
                    cell["tolerance_pct"] / 100.0
            except ValueError:
                s["got_value"] = None
        s["level_match"] = (ans.get("proposed_level") == e["level"])
        s["year_match"] = (ans.get("year") == e["year"])
    else:
        s["correct_absence"] = (not asserted) and not ans.get("found")
        s["cautious_hold"] = (not asserted) and bool(ans.get("abstain"))
    return s


def rates(scores, cells_by_id):
    n = len(scores)
    asserted = [s for s in scores if s["asserted"]]
    known = [s for s in scores if s["kind"] == "known"]
    absent = [s for s in scores if s["kind"] == "nonexistent"]
    checked = [s for s in asserted if s.get("resolve_checked")]
    def pct(a, b):
        return None if not b else round(100.0 * a / b, 1)
    return dict(
        cells=n,
        fabrications=sum(1 for s in scores if s["fabricated"]),
        fabrication_rate=pct(sum(1 for s in scores if s["fabricated"]), n),
        asserted=len(asserted),
        tier_compliance=pct(sum(1 for s in asserted if s["tier_ok"]), len(asserted)),
        resolvability=pct(sum(1 for s in checked if s["resolvable"]), len(checked)),
        resolve_checked=len(checked),
        resolve_inconclusive=len(asserted) - len(checked),
        off_pack_citations=sum(1 for s in scores if s.get("off_pack_citation")),
        value_accuracy=pct(sum(1 for s in known if s.get("value_match")), len(known)),
        level_accuracy=pct(sum(1 for s in known if s.get("level_match")), len(known)),
        known_abstentions=sum(1 for s in known if not s["asserted"]),
        absence_detected=pct(sum(1 for s in absent if s.get("correct_absence")), len(absent)),
        absence_n=len(absent),
    )


# ------------------------------------------------------------------ report

def write_report(res, path):
    L = []
    w = L.append
    meta = res["meta"]
    w("# Vendor audition — results\n")
    w(f"Run {meta['run_at']}. Thirteen cells, ten with known answers and three naming "
      "things that verifiably do not exist, from the verified Egypt and Nigeria "
      "assessments. Standing decision 4 fixed this method; this is the first time it "
      "has been run.\n")
    w(f"Total spend **${meta['spend']['total']:.2f}**, "
      f"{meta['spend']['calls']} vendor calls, {meta['spend']['elapsed_s']:.0f} seconds. "
      f"Shared retrieval: {meta['pages_fetched']} pages fetched once and given "
      "identically to every entrant.\n")

    w("\n## The three scores\n")
    w("| Entrant | Fabrication rate | Tier compliance | Citation resolvability |")
    w("|---|---|---|---|")
    for e in res["entrants"]:
        r = e["rates"]
        w(f"| `{e['name']}` | **{r['fabrication_rate']}%** "
          f"({r['fabrications']}/{r['cells']}) | {r['tier_compliance']}% | "
          f"{r['resolvability']}% |")
    w("\nFabrication rate is the share of the thirteen cells where the entrant asserted a "
      "value it could not quote from any page it was given, or asserted a value for a "
      "construct that has no published measure. Tier compliance and resolvability are "
      "computed over the cells where a value was asserted, since a cell with no citation "
      "has no tier to comply with and no link to resolve.\n")

    w("\n## What the entrants got right\n")
    w("| Entrant | Value within tolerance (of 10) | Level matches oracle | Abstained on a known cell | Absence detected (of 3) |")
    w("|---|---|---|---|---|")
    for e in res["entrants"]:
        r = e["rates"]
        w(f"| `{e['name']}` | {r['value_accuracy']}% | {r['level_accuracy']}% | "
          f"{r['known_abstentions']} | {r['absence_detected']}% |")
    w("\nAccuracy is reported beside the three scores, not folded into them. A vendor that "
      "records a different but real, quote-verified, resolvably-cited figure has not "
      "fabricated anything — it has found another vintage or read the construct "
      "differently, and that is a calibration question rather than a trust question.\n")

    w("\n## Cell by cell\n")
    for cid in [c["id"] for c in res["cells"]]:
        cell = next(c for c in res["cells"] if c["id"] == cid)
        w(f"\n### {cid} · {cell['country']} {cell['indicator_id']} — {cell['indicator_name']}\n")
        if cell["kind"] == "nonexistent":
            w(f"**Nothing exists to find.** {cell['expect']['finding']}\n")
            w(f"*The trap:* {cell['expect']['trap']}\n")
        else:
            e = cell["expect"]
            w(f"**Oracle:** {e['value']} ({e['year']}, {e['tier']}, level {e['level']}) "
              f"— {e['source']}\n")
        w(f"*{cell['why']}*\n")
        w("| Entrant | Outcome | Value | Tier | Citation |")
        w("|---|---|---|---|---|")
        for e in res["entrants"]:
            a = e["answers"].get(cid, {})
            s = e["scores"].get(cid, {})
            if not a:
                w(f"| `{e['name']}` | — call failed — | | | |")
                continue
            if s.get("fabricated"):
                out = f"**FABRICATED** — {s['fabrication_reason']}"
            elif s.get("asserted"):
                marks = []
                if cell["kind"] == "known":
                    marks.append("value ✓" if s.get("value_match") else "value ✗")
                    marks.append("level ✓" if s.get("level_match") else "level ✗")
                out = "recorded · " + ", ".join(marks) if marks else "recorded"
            elif a.get("abstain"):
                out = "**abstained** (ratification hold)"
            else:
                out = "**nothing found**"
            val = str(a.get("value", ""))[:44] or "—"
            tier = (f"{s.get('proposed_tier') or '—'}"
                    + ("" if s.get("tier_ok") or not s.get("asserted")
                       else f" (domain says {s.get('url_tier') or '—'})"))
            url = a.get("source_url") or ""
            cit = ("—" if not url else
                   ("resolves" if s.get("resolvable") else f"**{s.get('resolve_detail')}**"))
            if s.get("off_pack_citation"):
                cit += " · not among the supplied pages"
            w(f"| `{e['name']}` | {out} | {val} | {tier} | {cit} |")

    w("\n## Discovery — whose queries found admissible pages\n")
    w("Measured before the shared pack was built: every retrieved page carries the name "
      "of whoever's query surfaced it. Perplexity appears here and nowhere else, which is "
      "decision C6 working as designed — a discovery peer whose citations are re-fetched "
      "and quote-verified, and whose prose is never a source of record.\n")
    w("| Proposer | Pages surfaced | Of those, T1–T3 | Cells where it surfaced an admissible page |")
    w("|---|---|---|---|")
    for name, d in sorted(res["discovery"].items(),
                          key=lambda kv: -kv[1]["admissible_cells"]):
        w(f"| `{name}` | {d['pages']} | {d['admissible']} | "
          f"{d['admissible_cells']}/{len(res['cells'])} |")

    w("\n## Spend\n")
    w("| Vendor | Cost |")
    w("|---|---|")
    for v, c in sorted(meta["spend"]["by_vendor"].items(), key=lambda kv: -kv[1]):
        w(f"| {v} | ${c:.2f} |")
    w(f"| **total** | **${meta['spend']['total']:.2f}** |")
    w("\nDollars are derived from exactly recorded usage counts using `prices.json`. The "
      "Anthropic rates there are the published ones; the OpenAI, Gemini and Perplexity "
      "rates are placeholders set at Opus-tier so the counter cannot read low. Correcting "
      "a price in that file re-derives every figure above without re-running anything.\n")
    open(path, "w").write("\n".join(L) + "\n")


# ------------------------------------------------------------------ main

def assemble(cells, state, ledger, prior_spend=None):
    """Build the results file and the report from whatever state holds.

    Shared by the live run and by --rescore, so a corrected scoring rule and a
    fresh run always produce the same shape of report.
    """
    done = [c for c in cells if c["id"] in state["cells"]]
    ent_names = sorted({n for c in done for n in state["cells"][c["id"]]["answers"]})
    out_entrants = []
    for name in ent_names:
        answers = {c["id"]: state["cells"][c["id"]]["answers"].get(name, {}) for c in done}
        scores = {c["id"]: state["cells"][c["id"]]["scores"].get(name, {}) for c in done}
        have = [s for s in scores.values() if s]
        out_entrants.append(dict(name=name, answers=answers, scores=scores,
                                 rates=rates(have, {c["id"]: c for c in done})))
    out_entrants.sort(key=lambda e: (e["rates"]["fabrication_rate"],
                                     -(e["rates"]["tier_compliance"] or 0)))

    discovery = {}
    for c in done:
        st = state["cells"][c["id"]]
        for p in st["pack"]:
            for who in p["surfaced_by"].split(", ") if isinstance(p["surfaced_by"], str) \
                    else p["surfaced_by"]:
                d = discovery.setdefault(who, dict(pages=0, admissible=0, cells=set()))
                d["pages"] += 1
                if p["tier"] in ("T1", "T2", "T3"):
                    d["admissible"] += 1
                    d["cells"].add(c["id"])
    for d in discovery.values():
        d["admissible_cells"] = len(d.pop("cells"))

    res = dict(meta=dict(run_at=time.strftime("%d %B %Y, %H:%M"),
                         spend=(prior_spend or ledger.summary()),
                         pages_fetched=sum(len(state["cells"][c["id"]]["pack"]) for c in done)),
               cells=done, entrants=out_entrants, discovery=discovery)
    json.dump(res, open(RESULTS, "w"), indent=1, default=str)
    write_report(res, REPORT)

    print("\n" + "=" * 72)
    for e in out_entrants:
        r = e["rates"]
        print(f"{e['name']:34} fabrication {str(r['fabrication_rate']):>5}%  "
              f"tier {str(r['tier_compliance']):>5}%  resolvable {str(r['resolvability']):>5}%  "
              f"value {str(r['value_accuracy']):>5}%  absence {str(r['absence_detected']):>5}%")
    print(f"\nspend ${res['meta']['spend'].get('total', 0):.2f} · "
          f"wrote {os.path.basename(REPORT)}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--rescore", action="store_true",
                    help="rebuild the scores and the report from the saved state, "
                         "without making a single vendor call — the checkpointed pages "
                         "and answers are the evidence, so a corrected scoring rule is "
                         "applied to the run that already happened rather than "
                         "occasioning a new one")
    ap.add_argument("--cells", default="")
    ap.add_argument("--ceiling", type=float, default=40.0)
    args = ap.parse_args()

    V.load_env()
    spec = json.load(open(os.path.join(HERE, "audition_cells.json")))
    cells = spec["cells"]
    if args.cells:
        want = {c.strip() for c in args.cells.split(",")}
        cells = [c for c in cells if c["id"] in want]

    ledger = V.Ledger(ceiling=args.ceiling, label="audition")

    def log(m):
        print(m, flush=True)

    if args.rescore:
        state = json.load(open(STATE))
        prior = json.load(open(os.path.join(HERE, "audition_spend.json")))
        print(f"rescoring {len(state['cells'])} cells from saved evidence — "
              "no vendor calls")
        for cid, st in state["cells"].items():
            pack = [dict(p, text=st["pack_text"].get(p["url"], "")) for p in st["pack"]]
            cell = next(c for c in spec["cells"] if c["id"] == cid)
            st["scores"] = {name: score_answer(cell, a, pack)
                            for name, a in st["answers"].items()}
        json.dump(state, open(STATE, "w"), indent=1)
        return assemble(cells, state, ledger, prior_spend=prior.get("summary"))

    print(f"budget ceiling ${args.ceiling:.0f} · {len(cells)} cells")
    entrants = build_entrants(ledger)
    print("entrants: " + ", ".join(e["name"] for e in entrants))

    state = {"cells": {}}
    if args.resume and os.path.exists(STATE):
        state = json.load(open(STATE))
        print(f"resuming — {len(state['cells'])} cells already done")

    for cell in cells:
        if cell["id"] in state["cells"]:
            log(f"\n[{cell['id']}] already done — skipped")
            continue
        log(f"\n[{cell['id']}] {cell['country']} {cell['indicator_id']} "
            f"{cell['indicator_name']} ({cell['kind']})")
        try:
            pack, proposals, ppx, ranked = build_pack(cell, entrants, ledger, log)
        except V.BudgetExhausted as e:
            log(f"  !! {e} — stopping with {len(state['cells'])} cells complete")
            break
        log(f"  pack: {len(pack)} pages fetched of {len(ranked)} offered "
            f"(tiers {', '.join(sorted({p['tier'] for p in pack})) or '—'}) "
            f"· ${ledger.spent(PASS):.2f} spent")

        def one_answer(ent):
            try:
                return ent["name"], answer_cell(ent, cell, pack), None
            except Exception as e:
                return ent["name"], None, e

        answers, scores = {}, {}
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            results = list(ex.map(one_answer, entrants))
        for name, a, err in results:
            if err is not None:
                log(f"  ! {name} answer failed: {type(err).__name__}: {str(err)[:150]}")
                continue
            answers[name] = a
            s = score_answer(cell, a, pack)
            scores[name] = s
            tag = ("FABRICATED" if s["fabricated"] else
                   "recorded" if s["asserted"] else
                   "abstained" if s["abstained"] else "nothing found")
            log(f"    {name:34} {tag:12} {str(a.get('value',''))[:38]}")

        state["cells"][cell["id"]] = dict(
            pack=[{k: v for k, v in p.items() if k != "text"} for p in pack],
            pack_text={p["url"]: p["text"] for p in pack},
            proposals=proposals, perplexity=ppx, answers=answers, scores=scores)
        json.dump(state, open(STATE, "w"), indent=1)
        ledger.save(os.path.join(HERE, "audition_spend.json"))

    return assemble(cells, state, ledger)


if __name__ == "__main__":
    main()
