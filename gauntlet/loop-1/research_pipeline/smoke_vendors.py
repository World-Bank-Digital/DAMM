#!/usr/bin/env python3
"""Prove every vendor path works before anything is built on top of it.

Six keys, five call shapes, and quote verification in five scripts. Costs a few cents.
Prints key
NAMES and outcomes only — never a key value (standing decision 3).
"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vendors as V

V.load_env()
led = V.Ledger(ceiling=5.0, label="smoke")
ok, fail = [], []


def check(name, fn):
    try:
        detail = fn()
        ok.append(name)
        print(f"PASS  {name:28} {detail}")
    except Exception as e:
        fail.append(name)
        print(f"FAIL  {name:28} {type(e).__name__}: {str(e)[:220]}")


print("keys present:", ", ".join(k for k in
      ("EXA_API_KEY", "JINA_API_KEY", "PERPLEXITY_API_KEY",
       "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY") if os.environ.get(k)))
print()

state = {}


def t_exa():
    r = V.exa_search("Egypt rural mobile broadband coverage ITU", led, "audition",
                     num_results=5, text_chars=1200)
    state["exa"] = r
    return f"{len(r)} results; top tier {r[0]['tier'] if r else '—'}"


def t_jina():
    txt = V.jina_fetch("https://www.itu.int/en/ITU-D/Statistics/Pages/stat/default.aspx",
                       led, "audition", max_chars=4000)
    state["page"] = txt
    return f"{len(txt)} chars of page text"


def t_quote():
    txt = state.get("page") or ""
    if len(txt) < 200:
        raise RuntimeError("no page text from the Jina step to verify against")
    probe = " ".join(txt.split()[8:16])
    good = V.quote_verify(probe, txt)
    bad = V.quote_verify("the ministry reported 91.4% coverage in 2029", txt)
    if not good or bad:
        raise RuntimeError(f"verifier wrong: real quote={good}, invented quote={bad}")
    return "real quote accepted, invented quote rejected"


def t_quote_scripts():
    """Quote verification must be script-blind.

    It was not. The alphanumeric fold kept only [a-z0-9], so an Arabic, Chinese,
    Cyrillic, Greek or Hebrew quote reduced to the empty string — and the empty string
    is a substring of every page, so a wholly invented quote in any of those scripts
    verified as genuine. Egypt publishes in Arabic. This is the check the fabrication
    rate rests on, so it is tested in every script the assessment might meet.
    """
    cases = [
        ("Arabic", "The platform serves citizens. مرحبا بكم في مصر الرقمية اليوم.",
         "هذه جملة عربية مختلقة تماما لا توجد", "مرحبا بكم في مصر الرقمية"),
        ("Chinese", "Report text 中国农业农村部发布了最新的统计数据资料。",
         "这是完全捏造的一句中文引文内容", "中国农业农村部发布了最新的统计"),
        ("Cyrillic", "Source: Министерство сельского хозяйства опубликовало данные.",
         "Это полностью выдуманная цитата которой нет", "Министерство сельского хозяйства"),
        ("Greek", "Text: Το Υπουργείο Γεωργίας δημοσίευσε τα στοιχεία.",
         "Αυτή είναι μια εντελώς κατασκευασμένη φράση", "Το Υπουργείο Γεωργίας δημοσίευσε"),
        ("Latin", "Rural electricity access in Egypt reached 100.0 percent in 2024.",
         "Rural electricity access in Egypt reached 62.4 percent", "reached 100.0 percent"),
    ]
    wrong = [name for name, page, fake, real in cases
             if V.quote_verify(fake, page) or not V.quote_verify(real, page)]
    if wrong:
        raise RuntimeError(f"quote verification wrong in: {', '.join(wrong)}")
    if V.quote_verify("··· —— ,,,,,,", "any page text here"):
        raise RuntimeError("a quote made only of punctuation was accepted")
    return f"{len(cases)} scripts: invented rejected, genuine accepted"


def t_tier():
    cases = {"https://data.worldbank.org/indicator/X": "T1",
             "https://openknowledge.worldbank.org/handle/1": "T2",
             "https://www.ncc.gov.ng/docs/report.pdf": "T3",
             "https://www.gsma.com/r/report.pdf": "T4",
             "https://agritechblog.example.com/post": "T5"}
    wrong = {u: (V.tier_for_url(u), want) for u, want in cases.items()
             if V.tier_for_url(u) != want}
    if wrong:
        raise RuntimeError(f"tier lookup wrong: {wrong}")
    return "5/5 domain→tier cases correct"


def t_resolvable():
    good, g = V.url_resolves("https://api.worldbank.org/v2/country/EGY/indicator/"
                             "NV.AGR.EMPL.KD?format=json&mrnev=1")
    root, r = V.url_resolves("https://www.worldbank.org/")
    if not good or root:
        raise RuntimeError(f"deep link={good}({g}) domain root={root}({r})")
    return f"deep link {g} accepted; domain root rejected"


def t_perplexity():
    r = V.perplexity_citations("What share of Egypt's rural population has 3G mobile "
                               "coverage, according to ITU?", led, "audition")
    state["ppx"] = r
    return f"{len(r['citations'])} citations returned (prose held separate)"


SCHEMA = {"type": "object",
          "properties": {"answer": {"type": "string"},
                         "confident": {"type": "boolean"}},
          "required": ["answer", "confident"],
          "additionalProperties": False}


def llm_test(vendor):
    def run():
        m = V.LLM(vendor, led)
        out = m.json_call("You answer in JSON only.",
                          "In one short phrase, what does the acronym FAO stand for?",
                          SCHEMA, "audition", max_tokens=2000, detail="smoke")
        if "answer" not in out:
            raise RuntimeError(f"schema not honoured: {out}")
        return f"model={m.model} · {str(out['answer'])[:60]}"
    return run


check("exa.search", t_exa)
check("jina.fetch", t_jina)
check("quote_verify", t_quote)
check("quote_verify (scripts)", t_quote_scripts)
check("tier_for_url", t_tier)
check("url_resolves", t_resolvable)
check("perplexity.citations", t_perplexity)
for v in ("anthropic", "openai", "gemini"):
    check(f"llm.{v}", llm_test(v))

print()
print("spend:", json.dumps(led.summary(), indent=1))
print(f"\n{len(ok)} passed, {len(fail)} failed" + (f" — {fail}" if fail else ""))
sys.exit(1 if fail else 0)
