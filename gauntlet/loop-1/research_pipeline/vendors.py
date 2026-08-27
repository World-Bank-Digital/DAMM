#!/usr/bin/env python3
"""Vendor access layer for the automated research pipeline.

One place where every outside call is made, metered and priced, so that:

  * keys are read from the repo-root `.env` and never printed (standing decision 3);
  * every call is recorded with its exact usage counts before dollars are derived,
    so a wrong price is a one-line correction rather than a re-run (`prices.json`);
  * the spend counter is live and the budget ceiling is enforced *before* a call is
    made, not discovered afterwards (budget-control decisions) — and exhaustion raises a
    named exception, because a budget-induced gap that looks like a real one is how
    Nigeria's 21 phantom gaps happened.

Retrieval is Exa (discovery) + Jina (fetch), per standing decision 3: the tier
protocol can be enforced in Exa's API parameters, and Jina returns the page text a
quote is verified against. Perplexity is a discovery peer only (decision C6) — this
module deliberately returns its *citations* separately from its prose so a caller
cannot accidentally record the prose as a source.

Reasoning vendors (Anthropic, OpenAI, Gemini) are reached through one uniform
`json_call`, so the audition compares judgment over identical retrieved evidence
rather than comparing each vendor's built-in search.
"""

import hashlib, json, math, os, re, tempfile, threading, time, unicodedata
import urllib.parse, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PRICES = json.load(open(os.path.join(HERE, "prices.json")))


def _durable_temporary(path, content, suffix):
    """Write and fsync bytes beside their destination, returning the temporary path."""
    path = os.path.abspath(path)
    directory = os.path.dirname(path)
    fd, temporary = tempfile.mkstemp(
        prefix=f".{os.path.basename(path)}.", suffix=suffix, dir=directory
    )
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise
    return path, directory, temporary


def _fsync_directory(directory):
    try:
        directory_fd = os.open(directory, getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError:
        pass


def atomic_write_bytes(path, content):
    """Replace one file only after its complete content is durable."""
    path, directory, temporary = _durable_temporary(path, content, ".tmp")
    try:
        os.replace(temporary, path)
        _fsync_directory(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def publish_bytes_once(path, content, label="file"):
    """Atomically create immutable bytes, accepting only an identical existing file."""
    path, directory, temporary = _durable_temporary(path, content, ".publish")
    try:
        try:
            os.link(temporary, path)
        except FileExistsError:
            if os.path.islink(path) or not os.path.isfile(path):
                raise ValueError(f"existing {label} is not a regular file")
            with open(path, "rb") as existing:
                if existing.read() != content:
                    raise ValueError(f"refusing to replace divergent existing {label}")
            return False
        _fsync_directory(directory)
        return True
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_write_text(path, content):
    atomic_write_bytes(path, content.encode("utf-8"))


def atomic_write_json(path, value):
    # Python otherwise emits NaN and Infinity, although neither is valid JSON.
    atomic_write_text(
        path, json.dumps(value, indent=1, default=str, allow_nan=False) + "\n")


def _invalid_json_constant(token):
    raise ValueError(f"non-finite JSON number {token!r} is not allowed")


def _nonfinite_paths(value, path="$"):
    if isinstance(value, float) and not math.isfinite(value):
        return [path]
    if isinstance(value, dict):
        paths = []
        for key, item in value.items():
            paths.extend(_nonfinite_paths(item, f"{path}.{key}"))
        return paths
    if isinstance(value, (list, tuple)):
        paths = []
        for index, item in enumerate(value):
            paths.extend(_nonfinite_paths(item, f"{path}[{index}]"))
        return paths
    return []


def require_finite_json(value):
    """Reject non-finite floats, including finite-looking literals that overflowed."""
    paths = _nonfinite_paths(value)
    if paths:
        raise ValueError("non-finite JSON number at " + ", ".join(paths[:8]))
    return value


def strict_json_load(path):
    """Load standards-compliant JSON, rejecting Python's NaN/Infinity extension."""
    with open(path, encoding="utf-8") as stream:
        return require_finite_json(
            json.load(stream, parse_constant=_invalid_json_constant))


def strict_json_loads(value):
    """Parse standards-compliant JSON, rejecting Python's NaN/Infinity extension."""
    return require_finite_json(
        json.loads(value, parse_constant=_invalid_json_constant))


def compatible_alias_presence(canonical_path, legacy_path, label):
    """Return which alias files exist, rejecting divergent duplicate identities."""
    canonical_present = regular_file_presence(canonical_path, f"{label} alias")
    legacy_present = regular_file_presence(legacy_path, f"{label} alias")
    if canonical_present and legacy_present:
        with open(canonical_path, "rb") as canonical_handle:
            canonical_bytes = canonical_handle.read()
        with open(legacy_path, "rb") as legacy_handle:
            legacy_bytes = legacy_handle.read()
        if canonical_bytes != legacy_bytes:
            raise ValueError(f"conflicting canonical and legacy {label}")
    return canonical_present, legacy_present


def regular_file_presence(path, label):
    """Return file presence while rejecting symlinks and non-regular aliases."""
    if not os.path.lexists(path):
        return False
    if os.path.islink(path) or not os.path.isfile(path):
        raise ValueError(f"{label} is not a regular file: {path}")
    return True


def load_compatible_json_alias(canonical_path, legacy_path, label):
    """Load the canonical JSON alias, or an unambiguous historical fallback."""
    canonical_present, legacy_present = compatible_alias_presence(
        canonical_path, legacy_path, label
    )
    if canonical_present:
        return strict_json_load(canonical_path)
    if legacy_present:
        return strict_json_load(legacy_path)
    return None


# ---------------------------------------------------------------- keys

def load_env(path=None):
    """Read the repo-root .env into os.environ. Values never leave this process."""
    path = path or os.path.join(REPO, ".env")
    if not os.path.exists(path):
        raise SystemExit(f"no .env at {path} — vendor keys are required")
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def key(name):
    v = os.environ.get(name)
    if not v:
        raise SystemExit(f"{name} is not set in .env")
    return v


# ---------------------------------------------------------------- spend

class BudgetExhausted(Exception):
    """Raised instead of silently returning nothing. The run must report where it stopped."""

    def __init__(self, pass_name, spent, cap):
        super().__init__(f"budget exhausted in pass '{pass_name}': ${spent:.2f} of ${cap:.2f}")
        self.pass_name, self.spent, self.cap = pass_name, spent, cap


class Ledger:
    """Live spend counter with a fixed per-pass allocation.

    Generation is reserved by allocating it up front: a pathological research pass
    can exhaust its own share and stop, but it cannot consume the document budget
    and leave nothing to review.
    """

    # Canonical-workflow apportionment, as fractions of the country ceiling. The two
    # new analytical products have their own protected shares: an AI assessment must
    # not consume the investment appraisal's budget (or vice versa), and generation
    # remains reserved so a difficult retrieval pass cannot leave no Draft DAR.
    # Every pass is named here, including the one that costs nothing: a pass missing from
    # the allocation has no share rather than a zero share, and the difference shows up as
    # a surface that cannot say what a pass is allowed to spend.
    ALLOCATION = {"research": 0.35, "automated_challenge": 0.10,
                  "country_research": 0.075,
                  "international_lessons": 0.075,
                  "ai": 0.10, "foresight": 0.10, "investment": 0.05,
                  "generation": 0.15,
                  # Deterministic rendering of an assessment already paid for.
                  "diagnostic": 0.00,
                  # Deterministic format conversion and packaging.
                  "export": 0.00,
                  "audition": 1.00}
    # Direct historical invocations of ``scans.py --lane all`` predate the canonical
    # coordinator. They retain the old aggregate cap without becoming an extra share of
    # the canonical ceiling. Canonical Stage 2/4 calls always use the protected names above.
    LEGACY_ALLOCATION = {"scans": 0.15, "g2": 0.10}

    def __init__(self, ceiling=500.0, label="run"):
        self.ceiling, self.label = ceiling, label
        self.checkpoint_identity = os.environ.get(
            "DAMM_CHECKPOINT_BINDING_SHA256", ""
        ).strip()
        if self.checkpoint_identity and not re.fullmatch(
                r"[0-9a-f]{64}", self.checkpoint_identity):
            raise ValueError("DAMM_CHECKPOINT_BINDING_SHA256 is not a SHA-256 digest")
        self.calls = []
        self._t0 = time.time()
        # Fetches and vendor calls run concurrently, so the counter is shared state.
        # Without the lock two callers can both pass `check` on the last dollar.
        #
        # RLock, not Lock: `save` holds the lock while calling `summary`, which calls
        # `spent`, which takes the lock again. With a plain Lock that deadlocks, and it
        # deadlocks at the first checkpoint of every run rather than rarely.
        self._lock = threading.RLock()
        self._carried_s = 0.0
        self._checkpoint_path = None

    # -- pricing ---------------------------------------------------
    @staticmethod
    def _price(vendor, model):
        table = PRICES.get(vendor, {})
        return table.get(model) or table.get("_default") or {}

    def record(self, vendor, pass_name, model="", in_tok=0, out_tok=0,
               searches=0, content_pages=0, fetches=0, requests=0, detail=""):
        p = self._price(vendor, model)
        cost = (in_tok / 1e6) * p.get("in_per_mtok", 0.0) \
             + (out_tok / 1e6) * p.get("out_per_mtok", 0.0) \
             + searches * PRICES.get("exa", {}).get("per_search", 0.0) \
             + content_pages * PRICES.get("exa", {}).get("per_content_page", 0.0) \
             + fetches * PRICES.get("jina", {}).get("per_fetch", 0.0) \
             + requests * p.get("per_request", 0.0)
        with self._lock:
            self.calls.append(dict(vendor=vendor, pass_name=pass_name, model=model,
                                   in_tok=in_tok, out_tok=out_tok, searches=searches,
                                   content_pages=content_pages, fetches=fetches,
                                   requests=requests, cost=round(cost, 6),
                                   detail=detail[:200],
                                   at=round(time.time() - self._t0, 1)))
            if self._checkpoint_path:
                # Persist inside the same lock that publishes the call. A normal exception,
                # coordinator retry, or process crash after this point cannot lose a paid
                # attempt and later spend the same protected allocation again.
                atomic_write_json(self._checkpoint_path, self.snapshot())
        return cost

    # -- reading ---------------------------------------------------
    def spent(self, pass_name=None):
        aliases = (
            {"automated_challenge", "g2"}
            if pass_name in {"automated_challenge", "g2"}
            else {pass_name}
        )
        with self._lock:
            return round(sum(c["cost"] for c in self.calls
                             if pass_name is None or c["pass_name"] in aliases), 6)

    def cap(self, pass_name):
        share = self.ALLOCATION.get(
            pass_name, self.LEGACY_ALLOCATION.get(pass_name, 1.0)
        )
        return self.ceiling * share

    def remaining(self, pass_name):
        return self.cap(pass_name) - self.spent(pass_name)

    def check(self, pass_name, headroom=0.0):
        """Called before an outside call. Raises rather than degrading silently."""
        if self.remaining(pass_name) <= headroom:
            raise BudgetExhausted(pass_name, self.spent(pass_name), self.cap(pass_name))

    def elapsed(self):
        return round(time.time() - self._t0 + self._carried_s, 1)

    def summary(self):
        by_pass, by_vendor = {}, {}
        for c in self.calls:
            by_pass[c["pass_name"]] = round(by_pass.get(c["pass_name"], 0) + c["cost"], 4)
            by_vendor[c["vendor"]] = round(by_vendor.get(c["vendor"], 0) + c["cost"], 4)
        value = dict(label=self.label, ceiling=self.ceiling, total=self.spent(),
                     calls=len(self.calls), elapsed_s=self.elapsed(),
                     by_pass=by_pass, by_vendor=by_vendor)
        if self.checkpoint_identity:
            value["checkpoint_identity_sha256"] = self.checkpoint_identity
        return value

    def snapshot(self):
        with self._lock:
            return dict(summary=self.summary(), calls=list(self.calls))

    def _bind_checkpoint_path(self, path):
        resolved = os.path.abspath(path)
        if self._checkpoint_path and self._checkpoint_path != resolved:
            raise ValueError("ledger is already bound to another spend checkpoint")
        self._checkpoint_path = resolved
        return resolved

    def attach(self, path):
        """Journal every subsequent vendor record to one durable spend checkpoint."""
        with self._lock:
            resolved = self._bind_checkpoint_path(path)
            if not os.path.exists(resolved):
                atomic_write_json(resolved, self.snapshot())
        return resolved

    def save(self, path):
        with self._lock:
            resolved = self._bind_checkpoint_path(path)
            atomic_write_json(resolved, self.snapshot())

    def restore(self, saved):
        """Restore one prior snapshot into a fresh ledger and return its call count."""
        prior, elapsed = self._validated_snapshot(saved)
        with self._lock:
            self.calls = prior + self.calls
            self._carried_s = elapsed
        return len(prior)

    def _validated_snapshot(self, saved):
        if not isinstance(saved, dict):
            raise ValueError("spend ledger snapshot is not an object")
        summary = saved.get("summary") or {}
        if not isinstance(summary, dict):
            raise ValueError("spend ledger summary is not an object")
        saved_identity = str(
            summary.get("checkpoint_identity_sha256") or ""
        )
        if self.checkpoint_identity:
            if saved_identity != self.checkpoint_identity:
                raise ValueError(
                    "spend ledger is not bound to this workflow checkpoint"
                )
        elif saved_identity:
            raise ValueError(
                "cannot load a workflow-bound spend ledger without its checkpoint identity"
            )
        prior = saved.get("calls") or []
        if not isinstance(prior, list) or any(not isinstance(call, dict) for call in prior):
            raise ValueError("spend ledger calls is not an array of objects")
        elapsed = summary.get("elapsed_s", 0) or 0
        if (isinstance(elapsed, bool) or not isinstance(elapsed, (int, float))
                or not math.isfinite(float(elapsed)) or elapsed < 0):
            raise ValueError("spend ledger elapsed_s is invalid")
        return list(prior), float(elapsed)

    def reconcile(self, saved):
        """Keep the longer of two prefix-compatible crash checkpoints.

        Generation embeds its ledger in the chapter state and also journals it to a
        standalone spend file. A crash may leave either atomic file one write ahead of
        the other. They are compatible only when one ordered call list is a prefix of
        the other; anything else is stale or tampered state and must fail closed.
        """
        prior, elapsed = self._validated_snapshot(saved)
        with self._lock:
            current = list(self.calls)
            if current == prior[:len(current)]:
                self.calls = prior
            elif prior != current[:len(prior)]:
                raise ValueError("spend ledger checkpoints have divergent call histories")
            self._carried_s = max(self._carried_s, elapsed)
            if self._checkpoint_path:
                atomic_write_json(self._checkpoint_path, self.snapshot())
            return len(self.calls)

    def load(self, path):
        """Carry a previous ledger forward, for a resumed run.

        A resume used to start the counter at zero and then overwrite the saved ledger,
        so a run finished in two sittings reported only the second one: Egypt's first
        pass read $0.26 when it had cost $15.75. Worse than the misreporting, the
        ceiling stopped binding — the run budget caps a country at $500, and a counter that
        resets on resume could be walked past that cap indefinitely by stopping and
        starting.
        """
        with self._lock:
            resolved = self._bind_checkpoint_path(path)
            if not os.path.exists(resolved):
                return 0
            saved = strict_json_load(resolved)
        return self.restore(saved)


# ---------------------------------------------------------------- http

class VendorError(Exception):
    pass


class ReplayExhausted(VendorError):
    """The offline replay has no recorded response for a requested vendor call."""


def stable_json_sha256(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def json_call_request_sha256(system, user, schema, pass_name, max_tokens, detail):
    """Identity of the exact JSON-model request an offline response answers."""
    return stable_json_sha256({
        "system": system, "user": user, "schema": schema,
        "pass_name": pass_name, "max_tokens": max_tokens, "detail": detail,
    })


def _http(url, data=None, headers=None, method=None, timeout=90, retries=3):
    body = json.dumps(data, allow_nan=False).encode() if data is not None else None
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    h.update(headers or {})
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(url, data=body, headers=h, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read().decode("utf-8", "replace")
            try:
                return strict_json_loads(raw)
            except json.JSONDecodeError:
                return raw
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:400]
            last = VendorError(f"{e.code} {url.split('?')[0]} :: {detail}")
            if e.code in (400, 401, 403, 404, 422):   # not retryable
                raise last
            if e.code == 429:
                # A rate limit is a wait, not a failure, and giving up on one turns a
                # vendor's throttle into a hole in the evidence. Honour Retry-After
                # when it is offered, and otherwise back off far enough to matter.
                try:
                    wait = float(e.headers.get("Retry-After") or 0)
                except (TypeError, ValueError):
                    wait = 0
                time.sleep(max(wait, 8 * (attempt + 1)))
                continue
        except Exception as e:                        # timeouts, connection resets
            last = VendorError(f"{type(e).__name__} {url.split('?')[0]} :: {e}")
        time.sleep(2 * (attempt + 1))
    raise last


# ---------------------------------------------------------------- tiers

# The Source-Tier Protocol's starter domain lookup, machine-readable. Anything not
# matched is T5 until reviewed — the protocol's own default, and the conservative
# one: a T5 citation can never yield Documented, so an unrecognised domain degrades
# to judgement rather than quietly passing as evidence.
TIER_DOMAINS = [
    ("T1", ["fao.org", "faostat", "aquastat", "worldbank.org", "data.worldbank.org",
            "api.worldbank.org", "itu.int", "ifad.org", "wfp.org", "findex",
            "ilostat.ilo.org", "unicef.org/statistics",
            # UN official databases are T1 by host, not by the un.org suffix: the same
            # suffix also carries the UN's newswire. The audition made this concrete —
            # every entrant proposed T1 for the E-Government Knowledgebase and was
            # marked non-compliant by a lookup that had never heard of the host.
            "unstats.un.org", "data.un.org", "publicadministration.un.org",
            "population.un.org", "comtrade.un.org", "sdgs.un.org", "unctadstat.unctad.org",
            "capmas.gov.eg", "nigerianstat.gov.ng", "dhsprogram.com", "ipcinfo.org"]),
    ("T2", ["openknowledge.worldbank.org", "openknowledge.fao.org", "cgiar.org", "ifpri.org",
            "doi.org", "nature.com", "sciencedirect.com", "springer.com", "link.springer.com",
            "frontiersin.org", "tandfonline.com", "wiley.com", "sagepub.com", "plos.org",
            "mdpi.com", "documents.worldbank.org", "elibrary.worldbank.org", "oecd.org"]),
    ("T3", ["faolex.fao.org", "ncc.gov.ng", "mcit.gov.eg", "ntra.gov.eg",
            "cbn.gov.ng", "cbe.org.eg", "fmard.gov.ng", "fmino.gov.ng"]),
    ("T4", ["gsma.com", "giz.de", "usaid.gov", "agra.org", "reliefweb.int",
            "ifc.org", "cgap.org", "technoserve.org", "mercycorps.org"]),
    ("T5", ["news.un.org", "blogs.worldbank.org", "un.org/press"]),
]
_GOV_RE = re.compile(r"\.gov(\.[a-z]{2})?$|\.go\.[a-z]{2}$|\.gouv\.[a-z]{2}$")


def tier_for_url(url, country=None):
    """Propose a tier from the publisher's domain. Reported, never weighted (C1).

    The most specific domain wins, not the highest tier: `openknowledge.worldbank.org`
    is the World Bank's *repository* of analytical reports (T2), and matching it on
    the shorter `worldbank.org` needle would file a flagship report as an official
    statistic. Longest matching needle first, therefore, in every case.

    A national statistical office is T1 wherever the country is known, not only for the
    two whose domains happened to be listed here. The protocol has always said official
    statistics are T1; the table implemented that for Egypt and Nigeria and left every
    other country's statistics bureau to the generic government pattern at T3, or below
    it — Kenya publishes at knbs.or.ke, which is not a .gov domain at all and tiered T5.
    The effect was a standing preference for international re-publishers over the body
    that produces the numbers.
    """
    if not url:
        return "T5"
    if country is not None:
        try:
            import nso_registry
            if nso_registry.is_office(url, country):
                return "T1"
        except Exception:
            pass
    host = (urllib.parse.urlparse(url).hostname or "").lower().lstrip(".")
    low = url.lower()
    best = None
    for tier, needles in TIER_DOMAINS:
        for n in needles:
            if host.endswith(n) or n in low:
                if best is None or len(n) > best[1]:
                    best = (tier, len(n))
    if best:
        return best[0]
    if _GOV_RE.search(host) or host.endswith(".int"):
        return "T3"
    if host.endswith(".edu") or host.endswith(".ac.uk"):
        return "T2"
    return "T5"


# ---------------------------------------------------------------- which pass to read

def engine_input_for(loop1_dir, basename):
    """The engine input a downstream pass should read, and whether it was machine-challenged.

    The Stage 1 automated challenge supersedes the first machine pass wherever it has
    run. This selection says nothing about human G1 or G2, both of which remain pending
    until after Stage 8.

    Retired ``_g2_input`` files remain readable for historical runs. If both names exist,
    their bytes must agree; ambiguity fails closed rather than selecting one silently.

    Returns (path, challenged).
    """
    canonical = os.path.join(
        loop1_dir, f"{basename}_automated_challenge_input.json"
    )
    legacy = os.path.join(loop1_dir, f"{basename}_g2_input.json")
    canonical_present, legacy_present = compatible_alias_presence(
        canonical,
        legacy,
        "automated-challenge engine inputs",
    )
    if canonical_present:
        return canonical, True
    if legacy_present:
        return legacy, True
    return os.path.join(loop1_dir, f"{basename}_input.json"), False


# ---------------------------------------------------------------- quote verification

def _norm(s):
    """Fold the differences that are formatting, keep the ones that are content."""
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace(" ", " ").replace("’", "'").replace("‘", "'")
    s = s.replace("“", '"').replace("”", '"')
    s = re.sub(r"[‐-―−]", "-", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def _alnum(s):
    """Letters and digits in ANY script, with everything else dropped.

    This was `[^a-z0-9]` and that was a hole in the most important check in the
    pipeline. An Arabic, Chinese, Cyrillic, Greek or Hebrew quote reduces to the
    empty string under an ASCII-only filter, and the empty string is a substring of
    every page — so an entirely invented quote in any of those scripts verified as
    genuine. Egypt publishes in Arabic. `str.isalnum` is Unicode-aware and keeps the
    content while still dropping the punctuation and markup the fold is there to
    ignore.
    """
    return "".join(c for c in _norm(s) if c.isalnum())


def quote_verify(quote, page_text):
    """True when the quote actually appears in the fetched page.

    Two passes: whitespace/punctuation-normalised, then letters and digits only. The
    second tolerates a table cell rendered with stray markup between words; neither
    tolerates a changed number or a changed word. This is the check that caught a
    fabricated pilot in the gauntlet, so it stays strict about content.
    """
    if not quote or not page_text or len(quote.strip()) < 8:
        return False
    reduced = _alnum(quote)
    if not reduced:
        # Nothing survived the fold, so there is nothing to match. Falling through
        # would test whether the empty string appears in the page, which it always
        # does. A quote made entirely of punctuation or symbols is not a quote.
        return False
    return _norm(quote) in _norm(page_text) or reduced in _alnum(page_text)


# ---------------------------------------------------------------- retrieval

def exa_search(query, ledger, pass_name, num_results=8, include_domains=None,
               start_published=None, category=None, text_chars=0):
    """Discovery. Domain and date filters are how the tier protocol reaches the API."""
    ledger.check(pass_name)
    payload = {"query": query, "numResults": num_results, "type": "auto"}
    if include_domains:
        payload["includeDomains"] = include_domains
    if start_published:
        payload["startPublishedDate"] = start_published
    if category:
        payload["category"] = category
    if text_chars:
        payload["contents"] = {"text": {"maxCharacters": text_chars}}
    j = _http("https://api.exa.ai/search", payload, {"x-api-key": key("EXA_API_KEY")})
    results = j.get("results", []) if isinstance(j, dict) else []
    ledger.record("exa", pass_name, searches=1,
                  content_pages=(len(results) if text_chars else 0),
                  detail=query)
    return [dict(title=r.get("title") or "", url=r.get("url") or "",
                 published=r.get("publishedDate") or "", text=r.get("text") or "",
                 tier=tier_for_url(r.get("url") or "")) for r in results]


def jina_fetch(url, ledger, pass_name, max_chars=120000, timeout=90):
    """Fetch page text a quote can be verified against. Returns '' on failure."""
    ledger.check(pass_name)
    target = "https://r.jina.ai/" + url
    try:
        txt = _http(target, headers={"Authorization": "Bearer " + key("JINA_API_KEY"),
                                     "X-Return-Format": "text",
                                     "Accept": "text/plain"},
                    method="GET", timeout=timeout, retries=2)
    except VendorError as e:
        ledger.record("jina", pass_name, fetches=1, detail=f"FAIL {url}")
        return ""
    if isinstance(txt, dict):
        txt = (txt.get("data") or {}).get("text") or txt.get("text") or json.dumps(txt)
    ledger.record("jina", pass_name, fetches=1, detail=url)
    return (txt or "")[:max_chars]


def url_resolves(url, timeout=25, retries=2):
    """Citation resolvability: does the deep link actually return a document?

    Returns (verdict, detail) where verdict is True, False, or None.

    A domain root is not a citation (protocol rule 3), so a bare-root URL fails here
    even when it answers 200. But a publisher's server failing on the day we check is
    not a bad citation, and marking it one would fault a vendor for someone else's
    outage — which is what happened in the audition, where a page Jina had already
    fetched successfully answered a Cloudflare 522 minutes later. Server-side failures
    and timeouts therefore return None: inconclusive, and excluded from the rate rather
    than counted against it.
    """
    if not url or not url.lower().startswith("http"):
        return False, "not a url"
    parsed = urllib.parse.urlparse(url)
    if parsed.path.strip("/") == "" and not parsed.query:
        return False, "domain root, not a document"
    req = urllib.request.Request(url, method="GET", headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"})
    last = (None, "unchecked")
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return (200 <= r.status < 300), f"HTTP {r.status}"
        except urllib.error.HTTPError as e:
            if e.code >= 500:
                last = (None, f"HTTP {e.code} — publisher server error, inconclusive")
            elif e.code in (403, 429):
                last = (None, f"HTTP {e.code} — fetch blocked, inconclusive")
            else:
                return False, f"HTTP {e.code}"
        except Exception as e:
            last = (None, f"{type(e).__name__} — inconclusive")
        time.sleep(1 + attempt)
    return last


# Perplexity throttles hardest of the six, and it is the one vendor whose calls have no
# reason to overlap: it contributes leads, not answers, so serialising it costs a little
# wall-clock and buys every row its discovery peer. Without this, four concurrent rows
# rate-limited each other and rows silently lost their C6 pass.
_PPX_LOCK = threading.Lock()
_PPX_MIN_GAP = 1.5
_ppx_last = [0.0]


def perplexity_citations(question, ledger, pass_name, model="sonar-pro"):
    """Discovery peer (decision C6).

    Returns the citation URLs and, separately, the prose. The prose is a lead, never
    a source of record: a synthesised answer has neither a publisher nor an
    archivable document, and the tier protocol requires both. Callers re-fetch the
    citations through Jina and quote-verify there.
    """
    ledger.check(pass_name)
    with _PPX_LOCK:
        gap = _PPX_MIN_GAP - (time.time() - _ppx_last[0])
        if gap > 0:
            time.sleep(gap)
        j = _http("https://api.perplexity.ai/chat/completions",
                  {"model": model, "messages": [{"role": "user", "content": question}]},
                  {"Authorization": "Bearer " + key("PERPLEXITY_API_KEY")})
        _ppx_last[0] = time.time()
    u = (j.get("usage") or {}) if isinstance(j, dict) else {}
    ledger.record("perplexity", pass_name, model=model, requests=1,
                  in_tok=u.get("prompt_tokens", 0), out_tok=u.get("completion_tokens", 0),
                  detail=question[:120])
    cites = j.get("citations") or []
    for sr in (j.get("search_results") or []):
        if sr.get("url") and sr["url"] not in cites:
            cites.append(sr["url"])
    prose = ""
    try:
        prose = j["choices"][0]["message"]["content"]
    except Exception:
        pass
    return dict(citations=cites, lead_prose=prose)


# ---------------------------------------------------------------- reasoning

_MODEL_PREFS = {
    # Preference order, checked against each vendor's live model list so a model
    # released after this file was written is still reachable without an edit. The
    # model actually used is recorded on every result and printed in the audition
    # report, so the choice is never invisible.
    "anthropic": ["claude-opus-5", "claude-opus-4-8", "claude-sonnet-5"],
    "openai": ["gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.6-sol"],
    "gemini": ["gemini-3.1-pro-preview", "gemini-2.5-pro", "gemini-pro-latest"],
}

# Substrings that mark a model as built for something other than text reasoning.
# Without this filter a prefix like "gemini-3-pro" resolves to `gemini-3-pro-image`,
# and an image model was auditioned as though it were the vendor's flagship.
_NOT_TEXT = ("image", "vision", "tts", "audio", "speech", "embed", "moderation",
             "whisper", "dall", "sora", "veo", "imagen", "lyria", "banana",
             "realtime", "live", "transcribe", "computer-use", "robotics",
             "customtools", "translate", "omni")


class ReplayLLM:
    """Offline adapter for a versioned recording of `LLM.json_call` responses."""

    FORMAT = "damm.llm-replay/v2"

    def __init__(self, path, ledger):
        tape = strict_json_load(path)
        self.format = tape.get("format")
        if self.format != self.FORMAT:
            raise VendorError(f"unsupported replay format: {tape.get('format')!r}")
        self.vendor = "replay"
        self.ledger = ledger
        self.model = tape.get("fixture_id") or "offline-replay"
        self._responses = {}
        self.consumed = []
        for item in tape.get("responses") or []:
            key_ = (item.get("pass_name"), item.get("detail"))
            if not all(key_) or key_ in self._responses:
                raise VendorError(f"invalid or duplicate replay response: {key_!r}")
            if self.format == self.FORMAT and not item.get("request_sha256"):
                raise VendorError(f"replay response lacks request hash: {key_!r}")
            if self.format == self.FORMAT and not item.get("response_sha256"):
                raise VendorError(f"replay response lacks response hash: {key_!r}")
            response = item.get("response")
            if (not isinstance(response, dict)
                    or stable_json_sha256(response) != item.get("response_sha256")):
                raise VendorError(f"replay response hash mismatch: {key_!r}")
            self._responses[key_] = dict(
                response=response,
                request_sha256=item.get("request_sha256"),
                response_sha256=item.get("response_sha256"),
            )

    def cache_identity(self, pass_name, detail, request_sha256=None):
        """Per-entry identity, so adding other tape entries does not bust this cache."""
        entry = self._responses.get((pass_name, detail))
        if not entry:
            return None
        if request_sha256 and request_sha256 != entry["request_sha256"]:
            raise VendorError(
                f"offline replay request hash mismatch for {(pass_name, detail)!r}: "
                f"expected {entry['request_sha256']}, got {request_sha256}")
        return {
            "request_sha256": entry["request_sha256"],
            "response_sha256": entry["response_sha256"],
        }

    def json_call(self, system, user, schema, pass_name, max_tokens=8000, detail=""):
        key_ = (pass_name, detail)
        if key_ not in self._responses:
            raise ReplayExhausted(
                f"offline replay has no response for {pass_name!r} / {detail!r}")
        entry = self._responses[key_]
        response = entry["response"]
        if not isinstance(response, dict):
            raise VendorError(f"offline replay response is not an object: {key_!r}")
        actual_request_sha = json_call_request_sha256(
            system, user, schema, pass_name, max_tokens, detail)
        if (entry["request_sha256"]
                and entry["request_sha256"] != actual_request_sha):
            raise VendorError(
                f"offline replay request hash mismatch for {key_!r}: "
                f"expected {entry['request_sha256']}, got {actual_request_sha}")
        actual_response_sha = stable_json_sha256(response)
        if (entry["response_sha256"]
                and entry["response_sha256"] != actual_response_sha):
            raise VendorError(
                f"offline replay response hash mismatch for {key_!r}: "
                f"expected {entry['response_sha256']}, got {actual_response_sha}")
        missing = [name for name in schema.get("required", []) if name not in response]
        if missing:
            raise VendorError(f"offline replay response {key_!r} misses {missing}")
        self.consumed.append(key_)
        return strict_json_loads(json.dumps(response, allow_nan=False))


class LLM:
    """One JSON-in / JSON-out interface over three reasoning vendors.

    Identical prompt, identical schema, identical retrieved evidence — so the
    audition measures judgment, not each vendor's own search product.
    """

    def __init__(self, vendor, ledger, model=None):
        self.vendor, self.ledger = vendor, ledger
        self.model = model or self._resolve()
        self._client = None

    # -- model resolution ------------------------------------------
    def _resolve(self):
        prefs = _MODEL_PREFS[self.vendor]
        try:
            available = [m for m in self.list_models()
                         if not any(x in m.lower() for x in _NOT_TEXT)]
        except Exception:
            return prefs[0]
        for p in prefs:
            if p in available:
                return p
            # Shortest near-match, not the alphabetically first: the shortest id
            # carrying the prefix is the base model, and the longer siblings are
            # the specialised variants.
            near = sorted((m for m in available if p in m), key=lambda m: (len(m), m))
            if near:
                return near[0]
        return prefs[0]

    def list_models(self):
        if self.vendor == "anthropic":
            j = _http("https://api.anthropic.com/v1/models?limit=100", method="GET",
                      headers={"x-api-key": key("ANTHROPIC_API_KEY"),
                               "anthropic-version": "2023-06-01"})
            return [m["id"] for m in j.get("data", [])]
        if self.vendor == "openai":
            j = _http("https://api.openai.com/v1/models", method="GET",
                      headers={"Authorization": "Bearer " + key("OPENAI_API_KEY")})
            return [m["id"] for m in j.get("data", [])]
        if self.vendor == "gemini":
            j = _http("https://generativelanguage.googleapis.com/v1beta/models"
                      "?pageSize=200&key=" + urllib.parse.quote(key("GEMINI_API_KEY")),
                      method="GET")
            return [m["name"].split("/")[-1] for m in j.get("models", [])]
        raise VendorError(f"unknown vendor {self.vendor}")

    # -- the one call ----------------------------------------------
    def json_call(self, system, user, schema, pass_name, max_tokens=8000, detail=""):
        """Return a dict validated against `schema` by the vendor's own JSON mode.

        A reasoning model can spend its whole output allowance thinking and return an
        empty body. That is a budget failure, not a refusal, and silently turning it
        into a missing row would be the worst kind of gap — one caused by us. So an
        empty or unparseable body is retried once with double the room, and only then
        raises.
        """
        last = None
        for attempt in range(2):
            self.ledger.check(pass_name)
            fn = getattr(self, "_call_" + self.vendor)
            try:
                out, in_tok, out_tok = fn(system, user, schema, max_tokens * (attempt + 1))
            except json.JSONDecodeError as e:
                last = VendorError(f"{self.model} returned no parseable JSON "
                                   f"(likely the output allowance was spent on "
                                   f"reasoning): {e}")
                self.ledger.record(self.vendor, pass_name, model=self.model,
                                   out_tok=max_tokens * (attempt + 1),
                                   detail=f"EMPTY {detail}")
                continue
            self.ledger.record(self.vendor, pass_name, model=self.model,
                               in_tok=in_tok, out_tok=out_tok, detail=detail)
            return out
        raise last

    def _call_anthropic(self, system, user, schema, max_tokens):
        import anthropic
        self._client = self._client or anthropic.Anthropic(api_key=key("ANTHROPIC_API_KEY"))
        r = self._client.messages.create(
            model=self.model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        text = next((b.text for b in r.content if b.type == "text"), "{}")
        return strict_json_loads(text), r.usage.input_tokens, r.usage.output_tokens

    def _call_openai(self, system, user, schema, max_tokens):
        import openai
        self._client = self._client or openai.OpenAI(api_key=key("OPENAI_API_KEY"))
        r = self._client.responses.create(
            model=self.model,
            instructions=system,
            input=user,
            max_output_tokens=max_tokens,
            text={"format": {"type": "json_schema", "name": "research_cell",
                             "schema": schema, "strict": True}},
        )
        u = r.usage
        return (strict_json_loads(r.output_text),
                getattr(u, "input_tokens", 0), getattr(u, "output_tokens", 0))

    def _call_gemini(self, system, user, schema, max_tokens):
        from google import genai
        from google.genai import types
        self._client = self._client or genai.Client(api_key=key("GEMINI_API_KEY"))
        r = self._client.models.generate_content(
            model=self.model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                # Thinking tokens are drawn from this same allowance, so a budget
                # sized for the answer alone returns an empty body. The floor buys
                # the model room to think and still answer.
                max_output_tokens=max(max_tokens, 16000),
                response_mime_type="application/json",
                response_json_schema=_gemini_schema(schema),
            ),
        )
        u = r.usage_metadata
        return (strict_json_loads(r.text or ""),
                getattr(u, "prompt_token_count", 0) or 0,
                (getattr(u, "candidates_token_count", 0) or 0)
                + (getattr(u, "thoughts_token_count", 0) or 0))


def _gemini_schema(schema):
    """Gemini's JSON-schema dialect rejects `additionalProperties`; strip it only."""
    if isinstance(schema, dict):
        return {k: _gemini_schema(v) for k, v in schema.items() if k != "additionalProperties"}
    if isinstance(schema, list):
        return [_gemini_schema(v) for v in schema]
    return schema
