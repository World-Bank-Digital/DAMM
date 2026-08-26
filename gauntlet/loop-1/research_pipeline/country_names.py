#!/usr/bin/env python3
"""Resolving a country name against a publisher's own list.

Every publisher keeps its own spelling. The World Bank says "Egypt, Arab Rep." and
"Vietnam"; the UN Statistics Division and FAOSTAT both say "Egypt" and "Viet Nam"; the
model is invoked with whatever the caller typed. Two lookups in this pipeline depend on
getting from one to the other — the national statistical office, and the FAOSTAT area —
and both began life as a hand-written map of the two countries that had been assessed.
A third country resolved to nothing, silently, and the lane it needed simply produced no
row.

So the resolution lives here once, and every lookup that needs it asks the publisher's
own list rather than a map somebody has to remember to extend.

Nothing here guesses. A name resolves by an exact match, by a recorded alias, or by a
narrow set of shape rules; where it does not resolve, the caller is told so and records
that as the reason, which is a finding rather than an absence.
"""
import re
import unicodedata

# Names that differ by more than punctuation, grouped by the country they denote.
#
# Groups rather than a map to one canonical spelling, because there is no canonical
# spelling to map to. The publishers this pipeline reads do not agree: the UN Statistics
# Division's list of statistical offices says "Turkey" and "Korea, Republic of", while
# FAOSTAT says "Türkiye" and "Republic of Korea", and the World Bank says neither. A map
# would resolve against whichever publisher it was written for and fail on the other,
# which is what a two-country map did before this.
ALIAS_GROUPS = [
    {"Egypt", "Egypt, Arab Rep."},
    {"Viet Nam", "Vietnam"},
    {"Iran (Islamic Republic of)", "Iran, Islamic Rep.", "Iran"},
    {"Republic of Korea", "Korea, Rep.", "Korea, Republic of", "South Korea"},
    {"Democratic People's Republic of Korea", "Korea, Dem. People's Rep.", "North Korea"},
    {"United Republic of Tanzania", "Tanzania"},
    {"Bolivia (Plurinational State of)", "Bolivia"},
    {"Venezuela (Bolivarian Republic of)", "Venezuela, RB", "Venezuela"},
    {"Lao People's Democratic Republic", "Lao PDR", "Laos"},
    {"Türkiye", "Turkiye", "Turkey"},
    {"Côte d'Ivoire", "Cote d'Ivoire", "Ivory Coast"},
    {"Democratic Republic of the Congo", "Congo, Dem. Rep.", "DR Congo"},
    {"Congo", "Congo, Rep."},
    {"Kyrgyzstan", "Kyrgyz Republic"},
    {"Slovakia", "Slovak Republic"},
    {"Republic of Moldova", "Moldova"},
    {"Russian Federation", "Russia"},
    {"Gambia", "Gambia, The"},
    {"Bahamas", "Bahamas, The"},
    {"Yemen", "Yemen, Rep."},
    {"North Macedonia", "Macedonia"},
    {"Cabo Verde", "Cape Verde"},
    {"Eswatini", "Swaziland"},
    {"Myanmar", "Burma"},
    {"Timor-Leste", "East Timor"},
    {"Czechia", "Czech Republic"},
    {"United States of America", "United States", "USA"},
    {"United Kingdom of Great Britain and Northern Ireland", "United Kingdom", "UK"},
    {"Micronesia (Federated States of)", "Micronesia, Fed. Sts."},
    {"China, Hong Kong SAR", "Hong Kong SAR, China", "Hong Kong"},
    {"China, Macao SAR", "Macao SAR, China", "Macao"},
    {"Brunei Darussalam", "Brunei"},
    {"Syrian Arab Republic", "Syria"},
    {"United Arab Emirates", "UAE"},
]


def _fold(s):
    """Casefold, strip accents and punctuation, collapse spaces."""
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9 ]+", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


_BY_FOLD = {}
for _g in ALIAS_GROUPS:
    _folded = {re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ",
               unicodedata.normalize("NFKD", x).encode("ascii", "ignore")
               .decode().lower())).strip() for x in _g}
    for _f in _folded:
        _BY_FOLD.setdefault(_f, set()).update(_folded)


def _group_for(folded_name):
    """Every folded spelling of the country this name denotes, including itself."""
    return _BY_FOLD.get(folded_name, {folded_name})


def _head(s):
    """The part before a comma or bracket: "Egypt, Arab Rep." -> "Egypt"."""
    return re.split(r"[,(]", str(s or ""))[0].strip()


def resolve(name, candidates):
    """The candidate that names this country, or None.

    Tried in order of certainty: the name as given, a recorded alias, the name without
    its qualifier, and finally a candidate whose own qualifier-free form matches. The
    last rule is what gets "Tanzania" to "United Republic of Tanzania" without letting
    "Congo" reach "Democratic Republic of the Congo", because that one is an alias.
    """
    if not name or not candidates:
        return None
    cands = list(candidates)
    by_fold = {_fold(c): c for c in cands}

    n = _fold(name)
    if n in by_fold:
        return by_fold[n]

    # Every other name for the same country, tried against this publisher's list.
    for form in _group_for(n) - {n}:
        if form in by_fold:
            return by_fold[form]

    # Beyond this point the qualifier is being dropped, and a qualifier is sometimes the
    # whole distinction: "Congo, Dem. Rep." and "Congo" are different countries with
    # different statistical offices. So a shortened match is refused whenever the name
    # given belongs to a known group and the candidate belongs to a different one.
    own = _group_for(n)

    def compatible(candidate):
        g = _group_for(_fold(candidate))
        return g == own or not (g & _BY_FOLD.keys()) or bool(g & own) or (
            _fold(candidate) not in _BY_FOLD and n not in _BY_FOLD)

    h = _fold(_head(name))
    if h and h in by_fold and compatible(by_fold[h]):
        return by_fold[h]
    if h:
        for form in _group_for(h) - {h}:
            if form in by_fold and compatible(by_fold[form]):
                return by_fold[form]

    # A candidate carrying a qualifier the caller left off: "Bolivia" against
    # "Bolivia (Plurinational State of)". Only when exactly one candidate matches, so an
    # ambiguous head such as "Congo" or "Korea" resolves to nothing rather than to a
    # coin toss.
    if h:
        hits = [c for c in cands if _fold(_head(c)) == h and compatible(c)]
        if len(hits) == 1:
            return hits[0]
    return None
