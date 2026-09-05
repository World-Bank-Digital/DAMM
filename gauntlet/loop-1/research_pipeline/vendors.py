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

Retrieval is Exa (discovery and extractive contents) + Jina (fallback fetch): the tier
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
with open(os.path.join(HERE, "prices.json")) as handle:
    PRICES = json.load(handle)

# Reader's ``X-Max-Tokens`` trims content, while ``X-Token-Budget`` rejects a
# request whose total charge would exceed the budget. Keep enough deliberately
# bounded room for the text response envelope, but reserve the *total* strict
# budget before transport so the local ledger and provider cap agree.
JINA_READER_METADATA_HEADROOM_TOKENS = 4_096


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


def _usage_token_count(usage, field, *, optional=False):
    """Return one authoritative nonnegative SDK token count."""
    value = getattr(usage, field, None) if usage is not None else None
    if value is None and optional:
        return 0
    if (isinstance(value, bool) or not isinstance(value, int) or value < 0):
        raise ValueError(f"provider usage field {field} is missing or invalid")
    return value


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
        self._reservations = {}
        self._reservation_journal = []
        self._reservation_counter = 0
        self._retrieval_request_locks = {}
        self._carried_s = 0.0
        self._checkpoint_path = None

    # -- pricing ---------------------------------------------------
    @staticmethod
    def _price(vendor, model, in_tok=0):
        if vendor not in PRICES or vendor.startswith("_"):
            raise VendorError(f"unknown vendor {vendor!r}; refusing paid request")
        table = PRICES.get(vendor, {})
        price = table.get(model) if model else table.get("_default")
        if model and vendor in {"anthropic", "openai", "gemini", "perplexity"}:
            if not isinstance(price, dict):
                raise VendorError(
                    f"no explicit tariff for {vendor}/{model}; refusing paid request"
                )
        price = price if isinstance(price, dict) else {}
        threshold = price.get("long_context_threshold_tokens")
        if (threshold is not None and in_tok > threshold
                and isinstance(price.get("long_context"), dict)):
            return {**price, **price["long_context"]}
        return price

    def estimated_cost(self, vendor, model="", in_tok=0, out_tok=0,
                       searches=0, content_pages=0, fetches=0, requests=0):
        """Price measured or bounded usage through the same path used by ``record``."""
        p = self._price(vendor, model, in_tok=in_tok)
        return (in_tok / 1e6) * p.get("in_per_mtok", 0.0) \
             + (out_tok / 1e6) * p.get("out_per_mtok", 0.0) \
             + searches * PRICES.get("exa", {}).get("per_search", 0.0) \
             + content_pages * PRICES.get("exa", {}).get("per_content_page", 0.0) \
             + fetches * PRICES.get("jina", {}).get("per_fetch", 0.0) \
             + requests * p.get("per_request", 0.0)

    def record(self, vendor, pass_name, model="", in_tok=0, out_tok=0,
               searches=0, content_pages=0, fetches=0, requests=0, detail="",
               structured_result=None, billed_cost=None, _reservation=None):
        derived_cost = self.estimated_cost(
            vendor, model=model, in_tok=in_tok, out_tok=out_tok,
            searches=searches, content_pages=content_pages, fetches=fetches,
            requests=requests,
        )
        if billed_cost is not None:
            if (isinstance(billed_cost, bool)
                    or not isinstance(billed_cost, (int, float))
                    or not math.isfinite(float(billed_cost))
                    or billed_cost < 0):
                raise ValueError("provider-reported cost is invalid")
            cost = float(billed_cost)
        else:
            cost = derived_cost
        with self._lock:
            if (_reservation is not None
                    and _reservation not in self._reservations):
                raise ValueError("unknown budget reservation")
            reservation_entry = (
                self._reservations[_reservation]
                if _reservation is not None else None)
            reserved_upper_bound = (
                reservation_entry["headroom"]
                if _reservation is not None else None)
            usage_exceeded = (
                reserved_upper_bound is not None
                and cost > reserved_upper_bound + 1e-9
            )
            if usage_exceeded:
                # Never publish an over-bound provider response as replayable success.
                # The actual charge remains in the append-only ledger, while the exact
                # request becomes a permanent terminal outcome across process restart.
                structured_result = {
                    "schema_version": "damm.structured-result/v1",
                    "request_sha256": reservation_entry["request_sha256"],
                    "outcome": VendorUsageExceededReservation.code,
                    "reserved_cost": float(reserved_upper_bound),
                    "actual_cost": float(cost),
                }
            call = dict(vendor=vendor, pass_name=pass_name, model=model,
                        in_tok=in_tok, out_tok=out_tok, searches=searches,
                        content_pages=content_pages, fetches=fetches,
                        requests=requests, cost=float(cost),
                        detail=detail[:200],
                        at=round(time.time() - self._t0, 1))
            if _reservation is not None:
                call["reservation_id"] = _reservation
            if structured_result is not None:
                if not isinstance(structured_result, dict):
                    raise ValueError("structured result journal is not an object")
                # Make the journal an immutable JSON value before publishing the call.
                call["structured_result"] = strict_json_loads(json.dumps(
                    structured_result, ensure_ascii=False, allow_nan=False))
            if billed_cost is not None:
                call["provider_reported_cost"] = float(billed_cost)
                call["derived_cost"] = float(derived_cost)
            self.calls.append(call)
            if _reservation is not None:
                # The append-only reservation entry and this linked paid-call record
                # are one durable resolution. Removing the live headroom before the
                # snapshot means its summary counts actual usage, not actual+reserved.
                self._reservations.pop(_reservation)
            if self._checkpoint_path:
                # Persist inside the same lock that publishes the call. A normal exception,
                # coordinator retry, or process crash after this point cannot lose a paid
                # attempt and later spend the same protected allocation again.
                atomic_write_json(self._checkpoint_path, self.snapshot())
            if usage_exceeded:
                raise VendorUsageExceededReservation(
                    vendor=vendor, model=model, pass_name=pass_name,
                    reserved=reserved_upper_bound, actual=cost,
                )
        return cost

    def settle(self, reservation, vendor, pass_name, model="", in_tok=0,
               out_tok=0, searches=0, content_pages=0, fetches=0, requests=0,
               detail="", structured_result=None, billed_cost=None):
        """Atomically replace a live reservation with its authoritative usage."""
        self.record(
            vendor, pass_name, model=model, in_tok=in_tok, out_tok=out_tok,
            searches=searches, content_pages=content_pages, fetches=fetches,
            requests=requests, detail=detail, structured_result=structured_result,
            billed_cost=billed_cost,
            _reservation=reservation,
        )
        # ``json_call_once`` assigns this result back to its local handle, making its
        # finally cleanup conditional without a second racy reservation lookup.
        return None

    def retrieval_request_lock(
            self, vendor, pass_name, request_sha256, model=""):
        """Serialize identical live retrievals so one paid result serves all peers."""
        identity = (vendor, pass_name, model, request_sha256)
        with self._lock:
            return self._retrieval_request_locks.setdefault(
                identity, threading.Lock())

    def claim_retrieval_result(
            self, vendor, pass_name, request_sha256, model=""):
        """Return the oldest matching durable retrieval result as an exact cache."""
        with self._lock:
            reserved = {
                event["reservation_id"]: event
                for event in self._reservation_journal
                if event.get("event") == "reserved"
            }
            for index, call in enumerate(self.calls):
                journal = call.get("structured_result")
                reservation = reserved.get(call.get("reservation_id"), {})
                if (reservation.get("request_sha256") == request_sha256
                        and reservation.get("vendor") == vendor
                        and reservation.get("pass_name") == pass_name
                        and reservation.get("model") == model
                        and (not isinstance(journal, dict)
                             or journal.get("request_sha256") != request_sha256)):
                    # Settlement does not erase the pre-transport request identity.
                    # Losing its result journal is corruption, never a cache miss
                    # that authorizes another charge for that same request.
                    raise VendorPaidRequestTerminal(
                        "settled retrieval request lost its durable result identity")
                if (not isinstance(journal, dict)
                        or journal.get("request_sha256") != request_sha256):
                    continue
                if (call.get("vendor") != vendor
                        or call.get("pass_name") != pass_name
                        or (call.get("model") or "") != model):
                    # Historical or independently generated journals can share a
                    # payload digest across protected lanes. They are not candidates
                    # for this call; keep scanning rather than cross-claiming or failing.
                    continue
                if (reservation.get("request_sha256")
                        and reservation["request_sha256"] != request_sha256):
                    raise VendorPaidRequestTerminal(
                        "durable retrieval result does not match its reservation")
                if journal.get("schema_version") != "damm.structured-result/v1":
                    raise VendorPaidRequestTerminal("durable retrieval result is invalid")
                outcome = journal.get("outcome")
                if outcome in ("retrieval_transport_ambiguous", "retrieval_endpoint_rejected"):
                    # This is deliberately not marked consumed: every later invocation
                    # of the same logical request must fail from the durable record,
                    # never reissue an attempt whose billing outcome is unresolved.
                    raise VendorPaidRequestTerminal(
                        f"durable {vendor} retrieval failure: {outcome}")
                if outcome == "retrieval_source_rejected":
                    # An authoritative unsuccessful response is reusable as a failed
                    # retrieval outcome. Replaying the exact request could only add an
                    # unaccounted provider charge; callers decide whether another
                    # selected source can still establish the needed evidence.
                    failure = _jina_failure_from_journal(journal, source=True)
                    raise JinaSourceRejected(
                        f"durable {vendor} retrieval failure: {failure['kind']}",
                        status=failure["http_status"],
                        provider_status=failure["provider_status"],
                        provider_name=failure["provider_name"],
                    )
                if outcome == "retrieval_exa_source_rejected":
                    failure = _exa_source_rejection_fields(journal.get("failure"))
                    raise SourceRejected("Exa could not retrieve the selected source",
                                         status=failure["http_status"])
                if outcome == "retrieval_http_terminal":
                    # Credential, credit, throttle, and endpoint failures are not
                    # evidence about one source. Their billing result lacks a usage
                    # field, so retain the conservative bound and never reissue them.
                    _jina_failure_from_journal(journal, source=False)
                    raise VendorPaidRequestTerminal(
                        f"durable {vendor} retrieval failure: {outcome}")
                if outcome == "retrieval_usage_missing":
                    raise VendorUsageUnmetered(
                        vendor=vendor, model=model, pass_name=pass_name,
                        detail="durable retrieval usage missing",
                    )
                if outcome == "retrieval_output_malformed":
                    raise VendorPaidRequestTerminal(
                        f"durable {vendor} retrieval failure: {outcome}")
                if outcome == VendorUsageExceededReservation.code:
                    reserved_cost = journal.get("reserved_cost")
                    actual_cost = journal.get("actual_cost")
                    if any(
                            isinstance(value, bool)
                            or not isinstance(value, (int, float))
                            or not math.isfinite(float(value))
                            or value < 0
                            for value in (reserved_cost, actual_cost)):
                        raise VendorPaidRequestTerminal(
                            "durable usage-exceeded result is invalid")
                    raise VendorUsageExceededReservation(
                        vendor=vendor, model=model, pass_name=pass_name,
                        reserved=float(reserved_cost), actual=float(actual_cost),
                    )
                response = journal.get("response")
                if (outcome != "complete" or not isinstance(response, dict)
                        or stable_json_sha256(response)
                        != journal.get("response_sha256")):
                    raise VendorPaidRequestTerminal("durable retrieval result is invalid")
                return True, strict_json_loads(json.dumps(response, allow_nan=False))
        return False, None

    def mark_retrieval_result_consumed(
            self, vendor, pass_name, request_sha256, model=""):
        """Compatibility no-op: exact retrieval outcomes are reusable within a run."""
        return None

    # -- reading ---------------------------------------------------
    @staticmethod
    def _pass_aliases(pass_name):
        return (
            frozenset({"automated_challenge", "g2"})
            if pass_name in {"automated_challenge", "g2"}
            else frozenset({pass_name})
        )

    def spent(self, pass_name=None):
        aliases = self._pass_aliases(pass_name)
        with self._lock:
            actual = math.fsum(
                c["cost"] for c in self.calls
                if pass_name is None or c["pass_name"] in aliases
            )
            unresolved = math.fsum(
                reservation["headroom"]
                for reservation in self._reservations.values()
                if pass_name is None or reservation["pass_name"] in aliases
            )
            return actual + unresolved

    def cap(self, pass_name):
        share = self.ALLOCATION.get(
            pass_name, self.LEGACY_ALLOCATION.get(pass_name, 1.0)
        )
        return self.ceiling * share

    def remaining(self, pass_name):
        return self.cap(pass_name) - self.spent(pass_name)

    def check(self, pass_name, headroom=0.0):
        """Called before an outside call. Raises rather than degrading silently."""
        if (not isinstance(headroom, (int, float)) or isinstance(headroom, bool)
                or not math.isfinite(float(headroom)) or headroom < 0):
            raise ValueError("budget headroom must be a finite nonnegative number")
        with self._lock:
            if self.remaining(pass_name) <= headroom:
                raise BudgetExhausted(
                    pass_name, self.spent(pass_name), self.cap(pass_name))

    def reserve(
            self, pass_name, headroom, *, vendor="", model="",
            request_sha256=""):
        """Durably reserve worst-case cost before a bounded paid request starts."""
        with self._lock:
            if request_sha256 and not re.fullmatch(r"[0-9a-f]{64}", request_sha256):
                raise ValueError("reservation request identity is not a SHA-256 digest")
            for pending in self._reservations.values():
                if (request_sha256
                        and pending["request_sha256"] == request_sha256
                        and pending["vendor"] == vendor
                        and pending["model"] == model
                        and pending["pass_name"] == pass_name):
                    raise VendorRequestPending(
                        vendor=vendor, model=model, pass_name=pass_name,
                        request_sha256=request_sha256,
                        headroom=pending["headroom"],
                    )
            self.check(pass_name, headroom=headroom)
            self._reservation_counter += 1
            reservation = self._reservation_counter
            entry = {
                "event": "reserved",
                "reservation_id": reservation,
                "pass_name": pass_name,
                "headroom": float(headroom),
                "vendor": str(vendor),
                "model": str(model),
                "request_sha256": str(request_sha256),
                "at": round(time.time() - self._t0, 1),
            }
            self._reservation_journal.append(entry)
            self._reservations[reservation] = dict(entry)
            if self._checkpoint_path:
                # This write occurs before transport. A SIGKILL after the provider
                # accepts the request cannot make its worst-case charge disappear.
                atomic_write_json(self._checkpoint_path, self.snapshot())
            return reservation

    def release(self, reservation):
        """Durably release a reservation only when no paid request was attempted."""
        with self._lock:
            if reservation not in self._reservations:
                raise ValueError("unknown budget reservation")
            self._reservations.pop(reservation)
            self._reservation_journal.append({
                "event": "released",
                "reservation_id": reservation,
                "at": round(time.time() - self._t0, 1),
            })
            if self._checkpoint_path:
                atomic_write_json(self._checkpoint_path, self.snapshot())

    def reservation_pending(self, reservation):
        with self._lock:
            return reservation in self._reservations

    def elapsed(self):
        return round(time.time() - self._t0 + self._carried_s, 1)

    def summary(self):
        by_pass, by_vendor = {}, {}
        for c in self.calls:
            by_pass[c["pass_name"]] = round(by_pass.get(c["pass_name"], 0) + c["cost"], 4)
            by_vendor[c["vendor"]] = round(by_vendor.get(c["vendor"], 0) + c["cost"], 4)
        for pending in self._reservations.values():
            pass_name = pending["pass_name"]
            vendor = pending["vendor"] or "unresolved"
            headroom = pending["headroom"]
            by_pass[pass_name] = round(by_pass.get(pass_name, 0) + headroom, 4)
            by_vendor[vendor] = round(by_vendor.get(vendor, 0) + headroom, 4)
        value = dict(label=self.label, ceiling=self.ceiling, total=self.spent(),
                     calls=len(self.calls), elapsed_s=self.elapsed(),
                     by_pass=by_pass, by_vendor=by_vendor,
                     unresolved_reservations=len(self._reservations),
                     reserved_upper_bound=round(sum(
                         row["headroom"] for row in self._reservations.values()), 6))
        if self.checkpoint_identity:
            value["checkpoint_identity_sha256"] = self.checkpoint_identity
        return value

    def snapshot(self):
        with self._lock:
            return dict(
                summary=self.summary(), calls=list(self.calls),
                reservation_journal=list(self._reservation_journal),
            )

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
            if not regular_file_presence(resolved, "spend checkpoint"):
                atomic_write_json(resolved, self.snapshot())
        return resolved

    def save(self, path):
        with self._lock:
            resolved = self._bind_checkpoint_path(path)
            atomic_write_json(resolved, self.snapshot())

    def restore(self, saved):
        """Restore one prior snapshot into a fresh ledger and return its call count."""
        prior, elapsed, journal, unresolved = self._validated_snapshot(saved)
        with self._lock:
            if self._reservation_journal or self._reservations:
                raise ValueError(
                    "cannot restore a spend ledger over live reservations")
            self.calls = prior + self.calls
            self._reservation_journal = journal
            self._reservations = unresolved
            self._reservation_counter = max(
                [0] + [row["reservation_id"] for row in journal])
            self._carried_s = elapsed
        return len(prior)

    @staticmethod
    def _validated_reservations(journal, calls):
        if (not isinstance(journal, list)
                or any(not isinstance(event, dict) for event in journal)):
            raise ValueError("spend reservation journal is not an array of objects")
        reserved = {}
        resolved = set()
        for event in journal:
            event_type = event.get("event")
            reservation_id = event.get("reservation_id")
            if (isinstance(reservation_id, bool)
                    or not isinstance(reservation_id, int)
                    or reservation_id <= 0):
                raise ValueError("spend reservation id is invalid")
            if event_type == "reserved":
                headroom = event.get("headroom")
                request_sha256 = event.get("request_sha256") or ""
                if (reservation_id in reserved
                        or isinstance(headroom, bool)
                        or not isinstance(headroom, (int, float))
                        or not math.isfinite(float(headroom))
                        or headroom < 0
                        or not isinstance(event.get("pass_name"), str)
                        or not event["pass_name"]
                        or not isinstance(event.get("vendor"), str)
                        or not isinstance(event.get("model"), str)
                        or not isinstance(request_sha256, str)
                        or (request_sha256 and not re.fullmatch(
                            r"[0-9a-f]{64}", request_sha256))):
                    raise ValueError("spend reservation entry is invalid")
                reserved[reservation_id] = dict(event)
            elif event_type == "released":
                if reservation_id not in reserved or reservation_id in resolved:
                    raise ValueError("spend reservation release is invalid")
                resolved.add(reservation_id)
            else:
                raise ValueError("spend reservation event is invalid")
        for call in calls:
            reservation_id = call.get("reservation_id")
            if reservation_id is None:
                continue
            if (isinstance(reservation_id, bool)
                    or not isinstance(reservation_id, int)):
                raise ValueError("spend reservation settlement is invalid")
            reservation = reserved.get(reservation_id)
            if (reservation is None
                    or reservation_id in resolved
                    or call.get("pass_name")
                    != reservation["pass_name"]
                    or call.get("vendor") != reservation["vendor"]
                    or (call.get("model") or "") != reservation["model"]):
                raise ValueError("spend reservation settlement is invalid")
            cost = call.get("cost")
            if (isinstance(cost, bool) or not isinstance(cost, (int, float))
                    or not math.isfinite(float(cost)) or cost < 0):
                raise ValueError("spend reservation settlement cost is invalid")
            journal = call.get("structured_result")
            outcome = journal.get("outcome") if isinstance(journal, dict) else None
            exceeded = float(cost) > reservation["headroom"] + 1e-9
            if exceeded:
                if (outcome != VendorUsageExceededReservation.code
                        or journal.get("request_sha256")
                        != reservation["request_sha256"]
                        or journal.get("actual_cost") != cost
                        or journal.get("reserved_cost")
                        != reservation["headroom"]):
                    raise ValueError(
                        "over-bound spend settlement is not terminal")
            elif outcome == VendorUsageExceededReservation.code:
                raise ValueError("usage-exceeded settlement did not exceed its bound")
            resolved.add(reservation_id)
        return {
            reservation_id: dict(entry)
            for reservation_id, entry in reserved.items()
            if reservation_id not in resolved
        }

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
        journal = saved.get("reservation_journal") or []
        unresolved = self._validated_reservations(journal, prior)
        elapsed = summary.get("elapsed_s", 0) or 0
        if (isinstance(elapsed, bool) or not isinstance(elapsed, (int, float))
                or not math.isfinite(float(elapsed)) or elapsed < 0):
            raise ValueError("spend ledger elapsed_s is invalid")
        return list(prior), float(elapsed), list(journal), unresolved

    def reconcile(self, saved):
        """Keep the longer of two prefix-compatible crash checkpoints.

        Generation embeds its ledger in the chapter state and also journals it to a
        standalone spend file. A crash may leave either atomic file one write ahead of
        the other. They are compatible only when one ordered call list is a prefix of
        the other; anything else is stale or tampered state and must fail closed.
        """
        prior, elapsed, journal, _unresolved = self._validated_snapshot(saved)
        with self._lock:
            current = list(self.calls)
            if current == prior[:len(current)]:
                self.calls = prior
            elif prior != current[:len(prior)]:
                raise ValueError("spend ledger checkpoints have divergent call histories")
            current_journal = list(self._reservation_journal)
            if current_journal == journal[:len(current_journal)]:
                self._reservation_journal = journal
            elif journal != current_journal[:len(journal)]:
                raise ValueError(
                    "spend reservation checkpoints have divergent histories")
            self._reservations = self._validated_reservations(
                self._reservation_journal, self.calls)
            self._reservation_counter = max(
                [0] + [
                    row["reservation_id"] for row in self._reservation_journal
                ])
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


class VendorPaidRequestTerminal(VendorError, BudgetExhausted):
    """A paid accounting outcome that must use the existing budget-stop path.

    Canonical stage runners already propagate ``BudgetExhausted`` through every
    evidence fallback and stop later work. These outcomes do not necessarily mean
    the numeric pass cap was exhausted; inheriting that stop signal prevents an
    ambiguous, unresolved, unmetered, or over-bound paid request from being mistaken
    for ordinary source unavailability.
    """

    def __init__(self, message):
        # BudgetExhausted has a different constructor. Initialize the shared
        # Exception base directly while preserving both public error families.
        Exception.__init__(self, message)


class VendorHTTPRejected(VendorError):
    """The provider returned an explicit unsuccessful HTTP response."""

    def __init__(self, message, *, status=None, provider_status=None,
                 provider_name="", reader_content_unavailable=False,
                 reader_diagnostic="endpoint_rejected", provider_tag=""):
        super().__init__(message)
        self.http_status = status
        # ``status`` remains as a compatibility alias for existing callers.
        self.status = status
        self.provider_status = provider_status
        self.provider_name = provider_name
        self.reader_content_unavailable = reader_content_unavailable
        self.reader_diagnostic = reader_diagnostic
        self.provider_tag = provider_tag


class SourceRejected(VendorHTTPRejected):
    """An authoritative source-specific rejection; another page may be usable."""


class JinaSourceRejected(SourceRejected):
    """A known permanent Reader response for one selected source only."""


class VendorNetworkError(VendorError):
    """No authoritative provider response was received after one transport attempt."""


class VendorRequestPending(VendorPaidRequestTerminal):
    """A pre-network durable reservation has no matching settlement after restart."""

    def __init__(
            self, *, vendor, model, pass_name, request_sha256, headroom):
        self.vendor = vendor
        self.model = model
        self.pass_name = pass_name
        self.request_sha256 = request_sha256
        self.headroom = headroom
        super().__init__(
            f"{vendor}/{model or '-'} request {request_sha256[:12]} has an "
            f"unresolved ${headroom:.6f} reservation in {pass_name}; "
            "refusing to reissue a possibly billed request"
        )


class VendorTransportAmbiguous(VendorPaidRequestTerminal):
    """One bounded paid request returned no authoritative outcome or usage."""

    code = "transport_outcome_ambiguous"

    def __init__(
            self, *, vendor, model, pass_name, detail, max_tokens,
            input_tokens, output_tokens):
        self.vendor = vendor
        self.model = model
        self.pass_name = pass_name
        self.detail = detail
        self.max_tokens = max_tokens
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        super().__init__(
            f"{vendor}/{model or '-'} paid request outcome is ambiguous; "
            f"charged the bounded upper estimate in {pass_name} and refused retry"
        )


class VendorUsageExceededReservation(VendorPaidRequestTerminal):
    """Provider-reported usage exceeded the pre-network hard reservation."""

    code = "usage_exceeded_reservation"

    def __init__(self, *, vendor, model, pass_name, reserved, actual):
        self.vendor = vendor
        self.model = model
        self.pass_name = pass_name
        self.reserved = reserved
        self.actual = actual
        super().__init__(
            f"{vendor}/{model or '-'} actual charge ${actual:.6f} exceeded "
            f"its ${reserved:.6f} reserved upper bound in {pass_name}"
        )


class VendorUsageUnmetered(VendorPaidRequestTerminal):
    """A nominally successful paid response omitted authoritative billed usage."""

    code = "usage_unmetered"

    def __init__(self, *, vendor, model, pass_name, detail=""):
        self.vendor = vendor
        self.model = model
        self.pass_name = pass_name
        self.detail = detail
        super().__init__(
            f"{vendor}/{model or '-'} response omitted authoritative "
            f"billed-token usage, provider-reported token usage, or "
            f"provider-reported total cost in {pass_name}; charged the "
            "reserved upper bound"
        )


NONRETRYABLE_STAGE_EXIT = 78


def stage_failure_exit(error, default=1):
    """Map a terminal paid outcome onto the coordinator's no-retry exit."""
    return (
        NONRETRYABLE_STAGE_EXIT
        if isinstance(error, VendorPaidRequestTerminal)
        else default
    )


def prefer_terminal_stage_failure(current, candidate):
    """Keep a terminal paid stop from being hidden by a concurrent budget stop."""
    if current is None or isinstance(candidate, VendorPaidRequestTerminal):
        return candidate
    return current


def run_stage_main(main):
    """Keep an uncaught terminal paid outcome out of the retryable CLI channel."""
    try:
        return main()
    except VendorPaidRequestTerminal as error:
        print(f"!! terminal paid request outcome: {error}")
        return NONRETRYABLE_STAGE_EXIT


class VendorOutputTruncated(VendorError):
    """A paid structured-output response ended before its JSON was complete."""

    code = "structured_output_truncated"

    def __init__(
            self, *, vendor, model, pass_name, detail, stop_reason, request_id,
            max_tokens, input_tokens, output_tokens, thinking_tokens,
            partial_output_chars, partial_output_sha256):
        self.vendor = vendor
        self.model = model
        self.pass_name = pass_name
        self.detail = detail
        self.stop_reason = stop_reason
        self.request_id = request_id
        self.max_tokens = max_tokens
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.thinking_tokens = thinking_tokens
        self.partial_output_chars = partial_output_chars
        self.partial_output_sha256 = partial_output_sha256
        super().__init__(
            f"{model} structured output was truncated ({stop_reason}) after "
            f"{output_tokens} output tokens, including {thinking_tokens} thinking tokens"
        )


class VendorMalformedOutput(VendorError):
    """A paid completed response was not valid structured JSON."""

    code = "structured_output_malformed"

    def __init__(
            self, *, vendor, model, pass_name, detail, stop_reason, request_id,
            max_tokens, input_tokens, output_tokens, thinking_tokens,
            partial_output_chars, partial_output_sha256, parse_error):
        self.vendor = vendor
        self.model = model
        self.pass_name = pass_name
        self.detail = detail
        self.stop_reason = stop_reason
        self.request_id = request_id
        self.max_tokens = max_tokens
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.thinking_tokens = thinking_tokens
        self.partial_output_chars = partial_output_chars
        self.partial_output_sha256 = partial_output_sha256
        self.parse_error = parse_error
        super().__init__(
            f"{model} returned malformed structured output "
            f"({stop_reason or 'completed'}) after {output_tokens} output tokens: "
            f"{parse_error}"
        )


class VendorOutputRejected(VendorError):
    """A paid structured-output request was refused or blocked by safety policy."""

    code = "structured_output_rejected"

    def __init__(
            self, *, vendor, model, pass_name, detail, stop_reason, request_id,
            max_tokens, input_tokens, output_tokens, thinking_tokens,
            partial_output_chars, partial_output_sha256):
        self.vendor = vendor
        self.model = model
        self.pass_name = pass_name
        self.detail = detail
        self.stop_reason = stop_reason
        self.request_id = request_id
        self.max_tokens = max_tokens
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.thinking_tokens = thinking_tokens
        self.partial_output_chars = partial_output_chars
        self.partial_output_sha256 = partial_output_sha256
        super().__init__(
            f"{model} rejected structured output ({stop_reason}) after "
            f"{output_tokens} output tokens, including {thinking_tokens} thinking tokens"
        )


class _ProviderOutputTruncated(Exception):
    """Private transport result; ``json_call`` adds pass identity and accounting."""

    def __init__(
            self, *, stop_reason, request_id, max_tokens, input_tokens,
            output_tokens, thinking_tokens, partial_output):
        self.stop_reason = stop_reason
        self.request_id = request_id
        self.max_tokens = max_tokens
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.thinking_tokens = thinking_tokens
        self.partial_output_chars = len(partial_output)
        self.partial_output_sha256 = hashlib.sha256(
            partial_output.encode("utf-8")
        ).hexdigest()


class _ProviderMalformedOutput(Exception):
    """Private transport parse failure carrying authoritative usage metadata."""

    def __init__(
            self, *, stop_reason, request_id, max_tokens, input_tokens,
            output_tokens, thinking_tokens, partial_output, parse_error):
        self.stop_reason = stop_reason
        self.request_id = request_id
        self.max_tokens = max_tokens
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.thinking_tokens = thinking_tokens
        self.partial_output_chars = len(partial_output)
        self.partial_output_sha256 = hashlib.sha256(
            partial_output.encode("utf-8")
        ).hexdigest()
        self.parse_error = str(parse_error)[:240]


class _ProviderOutputRejected(Exception):
    """Private billed refusal/safety result carrying authoritative usage metadata."""

    def __init__(
            self, *, stop_reason, request_id, max_tokens, input_tokens,
            output_tokens, thinking_tokens, partial_output):
        self.stop_reason = stop_reason
        self.request_id = request_id
        self.max_tokens = max_tokens
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.thinking_tokens = thinking_tokens
        self.partial_output_chars = len(partial_output)
        self.partial_output_sha256 = hashlib.sha256(
            partial_output.encode("utf-8")
        ).hexdigest()


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


def _retrieval_request_sha256(
        operation, payload, *, vendor, pass_name, model=""):
    return stable_json_sha256({
        "operation": operation,
        "vendor": vendor,
        "model": model,
        "pass_name": pass_name,
        "payload": payload,
    })


def _retrieval_result_journal(request_sha256, response):
    return {
        "schema_version": "damm.structured-result/v1",
        "request_sha256": request_sha256,
        "outcome": "complete",
        "response_sha256": stable_json_sha256(response),
        "response": response,
    }


def _retrieval_failure_journal(request_sha256, outcome, failure=None):
    journal = {
        "schema_version": "damm.structured-result/v1",
        "request_sha256": request_sha256,
        "outcome": outcome,
    }
    if failure is not None:
        if not isinstance(failure, dict):
            raise ValueError("retrieval failure journal is not an object")
        journal["failure"] = strict_json_loads(json.dumps(
            failure, ensure_ascii=False, allow_nan=False))
    return journal


_JINA_SOURCE_REJECTION_TUPLES = {
    # Exact payload observed in the Nigeria canary.
    ("jina_submitted_data_malformed", 422, 42203,
     "SubmittedDataMalformedError"),
    ("jina_budget_cap", 409, 40904, "BudgetExceededError"),
    ("jina_content_unavailable", 422, 42206, "AssertionFailureError"),
}
_JINA_PROVIDER_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,79}")
_JINA_TERMINAL_KINDS = frozenset({
    "endpoint_rejected", "jina_navigation_failed", "jina_access_failed",
    "jina_internal_assertion", "jina_assertion_unclassified",
})


def _jina_failure_fields(error, kind):
    """Store a fixed, redacted classification rather than an HTTP response body."""
    http_status = error.http_status
    provider_status = error.provider_status
    provider_name = error.provider_name
    if (isinstance(http_status, bool) or not isinstance(http_status, int)
            or not 100 <= http_status <= 599):
        http_status = 0
    if (isinstance(provider_status, bool)
            or not isinstance(provider_status, int)
            or not 0 <= provider_status <= 99_999):
        provider_status = 0
    if (not isinstance(provider_name, str)
            or not _JINA_PROVIDER_NAME.fullmatch(provider_name)):
        provider_name = ""
    failure = {
        "kind": kind,
        "http_status": http_status,
        "provider_status": provider_status,
        "provider_name": provider_name,
    }
    if kind in _JINA_TERMINAL_KINDS:
        # Unknown provider names are untrusted text, even when identifier-shaped.
        failure["provider_name"] = (
            "AssertionFailureError" if (
                http_status, provider_status, provider_name
            ) == (422, 42206, "AssertionFailureError") else "")
        return failure
    if tuple(failure[key] for key in (
            "kind", "http_status", "provider_status", "provider_name")) \
            not in _JINA_SOURCE_REJECTION_TUPLES:
        raise ValueError("unrecognized Jina source rejection")
    return failure


def _jina_failure_from_journal(journal, *, source):
    failure = journal.get("failure")
    if not isinstance(failure, dict) or set(failure) != {
            "kind", "http_status", "provider_status", "provider_name"}:
        raise VendorPaidRequestTerminal("durable Jina retrieval failure is invalid")
    kind = failure.get("kind")
    http_status = failure.get("http_status")
    provider_status = failure.get("provider_status")
    provider_name = failure.get("provider_name")
    if (not isinstance(kind, str) or isinstance(http_status, bool)
            or not isinstance(http_status, int)
            or not (http_status == 0 or 100 <= http_status <= 599)
            or isinstance(provider_status, bool)
            or not isinstance(provider_status, int)
            or not 0 <= provider_status <= 99_999
            or not isinstance(provider_name, str)
            or (provider_name and not _JINA_PROVIDER_NAME.fullmatch(provider_name))):
        raise VendorPaidRequestTerminal("durable Jina retrieval failure is invalid")
    fields = {
        "kind": kind,
        "http_status": http_status,
        "provider_status": provider_status,
        "provider_name": provider_name,
    }
    if source:
        if tuple(fields[key] for key in (
                "kind", "http_status", "provider_status", "provider_name")) \
                not in _JINA_SOURCE_REJECTION_TUPLES:
            raise VendorPaidRequestTerminal("durable Jina source rejection is invalid")
    elif kind not in _JINA_TERMINAL_KINDS:
        raise VendorPaidRequestTerminal("durable Jina endpoint rejection is invalid")
    elif kind != "endpoint_rejected" and (
            http_status, provider_status, provider_name
    ) != (422, 42206, "AssertionFailureError"):
        raise VendorPaidRequestTerminal("durable Jina assertion classification is invalid")
    return fields


def _unique_http_fields(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("ambiguous HTTP JSON envelope")
        result[name] = value
    return result


def _reader_content_unavailable(body, url):
    """Recognize one target-bound Reader assertion, never arbitrary 42206s.

    jina-ai/reader@1574bfd src/api/crawler.ts emits this exact message when
    no snapshot exists. Other AssertionFailureErrors include service failures.
    Keep only this boolean; never propagate the provider message or URL.
    """
    if (not isinstance(body, dict)
            or not url.startswith(("https://r.jina.ai/https://",
                                   "https://r.jina.ai/http://"))
            or set(body) - {"data", "cause", "code", "status", "name",
                            "message", "readableMessage"}
            or body.get("code") != 422
            or body.get("data") is not None
            or body.get("cause") not in (None, {})):
        return False
    message = "No content available for URL " + url[len("https://r.jina.ai/"):]
    return (body.get("message") == message
            and ("readableMessage" not in body
                 or body["readableMessage"] == "AssertionFailureError: " + message))


def _reader_diagnostic(body, url):
    """Retain fixed investigation categories without retaining provider prose.

    These labels never authorize fallback. Even a navigation/access assertion
    can originate in the Reader service, so every one remains terminal.
    """
    if (not isinstance(body, dict)
            or (body.get("code"), body.get("status"), body.get("name"))
            != (422, 42206, "AssertionFailureError")
            or not url.startswith(("https://r.jina.ai/https://",
                                   "https://r.jina.ai/http://"))):
        return "endpoint_rejected"
    message = body.get("message")
    if isinstance(message, str):
        target = url[len("https://r.jina.ai/"):]
        parsed = urllib.parse.urlsplit(target)
        origin = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
        if message.startswith(f"Failed to goto {target}: "):
            return "jina_navigation_failed"
        if message.startswith((f"Failed to access {target}: ",
                               f"Failed to access {origin}: ")):
            return "jina_access_failed"
        if message.startswith(("Invalid concurrency: ", "Unknown model: ",
                               "Failed to process the page: ")):
            return "jina_internal_assertion"
    return "jina_assertion_unclassified"


def _http(url, data=None, headers=None, method=None, timeout=90, retries=1):
    body = json.dumps(data, allow_nan=False).encode() if data is not None else None
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    h.update(headers or {})
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(url, data=body, headers=h, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw_bytes = r.read(8 * 1024 * 1024 + 1)
            if len(raw_bytes) > 8 * 1024 * 1024:
                # A completed oversized response is malformed, not permission
                # to retry. The caller settles its existing bounded reservation.
                return None
            try:
                raw = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                # Do not silently repair malformed provider bytes into evidence.
                # This completed response still settles the caller's reservation.
                return None
            try:
                return require_finite_json(json.loads(
                    raw, parse_constant=_invalid_json_constant,
                    object_pairs_hook=_unique_http_fields))
            except (ValueError, json.JSONDecodeError):
                # A completed HTTP response with non-standard JSON (such as NaN)
                # is still a response, not a lost transport outcome. Let the
                # provider-specific caller account for its malformed payload under
                # its strict cap instead of treating it as ambiguous network loss.
                return raw
        except urllib.error.HTTPError as e:
            raw_detail = ""
            try:
                error_bytes = e.read(65536 + 1)
                if len(error_bytes) <= 65536:
                    raw_detail = error_bytes.decode("utf-8", "replace")
            except Exception as read_error:
                raw_detail = (
                    f"<unreadable HTTP error body: {type(read_error).__name__}>"
                )
            finally:
                # HTTPError owns a file-like response body. Close it after the small
                # diagnostic read so a burst of rejected pages cannot leak handles.
                e.close()
            detail = raw_detail[:400]
            provider_status = None
            provider_name = ""
            try:
                error_body = require_finite_json(json.loads(
                    raw_detail, parse_constant=_invalid_json_constant,
                    object_pairs_hook=_unique_http_fields))
            except (ValueError, json.JSONDecodeError):
                error_body = None
            if isinstance(error_body, dict) and "code" in error_body:
                code = error_body["code"]
                if isinstance(code, bool) or not isinstance(code, int) or code != e.code:
                    error_body = None
            if isinstance(error_body, dict):
                candidate_status = error_body.get("status")
                if (isinstance(candidate_status, int)
                        and not isinstance(candidate_status, bool)):
                    provider_status = candidate_status
                candidate_name = error_body.get("name")
                if isinstance(candidate_name, str):
                    provider_name = candidate_name[:80]
            last = VendorHTTPRejected(
                f"{e.code} {url.split('?')[0]} :: {detail}",
                status=e.code, provider_status=provider_status,
                provider_name=provider_name,
                provider_tag=(error_body.get("tag") if isinstance(error_body, dict)
                              and error_body.get("tag") in (
                                  "NO_CONTENT_FOUND", "FETCH_DOCUMENT_ERROR", "ROBOTS_FILTER_FAILED")
                              else ""),
                reader_content_unavailable=_reader_content_unavailable(error_body, url),
                reader_diagnostic=_reader_diagnostic(error_body, url))
            if e.code in (400, 401, 402, 403, 404, 409, 422):   # not retryable
                raise last
            if e.code == 429:
                # A rate limit is a wait, not a failure, and giving up on one turns a
                # vendor's throttle into a hole in the evidence. Honour Retry-After
                # when it is offered, and otherwise back off far enough to matter.
                if attempt + 1 >= retries:
                    break
                try:
                    wait = float(e.headers.get("Retry-After") or 0)
                except (TypeError, ValueError):
                    wait = 0
                time.sleep(max(wait, 8 * (attempt + 1)))
                continue
        except Exception as e:                        # timeouts, connection resets
            last = VendorNetworkError(
                f"{type(e).__name__} {url.split('?')[0]} :: {e}")
        if attempt + 1 < retries:
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

def _valid_web_url(value):
    if not isinstance(value, str) or not value or any(ord(c) < 32 for c in value):
        return False
    try:
        parsed = urllib.parse.urlsplit(value)
        return (parsed.scheme in ("http", "https") and bool(parsed.hostname)
                and parsed.username is None and parsed.password is None)
    except ValueError:
        return False


def _valid_exa_page(result):
    return (isinstance(result, dict) and _valid_web_url(result.get("url"))
            and all(result.get(field) is None or isinstance(result[field], str)
                    for field in ("title", "text", "publishedDate", "published")))

def exa_search(query, ledger, pass_name, num_results=8, include_domains=None,
               start_published=None, category=None, text_chars=0):
    lock_sha256 = stable_json_sha256({
        "query": query,
        "num_results": num_results,
        "include_domains": include_domains,
        "start_published": start_published,
        "category": category,
        "text_chars": text_chars,
    })
    with ledger.retrieval_request_lock(
            "exa", pass_name, lock_sha256):
        return _exa_search_unlocked(
            query, ledger, pass_name, num_results=num_results,
            include_domains=include_domains, start_published=start_published,
            category=category, text_chars=text_chars,
        )


def _exa_search_unlocked(
        query, ledger, pass_name, num_results=8, include_domains=None,
        start_published=None, category=None, text_chars=0):
    """Discovery. Domain and date filters are how the tier protocol reaches the API."""
    if (isinstance(num_results, bool) or not isinstance(num_results, int)
            or not 1 <= num_results <= 10):
        raise ValueError("Exa num_results must be an integer from 1 to 10")
    if (isinstance(text_chars, bool) or not isinstance(text_chars, int)
            or not 0 <= text_chars <= 120000):
        raise ValueError("Exa text_chars must be an integer from 0 to 120000")
    payload = {"query": query, "numResults": num_results, "type": "auto"}
    if include_domains:
        payload["includeDomains"] = include_domains
    if start_published:
        payload["startPublishedDate"] = start_published
    if category:
        payload["category"] = category
    if text_chars:
        payload["contents"] = {"text": {"maxCharacters": text_chars}}
    request_sha256 = _retrieval_request_sha256(
        "exa.search/v1", payload, vendor="exa", pass_name=pass_name)
    claimed, cached = ledger.claim_retrieval_result(
        "exa", pass_name, request_sha256)
    if claimed:
        results = cached.get("results")
        if not isinstance(results, list) or not all(_valid_exa_page(result) for result in results):
            raise VendorPaidRequestTerminal("durable Exa result is invalid")
        return results

    # Auto search is a fixed-price request through ten results, including text
    # contents. Keeping this helper inside that documented shape makes its maximum
    # charge knowable before transport; new summary/additional-result shapes need a
    # new explicit tariff rather than silently inheriting this bound.
    reservation = ledger.reserve(
        pass_name,
        ledger.estimated_cost("exa", searches=1),
        vendor="exa", request_sha256=request_sha256,
    )
    transport_attempted = False
    try:
        try:
            transport_attempted = True
            j = _http(
                "https://api.exa.ai/search", payload,
                {"x-api-key": key("EXA_API_KEY")}, retries=1,
            )
        except VendorError as error:
            reservation = ledger.settle(
                reservation, "exa", pass_name, searches=1,
                detail=f"AMBIGUOUS-UPPER-BOUND {query}",
                structured_result=_retrieval_failure_journal(
                    request_sha256, "retrieval_transport_ambiguous"),
            )
            raise VendorTransportAmbiguous(
                vendor="exa", model="", pass_name=pass_name, detail=query,
                max_tokens=0, input_tokens=0, output_tokens=0,
            ) from None
        if (not isinstance(j, dict) or "results" not in j
                or not isinstance(j.get("results"), list)
                or len(j["results"]) > num_results
                or not all(_valid_exa_page(result) for result in j["results"])):
            reservation = ledger.settle(
                reservation, "exa", pass_name, searches=1,
                detail=f"MALFORMED-UPPER-BOUND {query}",
                structured_result=_retrieval_failure_journal(
                    request_sha256, "retrieval_output_malformed"),
            )
            raise VendorPaidRequestTerminal("malformed Exa response: invalid source fields")
        raw_results = j["results"]
        results = [
            dict(
                title=result.get("title") or "",
                url=result.get("url") or "",
                published=result.get("publishedDate") or "",
                text=(result.get("text") or "")[:text_chars or 120000],
                tier=tier_for_url(result.get("url") or ""),
            )
            for result in raw_results
        ]
        journal = _retrieval_result_journal(
            request_sha256, {"results": results})
        reservation = ledger.settle(
            reservation, "exa", pass_name, searches=1,
            content_pages=(len(results) if text_chars else 0), detail=query,
            structured_result=journal,
        )
        ledger.mark_retrieval_result_consumed(
            "exa", pass_name, request_sha256)
        return results
    finally:
        if (reservation is not None and not transport_attempted
                and ledger.reservation_pending(reservation)):
            ledger.release(reservation)


_EXA_SOURCE_HTTP_REJECTIONS = frozenset({
    ("NO_CONTENT_FOUND", 400), ("FETCH_DOCUMENT_ERROR", 422), ("ROBOTS_FILTER_FAILED", 403),
})
_EXA_SOURCE_STATUS_REJECTIONS = frozenset({
    ("CRAWL_NOT_FOUND", 404), ("SOURCE_NOT_AVAILABLE", 403),
})


def _exa_source_rejection_fields(failure):
    if (not isinstance(failure, dict) or set(failure) != {"tag", "http_status"}
            or not isinstance(failure["tag"], str)
            or type(failure["http_status"]) is not int
            or (failure["tag"], failure["http_status"])
            not in _EXA_SOURCE_HTTP_REJECTIONS | _EXA_SOURCE_STATUS_REJECTIONS):
        raise VendorPaidRequestTerminal("invalid durable Exa source rejection")
    return failure


def exa_contents(url, ledger, pass_name, max_chars=18000):
    """Fetch one citation's extractive text, with a durable one-page cost bound.

    Search already includes page text. This separate endpoint covers citations
    discovered by the peer, without relying on Reader as their only fetcher.
    No generated summaries, highlights, or additional pages are requested.
    """
    if (not _valid_web_url(url) or len(url) > 2048
            or isinstance(max_chars, bool) or not isinstance(max_chars, int)
            or not 200 <= max_chars <= 120000):
        raise ValueError("invalid bounded Exa contents request")
    payload = {"urls": [url], "text": {"maxCharacters": max_chars},
               "highlights": False, "subpages": 0}
    request_sha256 = _retrieval_request_sha256(
        "exa.contents/v1", payload, vendor="exa", model="contents", pass_name=pass_name)
    with ledger.retrieval_request_lock("exa", pass_name, request_sha256, model="contents"):
        claimed, cached = ledger.claim_retrieval_result(
            "exa", pass_name, request_sha256, model="contents")
        if claimed:
            if not isinstance(cached.get("text"), str):
                raise VendorPaidRequestTerminal("durable Exa contents result is invalid")
            return cached["text"][:max_chars]
        credential = key("EXA_API_KEY")
        headroom = ledger.estimated_cost("exa", model="contents", requests=1)
        if not math.isfinite(headroom) or headroom <= 0:
            raise VendorError("Exa contents tariff is unavailable")
        reservation = ledger.reserve(
            pass_name, headroom, vendor="exa", model="contents", request_sha256=request_sha256)

        def settle(outcome, response=None, reported_bound=None, failure=None):
            journal = (_retrieval_result_journal(request_sha256, response)
                       if response is not None
                       else _retrieval_failure_journal(request_sha256, outcome, failure))
            ledger.settle(reservation, "exa", pass_name, model="contents", requests=1,
                          detail=_redacted_request_url(url), structured_result=journal,
                          billed_cost=reported_bound)

        try:
            result = _http("https://api.exa.ai/contents", data=payload,
                           headers={"x-api-key": credential}, retries=1)
        except VendorHTTPRejected as error:
            if (error.provider_tag, error.http_status) in _EXA_SOURCE_HTTP_REJECTIONS:
                fields = {"tag": error.provider_tag, "http_status": error.http_status}
                settle("retrieval_exa_source_rejected", failure=fields)
                raise SourceRejected("Exa could not retrieve the selected source",
                                     status=error.http_status) from None
            settle("retrieval_endpoint_rejected")
            raise VendorPaidRequestTerminal(
                "Exa contents endpoint rejected the request; bounded charge retained") from None
        except VendorError:
            settle("retrieval_transport_ambiguous")
            raise VendorPaidRequestTerminal(
                "Exa contents request outcome is ambiguous; bounded charge retained") from None

        # The API calls this an estimate. It cannot reduce our reservation, but
        # evidence of a higher possible charge must stop the workflow and survive
        # restart, rather than silently accept a changed tariff or extra product.
        if isinstance(result, dict) and "costDollars" in result:
            costs = result["costDollars"]
            reported = costs.get("total") if isinstance(costs, dict) else None
            try:
                valid_cost = (not isinstance(reported, bool) and isinstance(reported, (int, float))
                              and math.isfinite(reported) and reported >= 0)
            except OverflowError:
                valid_cost = False
            if not valid_cost:
                settle("retrieval_usage_missing")
                raise VendorUsageUnmetered(vendor="exa", model="contents", pass_name=pass_name)
            if reported > headroom + 1e-9:
                settle("usage_exceeded_reservation", reported_bound=reported)

        # Bind the sole status/result to the requested page. An empty or malformed
        # envelope is never permission to fall through to another paid provider.
        statuses = result.get("statuses") if isinstance(result, dict) else None
        pages = result.get("results") if isinstance(result, dict) else None
        valid = (isinstance(statuses, list) and len(statuses) == 1
                 and isinstance(statuses[0], dict) and statuses[0].get("id") == url
                 and isinstance(pages, list) and len(pages) <= 1)
        text = None
        if valid and statuses[0].get("status") == "success" and len(pages) == 1:
            page = pages[0]
            if (_valid_exa_page(page) and page.get("id") == url and page.get("url") == url
                    and isinstance(page.get("text"), str)):
                try:
                    page["text"].encode("utf-8")
                    text = page["text"][:max_chars]
                except UnicodeEncodeError:
                    pass
        if valid and statuses[0].get("status") == "error" and not pages:
            failure = statuses[0].get("error")
            if (isinstance(failure, dict) and isinstance(failure.get("tag"), str)
                    and type(failure.get("httpStatusCode")) is int
                    and (failure["tag"], failure["httpStatusCode"])
                    in _EXA_SOURCE_STATUS_REJECTIONS):
                fields = _exa_source_rejection_fields({"tag": failure["tag"],
                                                      "http_status": failure["httpStatusCode"]})
                settle("retrieval_exa_source_rejected", failure=fields)
                raise SourceRejected("Exa could not retrieve the selected source",
                                     status=fields["http_status"])
        if text is None:
            settle("retrieval_usage_missing")
            raise VendorUsageUnmetered(vendor="exa", model="contents", pass_name=pass_name)
        # One requested page, one content type: retain the full documented bound
        # even for an unavailable source. costDollars is an estimate, not billing.
        settle("complete", {"text": text})
        return text


def usable_source_text(text, max_chars):
    """Return the bounded extract only when it has enough text for evidence gates."""
    if isinstance(text, str) and len(text[:max_chars].strip()) >= 200:
        return text[:max_chars]
    return ""


def read_source(source, ledger, pass_name, max_chars=18000):
    """Use Exa's extractive page text and citation contents before Reader.

    Callers pass an Exa result (or a citation with no text), never generated
    summaries or discovery-peer prose. Quote and country gates still apply to
    the returned page. Short contents need Reader; an actual terminal
    Reader outcome must propagate rather than be hidden by a fallback.
    """
    if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars < 200:
        raise ValueError("source text cap must be an integer of at least 200")
    text = usable_source_text(source.get("text"), max_chars)
    if text:
        return {"text": text, "retrieval_provider": "exa"}
    text = usable_source_text(exa_contents(source["url"], ledger, pass_name, max_chars), max_chars)
    if text:
        return {"text": text, "retrieval_provider": "exa"}
    return {
        "text": jina_fetch(source["url"], ledger, pass_name, max_chars=max_chars),
        "retrieval_provider": "jina",
    }


def jina_fetch(url, ledger, pass_name, max_chars=120000, timeout=90):
    lock_sha256 = stable_json_sha256({
        "url": url,
        "max_chars": max_chars,
    })
    with ledger.retrieval_request_lock(
            "jina", pass_name, lock_sha256):
        return _jina_fetch_unlocked(
            url, ledger, pass_name, max_chars=max_chars, timeout=timeout)


def _jina_source_rejection_kind(error):
    """Return a known per-source Reader failure kind, else fail closed."""
    fields = (
        error.http_status,
        error.provider_status,
        error.provider_name,
    )
    for kind, http_status, provider_status, provider_name \
            in _JINA_SOURCE_REJECTION_TUPLES:
        if fields == (http_status, provider_status, provider_name):
            if (kind == "jina_content_unavailable"
                    and error.reader_content_unavailable is not True):
                return None
            return kind
    return None


def _jina_http_terminal_error(error):
    status = error.status if error.status is not None else "unclassified"
    return VendorPaidRequestTerminal(
        f"Jina Reader endpoint returned HTTP {status}; charged the bounded upper "
        "estimate and refused retry"
    )


def _redacted_request_url(url):
    """Identify a request without exposing credentials, paths, or query material."""
    return "source-sha256:" + hashlib.sha256(str(url).encode("utf-8")).hexdigest()


def _jina_fetch_unlocked(
        url, ledger, pass_name, max_chars=120000, timeout=90):
    """Fetch page text a quote can be verified against. Returns '' on failure."""
    if (isinstance(max_chars, bool) or not isinstance(max_chars, int)
            or max_chars <= 0):
        raise ValueError("Jina max_chars must be a positive integer")
    # Reader's output cap is at least 500. It trims returned content, whereas
    # its strict total budget can also cover the response envelope. Sending the
    # same value for both headers left no envelope room and produced 40904
    # BudgetExceededError on otherwise usable pages. The total provider budget
    # is nevertheless the hard pre-call spend bound, so reserve and send it.
    content_token_cap = max(500, max_chars)
    strict_token_budget = (
        content_token_cap + JINA_READER_METADATA_HEADROOM_TOKENS)
    request_payload = {
        "url": url,
        "max_tokens": content_token_cap,
        "token_budget": strict_token_budget,
        "max_characters": max_chars,
        "return_format": "text",
    }
    request_sha256 = _retrieval_request_sha256(
        "jina.reader/v1", request_payload, vendor="jina", pass_name=pass_name)
    claimed, cached = ledger.claim_retrieval_result(
        "jina", pass_name, request_sha256)
    if claimed:
        text = cached.get("text")
        if not isinstance(text, str):
            raise VendorPaidRequestTerminal("durable Jina result is invalid")
        return text
    reservation = ledger.reserve(
        pass_name,
        ledger.estimated_cost("jina", out_tok=strict_token_budget),
        vendor="jina", request_sha256=request_sha256,
    )
    transport_attempted = False
    detail_url = _redacted_request_url(url)
    target = "https://r.jina.ai/" + url
    try:
        try:
            transport_attempted = True
            response = _http(
                target,
                headers={
                    "Authorization": "Bearer " + key("JINA_API_KEY"),
                    "X-Return-Format": "text",
                    "X-Max-Tokens": str(content_token_cap),
                    "X-Token-Budget": str(strict_token_budget),
                    "Accept": "application/json",
                },
                method="GET", timeout=timeout, retries=1,
            )
        except VendorHTTPRejected as error:
            # Only target-specific, permanent Reader rejections can be handled as one
            # unusable source. Authentication, balance, throttling, and service errors
            # must not turn into an evidence gap or invite a second paid attempt.
            source_kind = _jina_source_rejection_kind(error)
            if source_kind is None:
                reservation = ledger.settle(
                    reservation, "jina", pass_name,
                    out_tok=strict_token_budget, fetches=1,
                    detail=f"HTTP-TERMINAL-UPPER-BOUND {detail_url}",
                    structured_result=_retrieval_failure_journal(
                        request_sha256, "retrieval_http_terminal",
                        failure=_jina_failure_fields(
                            error, error.reader_diagnostic
                            if error.reader_diagnostic in _JINA_TERMINAL_KINDS
                            else "endpoint_rejected")),
                )
                raise _jina_http_terminal_error(error) from None
            # The provider gives no metered usage with an explicit rejection. Keep the
            # full bounded reservation as spent rather than assuming the request was
            # free, and journal it so an immediate retry cannot make another request.
            reservation = ledger.settle(
                reservation, "jina", pass_name,
                out_tok=strict_token_budget, fetches=1,
                detail=f"HTTP-REJECTED-UPPER-BOUND {detail_url}",
                structured_result=_retrieval_failure_journal(
                    request_sha256, "retrieval_source_rejected",
                    failure=_jina_failure_fields(error, source_kind)),
            )
            raise JinaSourceRejected(
                "Jina Reader provider rejected the selected source", status=error.http_status,
                provider_status=error.provider_status,
                provider_name=error.provider_name,
            ) from None
        except VendorError as error:
            reservation = ledger.settle(
                reservation, "jina", pass_name,
                out_tok=strict_token_budget, fetches=1,
                detail=f"AMBIGUOUS-UPPER-BOUND {detail_url}",
                structured_result=_retrieval_failure_journal(
                    request_sha256, "retrieval_transport_ambiguous"),
            )
            raise VendorTransportAmbiguous(
                vendor="jina", model="", pass_name=pass_name, detail=detail_url,
                max_tokens=strict_token_budget, input_tokens=0,
                output_tokens=strict_token_budget,
            ) from None

        data = response.get("data") if isinstance(response, dict) else None
        if not isinstance(data, dict):
            data = {}
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        usage_tokens = usage.get("tokens")
        # Do not stringify arbitrary JSON into purported source evidence.
        text = data.get("content", data.get("text", response.get("text") if isinstance(response, dict) else None))
        if (not isinstance(text, str) or isinstance(usage_tokens, bool) or not isinstance(usage_tokens, int)
                or usage_tokens < 0):
            # A successful response without its documented billed-token field cannot
            # be accounted exactly. Charge the full hard provider cap and fail closed
            # instead of making further requests against possibly-spent headroom.
            text = ""
            journal = _retrieval_failure_journal(
                request_sha256, "retrieval_usage_missing")
            reservation = ledger.settle(
                reservation, "jina", pass_name,
                out_tok=strict_token_budget, fetches=1,
                detail=f"UNMETERED-UPPER-BOUND {detail_url}",
                structured_result=journal,
            )
            raise VendorUsageUnmetered(
                vendor="jina", model="", pass_name=pass_name, detail=detail_url)

        text = text[:max_chars]
        journal = _retrieval_result_journal(
            request_sha256, {"text": text})
        reservation = ledger.settle(
            reservation, "jina", pass_name, out_tok=usage_tokens, fetches=1,
            detail=detail_url, structured_result=journal,
        )
        ledger.mark_retrieval_result_consumed(
            "jina", pass_name, request_sha256)
        return text
    finally:
        if (reservation is not None and not transport_attempted
                and ledger.reservation_pending(reservation)):
            ledger.release(reservation)


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
PERPLEXITY_MAX_TOKENS = 1200


def perplexity_citations(
        question, ledger, pass_name, model="sonar-pro",
        max_tokens=PERPLEXITY_MAX_TOKENS):
    lock_sha256 = stable_json_sha256({
        "question": question,
        "model": model,
        "max_tokens": max_tokens,
    })
    with ledger.retrieval_request_lock(
            "perplexity", pass_name, lock_sha256, model=model):
        return _perplexity_citations_unlocked(
            question, ledger, pass_name, model=model, max_tokens=max_tokens)


def _perplexity_citations_unlocked(
        question, ledger, pass_name, model="sonar-pro",
        max_tokens=PERPLEXITY_MAX_TOKENS):
    """Discovery peer (decision C6).

    Returns the citation URLs and, separately, the prose. The prose is a lead, never
    a source of record: a synthesised answer has neither a publisher nor an
    archivable document, and the tier protocol requires both. Callers re-fetch the
    citations through Jina and quote-verify there.
    """
    if (isinstance(max_tokens, bool) or not isinstance(max_tokens, int)
            or not 1 <= max_tokens <= 128000):
        raise ValueError("Perplexity max_tokens must be an integer from 1 to 128000")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": question}],
        "max_tokens": max_tokens,
        # Pin the request-fee tier rather than relying on a mutable provider default.
        "web_search_options": {"search_context_size": "low"},
    }
    request_sha256 = _retrieval_request_sha256(
        "perplexity.chat-completions/v1", payload, vendor="perplexity",
        pass_name=pass_name, model=model)
    claimed, cached = ledger.claim_retrieval_result(
        "perplexity", pass_name, request_sha256, model=model)
    if claimed:
        result = cached.get("result")
        if (not isinstance(result, dict)
                or not isinstance(result.get("citations"), list)
                or not all(_valid_web_url(url)
                           for url in result["citations"])
                or not isinstance(result.get("lead_prose"), str)):
            raise VendorPaidRequestTerminal("durable Perplexity result is invalid")
        return result
    # Ordinary text tokenization cannot exceed UTF-8 bytes. The fixed allowance
    # covers the request wrapper and provider control tokens not present in question.
    input_token_bound = len(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")) + 4096
    reservation = ledger.reserve(
        pass_name,
        ledger.estimated_cost(
            "perplexity", model=model, in_tok=input_token_bound,
            out_tok=max_tokens, requests=1,
        ),
        vendor="perplexity", model=model, request_sha256=request_sha256,
    )
    transport_attempted = False
    try:
        try:
            with _PPX_LOCK:
                gap = _PPX_MIN_GAP - (time.time() - _ppx_last[0])
                if gap > 0:
                    time.sleep(gap)
                transport_attempted = True
                j = _http(
                    "https://api.perplexity.ai/chat/completions", payload,
                    {"Authorization": "Bearer " + key("PERPLEXITY_API_KEY")},
                    retries=1,
                )
                _ppx_last[0] = time.time()
        except VendorError as error:
            reservation = ledger.settle(
                reservation, "perplexity", pass_name, model=model, requests=1,
                in_tok=input_token_bound, out_tok=max_tokens,
                detail=f"AMBIGUOUS-UPPER-BOUND {question[:120]}",
                structured_result=_retrieval_failure_journal(
                    request_sha256, "retrieval_transport_ambiguous"),
            )
            raise VendorTransportAmbiguous(
                vendor="perplexity", model=model, pass_name=pass_name,
                detail=question[:120], max_tokens=max_tokens,
                input_tokens=input_token_bound, output_tokens=max_tokens,
            ) from None
        u = j.get("usage") if isinstance(j, dict) else None
        u = u if isinstance(u, dict) else {}
        prompt_tokens = u.get("prompt_tokens")
        completion_tokens = u.get("completion_tokens")
        cost_data = u.get("cost") if isinstance(u.get("cost"), dict) else {}
        total_cost = cost_data.get("total_cost")
        if any(
                isinstance(value, bool) or not isinstance(value, int) or value < 0
                for value in (prompt_tokens, completion_tokens)) or (
                isinstance(total_cost, bool)
                or not isinstance(total_cost, (int, float))
                or not math.isfinite(float(total_cost))
                or total_cost < 0):
            # As with Reader, a nominally successful response without its documented
            # usage cannot release unknown spend. Consume the full provider-bounded
            # reservation and discard the unmetered lead.
            result = {"citations": [], "lead_prose": ""}
            journal = _retrieval_failure_journal(
                request_sha256, "retrieval_usage_missing")
            reservation = ledger.settle(
                reservation, "perplexity", pass_name, model=model, requests=1,
                in_tok=input_token_bound, out_tok=max_tokens,
                detail=f"UNMETERED-UPPER-BOUND {question[:120]}",
                structured_result=journal,
            )
            raise VendorUsageUnmetered(
                vendor="perplexity", model=model, pass_name=pass_name,
                detail=question[:120],
            )
        raw_citations = j.get("citations", [])
        raw_search_results = j.get("search_results", [])
        choices = j.get("choices")
        if (not isinstance(raw_citations, list)
                or not all(_valid_web_url(url) for url in raw_citations)
                or not isinstance(raw_search_results, list)
                or not all(isinstance(row, dict) and _valid_web_url(row.get("url"))
                           for row in raw_search_results)
                or not isinstance(choices, list) or len(choices) != 1
                or not isinstance(choices[0], dict)
                or not isinstance(choices[0].get("message"), dict)
                or not isinstance(choices[0]["message"].get("content"), str)):
            reservation = ledger.settle(
                reservation, "perplexity", pass_name, model=model, requests=1,
                in_tok=prompt_tokens, out_tok=completion_tokens,
                billed_cost=total_cost, detail="MALFORMED-DISCOVERY-RESPONSE",
                structured_result=_retrieval_failure_journal(
                    request_sha256, "retrieval_output_malformed"),
            )
            raise VendorPaidRequestTerminal("malformed Perplexity discovery response")
        cites = list(raw_citations)
        for sr in raw_search_results:
            if (isinstance(sr, dict) and isinstance(sr.get("url"), str)
                    and sr["url"] not in cites):
                cites.append(sr["url"])
        prose = choices[0]["message"]["content"]
        result = dict(
            citations=cites,
            lead_prose=prose if isinstance(prose, str) else "",
        )
        journal = _retrieval_result_journal(
            request_sha256, {"result": result})
        reservation = ledger.settle(
            reservation, "perplexity", pass_name, model=model, requests=1,
            in_tok=prompt_tokens, out_tok=completion_tokens,
            detail=question[:120], structured_result=journal,
            billed_cost=total_cost,
        )
        ledger.mark_retrieval_result_consumed(
            "perplexity", pass_name, request_sha256, model=model)
        return result
    finally:
        if (reservation is not None and not transport_attempted
                and ledger.reservation_pending(reservation)):
            ledger.release(reservation)


# ---------------------------------------------------------------- reasoning

_MODEL_PREFS = {
    # Preference order, checked against each vendor's live model list so a model
    # released after this file was written is still reachable without an edit. The
    # model actually used is recorded on every result and printed in the audition
    # report, so the choice is never invisible.
    "anthropic": ["claude-opus-5", "claude-opus-4-8", "claude-sonnet-5"],
    "openai": ["gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.6-sol"],
    "gemini": ["gemini-3.1-pro-preview", "gemini-2.5-pro"],
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
        if vendor not in _MODEL_PREFS:
            raise VendorError(f"unknown vendor {vendor!r}; refusing reasoning request")
        self.vendor, self.ledger = vendor, ledger
        self.model = model or self._resolve()
        # Model resolution may discover a new or near-matching identifier. Never let
        # that convenience silently route a paid request through a generic tariff.
        self.ledger._price(self.vendor, self.model)
        self._client = None
        self._durable_outcomes = False
        self._claimed_durable_calls = set()
        self._durable_claim_lock = threading.Lock()

    def enable_durable_outcomes(self):
        """Journal and claim bounded provider outcomes for crash-safe stage resume."""
        self._durable_outcomes = True
        return self

    def _durable_outcome(self, request_sha256):
        """Claim the oldest matching paid outcome not used by this process."""
        if not self._durable_outcomes:
            return None
        # Appends and checkpoint loads publish under the ledger lock. Snapshotting and
        # claiming under that same lock prevents a concurrent append from changing the
        # index set halfway through a scan.
        with self._durable_claim_lock, self.ledger._lock:
            for index, call in enumerate(self.ledger.calls):
                if index in self._claimed_durable_calls:
                    continue
                journal = call.get("structured_result")
                if (not isinstance(journal, dict)
                        or journal.get("request_sha256") != request_sha256):
                    continue
                if (call.get("vendor") != self.vendor
                        or call.get("model") != self.model):
                    raise VendorError(
                        "durable structured result vendor/model does not match resume"
                    )
                if journal.get("schema_version") != "damm.structured-result/v1":
                    raise VendorError("durable structured result schema is invalid")
                outcome = journal.get("outcome")
                if outcome == "complete":
                    response = journal.get("response")
                    if (not isinstance(response, dict)
                            or stable_json_sha256(response)
                            != journal.get("response_sha256")):
                        raise VendorError("durable structured result hash is invalid")
                    value = strict_json_loads(json.dumps(response, allow_nan=False))
                elif outcome in {
                        VendorOutputTruncated.code,
                        VendorMalformedOutput.code,
                        VendorOutputRejected.code,
                        VendorTransportAmbiguous.code,
                        VendorUsageExceededReservation.code,
                }:
                    def count(name, default=0):
                        item = journal.get(name, default)
                        return (item if isinstance(item, int)
                                and not isinstance(item, bool) and item >= 0 else default)

                    common = dict(
                        vendor=self.vendor,
                        model=self.model,
                        pass_name=call.get("pass_name") or "",
                        detail=call.get("detail") or "",
                        stop_reason=str(journal.get("stop_reason") or "recorded")[:80],
                        request_id="durable-ledger",
                        max_tokens=count("max_tokens"),
                        input_tokens=count("input_tokens"),
                        output_tokens=count("output_tokens"),
                        thinking_tokens=count("thinking_tokens"),
                        partial_output_chars=count("partial_output_chars"),
                        partial_output_sha256=(
                            str(journal.get("partial_output_sha256") or "")
                            or hashlib.sha256(b"").hexdigest()
                        ),
                    )
                    if outcome == VendorUsageExceededReservation.code:
                        reserved_cost = journal.get("reserved_cost")
                        actual_cost = journal.get("actual_cost")
                        if any(
                                isinstance(item, bool)
                                or not isinstance(item, (int, float))
                                or not math.isfinite(float(item))
                                or item < 0
                                for item in (reserved_cost, actual_cost)):
                            raise VendorError(
                                "durable usage-exceeded result is invalid")
                        value = VendorUsageExceededReservation(
                            vendor=self.vendor, model=self.model,
                            pass_name=call.get("pass_name") or "",
                            reserved=float(reserved_cost),
                            actual=float(actual_cost),
                        )
                    elif outcome == VendorOutputTruncated.code:
                        value = VendorOutputTruncated(**common)
                    elif outcome == VendorMalformedOutput.code:
                        value = VendorMalformedOutput(
                            **common,
                            parse_error="recorded malformed structured output",
                        )
                    elif outcome == VendorOutputRejected.code:
                        value = VendorOutputRejected(**common)
                    else:
                        value = VendorTransportAmbiguous(
                            vendor=self.vendor,
                            model=self.model,
                            pass_name=call.get("pass_name") or "",
                            detail=call.get("detail") or "",
                            max_tokens=count("max_tokens"),
                            input_tokens=count("input_tokens"),
                            output_tokens=count("output_tokens"),
                        )
                else:
                    raise VendorError("durable structured result outcome is invalid")
                if outcome not in {
                        VendorTransportAmbiguous.code,
                        VendorUsageExceededReservation.code,
                }:
                    # An ambiguous result is a permanent stop for its exact request.
                    # Leaving it unclaimed prevents a later identical call in this
                    # process from falling through to transport.
                    self._claimed_durable_calls.add(index)
                return value
        return None

    def _mark_durable_outcome_consumed(self, request_sha256):
        """Mark the live result just returned to this process as already consumed."""
        if not self._durable_outcomes:
            return
        with self._durable_claim_lock, self.ledger._lock:
            for index in range(len(self.ledger.calls) - 1, -1, -1):
                if index in self._claimed_durable_calls:
                    continue
                journal = self.ledger.calls[index].get("structured_result")
                if (isinstance(journal, dict)
                        and journal.get("request_sha256") == request_sha256):
                    self._claimed_durable_calls.add(index)
                    return

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
    def _call_usage_bound(self, system, user, schema, max_tokens):
        """Conservative token bounds before a bounded provider request starts."""
        request_bytes = len((
            str(system) + str(user)
            + json.dumps(schema, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        ).encode("utf-8"))
        # Tokenizers cannot emit more ordinary text tokens than input bytes. The fixed
        # allowance covers provider wrappers and schema-mode control tokens not present
        # in our serialized request estimate.
        input_tokens = request_bytes + 4096
        return input_tokens, max_tokens

    def _call_cost_headroom(self, system, user, schema, max_tokens):
        """Conservative upper-bound cost before a bounded provider request starts."""
        input_tokens, output_tokens = self._call_usage_bound(
            system, user, schema, max_tokens)
        return self.ledger.estimated_cost(
            self.vendor, model=self.model, in_tok=input_tokens,
            out_tok=output_tokens,
        )

    def _failure_journal(self, request_sha256, outcome, error):
        if not self._durable_outcomes:
            return None
        return {
            "schema_version": "damm.structured-result/v1",
            "request_sha256": request_sha256,
            "outcome": outcome,
            "max_tokens": error.max_tokens,
            "stop_reason": str(error.stop_reason or "unknown")[:80],
            "input_tokens": int(error.input_tokens or 0),
            "output_tokens": int(error.output_tokens or 0),
            "thinking_tokens": int(error.thinking_tokens or 0),
            "partial_output_chars": int(error.partial_output_chars or 0),
            "partial_output_sha256": error.partial_output_sha256,
        }

    def _complete_journal(self, request_sha256, response):
        if not self._durable_outcomes:
            return None
        return {
            "schema_version": "damm.structured-result/v1",
            "request_sha256": request_sha256,
            "outcome": "complete",
            "response_sha256": stable_json_sha256(response),
            "response": response,
        }

    @staticmethod
    def _ambiguous_journal(
            request_sha256, max_tokens, input_tokens, output_tokens):
        return {
            "schema_version": "damm.structured-result/v1",
            "request_sha256": request_sha256,
            "outcome": VendorTransportAmbiguous.code,
            "max_tokens": max_tokens,
            "stop_reason": "transport_outcome_ambiguous",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "thinking_tokens": 0,
            "partial_output_chars": 0,
            "partial_output_sha256": hashlib.sha256(b"").hexdigest(),
        }

    def json_call_once(
            self, system, user, schema, pass_name, max_tokens=8000, detail=""):
        """Make exactly one bounded provider request and journal its paid outcome.

        One invocation makes one paid request and records its authoritative usage on
        every outcome. Adaptive retries belong to a stage controller that can persist
        the failure and change the request allowance without replaying paid work. A
        stage still validates the unchanged local schema because provider wire subsets
        cannot express every bound.
        """
        request_sha256 = json_call_request_sha256(
            system, user, schema, pass_name, max_tokens, detail)
        input_bound, output_bound = self._call_usage_bound(
            system, user, schema, max_tokens)
        reservation = self.ledger.reserve(
            pass_name,
            self._call_cost_headroom(system, user, schema, max_tokens),
            vendor=self.vendor, model=self.model,
            request_sha256=request_sha256,
        )
        transport_attempted = False
        try:
            fn = getattr(self, "_call_" + self.vendor)
            try:
                transport_attempted = True
                out, in_tok, out_tok = fn(system, user, schema, max_tokens)
            except _ProviderOutputTruncated as error:
                ledger_detail = (
                    f"TRUNCATED {detail}; stop_reason={error.stop_reason}; "
                    f"thinking_tokens={error.thinking_tokens}"
                )
                reservation = self.ledger.settle(
                    reservation,
                    self.vendor,
                    pass_name,
                    model=self.model,
                    in_tok=error.input_tokens,
                    out_tok=error.output_tokens,
                    detail=ledger_detail,
                    structured_result=self._failure_journal(
                        request_sha256, VendorOutputTruncated.code, error),
                )
                raise VendorOutputTruncated(
                    vendor=self.vendor,
                    model=self.model,
                    pass_name=pass_name,
                    detail=detail,
                    stop_reason=error.stop_reason,
                    request_id=error.request_id,
                    max_tokens=error.max_tokens,
                    input_tokens=error.input_tokens,
                    output_tokens=error.output_tokens,
                    thinking_tokens=error.thinking_tokens,
                    partial_output_chars=error.partial_output_chars,
                    partial_output_sha256=error.partial_output_sha256,
                ) from None
            except _ProviderMalformedOutput as error:
                ledger_detail = (
                    f"MALFORMED {detail}; stop_reason={error.stop_reason}; "
                    f"thinking_tokens={error.thinking_tokens}"
                )
                reservation = self.ledger.settle(
                    reservation,
                    self.vendor,
                    pass_name,
                    model=self.model,
                    in_tok=error.input_tokens,
                    out_tok=error.output_tokens,
                    detail=ledger_detail,
                    structured_result=self._failure_journal(
                        request_sha256, VendorMalformedOutput.code, error),
                )
                raise VendorMalformedOutput(
                    vendor=self.vendor,
                    model=self.model,
                    pass_name=pass_name,
                    detail=detail,
                    stop_reason=error.stop_reason,
                    request_id=error.request_id,
                    max_tokens=error.max_tokens,
                    input_tokens=error.input_tokens,
                    output_tokens=error.output_tokens,
                    thinking_tokens=error.thinking_tokens,
                    partial_output_chars=error.partial_output_chars,
                    partial_output_sha256=error.partial_output_sha256,
                    parse_error=error.parse_error,
                ) from None
            except _ProviderOutputRejected as error:
                ledger_detail = (
                    f"REJECTED {detail}; stop_reason={error.stop_reason}; "
                    f"thinking_tokens={error.thinking_tokens}"
                )
                reservation = self.ledger.settle(
                    reservation,
                    self.vendor,
                    pass_name,
                    model=self.model,
                    in_tok=error.input_tokens,
                    out_tok=error.output_tokens,
                    detail=ledger_detail,
                    structured_result=self._failure_journal(
                        request_sha256, VendorOutputRejected.code, error),
                )
                raise VendorOutputRejected(
                    vendor=self.vendor,
                    model=self.model,
                    pass_name=pass_name,
                    detail=detail,
                    stop_reason=error.stop_reason,
                    request_id=error.request_id,
                    max_tokens=error.max_tokens,
                    input_tokens=error.input_tokens,
                    output_tokens=error.output_tokens,
                    thinking_tokens=error.thinking_tokens,
                    partial_output_chars=error.partial_output_chars,
                    partial_output_sha256=error.partial_output_sha256,
                ) from None
            except Exception as error:
                # The SDK made exactly one attempt (configured below), but a timeout or
                # broken response does not prove whether the provider billed it. Charge
                # the full bounded usage and durably refuse the same request on resume.
                reservation = self.ledger.settle(
                    reservation,
                    self.vendor,
                    pass_name,
                    model=self.model,
                    in_tok=input_bound,
                    out_tok=output_bound,
                    detail=f"AMBIGUOUS-UPPER-BOUND {detail}",
                    structured_result=self._ambiguous_journal(
                        request_sha256, max_tokens, input_bound, output_bound),
                )
                raise VendorTransportAmbiguous(
                    vendor=self.vendor,
                    model=self.model,
                    pass_name=pass_name,
                    detail=detail,
                    max_tokens=max_tokens,
                    input_tokens=input_bound,
                    output_tokens=output_bound,
                ) from None
            reservation = self.ledger.settle(
                reservation,
                self.vendor, pass_name, model=self.model,
                in_tok=in_tok, out_tok=out_tok, detail=detail,
                structured_result=self._complete_journal(request_sha256, out))
            return out
        finally:
            if (reservation is not None and not transport_attempted
                    and self.ledger.reservation_pending(reservation)):
                self.ledger.release(reservation)

    def json_call(self, system, user, schema, pass_name, max_tokens=8000, detail=""):
        """Legacy adaptive interface used by stages without unit checkpoints.

        Stage 6 calls :meth:`json_call_once` and owns a durable, stateful retry. Older
        stages retain their historical one-larger-retry behavior so this change does
        not turn a single truncated cell into a replay of an entire stage.
        """
        last = None
        for attempt in range(2):
            attempt_tokens = max_tokens * (attempt + 1)
            request_sha256 = json_call_request_sha256(
                system, user, schema, pass_name, attempt_tokens, detail)
            durable = self._durable_outcome(request_sha256)
            if durable is not None:
                if isinstance(durable, Exception):
                    error = durable
                    if isinstance(error, (VendorOutputTruncated, VendorMalformedOutput)):
                        last = error
                        continue
                    raise error
                return durable
            try:
                result = self.json_call_once(
                    system,
                    user,
                    schema,
                    pass_name,
                    max_tokens=attempt_tokens,
                    detail=detail,
                )
                self._mark_durable_outcome_consumed(request_sha256)
                return result
            except (VendorOutputTruncated, VendorMalformedOutput) as error:
                self._mark_durable_outcome_consumed(request_sha256)
                last = error
        raise last

    def _call_anthropic(self, system, user, schema, max_tokens):
        import anthropic
        self._client = self._client or anthropic.Anthropic(
            api_key=key("ANTHROPIC_API_KEY"), max_retries=0)
        r = self._client.messages.create(
            model=self.model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}],
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": anthropic.transform_schema(
                        _anthropic_schema_input(schema)),
                }
            },
        )
        text = next((b.text for b in r.content if b.type == "text"), "")
        usage = r.usage
        details = getattr(usage, "output_tokens_details", None)
        input_tokens = _usage_token_count(usage, "input_tokens") + sum(
            _usage_token_count(usage, field, optional=True)
            for field in ("cache_creation_input_tokens", "cache_read_input_tokens")
        )
        output_tokens = _usage_token_count(usage, "output_tokens")
        thinking_tokens = _usage_token_count(
            details, "thinking_tokens", optional=True)
        stop_reason = str(getattr(r, "stop_reason", "") or "")
        stop_details = getattr(r, "stop_details", None)
        if (stop_reason == "refusal"
                or getattr(stop_details, "type", None) == "refusal"):
            raise _ProviderOutputRejected(
                stop_reason="refusal",
                request_id=str(getattr(r, "id", "") or ""),
                max_tokens=max_tokens,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=thinking_tokens,
                partial_output=text,
            )
        if stop_reason == "max_tokens":
            raise _ProviderOutputTruncated(
                stop_reason=stop_reason,
                request_id=str(getattr(r, "id", "") or ""),
                max_tokens=max_tokens,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=thinking_tokens,
                partial_output=text,
            )
        if stop_reason != "end_turn":
            # A syntactically complete-looking prefix is not a completed response.
            # In particular, increasing max_tokens cannot repair a context-window
            # failure caused by the unchanged input, and pause/tool states require a
            # continuation protocol this JSON adapter deliberately does not provide.
            raise _ProviderOutputRejected(
                stop_reason=f"non_complete:{stop_reason or 'missing'}"[:80],
                request_id=str(getattr(r, "id", "") or ""),
                max_tokens=max_tokens,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=thinking_tokens,
                partial_output=text,
            )
        try:
            parsed = strict_json_loads(text)
        except ValueError as error:
            raise _ProviderMalformedOutput(
                stop_reason=str(getattr(r, "stop_reason", "") or "completed"),
                request_id=str(getattr(r, "id", "") or ""),
                max_tokens=max_tokens,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=thinking_tokens,
                partial_output=text,
                parse_error=f"{type(error).__name__}: {error}",
            ) from None
        return parsed, input_tokens, output_tokens

    def _call_openai(self, system, user, schema, max_tokens):
        import openai
        self._client = self._client or openai.OpenAI(
            api_key=key("OPENAI_API_KEY"), max_retries=0)
        r = self._client.responses.create(
            model=self.model,
            instructions=system,
            input=user,
            max_output_tokens=max_tokens,
            text={"format": {"type": "json_schema", "name": "research_cell",
                             "schema": _openai_schema(schema), "strict": True}},
        )
        u = r.usage
        details = getattr(u, "output_tokens_details", None)
        input_tokens = _usage_token_count(u, "input_tokens")
        output_tokens = _usage_token_count(u, "output_tokens")
        thinking_tokens = _usage_token_count(
            details, "reasoning_tokens", optional=True)
        text = str(getattr(r, "output_text", "") or "")
        incomplete = getattr(r, "incomplete_details", None)
        reason = str(getattr(incomplete, "reason", "") or "")
        refusal = ""
        for item in getattr(r, "output", None) or []:
            if getattr(item, "type", None) != "message":
                continue
            for content in getattr(item, "content", None) or []:
                if getattr(content, "type", None) == "refusal":
                    refusal = str(getattr(content, "refusal", "") or "")
                    break
            if refusal:
                break
        response_error = getattr(r, "error", None)
        response_status = str(getattr(r, "status", "") or "")
        if response_status == "failed" or response_error is not None:
            error_code = str(
                getattr(response_error, "code", "") or "response_failed"
            )
            raise _ProviderOutputRejected(
                # The provider's error message can contain request material. Persist
                # only its bounded machine-readable code in the Stage 6 checkpoint.
                stop_reason=f"failed:{error_code}"[:80],
                request_id=str(getattr(r, "id", "") or ""),
                max_tokens=getattr(r, "max_output_tokens", None) or max_tokens,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=thinking_tokens,
                partial_output=text,
            )
        if ((getattr(r, "status", None) == "incomplete"
             and reason == "content_filter") or refusal):
            raise _ProviderOutputRejected(
                stop_reason=reason or "refusal",
                request_id=str(getattr(r, "id", "") or ""),
                max_tokens=getattr(r, "max_output_tokens", None) or max_tokens,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=thinking_tokens,
                partial_output=text or refusal,
            )
        if getattr(r, "status", None) == "incomplete" and reason == "max_output_tokens":
            raise _ProviderOutputTruncated(
                stop_reason=reason,
                request_id=str(getattr(r, "id", "") or ""),
                max_tokens=getattr(r, "max_output_tokens", None) or max_tokens,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=thinking_tokens,
                partial_output=text,
            )
        if response_status != "completed":
            # Only the provider's completed terminal state can authorize parsing.
            # Queued/in-progress/cancelled and unknown incomplete states may expose
            # valid-looking partial text, but accepting it would publish unpaid-for
            # assumptions as a complete structured result.
            state = (
                f"incomplete:{reason or 'unknown'}"
                if response_status == "incomplete"
                else f"non_complete:{response_status or 'missing'}"
            )
            raise _ProviderOutputRejected(
                stop_reason=state[:80],
                request_id=str(getattr(r, "id", "") or ""),
                max_tokens=getattr(r, "max_output_tokens", None) or max_tokens,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=thinking_tokens,
                partial_output=text,
            )
        try:
            parsed = strict_json_loads(text)
        except ValueError as error:
            raise _ProviderMalformedOutput(
                stop_reason=(reason or str(getattr(r, "status", "") or "completed")),
                request_id=str(getattr(r, "id", "") or ""),
                max_tokens=getattr(r, "max_output_tokens", None) or max_tokens,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=thinking_tokens,
                partial_output=text,
                parse_error=f"{type(error).__name__}: {error}",
            ) from None
        return parsed, input_tokens, output_tokens

    def _call_gemini(self, system, user, schema, max_tokens):
        from google import genai
        from google.genai import types
        self._client = self._client or genai.Client(
            api_key=key("GEMINI_API_KEY"),
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(attempts=1)),
        )
        r = self._client.models.generate_content(
            model=self.model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                # Thinking tokens share this allowance. Stage controllers can make one
                # persisted, larger retry; the adapter must honor the requested cap.
                max_output_tokens=max_tokens,
                response_mime_type="application/json",
                response_json_schema=_gemini_schema(schema),
            ),
        )
        u = r.usage_metadata
        input_tokens = _usage_token_count(u, "prompt_token_count")
        answer_tokens = _usage_token_count(u, "candidates_token_count")
        thinking_tokens = _usage_token_count(
            u, "thoughts_token_count", optional=True)
        output_tokens = answer_tokens + thinking_tokens
        try:
            text = str(getattr(r, "text", "") or "")
        except (AttributeError, ValueError):
            # Safety-blocked responses can have no candidate from which the SDK can
            # synthesize its convenience ``text`` property.
            text = ""
        candidates = getattr(r, "candidates", None) or []
        finish = getattr(candidates[0], "finish_reason", None) if candidates else None
        reason = (
            getattr(finish, "name", None)
            or getattr(finish, "value", None)
            or str(finish or "")
        )
        reason = str(reason).rsplit(".", 1)[-1]
        prompt_feedback = getattr(r, "prompt_feedback", None)
        blocked = getattr(prompt_feedback, "block_reason", None)
        blocked_reason = (
            getattr(blocked, "name", None)
            or getattr(blocked, "value", None)
            or str(blocked or "")
        )
        blocked_reason = str(blocked_reason).rsplit(".", 1)[-1]
        if (blocked_reason and blocked_reason != "BLOCKED_REASON_UNSPECIFIED"):
            raise _ProviderOutputRejected(
                stop_reason=blocked_reason,
                request_id=str(getattr(r, "response_id", "") or ""),
                max_tokens=max_tokens,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=thinking_tokens,
                partial_output=text,
            )
        if not candidates:
            raise _ProviderOutputRejected(
                stop_reason="NO_CANDIDATE",
                request_id=str(getattr(r, "response_id", "") or ""),
                max_tokens=max_tokens,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=thinking_tokens,
                partial_output=text,
            )
        if reason.upper() == "MAX_TOKENS":
            raise _ProviderOutputTruncated(
                stop_reason="MAX_TOKENS",
                request_id=str(getattr(r, "response_id", "") or ""),
                max_tokens=max_tokens,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=thinking_tokens,
                partial_output=text,
            )
        if reason.upper() != "STOP":
            raise _ProviderOutputRejected(
                stop_reason=reason.upper() or "UNKNOWN_FINISH_REASON",
                request_id=str(getattr(r, "response_id", "") or ""),
                max_tokens=max_tokens,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=thinking_tokens,
                partial_output=text,
            )
        try:
            parsed = strict_json_loads(text)
        except ValueError as error:
            raise _ProviderMalformedOutput(
                stop_reason=reason or "completed",
                request_id=str(getattr(r, "response_id", "") or ""),
                max_tokens=max_tokens,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=thinking_tokens,
                partial_output=text,
                parse_error=f"{type(error).__name__}: {error}",
            ) from None
        return parsed, input_tokens, output_tokens


def _constraint_description(name, value):
    if name == "minLength":
        return f"Use at least {value} characters."
    if name == "maxLength":
        return f"Use at most {value} characters."
    if name == "uniqueItems" and value is True:
        return "Array elements must be unique."
    if name == "additionalProperties" and value is False:
        return "Do not include properties other than those explicitly listed."
    return ""


_ANTHROPIC_UNION_OUTER_FIELDS = {
    # Annotations and definitions apply to the union as a whole. Anthropic's SDK
    # accepts these beside ``anyOf`` and recursively transforms the variants.
    "$anchor", "$comment", "$defs", "$dynamicAnchor", "$id", "$schema",
    "const", "default", "definitions", "deprecated", "description", "enum",
    "examples", "readOnly", "title", "writeOnly",
}
_ANTHROPIC_COMPLEX_UNION_FIELDS = {
    # Distributing these over a generated anyOf needs a full schema algebra. None is
    # used by this pipeline, so reject a future ambiguous combination explicitly.
    "$ref", "allOf", "anyOf", "if", "not", "oneOf", "then", "else",
}


def _anthropic_schema_input(schema):
    """Canonicalize list-valued JSON Schema types before the SDK transformer.

    Anthropic's API accepts JSON Schema type arrays, but current Python SDK releases
    assert before transport when ``transform_schema`` receives one. Convert only the
    wire copy to an equivalent ``anyOf``. Type-specific constraints travel with each
    concrete branch; they are omitted from a null branch because JSON Schema ignores
    those constraints for a null instance. The caller's authoritative local schema is
    never mutated.
    """
    if isinstance(schema, list):
        return [_anthropic_schema_input(value) for value in schema]
    if not isinstance(schema, dict):
        return schema

    normalized = {
        name: _anthropic_schema_input(value)
        for name, value in schema.items()
    }
    type_union = normalized.get("type")
    if not isinstance(type_union, list):
        return normalized
    if (not type_union
            or any(not isinstance(value, str) or not value for value in type_union)
            or len(set(type_union)) != len(type_union)):
        raise VendorError("invalid list-valued JSON Schema type for Anthropic")
    complex_fields = sorted(
        _ANTHROPIC_COMPLEX_UNION_FIELDS.intersection(normalized))
    if complex_fields:
        raise VendorError(
            "cannot normalize an Anthropic type union combined with "
            + ", ".join(complex_fields)
        )

    outer = {
        name: value for name, value in normalized.items()
        if name in _ANTHROPIC_UNION_OUTER_FIELDS
    }
    branch_constraints = {
        name: value for name, value in normalized.items()
        if name != "type" and name not in _ANTHROPIC_UNION_OUTER_FIELDS
    }
    branches = []
    for value_type in type_union:
        branch = {"type": value_type}
        if value_type != "null":
            branch.update(branch_constraints)
        branches.append(branch)
    outer["anyOf"] = branches
    return outer


def _wire_schema(schema, unsupported):
    """Return a provider subset while preserving stripped constraints as guidance."""
    if isinstance(schema, dict):
        transformed = {}
        guidance = []
        for name, value in schema.items():
            if name in unsupported:
                clause = _constraint_description(name, value)
                if clause:
                    guidance.append(clause)
                continue
            transformed[name] = _wire_schema(value, unsupported)
        if guidance:
            description = str(transformed.get("description") or "").strip()
            transformed["description"] = " ".join(
                ([description] if description else []) + guidance
            )
        return transformed
    if isinstance(schema, list):
        return [_wire_schema(value, unsupported) for value in schema]
    return schema


def _gemini_schema(schema):
    """Transform Stage-6 constraints outside Gemini's documented schema subset."""
    return _wire_schema(
        schema,
        {"additionalProperties", "minLength", "maxLength", "uniqueItems"},
    )


def _openai_schema(schema):
    """Strip constraints outside OpenAI's documented strict-schema subset.

    Stage controllers validate the unchanged schema after the provider returns. This
    wire-only copy prevents a strict request from failing before generation while
    retaining the bounded contract locally.
    """
    return _wire_schema(schema, {"minLength", "maxLength", "uniqueItems"})
