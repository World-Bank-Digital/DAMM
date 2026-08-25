#!/usr/bin/env python3
"""The national statistical office of every country, and why it is T1.

The source-tier protocol puts official statistics at T1. The domain table that implements
it named exactly two statistical offices — Egypt's and Nigeria's — because those are the
two countries that had been assessed. Every other country's official statistics fell
through to the generic government pattern and were tiered T3, below a World Bank
re-publication of the same number. Kenya's National Bureau of Statistics publishes at
knbs.or.ke, which is not a .gov domain at all, so it tiered T5 — the tier reserved for
newswires and blogs.

The effect was a standing bias toward international re-publishers and against the body
that actually produces a country's statistics, in every country except the two hard-coded
ones. That is the opposite of what the protocol says.

The registry is the UN Statistics Division's own list of national statistical offices,
parsed once and committed as data. It is refreshed deliberately rather than fetched per
run: a research pass must not depend on a web page being up, and a tier that changed
silently between two runs of the same country would be worse than a tier that is wrong.

    python3 nso_registry.py --refresh    # re-parse the UNSD list and rewrite the JSON
"""
import json, os, re, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "nso_registry.json")
SOURCE = "https://unstats.un.org/home/nso_sites/"

_ENTRY = re.compile(
    r'<li class="leaf"><strong>(.*?)</strong>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S)


def _text(s):
    import html as _h
    return _h.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def _host(url):
    h = (urllib.parse.urlparse(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def refresh():
    """Re-parse the UNSD list. Returns {country: [host, ...]}."""
    with urllib.request.urlopen(SOURCE, timeout=60) as r:
        page = r.read().decode("utf-8", "ignore")
    out = {}
    for m in _ENTRY.finditer(page):
        country = _text(m.group(1))
        url = m.group(2).strip()
        if not url.startswith("http"):
            continue
        host = _host(url)
        if not host:
            continue
        out.setdefault(country, [])
        if host not in out[country]:
            out[country].append(host)
    if len(out) < 100:
        raise SystemExit(f"the UNSD list parsed to only {len(out)} countries — refusing to "
                         "overwrite the registry with a partial read")
    return out


def load():
    try:
        with open(DATA) as f:
            return json.load(f).get("offices", {})
    except Exception:
        return {}


_OFFICES = load()

# Country names the model uses that the UNSD list words differently.
ALIASES = {
    "Egypt, Arab Rep.": "Egypt",
    "Egypt Arab Rep": "Egypt",
    "Vietnam": "Viet Nam",
    "Iran, Islamic Rep.": "Iran (Islamic Republic of)",
    "Korea, Rep.": "Republic of Korea",
    "Tanzania": "United Republic of Tanzania",
    "Bolivia": "Bolivia (Plurinational State of)",
    "Venezuela, RB": "Venezuela (Bolivarian Republic of)",
    "Lao PDR": "Lao People's Democratic Republic",
    "Syrian Arab Republic": "Syrian Arab Republic",
    "Turkiye": "Türkiye",
    "Turkey": "Türkiye",
    "Cote d'Ivoire": "Côte d'Ivoire",
    "Congo, Dem. Rep.": "Democratic Republic of the Congo",
    "Kyrgyz Republic": "Kyrgyzstan",
    "Slovak Republic": "Slovakia",
    "Moldova": "Republic of Moldova",
}


def domains_for(country):
    """The statistical office host(s) for one country. Empty when it is not listed."""
    if not country:
        return []
    name = ALIASES.get(country.strip(), country.strip())
    if name in _OFFICES:
        return list(_OFFICES[name])
    low = name.lower()
    for k, v in _OFFICES.items():
        if k.lower() == low:
            return list(v)
    # A trailing qualifier the model carries and the UNSD list does not, such as
    # "Egypt, Arab Rep." reaching here without an alias.
    head = re.split(r"[,(]", name)[0].strip().lower()
    for k, v in _OFFICES.items():
        if k.lower() == head:
            return list(v)
    return []


def all_domains():
    return {h for hosts in _OFFICES.values() for h in hosts}


def is_office(url, country=None):
    """Whether a URL is published by a statistical office.

    With a country, only that country's office counts — another country's statistics
    bureau is a perfectly good publisher and still says nothing about this country, and
    the isolation gate should be the thing that catches it, not the tier.
    """
    host = _host(url)
    if not host:
        return False
    hosts = domains_for(country) if country else all_domains()
    return any(host == h or host.endswith("." + h) for h in hosts)


if __name__ == "__main__":
    if "--refresh" in sys.argv:
        offices = refresh()
        json.dump({"_source": SOURCE,
                   "_note": ("The UN Statistics Division's list of national statistical "
                             "offices. Refresh with: python3 nso_registry.py --refresh"),
                   "offices": offices}, open(DATA, "w"), indent=1, ensure_ascii=False)
        print(f"wrote {os.path.basename(DATA)} — {len(offices)} countries")
    else:
        print(f"{len(_OFFICES)} countries in the registry")
        for c in ("Egypt", "Nigeria", "Kenya", "India", "Bhutan"):
            print(f"  {c:<10} {domains_for(c)}")
