#!/usr/bin/env python3
"""Automated per-indicator research — the first pass of the pipeline.

Takes one country and produces a full engine input: all 57 indicator rows plus the two
carried candidates, each with a value, a source, a source URL, a proposed tier, a year,
a level, and a rung-by-rung argument that includes the negative finding — why the level
above was not proposed.

The design decisions this file implements, and where to find them:

  C1  tier, never a score; a non-numeric data-quality flag beside it   -> `row_from`
  C2  the machine sets the level; there is no confirmation step        -> `derive_level`
  C3  the machine may abstain, and a hold is not an absence            -> `gates.py`
  C4  prerequisites need T1-T3 quote-verified evidence                 -> `gates.py`
  C6  Perplexity discovers; its citations are re-fetched and verified  -> `retrieve`
  C7  one country per task, no shared leads, bleed rejected            -> `gates.py`
  G2  a live spend counter and visible exhaustion                      -> `vendors.Ledger`
  G3  fixed per-pass allocation, generation reserved                   -> `vendors.Ledger`

Two things it deliberately does NOT do. It does not run Gate 2 — the automated
refutation pass is Thread 3, and its absence is why this pass will hold more rows than
the hand-run assessments did. And it does not consult the verified Egypt or Nigeria
assessments for anything: those are the test oracle, and a pipeline that reads its own
answer key measures nothing.

Usage:
    python3 research_orchestrator.py --country Egypt --iso EGY --out EGY_shadow \\
        [--ceiling 500] [--resume] [--rows 2.1,1.8] [--vendor anthropic/claude-opus-5]
"""

import argparse, json, os, sys, threading, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP1 = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(LOOP1, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, LOOP1)

import vendors as V
import gates as G
from cell_schema import (CELL_SCHEMA, QUERY_SCHEMA, SYSTEM, cell_prompt,
                         LADDER_TEXT, threshold_text)
from engine_v17 import MODEL, tlevel
from build_inputs import ladder_level, standalone, americanize
import machine_pass

PASS = "research"
MODEL_FILE = os.path.join(REPO, "model", "DAMM-v1.7-model.json")
# The assessment year comes from the model file, so a ratification that moves it moves
# the currency gate with it rather than leaving a constant behind in this file.
ASSESSMENT_YEAR = json.load(open(MODEL_FILE))["config"]["assessment_year"]

MAX_QUERIES = 3
EXA_RESULTS = 6
MAX_PAGES = 10
PAGE_CHARS = 6000
FETCH_WORKERS = 6
ROW_WORKERS = 4
TIER_QUOTA = {"T1": 4, "T2": 2, "T3": 2, "T4": 2, "T5": 1}

# The two carried candidates (spec 13.2). They are researched like any other row and
# then held outside every aggregate — `candidate_indicators.never` in the model file
# bars them from every mean, every prerequisite and the readiness matrix.
CANDIDATES = {
    "A1-CAND-IMP": "Cereal import dependency ratio (%)",
    "A1-CAND-IRR": "Share of cultivated area equipped for irrigation (%)",
}


# ------------------------------------------------------------------ row specs

def build_specs(model):
    """One spec per row: what to research, and what the level would turn on."""
    by_id = {i["id"]: i for i in model["indicators"]}
    specs = []
    for iid, m in MODEL.items():
        mi = by_id.get(iid, {})
        specs.append(dict(
            id=iid, name=m["name"], method=("ladder" if m["kind"] == "l" else "threshold"),
            direction=("higher-is-better" if m["dir"] == "H" else "lower-is-better"),
            thresholds=m["th"], prerequisite=m["prereq"], pillar=m["pillar"],
            candidate=False,
            open_question=(mi.get("ratification") or {}).get("open_question", ""),
            severity=(mi.get("ratification") or {}).get("severity", "")))
    for cid, cname in CANDIDATES.items():
        specs.append(dict(id=cid, name=cname, method="threshold",
                          direction="higher-is-better", thresholds=[],
                          prerequisite=None, pillar="A1", candidate=True,
                          open_question="", severity=""))
    return specs


DISAGGREGATION = [
    ("rural", "RURAL", "a national figure does not measure a rural indicator, however "
                       "close the two look"),
    ("female", "FEMALE", "a figure covering all adults does not measure a female one"),
    ("women", "WOMEN", "a figure covering all adults does not measure one about women"),
    ("smallholder", "SMALLHOLDER", "a figure covering all farms does not measure one "
                                   "about smallholders"),
    ("youth", "YOUTH", "a figure covering all ages does not measure one about youth"),
]


def construct_for(spec, country):
    """What this indicator measures, said plainly, with its traps named."""
    lines = [f"{spec['name']} for {country}."]
    low = spec["name"].lower()
    for needle, caps, warning in DISAGGREGATION:
        if needle in low:
            lines.append(f"This indicator names {caps} specifically: {warning}. If only "
                         f"a broader figure is published, that is a construct mismatch, "
                         f"not an answer — abstain and record the broader figure as "
                         f"context in construct_note.")
            break
    if spec["open_question"]:
        lines.append("DEFINITION NOT YET RATIFIED. The assessment's own indicator census "
                     "records this open question about what this row should mean: "
                     f"\"{spec['open_question']}\" Judge the construct match against the "
                     "indicator's NAME as written, and say in construct_note if the best "
                     "available evidence sits on the wrong side of that question.")
    return " ".join(lines)


def scoring_text(spec):
    if spec["candidate"]:
        return ("SCORING: this is a CARRIED CANDIDATE indicator, recorded but never "
                "scored. Record the value, source, tier and year; leave proposed_level "
                "at 0.")
    if spec["method"] == "ladder":
        return LADDER_TEXT
    return threshold_text(spec["direction"], spec["thresholds"])


# ------------------------------------------------------------------ retrieval

def retrieve(spec, country, llm, ledger, log, pass_name=PASS):
    """Discovery and fetch for exactly one row of exactly one country.

    Queries are generated per row from that row's own construct — there is no shared
    lead list anywhere in this function, which is what closes defect #11.

    `pass_name` decides which budget allocation the searching bills against. Gate 2 does
    its own retrieval through this same function, and billing that to the research pass
    would let one pass spend another's share — which is exactly what decision G3's fixed
    allocation exists to prevent.
    """
    construct = construct_for(spec, country)
    try:
        plan = llm.json_call(
            "You plan evidence searches for a national statistics assessment. JSON only.",
            f"COUNTRY: {country}\nINDICATOR: {spec['id']} — {spec['name']}\n"
            f"WHAT IT MEASURES: {construct}\n\n"
            "Propose the web searches most likely to surface the highest-tier published "
            "source for this exact construct, for this country and no other. Search the "
            "publisher, not the topic.",
            QUERY_SCHEMA, pass_name, max_tokens=2000, detail=f"queries {spec['id']}")
    except V.BudgetExhausted:
        raise
    except Exception as e:
        log(f"    ! query planning failed: {str(e)[:100]}")
        plan = {"queries": [f"{country} {spec['name']} statistics"], "likely_publishers": []}

    seen, ranked = {}, []

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

    # The planner's queries plus one deterministic query built from the country and the
    # indicator name. Two probe runs of the same row produced a Documented level and a
    # gap purely because the planner's three queries went a different way the second
    # time and never reached the ministry page that carries the answer. A plain,
    # always-present query costs one search and puts a floor under retrieval, so a row's
    # outcome turns less on which phrasing the planner happened to choose.
    queries = [q for q in (plan.get("queries") or [])[:MAX_QUERIES] if q.strip()]
    baseline = f"{country} {spec['name']}"
    if not any(baseline.lower() == q.lower() for q in queries):
        queries.append(baseline)

    def one_search(q):
        try:
            return V.exa_search(q, ledger, pass_name, num_results=EXA_RESULTS)
        except V.BudgetExhausted:
            raise
        except Exception as e:
            log(f"    ! search failed: {str(e)[:80]}")
            return []

    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as ex:
        for res in ex.map(one_search, queries):
            for r in res:
                offer(r["url"], r["title"], "exa", r.get("published", ""))

    # Perplexity as discovery peer only (C6). Its citations join the fetch queue and
    # are quote-verified like any other page; its prose is kept beside the row as a
    # lead and can never become the source of record.
    ppx = {"citations": [], "lead_prose": "", "error": ""}
    try:
        ppx = V.perplexity_citations(
            f"For {country} only: {construct} Which published source states this, and "
            f"what does it say? If no source publishes this exact measure, say so.",
            ledger, pass_name)
        for u in ppx["citations"]:
            offer(u, "", "perplexity")
    except V.BudgetExhausted:
        raise
    except Exception as e:
        # Recorded on the row, not just logged: a row that lost its discovery peer was
        # researched on a narrower base than its neighbours, and that difference has to
        # be visible to anyone reading the row afterwards.
        ppx["error"] = str(e)[:200]
        log(f"    ! {spec['id']}: perplexity discovery unavailable — {str(e)[:90]}")

    ranked.sort(key=lambda s: (s["tier"], -len(s["surfaced_by"])))
    quota, chosen = dict(TIER_QUOTA), []
    for s in ranked:
        if quota.get(s["tier"], 0) > 0 and len(chosen) < MAX_PAGES:
            quota[s["tier"]] -= 1
            chosen.append(s)
    for s in ranked:
        if len(chosen) >= MAX_PAGES:
            break
        if s not in chosen:
            chosen.append(s)

    def one_fetch(s):
        return s, V.jina_fetch(s["url"], ledger, pass_name, max_chars=PAGE_CHARS * 3)

    pack = []
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as ex:
        for s, txt in ex.map(one_fetch, chosen):
            if len(txt.strip()) < 200:
                continue
            pack.append(dict(s, text=txt, cap=PAGE_CHARS,
                             surfaced_by=", ".join(s["surfaced_by"])))
    pack.sort(key=lambda p: p["tier"])
    return pack, plan, ppx, construct


# ------------------------------------------------------------------ derivation

def derive_class(spec, value_kind, tier, url):
    """The evidence class is derived from what was recorded, never chosen.

    A T5-only citation derives Judged, never Documented — a design invariant, and the
    reason the tier gate can hold a row without deleting what it found.

    A ladder indicator is never Measured, whatever the vendor returned. Measured means
    "the level is threshold-derived from a recorded number", and a ladder indicator has
    no thresholds to derive against — its level comes from the presence rung. Neither
    verified assessment carries a single Measured ladder row, and letting one through
    would put a class on the page that its own level could not have come from.
    """
    if value_kind == "number" and spec["method"] != "ladder":
        return "Measured"
    if url and tier and tier != "T5":
        return "Documented"
    return "Judged"


def derive_level(spec, ans, cls, verdict):
    """Return (level, how). A hold or a reject never yields a level (C3)."""
    if verdict != "pass" or spec["candidate"]:
        return None, "level withheld"
    if spec["method"] == "ladder":
        lvl, why = ladder_level(ans.get("presence_rung"), ans.get("quality_evidence"),
                                ans.get("scale_evidence"))
        if lvl is None:
            return None, "ladder rung not established"
        return lvl, f"ladder {ans.get('presence_rung')}{why}"
    if cls == "Measured":
        try:
            v = float(str(ans["value"]).replace(",", "").replace("%", "").strip())
        except (ValueError, KeyError):
            return None, "recorded value is not numeric"
        return tlevel(v, "H" if spec["direction"] == "higher-is-better" else "L",
                      spec["thresholds"]), "threshold"
    # A threshold indicator that no one publishes a headline number for. The evidence is
    # real — a range, several partial measures, a qualitative finding — and the machine
    # argues it against the cut points itself, which is what C2 means by the machine
    # setting levels. Both verified assessments carry rows of exactly this shape:
    # Documented, with a level. Holding them instead would report an absence where there
    # is evidence, and manufacturing a number from a range would give the row a
    # precision its sources do not have.
    claimed = ans.get("proposed_level")
    if isinstance(claimed, int) and 1 <= claimed <= 5:
        return claimed, "argued against the cut points from non-numeric evidence"
    return None, "no level argued and no numeric value recorded"


def numeric(ans):
    try:
        return float(str(ans["value"]).replace(",", "").replace("%", "").strip())
    except (ValueError, KeyError, TypeError):
        return None


def compose_note(ans, verdict, gate, how, corroboration):
    """The row's note: the negative finding, the hold reason, the quality flag.

    Standalone prose only — the report is a document, not a process history.
    """
    bits = []
    if verdict == "hold":
        bits.append(f"RATIFICATION HOLD — {gate.reason}. The level is withheld and this "
                    f"row leaves every mean.")
    elif verdict == "reject":
        bits.append(f"EVIDENCE REJECTED — {gate.reason}.")
    if ans.get("data_quality_flag"):
        bits.append(ans["data_quality_flag"])
    if verdict in ("pass", "gap") and ans.get("negative_finding"):
        bits.append("Next level not proposed: " + ans["negative_finding"])
    if ans.get("construct_note") and verdict != "hold":
        bits.append(ans["construct_note"])
    if corroboration:
        bits.append(corroboration)
    return americanize(standalone(" ".join(b.strip().rstrip(".") + "." for b in bits if b)))


def gap_value(ans, spec, country):
    trail = (ans.get("search_trail") or "").strip()
    if not trail:
        trail = (f"no source publishing {spec['name'].lower()} for {country} was located "
                 f"at any admissible tier")
    return "DATA GAP — " + trail


def row_from(spec, ans, verdict, gate, pack, corroboration, country):
    """Turn one gated answer into one engine input row."""
    asserted = bool(ans.get("found")) and ans.get("value_kind") in ("number", "statement") \
        and str(ans.get("value", "")).strip() != ""
    tier = (ans.get("proposed_tier") or "")
    url = (ans.get("source_url") or "").strip()
    # The tier of record is the tier of the domain that actually carries the page, not
    # the tier the vendor proposed for it. Tier is a property of the publisher.
    if url:
        tier = V.tier_for_url(url)

    if not asserted or verdict in ("reject", "gap"):
        return dict(value=americanize(standalone(gap_value(ans, spec, country))),
                    cls="Gap", level=None, year=2026,
                    src=f"Automated source search, {time.strftime('%d %B %Y')}",
                    note=compose_note(ans, verdict, gate, "", corroboration),
                    tier="", tier_detail="", url="")

    cls = derive_class(spec, ans.get("value_kind"), tier, url)
    level, how = derive_level(spec, ans, cls, verdict)
    if cls == "Measured":
        value = numeric(ans)
        if value is None:
            cls, value = "Documented", str(ans.get("value"))[:220]
    else:
        value = americanize(standalone(str(ans.get("value"))[:220]))

    return dict(value=value, cls=cls, level=level,
                year=(ans.get("year") or 2026) if ans.get("year") else 2026,
                src=americanize(standalone(ans.get("source_title") or "")),
                note=compose_note(ans, verdict, gate, how, corroboration),
                tier=tier, tier_detail=ans.get("data_quality_flag") or "", url=url)


# ------------------------------------------------------------------ one row

def research_row(spec, country, llm, ledger, wdi, log, t1_fill=False):
    pack, plan, ppx, construct = retrieve(spec, country, llm, ledger, log)

    extra = ""
    if spec["prerequisite"]:
        extra = (f"THIS ROW IS A PREREQUISITE ({spec['prerequisite']}). It gates whole "
                 "columns of the readiness matrix, so it requires T1-T3 evidence you can "
                 "quote verbatim. If the best available evidence is T4, T5, or cannot be "
                 "quoted, abstain rather than record it.")
    user = cell_prompt(country, spec["id"], spec["name"], construct,
                       scoring_text(spec), pack, extra)
    ans = llm.json_call(SYSTEM, user, CELL_SCHEMA, PASS, max_tokens=6000,
                        detail=f"answer {spec['id']}")

    by_url = {p["url"]: p for p in pack}
    cited = (ans.get("source_url") or "").split("#")[0]
    page = by_url.get(cited)
    quote_ok = V.quote_verify(ans.get("quote", ""), page["text"]) if page else False
    is_ladder = spec["method"] == "ladder" and not spec["candidate"]
    ladder_derived = ladder_level(ans.get("presence_rung"), ans.get("quality_evidence"),
                                  ans.get("scale_evidence"))[0] if is_ladder else None
    gate_list = G.run_gates(ans, country=country, indicator_id=spec["id"],
                            is_prerequisite=bool(spec["prerequisite"]),
                            quote_ok=quote_ok,
                            quote_page_tier=(page or {}).get("tier", ""),
                            cited_url=cited, page_urls=set(by_url),
                            derived_level=ladder_derived, is_ladder=is_ladder,
                            assessment_year=ASSESSMENT_YEAR)
    verdict, gate = G.verdict_of(gate_list)
    asserted = bool(ans.get("found")) and ans.get("value_kind") in ("number", "statement") \
        and str(ans.get("value", "")).strip() != ""
    if verdict == "pass" and not asserted:
        # Nothing was found. That is a gap, and calling it a pass in the record would
        # make a row that asserts nothing read like a row that cleared every gate.
        verdict = "gap"

    # Independent corroboration, where a machine-fetchable T1 series covers this row.
    # It is reported, never substituted: the point of the shadow run is to measure what
    # the research lane produces, and quietly swapping in an API figure would measure
    # the API instead.
    corroboration = ""
    w = wdi.get(spec["id"])
    if w and w.get("status") == "ok":
        got = numeric(ans)
        if got is None:
            corroboration = (f"An independent T1 series ({w['src']}) reports "
                             f"{round(w['value'], 2)} for {w['year']}.")
        else:
            near = abs(got - w["value"]) <= max(abs(w["value"]) * 0.02, 1e-9)
            corroboration = (f"Corroborated by an independent T1 series ({w['src']}): "
                             f"{round(w['value'], 2)} for {w['year']}."
                             if near else
                             f"An independent T1 series ({w['src']}) reports "
                             f"{round(w['value'], 2)} for {w['year']}, which differs "
                             f"from the value recorded here.")

    row = row_from(spec, ans, verdict, gate, pack, corroboration, country)

    # The research lane found nothing and a machine-readable T1 series has the figure.
    # Filling is off by default and never silent: the row records which lane produced it,
    # so a reader can always tell autonomous research from a curated series.
    if t1_fill and row["cls"] == "Gap" and w and w.get("status") == "ok" \
            and not spec["candidate"]:
        lvl = (tlevel(w["value"], "H" if spec["direction"] == "higher-is-better" else "L",
                      spec["thresholds"]) if spec["method"] == "threshold" else None)
        row = dict(value=w["value"], cls="Measured", level=lvl, year=w["year"],
                   src=americanize(standalone(w["src"])), tier="T1", tier_detail="",
                   url=w["url"],
                   note=americanize(standalone(
                       "Recorded from the machine-readable T1 lane. The research lane did "
                       "not reach a country value for this row, and the series was fetched "
                       "directly from the publisher's interface. " + (w.get("note") or ""))))
    record = dict(id=spec["id"], name=spec["name"], country=country,
                  verdict=verdict, gates=[g.as_dict() for g in gate_list],
                  quote_verified=quote_ok, answer=ans, row=row,
                  queries=plan.get("queries", []),
                  perplexity_citations=ppx.get("citations", []),
                  perplexity_lead=ppx.get("lead_prose", "")[:1200],
                  perplexity_error=ppx.get("error", ""),
                  pack=[{k: v for k, v in p.items() if k != "text"} for p in pack],
                  wdi_corroboration=w if w else None)
    return row, record


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", required=True)
    ap.add_argument("--iso", required=True)
    ap.add_argument("--out", required=True, help="basename, e.g. EGY_shadow")
    ap.add_argument("--ceiling", type=float, default=500.0)
    ap.add_argument("--vendor", default="anthropic/claude-opus-5")
    ap.add_argument("--rows", default="")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--t1-fill", action="store_true",
                    help="let the machine-readable T1 lane fill a row the research lane "
                         "left as a gap. Off by default, because a measurement run that "
                         "silently substituted an API figure would be measuring the API. "
                         "On, every row it fills says so on its own face.")
    args = ap.parse_args()

    V.load_env()
    model = json.load(open(MODEL_FILE))
    specs = build_specs(model)
    if args.rows:
        want = {r.strip() for r in args.rows.split(",")}
        specs = [s for s in specs if s["id"] in want]

    vendor, _, mname = args.vendor.partition("/")
    ledger = V.Ledger(ceiling=args.ceiling, label=args.out)
    llm = V.LLM(vendor, ledger, model=mname or None)

    state_path = os.path.join(LOOP1, f"{args.out}_state.json")
    state = {"rows": {}, "records": {}}
    if args.resume and os.path.exists(state_path):
        state = json.load(open(state_path))
        print(f"resuming — {len(state['rows'])} rows already researched")

    print(f"{args.country} ({args.iso}) · {len(specs)} rows · vendor {vendor}/{llm.model}")
    print(f"budget ${args.ceiling:.0f}, research allocation "
          f"${ledger.cap(PASS):.0f} (decision G3)\n")

    print("fetching the machine-readable T1 lane for independent corroboration...")
    try:
        wdi = machine_pass.fetch_country(args.iso)
        print(f"  {sum(1 for r in wdi.values() if r.get('status') == 'ok')} of "
              f"{len(wdi)} series returned\n")
    except Exception as e:
        print(f"  ! machine lane unavailable ({str(e)[:100]}); rows proceed uncorroborated\n")
        wdi = {}

    lock = threading.Lock()
    todo = [s for s in specs if s["id"] not in state["rows"]]
    stopped = None

    def log(m):
        print(m, flush=True)

    def work(spec):
        nonlocal stopped
        if stopped:
            return
        t0 = time.time()
        try:
            row, record = research_row(spec, args.country, llm, ledger, wdi, log,
                                       t1_fill=args.t1_fill)
        except V.BudgetExhausted as e:
            with lock:
                stopped = str(e)
            return
        except Exception as e:
            log(f"  ! {spec['id']} failed: {type(e).__name__}: {str(e)[:160]}")
            return
        with lock:
            state["rows"][spec["id"]] = row
            state["records"][spec["id"]] = record
            json.dump(state, open(state_path, "w"), indent=1, default=str)
            ledger.save(os.path.join(LOOP1, f"{args.out}_spend.json"))
            n = len(state["rows"])
        mark = {"pass": "  ", "hold": "H ", "reject": "R ", "gap": "G "}[record["verdict"]]
        log(f"{mark}[{n:2}/{len(specs)}] {spec['id']:12} {record['verdict']:6} "
            f"{str(row['cls']):10} L{row['level']} {str(row['value'])[:34]:36} "
            f"${ledger.spent(PASS):6.2f} {time.time() - t0:4.0f}s")

    with ThreadPoolExecutor(max_workers=ROW_WORKERS) as ex:
        list(ex.map(work, todo))

    if stopped:
        print(f"\n!! {stopped}")
        print("   The run stopped where the budget ran out. Rows never reached are "
              "absent from the output, NOT recorded as gaps — a budget-induced gap "
              "must never be indistinguishable from a real one.")

    # ---- assemble the engine input
    rows = dict(state["rows"])
    missing = [s["id"] for s in build_specs(model) if s["id"] not in rows]
    if missing and not args.rows:
        print(f"\n!! {len(missing)} rows not researched: {missing}")
        print("   Engine input NOT written — a partial input would score as though the "
              "missing rows had been looked for and not found.")
        json.dump(state["records"], open(os.path.join(LOOP1, f"{args.out}_research.json"),
                                         "w"), indent=1, default=str)
        return 1

    dn_path = os.path.join(LOOP1, "definition_notes.json")
    dnotes = json.load(open(dn_path)) if os.path.exists(dn_path) else {}
    for i, r in rows.items():
        if i in dnotes:
            r["defnote"] = dnotes[i]["q"]
            r["defsev"] = dnotes[i]["sev"]

    inp = os.path.join(LOOP1, f"{args.out}_input.json")
    json.dump(rows, open(inp, "w"), indent=1, default=str)
    json.dump(state["records"], open(os.path.join(LOOP1, f"{args.out}_research.json"), "w"),
              indent=1, default=str)
    ledger.save(os.path.join(LOOP1, f"{args.out}_spend.json"))

    s = ledger.summary()
    held = sum(1 for r in rows.values() if r["level"] is None and r["cls"] != "Gap")
    gaps = sum(1 for r in rows.values() if r["cls"] == "Gap")
    print(f"\nwrote {os.path.basename(inp)} — {len(rows)} rows, {gaps} gaps, {held} held")
    print(f"spend ${s['total']:.2f} of ${ledger.cap(PASS):.0f} allocated "
          f"(${args.ceiling:.0f} country ceiling) in {s['elapsed_s'] / 60:.0f} minutes, "
          f"{s['calls']} vendor calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
