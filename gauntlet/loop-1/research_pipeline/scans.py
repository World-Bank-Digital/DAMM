#!/usr/bin/env python3
"""Pass three: the scans (design decisions 2, 3 and E2).

Two lanes that must never be confused with each other, and never with the 57 indicators.

**The country lane** gathers what a roadmap needs and the instrument does not measure:
the national strategies, institutions, legal instruments, programmes and financing that
chapters 3 to 10 have to be written against. These are country evidence and obey the same
rules as an indicator row — a source with a tier, a verified quote, and the isolation
gate, so a finding about this country cannot rest on another country's page.

**The international lane** gathers precedent from elsewhere. It exists for the DAR only
(E2): the diagnostic is a standalone document with bounded international content, and
free-form comparison has no business in it. A pointer here is never an endorsement and
never a comparison of countries.

The separation is structural, not editorial. The two lanes are written to different keys,
every international pointer records which country it came from, and each lane has a gate
that rejects the other lane's material:

  * a country finding whose source is about another country is rejected (isolation), and
  * an international pointer drawn from a page about *this* country is rejected too —
    that is country evidence wearing a precedent label, and it would let material that
    failed the diagnostic's standards in through a side door.

Nothing in this file scores anything. The scans inform prose; they never touch a level, a
mean, a prerequisite or the readiness matrix.

    python3 scans.py --country Egypt --iso EGY --out EGY_shadow [--ceiling 500] [--resume]
"""

import argparse, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP1 = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(LOOP1, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, LOOP1)

import vendors as V
import gates as G

PASS = "scans"
MODEL_FILE = os.path.join(REPO, "model", "DAMM-v1.7-model.json")
MODEL = json.load(open(MODEL_FILE))
ASSESSMENT_YEAR = MODEL["config"]["assessment_year"]

EXA_RESULTS = 6
MAX_PAGES = 6
PAGE_CHARS = 6000
FETCH_WORKERS = 6
TOPIC_WORKERS = 3

# One precedent pointer per prescriptive chapter, and no more (E2). The cap is the point:
# an uncapped scan produces a league table, and a league table is a comparison of
# countries whatever the surrounding prose calls it.
POINTERS_PER_CHAPTER = 1


def prescriptive_chapters():
    """The chapters the scans exist to serve. Read from the model, never listed here."""
    return [c for c in MODEL["dar_outline"] if c["kind"] == "prescriptive"]


FINDING_SCHEMA = {
    "type": "object",
    "properties": {
        "found": {"type": "boolean"},
        "statement": {"type": "string"},
        "quote": {"type": "string"},
        "source_name": {"type": "string"},
        "source_url": {"type": "string"},
        "published_year": {"type": ["integer", "null"]},
        "about_country": {"type": "string"},
        "why_it_matters": {"type": "string"},
        "abstained_because": {"type": "string"},
    },
    "required": ["found", "statement", "quote", "source_name", "source_url",
                 "published_year", "about_country", "why_it_matters", "abstained_because"],
    "additionalProperties": False,
}

QUERY_SCHEMA = {
    "type": "object",
    "properties": {"queries": {"type": "array", "items": {"type": "string"}}},
    "required": ["queries"],
    "additionalProperties": False,
}

SYSTEM = ("You gather published evidence for a national digital agriculture roadmap. "
          "You quote sources exactly and you abstain rather than guess. JSON only.")


def _search_and_fetch(queries, ledger, log, want_country=None):
    """Discovery then fetch, returning fetched pages with their tiers.

    `want_country` biases nothing — retrieval is neutral. Which country a page is about
    is decided later, by the gates, from the page itself.
    """
    seen, ranked = {}, []

    def one_search(q):
        try:
            return V.exa_search(q, ledger, PASS, num_results=EXA_RESULTS)
        except V.BudgetExhausted:
            raise
        except Exception as e:
            log(f"    ! search failed: {str(e)[:80]}")
            return []

    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as ex:
        for res in ex.map(one_search, queries):
            for r in res or []:
                u = (r.get("url") or "").split("#")[0]
                if not u or u in seen:
                    continue
                seen[u] = dict(url=u, title=r.get("title") or "",
                               tier=V.tier_for_url(u))
                ranked.append(seen[u])

    # Best tier first: a scan that reads whatever came back first inherits the search
    # engine's ordering, which is popularity, not authority.
    ranked.sort(key=lambda r: r["tier"])
    picks = ranked[:MAX_PAGES]

    def fetch(r):
        try:
            text = V.jina_fetch(r["url"], ledger, PASS, max_chars=PAGE_CHARS * 3)
            return dict(r, text=text or "")
        except V.BudgetExhausted:
            raise
        except Exception as e:
            log(f"    ! fetch failed {r['url'][:50]}: {str(e)[:60]}")
            return None

    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as ex:
        pages = [p for p in ex.map(fetch, picks) if p and p["text"].strip()]
    return pages


def _pack(pages):
    return "\n\n".join(
        f"[{i + 1}] {p['title']} — {p['url']} ({p['tier']})\n{p['text'][:PAGE_CHARS]}"
        for i, p in enumerate(pages))


def _verify(ans, pages, log):
    """The quote must be on a page that was actually fetched (decision C6).

    Returns the matching page, or None. A finding whose quote is on no page is a finding
    the model wrote rather than read, and it is discarded rather than downgraded.
    """
    quote = (ans.get("quote") or "").strip()
    if not quote:
        return None
    for p in pages:
        if V.quote_verify(quote, p["text"]):
            return p
    return None


# ------------------------------------------------------------------ the lane gates
#
# Pure, so the rule that keeps the two lanes apart can be tested without a key or a
# network. Each gate rejects the other lane's material; between them they are what makes
# an international scan safe to run beside a country assessment.

def country_lane_gate(quote, url, country):
    """Country evidence must be about this country. Returns a refusal, or None."""
    foreign = G.foreign_attribution(quote or "", country)
    if foreign:
        return f"the quote is about {', '.join(foreign[:2])}, not {country}"
    owner = G.foreign_url(url or "", country)
    if owner:
        return f"the citation belongs to {owner}"
    return None


def international_lane_gate(about_country, page_title, url, country):
    """A precedent must come from somewhere else. Returns a refusal, or None.

    The mirror of the isolation gate. A pointer drawn from a page about the assessed
    country is that country's own evidence wearing a precedent label — it would reach the
    DAR without having passed the standards the country lane is held to, which is the one
    way this lane could do damage.
    """
    about = (about_country or "").strip()
    if not about:
        return "it does not say which country it is about"
    if G.names_country(about, country):
        return f"it points at {country}, which is the country being assessed, not a precedent"
    if G.foreign_url(url or "", country) is None and G.names_country(page_title or "", country):
        return f"the citation is a {country} page, not another country's"
    return None


# ------------------------------------------------------------------ the lanes

def country_topic(chapter, country):
    """What the country lane asks for one chapter. Built from the chapter's own content."""
    return (f"What has {country} already published that a roadmap chapter on "
            f"\"{chapter['title']}\" would have to take account of? {chapter['content']}")


def scan_country(chapter, country, llm, ledger, log):
    """Country evidence outside the indicator set, for one chapter."""
    topic = country_topic(chapter, country)
    try:
        plan = llm.json_call(
            SYSTEM,
            f"COUNTRY: {country}\nTOPIC: {topic}\n\n"
            "Propose web searches most likely to surface the country's own published "
            "documents on this — ministry strategies, national plans, legal instruments, "
            "programme documents, development-partner reports about this country. "
            "Search the publisher, not the topic.",
            QUERY_SCHEMA, PASS, max_tokens=1200, detail=f"queries ch{chapter['n']}")
        queries = [q for q in (plan.get("queries") or [])[:3] if q.strip()]
    except V.BudgetExhausted:
        raise
    except Exception as e:
        log(f"    ! query planning failed: {str(e)[:80]}")
        queries = []
    queries.append(f"{country} {chapter['title']} digital agriculture strategy")

    pages = _search_and_fetch(queries, ledger, log)
    if not pages:
        return None, "no page could be retrieved"

    ans = llm.json_call(
        SYSTEM,
        f"COUNTRY: {country}\nASSESSMENT YEAR: {ASSESSMENT_YEAR}\n"
        f"ROADMAP CHAPTER: {chapter['n']} — {chapter['title']}\n"
        f"WHAT THE CHAPTER COVERS: {chapter['content']}\n\n"
        f"SOURCES:\n{_pack(pages)}\n\n"
        "Report ONE thing from these sources that a person drafting this chapter for "
        f"{country} would need to know and that a set of maturity indicators would not "
        "tell them: an existing strategy, an institution, a legal instrument, a "
        "programme, a financing arrangement, a stated commitment.\n\n"
        "Rules. The quote must be copied EXACTLY from one of the sources above. The "
        f"source must be about {country}; if the only material you have is about another "
        "country, set found=false. Set found=false and say why in abstained_because if "
        "the sources do not carry something worth reporting. Never write a statement the "
        "quote does not support.",
        FINDING_SCHEMA, PASS, max_tokens=2500, detail=f"country ch{chapter['n']}")

    if not ans.get("found"):
        return None, ans.get("abstained_because") or "nothing worth reporting was found"

    page = _verify(ans, pages, log)
    if not page:
        return None, "the quote it reported is on none of the pages that were read"

    # Isolation, in both the prose and the citation (decision C7).
    refusal = country_lane_gate(ans.get("quote", ""), page["url"], country)
    if refusal:
        return None, refusal

    return dict(
        chapter=chapter["n"], chapter_title=chapter["title"], lane="country",
        statement=ans["statement"].strip(), quote=ans["quote"].strip(),
        why_it_matters=ans.get("why_it_matters", "").strip(),
        source_name=ans.get("source_name") or page["title"],
        source_url=page["url"], tier=page["tier"],
        published_year=ans.get("published_year"),
        about_country=country,
    ), None


def scan_international(chapter, country, llm, ledger, log):
    """One precedent pointer from another country, for the DAR only (E2)."""
    try:
        plan = llm.json_call(
            SYSTEM,
            f"TOPIC: national digital agriculture strategies — \"{chapter['title']}\". "
            f"{chapter['content']}\n\n"
            "Propose web searches for how OTHER countries have handled this in their "
            f"published national strategies. Do not search for {country}.",
            QUERY_SCHEMA, PASS, max_tokens=1200, detail=f"queries intl ch{chapter['n']}")
        queries = [q for q in (plan.get("queries") or [])[:3] if q.strip()]
    except V.BudgetExhausted:
        raise
    except Exception as e:
        log(f"    ! query planning failed: {str(e)[:80]}")
        queries = []
    queries.append(f"national digital agriculture strategy {chapter['title']}")

    pages = _search_and_fetch(queries, ledger, log)
    if not pages:
        return None, "no page could be retrieved"

    ans = llm.json_call(
        SYSTEM,
        f"ROADMAP CHAPTER: {chapter['n']} — {chapter['title']}\n"
        f"WHAT THE CHAPTER COVERS: {chapter['content']}\n\n"
        f"SOURCES:\n{_pack(pages)}\n\n"
        "Report ONE approach another country has published on this, as a pointer for "
        "drafters to consider — not a recommendation, not a ranking, and not a claim "
        f"that it would work in {country}.\n\n"
        "Rules. The quote must be copied EXACTLY from one of the sources above. Name the "
        "country it is about in about_country. The source must be about a country other "
        f"than {country}; if all you have is {country} material, set found=false. Set "
        "found=false and say why if the sources carry nothing worth pointing at.",
        FINDING_SCHEMA, PASS, max_tokens=2500, detail=f"intl ch{chapter['n']}")

    if not ans.get("found"):
        return None, ans.get("abstained_because") or "nothing worth pointing at was found"

    page = _verify(ans, pages, log)
    if not page:
        return None, "the quote it reported is on none of the pages that were read"

    about = (ans.get("about_country") or "").strip()
    refusal = international_lane_gate(about, page.get("title", ""), page["url"], country)
    if refusal:
        return None, refusal

    return dict(
        chapter=chapter["n"], chapter_title=chapter["title"], lane="international",
        statement=ans["statement"].strip(), quote=ans["quote"].strip(),
        why_it_matters=ans.get("why_it_matters", "").strip(),
        source_name=ans.get("source_name") or page["title"],
        source_url=page["url"], tier=page["tier"],
        published_year=ans.get("published_year"),
        about_country=about,
        # Carried on every record, not applied at render time. A flag the renderer has to
        # remember to check is a flag that will one day not be checked.
        applies_to="dar_only",
    ), None


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", required=True)
    ap.add_argument("--iso", required=True)
    ap.add_argument("--out", required=True, help="basename of the research pass")
    ap.add_argument("--ceiling", type=float, default=500.0)
    ap.add_argument("--vendor", default="anthropic/claude-opus-5")
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()

    V.load_env()
    vendor, _, mname = a.vendor.partition("/")
    ledger = V.Ledger(ceiling=a.ceiling, label=f"{a.out}_scans")
    llm = V.LLM(vendor, ledger, model=mname or None)

    state_path = os.path.join(LOOP1, f"{a.out}_scans_state.json")
    spend_path = os.path.join(LOOP1, f"{a.out}_scans_spend.json")
    out_path = os.path.join(LOOP1, f"{a.out}_scans.json")

    state = {"country": {}, "international": {}, "abstained": {}}
    if a.resume and os.path.exists(state_path):
        state = json.load(open(state_path))
        carried = ledger.load(spend_path)
        done = len(state["country"]) + len(state["international"])
        print(f"resuming — {done} scans already done, {carried} earlier vendor calls "
              f"carried (${ledger.spent():.2f} spent)")

    chapters = prescriptive_chapters()
    units = ([("country", c) for c in chapters]
             + [("international", c) for c in chapters][:len(chapters) * POINTERS_PER_CHAPTER])
    total = len(units)
    print(f"{a.country} ({a.iso}) · {total} rows · vendor {a.vendor}")
    print(f"budget ${a.ceiling:.0f}, scans allocation "
          f"${a.ceiling * V.Ledger.ALLOCATION[PASS]:.0f} (decision G3)")
    print()
    sys.stdout.flush()

    lock = __import__("threading").Lock()
    counter = {"n": 0}
    stopped = None

    def log(msg):
        print(msg)
        sys.stdout.flush()

    def save():
        json.dump(state, open(state_path, "w"), indent=1, default=str)
        ledger.save(spend_path)

    def run_one(unit):
        nonlocal stopped
        lane, chapter = unit
        key = f"{lane}:{chapter['n']}"
        if key in state[lane] or key in state["abstained"]:
            return
        if stopped:
            return
        t0 = time.time()
        try:
            fn = scan_country if lane == "country" else scan_international
            rec, why = fn(chapter, a.country, llm, ledger, log)
        except V.BudgetExhausted as e:
            with lock:
                stopped = str(e)
            return
        except Exception as e:
            rec, why = None, f"the scan failed: {str(e)[:120]}"

        with lock:
            counter["n"] += 1
            n = counter["n"]
            if rec:
                state[lane][key] = rec
                mark, outcome = ("C" if lane == "country" else "I"), "found"
                detail = rec["statement"][:34]
            else:
                state["abstained"][key] = {"lane": lane, "chapter": chapter["n"],
                                           "why": why}
                mark, outcome = "A", "abstain"
                detail = (why or "")[:34]
            save()
            print(f"{mark} [{n:2d}/{total}] {key:<18} {outcome:<7} {chapter['title'][:22]:<24} "
                  f"{detail:<36} $ {ledger.spent():5.2f} {int(time.time() - t0):3d}s")
            sys.stdout.flush()

    with ThreadPoolExecutor(max_workers=TOPIC_WORKERS) as ex:
        list(ex.map(run_one, units))

    if stopped:
        print(f"\n!! {stopped}")
        print("   The scan stopped where the budget ran out. Topics never reached are "
              "absent from the output, NOT recorded as having found nothing.")
        save()
        return 0

    payload = {
        "country": a.country,
        "iso3": a.iso,
        "assessment_year": ASSESSMENT_YEAR,
        "country_findings": list(state["country"].values()),
        # Kept under its own key, and every record inside it carries applies_to=dar_only.
        # Two independent statements of the same rule, because this is the one that would
        # put another country's material into a document about this one.
        "international_pointers": list(state["international"].values()),
        "abstained": list(state["abstained"].values()),
        "note": ("International pointers feed the DAR only (E2). They are never country "
                 "evidence, never an endorsement, and never a comparison of countries. "
                 "Nothing in this file scores anything."),
    }
    json.dump(payload, open(out_path, "w"), indent=1, default=str)
    ledger.save(spend_path)

    nc, ni, na = (len(state["country"]), len(state["international"]),
                  len(state["abstained"]))
    print()
    print(f"wrote {a.out}_scans.json — {nc} country findings, {ni} international "
          f"pointers, {na} abstentions")
    s = ledger.summary()
    print(f"spend ${s['total']:.2f} of ${a.ceiling * V.Ledger.ALLOCATION[PASS]:.0f} "
          f"allocated (${a.ceiling:.0f} country ceiling), {s['calls']} vendor calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
