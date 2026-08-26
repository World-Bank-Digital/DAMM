#!/usr/bin/env python3
"""Pass five: the draft Digital Agriculture Roadmap (design decisions E3, E4, E5).

Eleven chapters of prose, and three defences against the failure that prose invites — a
fluent paragraph carrying a number the evidence never produced.

**Chapters see only what they may cite (E4).** Each chapter's binding lives in the model
file: the pillars, indicators, use-case columns, prerequisites and derived sources it may
draw on. The pack assembled for a chapter contains that and nothing else, so citing
outside the binding is not something the writer is trusted to avoid. A financing chapter
reaching for connectivity indicators reads perfectly fluently and is wrong, and this is
the only mechanism that catches it before a reader does.

**Every figure is checked against the engine (E3).** The writer returns its figures as
data alongside the prose. Each is matched against the numbers the engine actually
produced, and the prose is swept for numbers that are in neither the figure list nor the
narrow set of things a sentence may legitimately count. The check is reported as a rate on
the document's own face rather than kept in a log.

**The gate blocks the emit (E5).** The diagnostic has one and it is much of why the
diagnostic survived review. This one refuses to write a document when a chapter has no
provenance banner, when a chapter cites outside its binding, when a prescriptive chapter
is presented as evidenced, or when fidelity falls below the floor. The gates are the
compensation for having removed the human from every step before final review.

Chapters 3 to 10 are prescriptive. They are marked *proposed, not evidenced* on the page,
in their own record, and in the gate — three statements of one fact, because this is the
one a reader must not miss.

    python3 generate_dar.py --country Egypt --iso EGY --out EGY_shadow [--ceiling 500] [--resume]
"""

import argparse, hashlib, html, io, json, math, os, posixpath, re, subprocess, sys, time, zipfile
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP1 = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(LOOP1, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, LOOP1)
sys.path.insert(0, os.path.join(REPO, "model"))

import vendors as V
import workflow_inputs as WI
from engine_v17 import MODEL, run as engine_run, tlevel
from reference_scorer import Scorer as ReferenceScorer

PASS = "generation"

# Every id the instrument names, so a reference to a row can be told from a claim about
# the country. Prerequisite ids are indicator ids, so the one set covers both.
KNOWN_IDS = frozenset(MODEL)
MODEL_FILE = os.path.join(REPO, "model", "DAMM-v1.7-model.json")
WORKFLOW_FILE = os.path.join(REPO, "workflow", "dar-workflow-v1.json")
ENGINE_FILE = os.path.join(LOOP1, "engine_v17.py")
REFERENCE_SCORER_FILE = os.path.join(REPO, "model", "reference_scorer.py")
MODEL_EXPORT_FILE = os.path.join(REPO, "model", "export_model.py")
WORKBOOK_BUILDER_FILE = os.path.join(LOOP1, "build_workbook_v17.py")
WORKBOOK_PARITY_FILE = os.path.join(LOOP1, "verify_workbook_parity.py")
RENDERER_FILE = os.path.join(LOOP1, "render_v17.py")
VENDORS_FILE = os.path.abspath(V.__file__)
SPEC = json.load(open(MODEL_FILE))
ASSESSMENT_YEAR = SPEC["config"]["assessment_year"]
OUTLINE = SPEC["dar_outline"]
PROHIBITIONS = SPEC.get("prohibitions", [])
EVIDENCE_CLASSES = frozenset(item["id"] for item in SPEC["evidence_classes"])
SOURCE_TIERS = frozenset(SPEC["source_tiers"])
CANDIDATE_INPUT_PATTERN = re.compile(SPEC["candidate_indicators"]["id_pattern"])
ASSESSMENT_ROW_FIELDS = ("value", "cls", "level", "year", "src", "note", "tier", "url")

# Below this, the document is not emitted. A roadmap where one figure in twenty is
# untraceable is not a roadmap with a small problem; it is a document a reader cannot use
# without checking every number themselves, which is the work it was meant to do for them.
FIDELITY_FLOOR = 0.95

CHAPTER_WORKERS = 3

SYSTEM = ("You draft chapters of a national Digital Agriculture Roadmap from an evidence "
          "pack. You use only the figures in the pack, you never invent a number, and you "
          "say plainly when something is proposed rather than evidenced. JSON only.")

CHAPTER_SCHEMA = {
    "type": "object",
    "properties": {
        "prose": {"type": "string"},
        "cites": {
            "type": "object",
            "properties": {
                "pillars": {"type": "array", "items": {"type": "string"}},
                "indicators": {"type": "array", "items": {"type": "string"}},
                "use_cases": {"type": "array", "items": {"type": "string"}},
                "prerequisites": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["pillars", "indicators", "use_cases", "prerequisites"],
            "additionalProperties": False,
        },
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "basis": {"type": "string", "enum": ["evidence", "proposal"]},
                    "source_refs": {
                        "type": "array", "items": {"type": "string"},
                    },
                },
                "required": ["text", "basis", "source_refs"],
                "additionalProperties": False,
            },
        },
        "figures": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "value": {"type": "string"},
                    "what_it_is": {"type": "string"},
                    "basis": {
                        "type": "string",
                        "enum": ["evidence", "calculation", "benchmark",
                                 "planning_assumption"],
                    },
                    "operation": {
                        "type": "string",
                        "enum": ["none", "sum", "difference", "product",
                                 "ratio", "percentage"],
                    },
                    "source_refs": {
                        "type": "array", "items": {"type": "string"},
                    },
                    "inputs": {
                        "type": "array", "items": {"type": "string"},
                    },
                    "rationale": {"type": "string"},
                },
                "required": ["value", "what_it_is", "basis", "operation",
                             "source_refs", "inputs", "rationale"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["prose", "cites", "claims", "figures"],
    "additionalProperties": False,
}


# ------------------------------------------------------- reviewed assessment input

def _candidate_input_rows(rows):
    """Canonical, unscored candidate observations carried beside the model rows."""
    if not isinstance(rows, dict):
        return {}
    return {
        indicator_id: row for indicator_id, row in rows.items()
        if (isinstance(indicator_id, str)
            and CANDIDATE_INPUT_PATTERN.fullmatch(indicator_id))
    }


def _present_text(value):
    return isinstance(value, str) and bool(value.strip())


def _finite_number(value):
    return type(value) is int or (type(value) is float and math.isfinite(value))


def _transform_contract_error(row, measure, metadata):
    if row.get("cls") != "Measured":
        return None
    value = row.get("value")
    inputs = metadata.get("transform_inputs")
    transform = measure.get("transform") if isinstance(measure, dict) else None
    if not _finite_number(value) or not isinstance(inputs, dict):
        return "Measured observation lacks numeric transform inputs"
    try:
        if transform == "identity" and set(inputs) == {"source_value"}:
            expected = inputs["source_value"]
        elif transform == "raw / 100" and set(inputs) == {"source_value"}:
            expected = inputs["source_value"] / 100
        elif (transform == "monthly_price / (annual_GNI_per_capita / 12) * 100"
              and set(inputs) == {"monthly_price", "annual_gni_per_capita"}
              and inputs["annual_gni_per_capita"] != 0):
            expected = (inputs["monthly_price"]
                        / (inputs["annual_gni_per_capita"] / 12) * 100)
        elif (transform == "max(male_rate - female_rate, 0)"
              and set(inputs) == {"male_rate", "female_rate"}):
            expected = max(inputs["male_rate"] - inputs["female_rate"], 0)
        else:
            return "Measured observation uses an unsupported transform input contract"
    except (TypeError, ZeroDivisionError):
        return "Measured observation transform inputs are not numeric"
    if not _finite_number(expected) or not math.isclose(
            value, expected, rel_tol=1e-9, abs_tol=1e-9):
        return "Measured value does not equal the ratified transform result"
    return None


def _ratified_row_contract_errors(indicator_id, row, model_spec):
    catalog = model_spec.get("indicator_definitions")
    entries = catalog.get("entries") if isinstance(catalog, dict) else None
    definition = entries.get(indicator_id) if isinstance(entries, dict) else None
    metadata = row.get("definition_metadata") if isinstance(row, dict) else None
    label = f"row {indicator_id}"
    if not isinstance(definition, dict):
        return [f"{label} has no ratified definition in the model"]
    if not isinstance(metadata, dict):
        return [f"{label} missing ratified definition_metadata"]
    measure = definition.get("measure")
    source_policy = definition.get("source_policy")
    scoring = definition.get("scoring")
    model_indicators = model_spec.get("indicators")
    indicator = next((item for item in (
                          model_indicators if isinstance(model_indicators, list) else [])
                      if isinstance(item, dict)
                      and item.get("id") == indicator_id), None)
    preferred = (source_policy.get("preferred_series")
                 if isinstance(source_policy, dict) else [])
    errors = []
    expected = {
        "definition_version": definition.get("definition_version"),
        "definition_sha256": _canonical_sha256(definition),
        "unit": measure.get("unit") if isinstance(measure, dict) else None,
        "population_scope": (measure.get("population_scope")
                             if isinstance(measure, dict) else None),
        "reference_period_rule": (measure.get("reference_period")
                                  if isinstance(measure, dict) else None),
        "transform": measure.get("transform") if isinstance(measure, dict) else None,
    }
    for field, expected_value in expected.items():
        if metadata.get(field) != expected_value:
            errors.append(f"{label} definition_metadata {field} does not match the model")
    if metadata.get("definition_match") is not True:
        errors.append(f"{label} definition_metadata must affirm definition_match")
    if (not isinstance(source_policy, dict)
            or not isinstance(source_policy.get("allowed_tiers"), list)
            or not source_policy["allowed_tiers"]
            or source_policy.get("minimum_confirmation")
            != "One load-bearing source plus construct review"
            or not isinstance(scoring, dict)
            or scoring.get("missing_rule") != "DATA GAP"
            or scoring.get("mismatch_rule") != "HOLD"):
        errors.append(f"{label} ratified definition policy is not executable")
    elif (row.get("cls") != "Gap"
          and row.get("tier") not in source_policy["allowed_tiers"]):
        errors.append(f"{label} source tier is not allowed by its ratified definition")
    expected_method = (indicator.get("method")
                       if isinstance(indicator, dict) else None)
    expected_direction = (indicator.get("direction")
                          if isinstance(indicator, dict) else None)
    expected_thresholds = (indicator.get("thresholds")
                           if isinstance(indicator, dict) else None)
    if (not isinstance(scoring, dict)
            or scoring.get("method") != expected_method
            or scoring.get("direction") != expected_direction
            or (expected_method == "threshold"
                and scoring.get("cuts") != expected_thresholds)
            or (expected_method == "ladder" and "cuts" in scoring)):
        errors.append(f"{label} definition scoring does not match the runtime model")
    if (expected_method == "threshold" and row.get("level") is not None
            and row.get("cls") != "Measured"):
        errors.append(f"{label} threshold score requires a Measured observation")
    if expected_method == "ladder" and row.get("cls") == "Measured":
        errors.append(f"{label} ladder observation cannot be Measured")
    for field in ("geography", "observation_period", "edition"):
        if not _present_text(metadata.get(field)):
            errors.append(f"{label} definition_metadata {field} is missing")
    if type(metadata.get("proxy")) is not bool:
        errors.append(f"{label} definition_metadata proxy must be boolean")
    elif metadata["proxy"] and not _specific_definition_text(
            metadata.get("proxy_justification")):
        errors.append(f"{label} proxy observation needs a specific justification")
    if (not isinstance(metadata.get("source_record_sha256"), str)
            or not _SHA256_TEXT.fullmatch(metadata["source_record_sha256"])):
        errors.append(f"{label} definition_metadata source_record_sha256 is invalid")
    if (not isinstance(metadata.get("construct_review_sha256"), str)
            or not _SHA256_TEXT.fullmatch(metadata["construct_review_sha256"])):
        errors.append(f"{label} definition_metadata construct_review_sha256 is invalid")
    for field in ("numerator", "denominator"):
        contract_value = measure.get(field) if isinstance(measure, dict) else None
        if contract_value == "not_applicable":
            if metadata.get(field) != "not_applicable":
                errors.append(
                    f"{label} definition_metadata {field} must be not_applicable")
        elif not (_present_text(metadata.get(field))
                  or _finite_number(metadata.get(field))):
            errors.append(f"{label} definition_metadata {field} is missing")
    source_series = metadata.get("source_series")
    if not _present_text(source_series):
        errors.append(f"{label} definition_metadata source_series is missing")
    elif preferred and source_series not in preferred:
        if not _specific_definition_text(metadata.get("fallback_justification")):
            errors.append(
                f"{label} non-preferred source_series needs a specific fallback justification")
    calibration_refs = model_spec.get("indicator_calibration_refs")
    expected_calibration = (calibration_refs.get(indicator_id)
                            if isinstance(calibration_refs, dict) else None)
    if expected_method == "threshold" and expected_calibration is None:
        errors.append(f"{label} threshold row has no ratified calibration reference")
    elif expected_calibration is not None:
        if metadata.get("calibration_ref") != expected_calibration:
            errors.append(f"{label} calibration_ref does not match the ratified model")
    elif "calibration_ref" in metadata:
        errors.append(f"{label} ladder row must not name a threshold calibration")
    transform_error = _transform_contract_error(row, measure, metadata)
    if transform_error:
        errors.append(f"{label} {transform_error}")
    return errors


def _assessment_row_errors(
        indicator_id, row, *, candidate=False, model_spec=None):
    """Validate one reviewed row against the model's evidence-class contract."""
    label = f"row {indicator_id}"
    errors = []
    if not isinstance(row, dict):
        return [f"{label} must be a JSON object"]

    for field in ASSESSMENT_ROW_FIELDS:
        if field not in row:
            errors.append(f"{label} missing required field {field}")

    cls = row.get("cls")
    value = row.get("value")
    level = row.get("level")
    year = row.get("year")
    src = row.get("src")
    note = row.get("note")
    tier = row.get("tier")
    url = row.get("url")

    if cls not in EVIDENCE_CLASSES:
        errors.append(
            f"{label} cls must be one of {', '.join(sorted(EVIDENCE_CLASSES))}")

    valid_level = level is None or (type(level) is int and 1 <= level <= 5)
    if not valid_level:
        errors.append(f"{label} level must be null or an integer from 1 to 5")
    if candidate and level is not None:
        errors.append(f"{label} candidate level must be null")
    if cls == "Gap" and level is not None:
        errors.append(f"{label} Gap level must be null")

    if not (type(year) is int and 1900 <= year <= ASSESSMENT_YEAR):
        errors.append(
            f"{label} year must be an integer from 1900 through {ASSESSMENT_YEAR}")

    for field, field_value in (("src", src), ("note", note),
                               ("tier", tier), ("url", url)):
        if field in row and not isinstance(field_value, str):
            errors.append(f"{label} {field} must be text")

    has_src = _present_text(src)
    has_tier = _present_text(tier)
    has_url = _present_text(url)
    if isinstance(tier, str) and tier and tier not in SOURCE_TIERS:
        errors.append(f"{label} tier must be blank or one of {', '.join(sorted(SOURCE_TIERS))}")
    if has_url and not re.match(r"^https?://", url, re.I):
        errors.append(f"{label} url must be an absolute HTTP(S) URL")
    if level is not None and not has_src:
        errors.append(f"{label} a level requires a source")

    numeric_value = _finite_number(value)
    text_value = _present_text(value)
    begins_gap = (
        text_value
        and re.match(r"^DATA GAP(?:\s|[\-\u2013\u2014]|$)", value.lstrip(), re.I)
    )

    if cls == "Measured":
        if not numeric_value:
            errors.append(f"{label} Measured value must be a finite number")
        if not (has_src and has_tier and has_url and tier != "T5"):
            errors.append(
                f"{label} Measured provenance requires source, URL, and a T1-T4 tier")
        if not candidate and indicator_id in MODEL:
            model_row = MODEL[indicator_id]
            if isinstance(model_spec, dict) and model_spec.get("ratified") is True:
                active_indicators = model_spec.get("indicators")
                active_row = next((item for item in (
                                      active_indicators
                                      if isinstance(active_indicators, list) else [])
                                   if isinstance(item, dict)
                                   and item.get("id") == indicator_id), None)
                if isinstance(active_row, dict):
                    model_row = {
                        "kind": ("t" if active_row.get("method") == "threshold"
                                 else "l"),
                        "dir": ({"higher-is-better": "H",
                                 "lower-is-better": "L"}.get(
                                     active_row.get("direction"), "")),
                        "th": active_row.get("thresholds") or [],
                    }
            if model_row["kind"] != "t":
                errors.append(f"{label} a ladder indicator cannot be Measured")
            elif (numeric_value and valid_level and level is not None
                  and tlevel(value, model_row["dir"], model_row["th"]) != level):
                errors.append(f"{label} Measured level does not match its thresholds")

    elif cls == "Documented":
        if not text_value or begins_gap:
            errors.append(f"{label} Documented value must be non-gap text")
        if not (has_src and has_tier and has_url and tier != "T5"):
            errors.append(
                f"{label} Documented provenance requires source, URL, and a T1-T4 tier")

    elif cls == "Judged":
        if not text_value or begins_gap:
            errors.append(f"{label} Judged value must be non-gap text")
        # A judgment is either unsupported by an artifact or supported only by T5.
        # A title without a resolvable URL still counts as no artifact, as it does in
        # the research derivation that assigns this class.
        if has_url or has_tier:
            if not (has_src and has_url and tier == "T5"):
                errors.append(
                    f"{label} Judged provenance must be source-free or a complete T5 citation")

    elif cls == "Gap":
        if not begins_gap:
            errors.append(f"{label} Gap value must begin DATA GAP and record the search trail")
        elif not value.lstrip()[len("DATA GAP"):].strip(" \t:-\u2013\u2014"):
            errors.append(f"{label} Gap value must begin DATA GAP and record the search trail")
        if not has_src:
            errors.append(f"{label} Gap provenance requires a search source")
        if has_tier != has_url:
            errors.append(f"{label} Gap tier and URL must either both be present or both be blank")

    if (not candidate and isinstance(model_spec, dict)
            and model_spec.get("ratified") is True
            and model_spec.get("status") == "ratified"):
        errors.extend(_ratified_row_contract_errors(indicator_id, row, model_spec))
    return errors


def assessment_input_errors(rows, spec=None):
    """All reasons reviewed G2 rows cannot safely be passed to the scoring engine."""
    if not isinstance(rows, dict):
        return ["reviewed engine input is not a JSON object"]

    active_spec = SPEC if spec is None else spec
    errors = []
    absent_rows = [indicator_id for indicator_id in MODEL if indicator_id not in rows]
    if absent_rows:
        errors.append(
            "reviewed engine input lacks model rows: " + ", ".join(absent_rows))

    for indicator_id in MODEL:
        if indicator_id in rows:
            errors.extend(_assessment_row_errors(
                indicator_id, rows[indicator_id], model_spec=active_spec))

    for indicator_id, row in rows.items():
        if indicator_id in MODEL:
            continue
        if (isinstance(indicator_id, str)
                and CANDIDATE_INPUT_PATTERN.fullmatch(indicator_id)):
            errors.extend(_assessment_row_errors(indicator_id, row, candidate=True))
        else:
            errors.append(f"unknown non-model row {indicator_id!r}")
    return errors


# ------------------------------------------------------------------ the gates
#
# Pure, so the rules that decide whether a document may be written can be tested without
# a key or a network.

def binding_gate(cites, binding, assessment=None):
    """What a chapter cited that its binding does not allow. Empty list when clean.

    The pack already withholds everything outside the binding, so a violation here means
    the writer produced an id from its own knowledge rather than from the evidence — which
    is precisely the failure the binding exists to catch.
    """
    if assessment is not None:
        binding = expand_binding(binding, assessment)
    out = []
    for kind in ("pillars", "indicators", "use_cases", "prerequisites"):
        allowed = set(binding.get(kind) or [])
        for cited in (cites.get(kind) or []):
            c = str(cited).strip()
            if c and c not in allowed:
                out.append(f"{kind[:-1]} {c}")
    return out


_NON_NUMERIC_REFERENCE = re.compile(
    r"\b(?:P\d{5,}|FY\d{4}(?:[/\-–—]\d{2,4})?"
    r"|(?:19|20)\d{2}[/\-–—]\d{2,4}"
    r"|[2345]G|(?:tranche|tier)\s*[-:]?\s*\d+)\b", re.I)
_NAMED_YEAR_REFERENCE = re.compile(
    r"\b(?:(?:[A-Z][\w'-]*\s+){1,4}Vision\s+(?:19|20)\d{2}"
    r"|Agenda\s+(?:19|20)\d{2})\b")


def _scrub_numeric_references(text):
    source = text or ""
    source = _NON_NUMERIC_REFERENCE.sub(
        lambda match: " " * len(match.group(0)), source)
    return _NAMED_YEAR_REFERENCE.sub(
        lambda match: " " * len(match.group(0)), source)


def _numbers(text):
    """Numbers as they appear in prose, without percent signs or thousands separators."""
    scrubbed = _scrub_numeric_references(text)
    return re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", scrubbed)


_NUMERIC_MENTION = re.compile(
    r"(?<![\w.])(?:(?P<sign>[+-])\s*|(?<!-)(?P<word_sign>minus|negative)\s+)?"
    r"(?P<currency>US\$|USD|EUR|GBP|\$|€|£)?\s*"
    r"(?P<level_prefix>L)?"
    r"(?P<number>(?:\d+(?:,\d{3})*(?:\.\d+)?|\.\d+))"
    r"(?P<exponent>[eE][+-]?\d+|[⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻]+)?"
    r"(?!\.\d)"
    r"(?:\s*(?P<scale>trillion|billion|million|thousand|bn|mn|m|k)\b)?"
    r"(?:\s*(?P<unit>percent\b|per\s+cent\b|%))?"
    r"(?:\s*(?P<currency_suffix>US\s+dollars?|USD|dollars?|euros?|pounds?)\b)?"
    r"(?:(?:\s*|-)(?P<measure>kg\s*/\s*ha|kilograms?\s+per\s+hectare|tonnes?|tons?|"
    r"farmers?|districts?|rows?|entries?|indicators?|people|persons?|users?|households?|"
    r"villages?|hectares?|acres?|feddans?|holdings?|sites?|records?|years?|months?|"
    r"days?|pages?|sources?|projects?|chapters?|pillars?|layers?))?(?!\w)",
    re.I,
)

_SMALL_NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "half": 0.5, "quarter": 0.25,
}
_TENS_NUMBER_WORDS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_FRACTION_NUMBER_WORDS = {
    "half": 0.5, "third": 1 / 3, "quarter": 0.25, "fourth": 0.25,
    "fifth": 0.2, "sixth": 1 / 6, "seventh": 1 / 7,
    "eighth": 0.125, "ninth": 1 / 9, "tenth": 0.1,
}
_NUMBER_WORD_ATOM = "|".join(
    list(_SMALL_NUMBER_WORDS) + list(_TENS_NUMBER_WORDS) + ["hundred"])
_NUMBER_WORD_SEQUENCE = (
    rf"(?:{_NUMBER_WORD_ATOM})"
    rf"(?:(?:[\s-]+(?:and[\s-]+)?)(?:{_NUMBER_WORD_ATOM}))*")
_FRACTION_WORD_ATOM = "|".join(_FRACTION_NUMBER_WORDS)
_SCALE_WORD_ATOM = "trillion|billion|million|thousand"
_FRACTION_FOLLOWER = (
    rf"(?=(?:\s+(?:of\b|(?:{_SCALE_WORD_ATOM})\b|percent\b|per\s+cent\b)"
    rf"|-(?:{_SCALE_WORD_ATOM})\b|\s*(?:[,.;:!?)]|$)))")
_WORD_NUMBER = re.compile(
    rf"(?<![\w-])(?:(?P<word_sign>minus|negative)\s+)?"
    rf"(?P<words>(?:"
    rf"{_NUMBER_WORD_SEQUENCE}[\s-]+and[\s-]+(?:a|an)[\s-]+"
    rf"(?:{_FRACTION_WORD_ATOM})"
    rf"|half[\s-]+a(?=\s+(?:{_SCALE_WORD_ATOM})\b)"
    rf"|(?:a|an|one)-(?:{_FRACTION_WORD_ATOM})"
    rf"|(?:a|an|one)\s+(?:{_FRACTION_WORD_ATOM}){_FRACTION_FOLLOWER}"
    rf"|(?:a|an)\s+dozen|dozen"
    rf"|(?:a|an)(?=\s+(?:{_SCALE_WORD_ATOM})\b)"
    rf"|{_NUMBER_WORD_SEQUENCE}(?:[\s-]+(?:a[\s-]+)?dozen)?))"
    rf"(?!\w)", re.I)
_WORD_SCALE = re.compile(r"(?:\s+|-)(trillion|billion|million|thousand)\b", re.I)
_WORD_CURRENCY = re.compile(
    r"\s+(US\s+dollars?|USD|dollars?|euros?|pounds?)\b", re.I)
_WORD_UNIT = re.compile(r"\s+(percent|per\s+cent)\b", re.I)
_WORD_MEASURE = re.compile(
    r"\s+(kg\s*/\s*ha|kilograms?\s+per\s+hectare|tonnes?|tons?|farmers?|"
    r"districts?|rows?|entries?|indicators?|people|persons?|users?|households?|villages?|"
    r"hectares?|acres?|feddans?|holdings?|sites?|records?|years?|months?|days?|"
    r"pages?|sources?|projects?|chapters?|pillars?|layers?)\b", re.I)
_WORD_OF_MEASURE = re.compile(
    r"\s+of\s+(?:the\s+)?(farmers?|districts?|people|persons?|users?|households?|"
    r"villages?|hectares?|acres?|feddans?|holdings?|sites?|records?|chapters?|"
    r"pillars?|layers?)\b", re.I)
_WORD_CURRENCY_BEFORE = re.compile(
    r"\b(US\s+dollars?|USD|dollars?|euros?|pounds?)\s+$", re.I)

_STRUCTURAL_MEASURES = frozenset({"chapters", "pillars", "layers"})
_NON_MEASURE_FOLLOWERS = frozenset({
    "and", "or", "but", "nor", "yet", "so", "of", "out", "in", "on", "at",
    "to", "from", "for", "with", "without", "by", "as", "than", "per", "is",
    "are", "was", "were", "be", "been", "being", "has", "have", "had", "do",
    "does", "did", "can", "could", "may", "might", "must", "shall", "should",
    "will", "would", "remain", "remains", "stand", "stands", "sit", "sits",
    "reflect", "reflects", "indicate", "indicates", "show", "shows", "suggest",
    "suggests", "signal", "signals", "place", "places", "represent", "represents",
    "overall", "nationally", "currently", "today", "approximately", "roughly",
})
_TRAILING_NOUN = re.compile(r"(?:\s+|-)(?P<noun>[A-Za-z][A-Za-z'-]*)\b")
_SUPERSCRIPT_TRANSLATION = str.maketrans(
    "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "0123456789+-")


def _consume_unknown_measure(text, end, measure, dimensioned=False):
    """Fail closed when a number is immediately relabelled with an unknown noun.

    Known measures are consumed by the main patterns.  This fallback prevents, for
    example, a score of ``3.6`` from being presented as ``3.6 gigawatts`` while retaining
    ordinary clause continuations such as ``3.6 and ...``.
    """
    if measure or dimensioned:
        return measure, end
    match = _TRAILING_NOUN.match(text, end)
    if not match:
        return "", end
    noun = match.group("noun").lower()
    # A bare score may omit the word "score", but it may not acquire any other noun.
    # Explicit dimensions (percent, currency, scale) have already made the claim
    # substantive and can carry descriptive prose such as "80 percent coverage".
    if noun in _NON_MEASURE_FOLLOWERS:
        return "", end
    return "unrecognised:" + noun, match.end()


def _parse_number_words(raw):
    normalised = re.sub(r"[\s-]+", " ", raw.lower()).strip()
    if normalised in {"a", "an"}:
        return 1.0
    if normalised == "half a":
        return 0.5
    if normalised in _FRACTION_NUMBER_WORDS:
        return float(_FRACTION_NUMBER_WORDS[normalised])
    fraction = re.fullmatch(
        rf"(?:a|an|one) ({_FRACTION_WORD_ATOM})", normalised)
    if fraction:
        return float(_FRACTION_NUMBER_WORDS[fraction.group(1)])
    mixed = re.fullmatch(
        rf"(.+?) and (?:a|an) ({_FRACTION_WORD_ATOM})", normalised)
    if mixed:
        whole = _parse_number_words(mixed.group(1))
        if whole is not None:
            return whole + _FRACTION_NUMBER_WORDS[mixed.group(2)]
    if normalised in {"dozen", "a dozen", "an dozen"}:
        return 12.0
    if normalised.endswith(" dozen"):
        multiplier = normalised[:-len(" dozen")].strip()
        if multiplier.endswith(" a"):
            multiplier = multiplier[:-2].strip()
        parsed_multiplier = _parse_number_words(multiplier)
        return parsed_multiplier * 12 if parsed_multiplier is not None else None

    total = 0
    current = 0
    for token in normalised.split():
        if token == "and":
            continue
        if token in _SMALL_NUMBER_WORDS:
            current += _SMALL_NUMBER_WORDS[token]
        elif token in _TENS_NUMBER_WORDS:
            current += _TENS_NUMBER_WORDS[token]
        elif token == "hundred":
            current = (current or 1) * 100
        else:
            return None
    total += current
    return float(total)


def _is_fraction_words(raw):
    """Whether a word phrase denotes a pure share rather than a scaled magnitude."""
    normalised = re.sub(r"[\s-]+", " ", raw.lower()).strip()
    return (normalised in _FRACTION_NUMBER_WORDS
            or bool(re.fullmatch(
                rf"(?:a|an|one) (?:{_FRACTION_WORD_ATOM})", normalised)))


def _parse_numeric_literal(raw, exponent=""):
    """Normalize decimal, scientific, and Unicode-superscript number literals."""
    if not exponent:
        return _norm_num(raw)
    try:
        # Preserve mantissa precision until after exponentiation. `_norm_num` rounds
        # ordinary displayed decimals to two places, which would turn 1.234e3 into 1230.
        base = float(str(raw).replace(",", ""))
        if exponent[:1].lower() == "e":
            power = int(exponent[1:])
            return base * (10.0 ** power)
        power = int(exponent.translate(_SUPERSCRIPT_TRANSLATION))
        return base ** power
    except (OverflowError, ValueError, ZeroDivisionError):
        # It remains a numeric claim even when its magnitude cannot be represented.
        return float("inf")


def _normalise_currency(raw):
    value = (raw or "").upper().replace(" ", "")
    if value in {"US$", "$", "USD", "USDOLLAR", "USDOLLARS", "DOLLAR", "DOLLARS"}:
        return "USD"
    if value in {"€", "EUR", "EURO", "EUROS"}:
        return "EUR"
    if value in {"£", "GBP", "POUND", "POUNDS"}:
        return "GBP"
    return value


def _normalise_measure(raw):
    value = re.sub(r"\s+", " ", (raw or "").strip().lower())
    if not value:
        return ""
    if value in {"row", "rows", "entry", "entries", "indicator", "indicators"}:
        return "rows"
    if value in {"farmer", "farmers"}:
        return "farmers"
    if value in {"district", "districts"}:
        return "districts"
    if value in {"person", "persons", "people"}:
        return "people"
    if value in {"ton", "tons", "tonne", "tonnes"}:
        return "tonnes"
    if value in {"kg / ha", "kg/ha", "kilogram per hectare",
                 "kilograms per hectare"}:
        return "kg/ha"
    if value in {"chapter", "chapters"}:
        return "chapters"
    if value in {"pillar", "pillars"}:
        return "pillars"
    if value in {"layer", "layers"}:
        return "layers"
    singular = {
        "user": "users", "household": "households", "village": "villages",
        "hectare": "hectares", "acre": "acres", "feddan": "feddans",
        "holding": "holdings", "site": "sites", "record": "records",
        "year": "year", "years": "year", "month": "months", "day": "days",
        "page": "pages",
        "source": "sources", "project": "projects",
    }
    return singular.get(value, value)


def _numeric_mentions(text):
    """Return numeric claims with their sign, currency, scale and percentage unit.

    A bare ``250`` is not the same claim as ``US$250 million``; likewise a declared
    million-dollar figure must not authorize a billion-dollar sentence.  Reference-like
    identifiers are blanked without changing offsets so they never become quantities.
    """
    source = text or ""
    scrubbed = _scrub_numeric_references(source)
    mentions = []
    for match in _NUMERIC_MENTION.finditer(scrubbed):
        exponent = match.group("exponent") or ""
        literal = match.group("number") + exponent
        number = _parse_numeric_literal(match.group("number"), exponent)
        if number is None:
            continue
        currency = _normalise_currency(
            match.group("currency") or match.group("currency_suffix"))
        scale = (match.group("scale") or "").lower()
        scale = {"bn": "billion", "mn": "million", "m": "million",
                 "k": "thousand"}.get(scale, scale)
        unit = (match.group("unit") or "").lower()
        if unit:
            unit = "percent"
        sign = "-" if (match.group("sign") == "-" or match.group("word_sign")) else "+"
        meaningful_groups = ("sign", "word_sign", "currency", "level_prefix", "number")
        mention_start = min(
            match.start(group) for group in meaningful_groups if match.group(group))
        measure = _normalise_measure(match.group("measure"))
        if match.group("level_prefix"):
            measure = "level"
        prefix = scrubbed[max(0, mention_start - 16):mention_start]
        if not measure and re.search(r"\blevel\s*$", prefix, re.I):
            measure = "level"
        suffix = scrubbed[match.end():match.end() + 60]
        if not measure and re.match(
                r"\s*(?:(?:rated|withheld|stale|bearing|measured|documented|judged|"
                r"gap|evidence|total|outcome(?:-basis)?|indicator|constituent|A1|C1|"
                r"C2|C3|C4|E1|O1)\s+){0,4}"
                r"(?:rows?|entries?|indicators?)\b", suffix, re.I):
            measure = "rows"
        if not measure:
            physical = re.match(
                r"\s*(?:(?:smallholder|named|beneficiary|rural|farmer-level|automatic|"
                r"synoptic|radio-sounding)\s+){0,3}(farmers?|districts?|villages?|"
                r"households?|hectares?|acres?|feddans?|holdings?|sites?)\b",
                suffix, re.I)
            if physical:
                measure = _normalise_measure(physical.group(1))
        if not measure and re.match(
                r"\s*(?:are\s+graded\s+|remain\s+)?"
                r"(?:Measured|Documented|Judged|Gap|rated|withheld|stale)\b",
                suffix, re.I):
            measure = "rows"
        quantity_end = match.end()
        measure, mention_end = _consume_unknown_measure(
            scrubbed, quantity_end, measure, bool(currency or scale or unit))
        mentions.append({
            "raw": literal,
            "number": -number if sign == "-" else number,
            "currency": currency,
            "scale": scale,
            "unit": unit,
            "measure": measure,
            "sign": sign,
            "start": mention_start,
            "end": mention_end,
            "quantity_end": quantity_end,
            "word": False,
        })

    # Word-form claims need the same controls as digits. In particular, spelling out
    # "twelve million" must not turn a substantive number into unchecked prose.
    for match in _WORD_NUMBER.finditer(scrubbed):
        number = _parse_number_words(match.group("words"))
        if number is None:
            continue
        fraction_words = _is_fraction_words(match.group("words"))
        start, end = match.start(), match.end()
        scale = ""
        suffix_currency = ""
        unit = ""
        scale_match = _WORD_SCALE.match(scrubbed, end)
        if scale_match:
            scale = scale_match.group(1).lower()
            end = scale_match.end()
        currency_match = _WORD_CURRENCY.match(scrubbed, end)
        if currency_match:
            suffix_currency = currency_match.group(1)
            end = currency_match.end()
        unit_match = _WORD_UNIT.match(scrubbed, end)
        if unit_match:
            unit = "percent"
            end = unit_match.end()
        elif fraction_words and not scale:
            unit = "fraction"
        measure = ""
        measure_match = _WORD_MEASURE.match(scrubbed, end)
        if measure_match:
            measure = _normalise_measure(measure_match.group(1))
            end = measure_match.end()
        elif fraction_words:
            of_measure = _WORD_OF_MEASURE.match(scrubbed, end)
            if of_measure:
                # Keep the raw quantity atomic ("a third") while retaining what the
                # fraction measures, so a bare score cannot authorize a population share.
                measure = _normalise_measure(of_measure.group(1))
        suffix = scrubbed[end:end + 60]
        if not measure and re.match(
                r"\s*(?:(?:rated|withheld|stale|bearing|measured|documented|judged|"
                r"gap|evidence|total|outcome(?:-basis)?|indicator|constituent|A1|C1|"
                r"C2|C3|C4|E1|O1)\s+){0,4}"
                r"(?:rows?|entries?|indicators?)\b", suffix, re.I):
            measure = "rows"
        if not measure:
            physical = re.match(
                r"\s*(?:(?:smallholder|named|beneficiary|rural|farmer-level|automatic|"
                r"synoptic|radio-sounding)\s+){0,3}(farmers?|districts?|villages?|"
                r"households?|hectares?|acres?|feddans?|holdings?|sites?)\b",
                suffix, re.I)
            if physical:
                measure = _normalise_measure(physical.group(1))
        if not measure and re.match(
                r"\s*(?:are\s+graded\s+|remain\s+)?"
                r"(?:Measured|Documented|Judged|Gap|rated|withheld|stale)\b",
                suffix, re.I):
            measure = "rows"
        prefix_currency = _WORD_CURRENCY_BEFORE.search(scrubbed[:start])
        currency = suffix_currency
        if prefix_currency:
            currency = prefix_currency.group(1)
            start = prefix_currency.start()
        quantity_end = end
        measure, end = _consume_unknown_measure(
            scrubbed, quantity_end, measure,
            bool(currency or scale or unit))
        mentions.append({
            "raw": source[start:end],
            "number": -number if match.group("word_sign") else number,
            "currency": _normalise_currency(currency),
            "scale": scale,
            "unit": unit,
            "measure": measure,
            "sign": "-" if match.group("word_sign") else "+",
            "start": start,
            "end": end,
            "quantity_end": quantity_end,
            "word": True,
        })
    mentions = sorted(mentions, key=lambda mention: (mention["start"], mention["end"]))
    for previous, current in zip(mentions, mentions[1:]):
        between = scrubbed[previous["end"]:current["start"]]
        paired = re.fullmatch(
            r"\s*(?:of(?:\s+(?:its|the))?|out\s+of|in|/)\s*", between, re.I)
        ranged = re.fullmatch(r"\s*[-–—]\s*", between)
        if paired or ranged:
            previous["substantive"] = True
            current["substantive"] = True
            if ranged:
                # Natural ranges put shared dimensions on either endpoint: 25-70%,
                # US$25-70 million. Both atomic claims must retain that dimension.
                for field in ("currency", "scale", "unit", "measure"):
                    values = {mention.get(field, "")
                              for mention in (previous, current)
                              if mention.get(field, "")}
                    if len(values) == 1:
                        previous[field] = current[field] = next(iter(values))
            # Natural pair syntax puts the shared noun after the denominator: "7 of 8
            # rows". Apply it to both operands so each atomic source must be rows.
            if paired and current.get("measure") and not previous.get("measure"):
                previous["measure"] = current["measure"]
    return mentions


def _mention_key(mention):
    return (mention["number"], mention["currency"], mention["scale"],
            mention["unit"], mention["sign"], mention.get("measure", ""))


def _mention_matches(mention, candidates, allow_semantic_omission=False):
    """Whether a mention is the same quantity as one of the declared candidates."""
    for candidate in candidates:
        if (mention["currency"], mention["scale"], mention["unit"], mention["sign"]) != (
                candidate["currency"], candidate["scale"], candidate["unit"],
                candidate["sign"]):
            continue
        mention_measure = mention.get("measure", "")
        candidate_measure = candidate.get("measure", "")
        if mention_measure != candidate_measure:
            # Scores are conventionally rendered as a bare number. Other semantic
            # units must be explicit so a row count cannot be relabelled as districts.
            if not (not mention_measure and (
                    candidate_measure in {"score", "year"}
                    or (allow_semantic_omission and candidate_measure))):
                continue
        if mention["number"] == candidate["number"]:
            return True
        decimals = len(mention["raw"].split(".")[1]) if "." in mention["raw"] else 0
        if decimals and round(candidate["number"], decimals) == mention["number"]:
            return True
    return False


def _norm_num(s):
    try:
        return round(float(str(s).replace(",", "").replace("%", "").strip()), 2)
    except (TypeError, ValueError):
        return None


def allowed_figures(assessment, foresight=None):
    """Every number the engine and the foresight exercise actually produced."""
    ok = set()

    def add(v):
        n = _norm_num(v)
        if n is not None:
            ok.add(n)

    for p in assessment["pillars"].values():
        for k in ("n", "rated", "held", "mean", "margin", "comp", "stale"):
            add(p.get(k))
    for l in assessment.get("layers", {}).values():
        if isinstance(l, dict):
            for k in ("n", "rated", "mean"):
                add(l.get(k))
    for m in assessment["matrix"].values():
        for k in ("n_bearing", "mean_readiness", "mean_need", "mean_outcome", "mean_driven"):
            add(m.get(k))
    for v in assessment["counts"].values():
        add(v)
    add(assessment.get("rated"))
    add(assessment.get("held"))
    for i in assessment["indicators"].values():
        add(i.get("level"))
        add(i.get("value"))
        add(i.get("year"))
    for m in ((foresight or {}).get("milestones") or []):
        add(m.get("target_level"))
        add(m.get("target_year"))
    return ok


def _rounds_to(n, raw, allowed):
    """Whether `n` is an allowed figure written to fewer decimals.

    A chapter that writes the A1 mean of 2.71 as "2.7" has not fabricated anything, and
    blocking the document for it would train everyone to loosen the gate. A figure that
    rounds to a real one is still traceable to a real one. Matching is at the precision
    the prose actually used, so "3" does not silently stand for 2.71.
    """
    decimals = len(raw.split(".")[1]) if "." in raw else 0
    return any(round(a, decimals) == n for a in allowed)


def _ordinary(n):
    """Numbers a sentence may carry without the engine having produced them.

    Small counts ("three pillars", "the eleven chapters") and calendar years. Deliberately
    narrow: anything wider would let a fabricated percentage through as ordinary prose.
    """
    if n is None:
        return False
    # A past/current year can identify a publication or observation. A future year is a
    # target and therefore a substantive planning claim that must be declared.
    if n == int(n) and 1900 <= n <= ASSESSMENT_YEAR:
        return True
    return False


def _ordinary_mention(mention, prose=""):
    """Allow linguistic enumerations and years only in genuine date contexts."""
    if (mention["currency"] or mention["scale"] or mention["unit"]
            or mention["sign"] == "-"
            or mention.get("substantive")):
        return False
    number = mention["number"]
    if (mention.get("word") and mention.get("measure") in _STRUCTURAL_MEASURES
            and number == int(number) and 0 <= number <= 11):
        return True
    if not _ordinary(number):
        return False
    if (mention.get("measure") and
            not str(mention.get("measure")).startswith("unrecognised:")):
        return False

    start = mention.get("start")
    end = mention.get("quantity_end", mention.get("end"))
    if start is None or end is None or not prose:
        return False
    before = prose[max(0, start - 60):start]
    after = prose[end:end + 40]
    # A four-digit magnitude must not inherit the calendar-year exemption merely by
    # looking like a year.
    if re.match(
            r"\s*(?:tonnes?|tons?|farmers?|people|persons?|users?|households?|"
            r"districts?|hectares?|acres?|sites?|villages?|devices?|records?)\b",
            after, re.I):
        return False
    if re.search(
            r"(?:\b(?:in|during|since|from|until|through|by|before|after|circa|dated|"
            r"for|and|or)\s+"
            r"|\bas\s+of\s+|\b(?:published|issued|recorded|observed|reported|measured|"
            r"collected|updated)\s+(?:in|during|for)\s+)$",
            before, re.I):
        return True
    if re.search(
            r"\b(?:law|act|decree|strategy|report|survey|census|plan|budget|publication|"
            r"edition|dataset|index|assessment|mission|cycle|study)\s+$", before, re.I):
        return True
    if re.match(
            r"\s+(?:(?:[\w-]+\s+){0,3})?(?:law|act|decree|strategy|report|survey|"
            r"census|plan|budget|edition|dataset|index|assessment|mission|cycle|study)\b",
            after, re.I):
        return True
    return bool(re.search(r"\(\s*$", before) and re.match(r"\s*\)", after))


# A figure the assessment states as a pair or as a level, rather than as one number:
# "5 of 10" is a coverage denominator and "level 3" is a rung. Both come straight out of
# the pack, and both used to be unparseable — so the writer quoting the evidence exactly
# was marked as claiming something the engine did not produce. Of the 95 figures the first
# Egypt roadmap was blocked over, 74 were of this shape.
_PAIR = re.compile(r"^\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:of|/|out of)\s*"
                   r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*$", re.I)
_RUNG = re.compile(r"^\s*(?:level|band|rung)\s*(\d+(?:\.\d+)?)\s*$", re.I)


def _composite_supported(raw, allowed):
    """Whether a composite figure is fully supported. None when it is not a composite."""
    if raw is None:
        return None
    text = str(raw)
    m = _PAIR.match(text)
    if m:
        a, b = _norm_num(m.group(1)), _norm_num(m.group(2))
        return a is not None and b is not None and a in allowed and b in allowed
    m = _RUNG.match(text)
    if m:
        n = _norm_num(m.group(1))
        return n is not None and n in allowed
    return None


def reference_ids(prose, known_ids, cited_ids=()):
    """Numbers in the prose that are references to rows, not claims about the country.

    The roadmap names a row the way the instrument does — "(3.11)" after the indicator's
    name, or "indicator 3.11". Read as a quantity, 3.11 is a number the engine never
    produced, and 86 of the 114 numbers the first Egypt roadmap was blocked over were
    references of exactly this kind.

    Matched in the shapes a reference actually takes, so a real figure that happens to
    equal an id — a pillar mean of 3.11, written as "mean 3.11" — is still checked.

    A chapter also declares what it cites. Where prose names an id the chapter has cited,
    that is a reference on the chapter's own account, which is firmer than any reading of
    the surrounding words: the roadmap writes "— 3.11" and "; 3.3" as often as it writes
    "(3.11)", and no amount of context matching separates those from a quantity.
    """
    if not prose or not known_ids:
        return set()
    out = {str(c).strip() for c in (cited_ids or [])
           if str(c).strip() in known_ids and str(c).strip() in prose}
    for m in re.finditer(r"[(\[§]\s*([0-9]+\.[0-9]+[A-Za-z-]*)\s*[)\]]?"
                         r"|(?:indicator|prerequisite|row|indicators|rows)\s+"
                         r"([0-9]+\.[0-9]+[A-Za-z-]*)", prose, re.I):
        tok = m.group(1) or m.group(2)
        if tok in known_ids:
            out.add(tok)
    return out


def prose_binding_gate(prose, allowed_citations):
    """References made in prose that the response omitted from its cites arrays."""
    outside = []
    indicator_refs = reference_ids(prose, KNOWN_IDS)
    allowed_rows = (set(allowed_citations.get("indicators") or [])
                    | set(allowed_citations.get("prerequisites") or []))
    for indicator_id in sorted(indicator_refs):
        if indicator_id not in allowed_rows:
            outside.append(f"prose indicator {indicator_id}")

    for kind, candidates in (
            ("pillar", MODEL and set(SPEC.get("pillars") or [])
             or set()),
            ("use_case", set((SPEC.get("use_cases") or {}).keys()))):
        # Older model revisions do not expose these as top-level maps; the assessment
        # outline still names the full vocabulary, so derive it there as a fallback.
        if not candidates:
            binding_key = "pillars" if kind == "pillar" else "use_cases"
            candidates = {value for chapter in OUTLINE
                          for value in chapter["binding"].get(binding_key, [])
                          if value != "*"}
        binding_key = "pillars" if kind == "pillar" else "use_cases"
        allowed = set(allowed_citations.get(binding_key) or [])
        for candidate in sorted(candidates, key=len, reverse=True):
            if re.search(rf"(?<![\w.]){re.escape(candidate)}(?![\w.])", prose or ""):
                if candidate not in allowed:
                    outside.append(f"prose {kind} {candidate}")
    return outside


def _prose_sentences(prose):
    """Sentence-sized claim spans, preserving the exact text returned by the writer."""
    return [part.strip() for part in re.split(
        r"(?<=[.!?])(?:[ \t]+|\n+)", (prose or "").strip()) if part.strip()]


def _proposal_claim_is_framed(sentence):
    """Recognize an explicit recommendation without treating an embedded fact as one."""
    text = (sentence or "").strip()
    if re.search(
            r"\b(?:should|must|propos(?:e|es)|recommend(?:s)?|assum(?:e|es)|sets?|"
            r"adopts?)\s+(?:to\s+)?(?:note|report|state|claim|observe|recognize|"
            r"acknowledge|study)"
            r"\b.*\b(?:that|claiming)\b",
            text, re.I):
        return False
    if re.search(
            r"\bshould\s+be\s+(?:recognized|regarded|understood|noted|reported|"
            r"acknowledged)\s+as\b",
            text, re.I):
        return False
    first_clause = re.split(r"[;:]|\bthat\b", text, maxsplit=1, flags=re.I)[0]
    if re.search(
            r"\b(?:should|must|propos(?:e|es)|recommend(?:s)?|assum(?:e|es)|sets?|"
            r"adopts?|allocates?|proposed|illustrative|indicative)\b",
            first_clause, re.I):
        return True
    return bool(re.search(
        r"\b(?:is|are|remains?|remain)\s+(?:an?\s+)?(?:explicit\s+)?(?:illustrative|"
        r"indicative|proposed|planning\s+assumptions?|subject\s+to)\b",
        text, re.I))


def claim_provenance_gate(prose, claims, allowed_origins, require_all=False,
                          prescriptive=False):
    """Classify every prose sentence and bind evidence to exact in-pack origins."""
    errors = []
    sentences = _prose_sentences(prose)
    sentence_set = set(sentences)
    by_text = {}
    for index, claim in enumerate(claims or []):
        text = str(claim.get("text") or "").strip()
        by_text.setdefault(text, []).append(claim)
        if text not in sentence_set:
            errors.append(f"claim {index} is not an exact prose sentence")
        refs = claim.get("source_refs") or []
        basis = claim.get("basis")
        if basis == "evidence":
            if not refs:
                errors.append(f"claim {index} has no source origin")
            outside = [ref for ref in refs if ref not in allowed_origins]
            if outside:
                errors.append(f"claim {index} origins outside pack: {', '.join(outside)}")
        elif basis == "proposal":
            if not prescriptive:
                errors.append(f"claim {index} is a proposal in a diagnostic chapter")
            if refs:
                errors.append(f"claim {index} proposal carries evidence origins")
            if not _proposal_claim_is_framed(text):
                errors.append(f"claim {index} is not explicitly framed as a proposal")
        else:
            errors.append(f"claim {index} has invalid basis")
    if require_all:
        for sentence in sentences:
            bound = by_text.get(sentence) or []
            if not bound:
                label = ("unbound diagnostic sentence" if not prescriptive
                         else "unbound prose sentence")
                errors.append(f"{label}: {sentence[:80]}")
            elif len(bound) > 1:
                errors.append(f"diagnostic sentence declared more than once: {sentence[:80]}")
    return errors


def _origin_candidates(source_refs, allowed_quantities):
    """Numeric mentions exposed by the exact origin ids a figure declares."""
    candidates = []
    for source_ref in source_refs or []:
        for key in allowed_quantities.get(source_ref, []):
            number, currency, scale, unit, sign, *semantic = key
            candidates.append({
                "raw": str(abs(number)), "number": number, "currency": currency,
                "scale": scale, "unit": unit, "sign": sign,
                "measure": semantic[0] if semantic else "",
            })
    return candidates


def _mentions_supported(mentions, candidates):
    if not mentions:
        return False
    if len(mentions) >= 2 and all(mention.get("substantive") for mention in mentions):
        explicit = {mention.get("measure", "") for mention in mentions} - {""}
        measures = explicit or {candidate.get("measure", "") for candidate in candidates}
        if len(explicit) > 1:
            return False
        for measure in measures:
            same_semantic = [candidate for candidate in candidates
                             if candidate.get("measure", "") == measure]
            if same_semantic and all(_mention_matches(
                    dict(mention, measure=measure), same_semantic)
                    for mention in mentions):
                for mention in mentions:
                    mention["measure"] = measure
                return True
        return False
    if all(_mention_matches(mention, candidates) for mention in mentions):
        return True
    return False


def _calculation_supported(figure, allowed_quantities):
    """Validate a small, auditable arithmetic claim from source-backed inputs."""
    refs = figure.get("source_refs") or []
    operation = figure.get("operation")
    candidates = _origin_candidates(refs, allowed_quantities)
    input_mentions = [mention for value in (figure.get("inputs") or [])
                      for mention in _numeric_mentions(value)]
    outputs = _numeric_mentions(figure.get("value") or "")
    if (not refs or len(input_mentions) != 2 or len(outputs) != 1
            or operation not in {"sum", "difference", "product", "ratio", "percentage"}
            or not str(figure.get("rationale") or "").strip()
            or not _mentions_supported(input_mentions, candidates)):
        return False

    a_mention, b_mention = input_mentions
    output_mention = outputs[0]
    a, b = a_mention["number"], b_mention["number"]
    a_dimension = (a_mention["currency"], a_mention["scale"], a_mention["unit"],
                   a_mention.get("measure", ""))
    b_dimension = (b_mention["currency"], b_mention["scale"], b_mention["unit"],
                   b_mention.get("measure", ""))
    output_dimension = (output_mention["currency"], output_mention["scale"],
                        output_mention["unit"], output_mention.get("measure", ""))
    dimensionless = ("", "", "", "")

    if operation in {"sum", "difference"}:
        if a_dimension != b_dimension or output_dimension != a_dimension:
            return False
        expected = a + b if operation == "sum" else a - b
    elif operation == "product":
        # Compound units need a richer dimensional model. Until that is explicit in the
        # contract, only a dimensionless product is safe to certify.
        if a_dimension != dimensionless or b_dimension != dimensionless \
                or output_dimension != dimensionless:
            return False
        expected = a * b
    elif operation in {"ratio", "percentage"}:
        if not b or a_dimension != b_dimension:
            return False
        required_output = (dimensionless if operation == "ratio"
                           else ("", "", "percent", ""))
        if output_dimension != required_output:
            return False
        expected = a / b
        if operation == "percentage":
            expected *= 100
    else:
        return False

    output = output_mention["number"]
    text = str(figure.get("value") or "").lower()
    if re.search(r"\b(?:more than|over|above|at least)\b", text):
        return expected >= output
    if re.search(r"\b(?:less than|under|below|at most)\b", text):
        return expected <= output
    decimals = len(outputs[0]["raw"].split(".")[1]) if "." in outputs[0]["raw"] else 0
    return round(expected, decimals) == output


def _figure_supported(figure, allowed, allowed_quantities, prescriptive):
    """Whether one figure has a valid, explicit evidence or proposal basis."""
    raw = figure.get("value")
    if allowed_quantities is None:
        composite = _composite_supported(raw, allowed)
        if composite is not None:
            return composite
    mentions = _numeric_mentions(str(raw or ""))
    if not mentions:
        return False

    # The pure helper predates typed origins. Production always supplies the structured
    # map; retaining the numeric-only path keeps the helper useful to old callers while
    # the public CLI remains strict.
    if allowed_quantities is None:
        tokens = [(mention["raw"], mention["number"]) for mention in mentions]
        token_supported = all(
            number in allowed or _rounds_to(number, token, allowed)
            for token, number in tokens)
        return token_supported

    basis = str(figure.get("basis") or "")
    operation = str(figure.get("operation") or "")
    refs = figure.get("source_refs") or []
    if any(ref not in allowed_quantities for ref in refs):
        return False
    if basis in ("evidence", "benchmark"):
        return operation == "none" and bool(refs) and _mentions_supported(
            mentions, _origin_candidates(refs, allowed_quantities))
    if basis == "calculation":
        return _calculation_supported(figure, allowed_quantities)
    if basis == "planning_assumption":
        return (operation == "none" and prescriptive and not refs
                and len(str(figure.get("rationale") or "").strip()) >= 10)
    return False


def fidelity_check(prose, figures, allowed, known_ids=(), cited_ids=(),
                   allowed_quantities=None, prescriptive=False):
    """Which claimed figures the engine supports, and what the prose says beyond them.

    Returns (supported, unsupported, stray). `stray` is numbers in the prose that are
    neither a claimed figure nor ordinary — a fabricated figure the writer did not even
    declare, which is the shape this check most has to catch.
    """
    supported, unsupported = [], []
    claimed_spans = []
    claimed_legacy = []

    def declared_spans(value):
        text = str(value or "")
        if not text.strip():
            return []
        pattern = re.escape(text.strip()).replace(r"\ ", r"\s+")
        if text.strip()[0].isalnum() or text.strip()[0] == ".":
            pattern = r"(?<![\w.])" + pattern
        if text.strip()[-1].isalnum():
            pattern += r"(?!\w)"
        return [(match.start(), match.end())
                for match in re.finditer(pattern, prose or "", re.I)]

    def assumption_is_framed(spans):
        for start, end in spans:
            sentence_start = max(
                (prose or "").rfind(mark, 0, start) for mark in ".!?\n") + 1
            endings = [(prose or "").find(mark, end) for mark in ".!?\n"]
            endings = [position for position in endings if position >= 0]
            sentence_end = min(endings) if endings else len(prose or "")
            context = (prose or "")[sentence_start:sentence_end]
            local_start = start - sentence_start
            local_end = end - sentence_start
            before = context[:local_start]
            after = context[local_end:]
            # The cue must directly govern this figure.  A keyword-window is not enough:
            # "proposes to report that the country currently has ..." still contains a
            # factual assertion.  Certify only a deliberately narrow surface grammar:
            # a proposal/assumption verb immediately before the value, or an explicit
            # planning qualifier on the noun phrase that ends at the value.
            before_scopes_figure = bool(re.search(
                r"(?:\b(?:propos(?:e|es)|assum(?:e|es)|sets?|adopts?|allocates?|targets?)"
                r"\s+(?:an?\s+)?"
                r"|\b(?:proposed|assumed|illustrative|indicative|planning|target(?:ed)?)"
                r"\s+(?:[A-Za-z][\w-]*\s+){0,4}(?:of|at|for|by|is|are|:)\s*)$",
                before, re.I))
            after_labels_figure = bool(re.match(
                r"\s+(?:is|are|as)\s+(?:an?\s+)?(?:planning\s+assumptions?|proposal|"
                r"proposed|illustrative|indicative|target)\b",
                after, re.I))
            if not (before_scopes_figure or after_labels_figure):
                return False
        return True

    for f in figures or []:
        raw = f.get("value")
        traceable = _figure_supported(f, allowed, allowed_quantities, prescriptive)
        spans = declared_spans(raw) if allowed_quantities is not None else []
        if (traceable and f.get("basis") == "planning_assumption"
                and allowed_quantities is not None):
            traceable = bool(spans) and assumption_is_framed(spans)
        # The production response contract says the value is copied exactly from prose.
        # Enforcing that here prevents one declared component of "7 of 8" from silently
        # authorizing an unrelated standalone 7 elsewhere in the chapter.
        if traceable and (allowed_quantities is None or spans):
            supported.append(f)
            claimed_spans.extend(spans)
            if allowed_quantities is None:
                claimed_legacy.extend(_numeric_mentions(str(raw or "")))
        else:
            unsupported.append(f)

    refs = reference_ids(prose, set(known_ids), cited_ids)
    stray = []
    for mention in _numeric_mentions(prose):
        raw = mention["raw"]
        if raw in refs:
            continue
        if (any(start <= mention["start"] and mention["end"] <= end
                for start, end in claimed_spans)
                or _mention_matches(mention, claimed_legacy)
                or _ordinary_mention(mention, prose)):
            continue
        stray.append(raw)
    return supported, unsupported, sorted(set(stray))


def qc_checks(doc):
    """The emit-blocking gate (E5). Returns [(name, ok, detail)]."""
    chapters = doc["chapters"]
    checks = []

    def add(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    missing_banner = [c["n"] for c in chapters if not c.get("provenance")]
    add("B1 every chapter carries a provenance banner", not missing_banner,
        f"missing on {', '.join(missing_banner)}" if missing_banner else "")

    outside = [f"{c['n']}: {', '.join(c['cited_outside_binding'])}"
               for c in chapters if c.get("cited_outside_binding")]
    add("B2 every citation and prose claim stays within its binding",
        not outside, "; ".join(outside))

    mislabelled = [c["n"] for c in chapters
                   if c["kind"] == "prescriptive" and c.get("status") != "proposed, not evidenced"]
    add("B3 no prescriptive chapter renders as evidenced", not mislabelled,
        f"chapters {', '.join(mislabelled)}" if mislabelled else "")

    # Fidelity is an evidence test, and it binds on the chapters that make claims about
    # the country. Chapters three to ten propose an investment programme: a budget line,
    # a district count, a target year. Those figures are proposals, and the engine could
    # not have produced them — holding them to "every number traces to the assessment"
    # asks a proposal to be evidence, which is the one thing chapter three to ten is
    # marked as not being. On the first Egypt roadmap the split was 97% on the diagnostic
    # chapters against 52% on the prescriptive ones, and the global rate of 53% was read
    # as the document being unsupported when its evidence chapters were nearly clean.
    #
    # What protects the prescriptive chapters is B3, which fails if one of them renders as
    # evidenced, and the banner each carries. Their fidelity is reported, never blocking.
    ev = [c for c in chapters if c["kind"] != "prescriptive"]
    ev_claimed = sum(len(c.get("figures") or []) for c in ev)
    ev_unsup = sum(len(c.get("unsupported_figures") or []) for c in ev)
    ev_rate = (ev_claimed - ev_unsup) / ev_claimed if ev_claimed else 1.0
    add(f"B4 evidence-chapter figure fidelity at or above {FIDELITY_FLOOR:.0%}",
        ev_rate >= FIDELITY_FLOOR,
        f"{ev_rate:.1%} — {ev_unsup} unsupported of {ev_claimed} claimed in the "
        f"{len(ev)} evidence chapters")

    pr = [c for c in chapters if c["kind"] == "prescriptive"]
    pr_claimed = sum(len(c.get("figures") or []) for c in pr)
    pr_assumptions = sum(
        1 for chapter in pr for figure in (chapter.get("figures") or [])
        if figure.get("basis") == "planning_assumption")
    # Reported so a reader can see how much of the programme is an explicit assumption.
    checks.append((f"      prescriptive chapters declare {pr_assumptions} planning "
                   f"assumptions, of {pr_claimed} figures", True, ""))

    strays = [f"{c['n']}: {', '.join(c['stray_numbers'][:4])}"
              for c in chapters if c.get("stray_numbers")]
    invalid_figures = [f"{c['n']}: {', '.join(str(v) for v in c['unsupported_figures'][:4])}"
                       for c in chapters if c.get("unsupported_figures")]
    cache_errors = [f"{c['n']}: cached response hash changed"
                    for c in chapters if c.get("cache_integrity_error")]
    b5_detail = "; ".join(strays + invalid_figures + cache_errors)
    add("B5 no undeclared numbers in the prose",
        not strays and not invalid_figures and not cache_errors,
        b5_detail)

    expected_ids = [str(chapter["n"]) for chapter in OUTLINE]
    actual_ids = [str(chapter.get("n", "")) for chapter in chapters]
    expected_by_id = {str(chapter["n"]): chapter for chapter in OUTLINE}
    malformed = []
    for chapter in chapters:
        chapter_id = str(chapter.get("n", ""))
        expected = expected_by_id.get(chapter_id)
        if not expected:
            malformed.append(f"unexpected {chapter_id or '<blank>'}")
            continue
        if chapter.get("title") != expected["title"] or chapter.get("kind") != expected["kind"]:
            malformed.append(f"{chapter_id} metadata")
        if not str(chapter.get("prose") or "").strip():
            malformed.append(f"{chapter_id} empty prose")
        if chapter_id == "A" and not chapter.get("annex"):
            malformed.append("A missing deterministic annex")
    b6_ok = actual_ids == expected_ids and not malformed
    detail = f"ids {actual_ids!r}; expected {expected_ids!r}"
    if malformed:
        detail += "; " + ", ".join(malformed)
    add("B6 every chapter of the outline is present", b6_ok, detail)

    return checks


# ------------------------------------------------------------------ the pack

# A binding may say ["*"] for "every one of these". Both the pack and the gate have to
# read it the same way, so it is expanded once here rather than interpreted twice.
#
# Neither expanded it before. The pack looked up an id called "*", found nothing, and
# handed chapters bound to every prerequisite no prerequisite evidence at all; the gate
# then compared each cited id against the literal set {"*"} and reported every one of
# them as a citation outside the binding. So the chapters most entitled to the evidence
# were the ones starved of it, and were then failed for going to look elsewhere.
_KINDS = {
    "pillars": lambda a: list(a.get("pillars") or {}),
    "indicators": lambda a: list(a.get("indicators") or {}),
    "use_cases": lambda a: list(a.get("matrix") or {}),
    "prerequisites": lambda a: list(a.get("prereq") or {}),
}


def expand_binding(binding, assessment):
    """The binding with any "*" replaced by every id of that kind."""
    out = dict(binding)
    for kind, all_ids in _KINDS.items():
        vals = list(out.get(kind) or [])
        if any(str(v).strip() == "*" for v in vals):
            out[kind] = all_ids(assessment)
    return out


def pack_for(chapter, assessment, scans, foresight):
    """The evidence text and typed citations a chapter may use."""
    b = expand_binding(chapter["binding"], assessment)
    out = []
    allowed_numbers = set()
    allowed_quantities = {}
    allowed = {kind: list(b.get(kind) or [])
               for kind in ("pillars", "indicators", "use_cases", "prerequisites")}

    def permit(kind, values):
        for value in values:
            if value and value not in allowed[kind]:
                allowed[kind].append(value)

    def permit_indicator_ids(values):
        values = [value for value in values if value]
        permit("indicators", values)
        permit("prerequisites", [value for value in values
                                  if value in assessment.get("prereq", {})])

    def permit_prerequisite_ids(values):
        values = [value for value in values if value]
        permit("prerequisites", values)
        permit("indicators", values)
        for value in values:
            kind = (assessment.get("prereq", {}).get(value) or {}).get("kind", "")
            if kind.startswith("UC:"):
                permit("use_cases", kind.split(":", 1)[1].split(","))

    def permit_quantity(origin, mention):
        key = _mention_key(mention)
        allowed_quantities.setdefault(origin, set()).add(key)
        allowed_numbers.add(mention["number"])

    def permit_number(origin, value, *, currency="", scale="", unit="", measure=""):
        if isinstance(value, bool):
            return
        number = _norm_num(value)
        if number is not None:
            permit_quantity(origin, {
                "raw": str(abs(number)), "number": number, "currency": currency,
                "scale": scale, "unit": unit,
                "measure": measure, "sign": "-" if number < 0 else "+",
            })

    def field_measure(path):
        field = str(path[-1]).lower() if path else ""
        parent = str(path[-2]).lower() if len(path) > 1 else ""
        if field in {"year", "target_year", "assessment_year"}:
            return "year"
        if field in {"level", "target_level"}:
            return "level"
        if (field in {"n", "rated", "held", "stale", "n_bearing"}
                or parent in {"comp", "counts", "basis"}
                or field in {"measured", "documented", "judged"}):
            return "rows"
        if (field.startswith("mean") or field in {"margin", "gap"}
                or (len(path) == 1 and str(path[0]) in
                    {"Foundation", "Enablers", "Transformation", "Outcomes"})):
            return "score"
        return ""

    def indicator_value_dimensions(indicator_id):
        name = str((MODEL.get(indicator_id) or {}).get("name") or "")
        if re.search(r"\(%\)|\bpercent\b", name, re.I):
            return {"unit": "percent"}
        if re.search(r"\bUSD\b|US\$", name, re.I):
            return {"currency": "USD"}
        if re.search(r"kg\s*/\s*ha|kg\s+per\s+hectare", name, re.I):
            return {"measure": "kg/ha"}
        return {"measure": "score"}

    def permit_numeric_fields(origin, value, path=(), resolver=None):
        exposed = []
        if isinstance(value, dict):
            for key, nested in value.items():
                exposed.extend(permit_numeric_fields(
                    origin, nested, path + (key,), resolver=resolver))
        elif isinstance(value, (list, tuple)):
            for index, nested in enumerate(value):
                exposed.extend(permit_numeric_fields(
                    origin, nested, path + (index,), resolver=resolver))
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            exact = origin + ":" + ":".join(str(part) for part in path)
            dimensions = ({"measure": field_measure(path)} if path else {})
            if resolver:
                dimensions.update(resolver(path) or {})
            permit_number(exact, value, **dimensions)
            exposed.append((exact, value))
        return exposed

    def permit_statement_numbers(origin, statement):
        exposed = []
        for index, mention in enumerate(_numeric_mentions(statement or "")):
            exact = f"{origin}:number:{index}"
            permit_quantity(exact, mention)
            exposed.append((exact, mention["raw"]))
        return exposed

    def origin_legend(exposed):
        return "; ".join(f"[[origin:{origin}]]={value}"
                         for origin, value in exposed)

    permit_indicator_ids(b.get("indicators") or [])
    permit_prerequisite_ids(b.get("prerequisites") or [])

    if b.get("pillars"):
        out.append("PILLARS:")
        for pid in b["pillars"]:
            p = assessment["pillars"].get(pid)
            if p:
                exposed = []
                for field in ("mean", "rated", "n", "held", "stale"):
                    exact = f"pillar:{pid}:{field}"
                    permit_number(exact, p.get(field), measure=field_measure((field,)))
                    exposed.append((exact, p.get(field)))
                out.append(f"  {pid}: mean {p['mean']} ({p['band']}), {p['rated']} of "
                           f"{p['n']} rated, {p['held']} withheld, {p['stale']} stale; "
                           f"{origin_legend(exposed)}")

    if b.get("indicators"):
        out.append("INDICATORS:")
        for iid in b["indicators"]:
            i = assessment["indicators"].get(iid)
            if i:
                exposed = []
                for field in ("value", "level", "year"):
                    exact = f"indicator:{iid}:{field}"
                    dimensions = (indicator_value_dimensions(iid) if field == "value"
                                  else {"measure": field_measure((field,))})
                    if i.get("cls") != "Gap":
                        permit_number(exact, i.get(field), **dimensions)
                        exposed.append((exact, i.get(field)))
                out.append(f"  {iid} {MODEL.get(iid, {}).get('name', '')}: value {i['value']}, "
                           f"level {i['level']}, {i['cls']}, {i['year']}, source {i['src']} "
                           f"{origin_legend(exposed)}")

    if b.get("use_cases"):
        out.append("USE-CASE READINESS:")
        for uc in b["use_cases"]:
            m = assessment["matrix"].get(uc)
            if m:
                exposed = []
                for field in ("mean_readiness", "mean_need", "mean_outcome",
                              "mean_driven", "n_bearing"):
                    exact = f"use_case:{uc}:{field}"
                    permit_number(exact, m.get(field), measure=field_measure((field,)))
                    if _norm_num(m.get(field)) is not None and not isinstance(
                            m.get(field), bool):
                        exposed.append((exact, m.get(field)))
                out.append(f"  {uc}: {m['status']} — {m['why']} (readiness "
                           f"{m['mean_readiness']}, need {m['mean_need']}, "
                           f"{m['n_bearing']} bearing rows); {origin_legend(exposed)}")
                rendered = json.dumps(m)
                permit_prerequisite_ids([
                    pid for pid in assessment.get("prereq", {}) if pid in rendered
                ])

    if b.get("prerequisites"):
        out.append("PREREQUISITES:")
        for pid in b["prerequisites"]:
            pr = assessment["prereq"].get(pid)
            if pr:
                out.append(f"  {pid} {pr['name']}: {pr['status']} ({pr['kind']})")

    for d in (b.get("derived") or []):
        if d == "constraints":
            constraints = assessment.get("constraints") or []
            origin = "derived:constraints"
            keyed_constraints = {item.get("id", str(index)): item
                                 for index, item in enumerate(constraints)}
            exposed = permit_numeric_fields(origin, keyed_constraints)
            out.append(f"CONSTRAINTS: {json.dumps(constraints)}; "
                       f"NUMERIC ORIGINS: {origin_legend(exposed)}")
            permit_indicator_ids([item.get("id") for item in constraints])
            permit("pillars", [item.get("pillar") for item in constraints])
        elif d == "leapfrog":
            leapfrog = assessment.get("leapfrog")
            origin = "derived:leapfrog"
            exposed = permit_numeric_fields(origin, leapfrog)
            out.append(f"LEAPFROG: {json.dumps(leapfrog)}; NUMERIC ORIGINS: "
                       f"{origin_legend(exposed)}")
        elif d == "kpi_baseline":
            kpi = assessment.get("kpi") or []
            origin = "derived:kpi_baseline"
            keyed_kpi = {item.get("id", str(index)): item
                         for index, item in enumerate(kpi)}

            def kpi_dimensions(path):
                if len(path) >= 2 and path[-1] == "value":
                    return indicator_value_dimensions(str(path[0]))
                return {"measure": field_measure(path)}

            exposed = permit_numeric_fields(origin, keyed_kpi, resolver=kpi_dimensions)
            # Index bases such as "2014-16=100" are semantic metadata in the vetted
            # model name, not arbitrary prose. Permit that base explicitly.
            for item in kpi:
                exposed.extend(permit_statement_numbers(
                    f"{origin}:{item.get('id')}:name", item.get("name")))
            out.append(f"KPI BASELINE: {json.dumps(kpi)}; NUMERIC ORIGINS: "
                       f"{origin_legend(exposed)}")
            permit_indicator_ids([item.get("id") for item in kpi])
        elif d == "pillar_profile":
            origin = "derived:pillar_profile"
            exposed = permit_numeric_fields(origin, assessment["pillars"])
            out.append(f"PILLAR PROFILE: {json.dumps(assessment['pillars'])}; "
                       f"NUMERIC ORIGINS: {origin_legend(exposed)}")
            permit("pillars", assessment["pillars"])
        elif d == "layer_profile":
            layers = assessment.get("layers")
            origin = "derived:layer_profile"
            exposed = permit_numeric_fields(origin, layers)
            out.append(f"LAYER PROFILE: {json.dumps(layers)}; NUMERIC ORIGINS: "
                       f"{origin_legend(exposed)}")
        elif d == "matrix":
            origin = "derived:matrix"
            exposed = permit_numeric_fields(origin, assessment["matrix"])
            out.append(f"MATRIX: {json.dumps(assessment['matrix'])}; NUMERIC ORIGINS: "
                       f"{origin_legend(exposed)}")
            permit("use_cases", assessment["matrix"])
            permit_prerequisite_ids([
                pid for matrix in assessment["matrix"].values()
                for pid, _status in (matrix.get("prereqs") or [])
            ])
            rendered = json.dumps(assessment["matrix"])
            permit_prerequisite_ids([
                pid for pid in assessment.get("prereq", {}) if pid in rendered
            ])
        elif d == "prerequisites":
            out.append(f"ALL PREREQUISITES: {json.dumps(assessment['prereq'])}")
            permit_prerequisite_ids(assessment["prereq"])
        elif d == "evidence_ledger":
            origin = "derived:evidence_ledger"
            ledger_numbers = {
                "counts": assessment["counts"],
                "rated": assessment.get("rated"),
                "held": assessment.get("held"),
            }
            exposed = permit_numeric_fields(origin, ledger_numbers)
            out.append(f"EVIDENCE COUNTS: "
                       f"{json.dumps(assessment['counts'])}, {assessment['rated']} rated, "
                       f"{assessment['held']} withheld; NUMERIC ORIGINS: "
                       f"{origin_legend(exposed)}")
        elif d == "register":
            out.append("SOURCE REGISTER: available in the annexes")
        elif d.startswith("foresight."):
            key = d.split(".", 1)[1]
            value = (foresight or {}).get(key)
            origin = f"foresight:{key}"
            if (isinstance(value, list) and all(
                    isinstance(item, dict) and item.get("indicator_id")
                    for item in value)):
                numeric_value = {item["indicator_id"]: item for item in value}
            else:
                numeric_value = value
            exposed = permit_numeric_fields(origin, numeric_value)
            out.append(f"FORESIGHT {key.upper()}: {json.dumps(value)}; "
                       f"NUMERIC ORIGINS: {origin_legend(exposed)}")
            records = value if isinstance(value, list) else [value]
            permit_indicator_ids([
                item.get("indicator_id") for item in records
                if isinstance(item, dict) and item.get("indicator_id") in MODEL
            ])

    country_findings = [(index, finding) for index, finding in enumerate(
        (scans or {}).get("country_findings", []))
        if str(finding.get("chapter")) == str(chapter["n"])]
    if country_findings:
        out.append("WHAT THE COUNTRY HAS PUBLISHED:")
        for index, s in country_findings:
            origin = f"scan:country_findings:{index}"
            exposed = permit_statement_numbers(origin, s.get("statement"))
            out.append(f"  - {s['statement']} [{s['source_name']}, {s['tier']}; "
                       f"numeric origins: {origin_legend(exposed)}]")

    # International precedent reaches the DAR and nothing else (E2), and only the
    # prescriptive chapters it was gathered for.
    if chapter["kind"] == "prescriptive":
        pointers = [(index, pointer) for index, pointer in enumerate(
            (scans or {}).get("international_pointers", []))
            if str(pointer.get("chapter")) == str(chapter["n"])]
        for index, s in pointers:
            origin = f"scan:international_pointers:{index}"
            exposed = permit_statement_numbers(origin, s.get("statement"))
            out.append(f"PRECEDENT ELSEWHERE (a pointer, never an endorsement and never a "
                       f"comparison of countries) — {s['about_country']}: {s['statement']} "
                       f"[{s['source_name']}, {s['tier']}; numeric origins: "
                       f"{origin_legend(exposed)}]")

    # Canonical stage 3 remains a separate product. It is attached under a private key
    # instead of flattened into scans, so country AI evidence, peer lessons and proposed
    # actions retain their epistemic status inside the integrated Draft.
    derived_allowed = set(b.get("derived") or [])
    ai = (scans or {}).get("_ai_assessment") or {}
    ai_sections = [section for section in ("as_is", "peer_experience")
                   if f"ai.{section}" in derived_allowed]
    include_ai_agenda = "ai.recommended_agenda" in derived_allowed
    if ai and (ai_sections or include_ai_agenda):
        out.append("AI IN DIGITAL AGRICULTURE (separate Stage 3 assessment):")
        for section in ai_sections:
            for index, finding in enumerate((ai.get(section) or {}).get("findings") or []):
                origin = f"ai:{section}:{index}"
                exposed = permit_statement_numbers(origin, finding.get("statement"))
                out.append(
                    f"  - {finding.get('id', origin)}: {finding.get('statement', '')} "
                    f"[{finding.get('source_name', '')}, {finding.get('tier', '')}; "
                    f"numeric origins: {origin_legend(exposed)}]"
                )
        if include_ai_agenda:
            for index, action in enumerate(
                    (ai.get("recommended_agenda") or {}).get("actions") or []):
                origin = f"ai:recommended_agenda:{index}"
                statement = json.dumps(action, ensure_ascii=False, default=str)
                exposed = permit_statement_numbers(origin, statement)
                out.append(
                    "  - PROPOSED AI ACTION FOR POST-COMPLETION VALIDATION: "
                    f"{statement}; NUMERIC ORIGINS: {origin_legend(exposed)}"
                )

    # Canonical stage 6 feeds the programme, financing, results and risk chapters. Its
    # numbers are traceable appraisal inputs and planning assumptions; no financing
    # decision is made here or by the generator.
    investment = (scans or {}).get("_investment_options") or {}
    if investment and "investment.options" in derived_allowed:
        out.append("PRELIMINARY INVESTMENT OPTIONS AND COST-BENEFIT ANALYSIS:")
        for index, option in enumerate(investment.get("options") or []):
            origin = f"investment:options:{index}"
            exposed = permit_numeric_fields(origin, option)
            out.append(
                f"  - {json.dumps(option, ensure_ascii=False, default=str)}; "
                f"NUMERIC ORIGINS: {origin_legend(exposed)}"
            )
        out.append(
            "  - DECISION STATUS: "
            f"{investment.get('decision_status', 'no_financing_decision_made')}"
        )
        if "investment.portfolio_sequencing" in derived_allowed:
            out.append(
                "  - PORTFOLIO SEQUENCING: "
                f"{investment.get('portfolio_sequencing', '')}"
            )

    text = "\n".join(out)
    claim_origins = sorted(set(re.findall(r"\[\[origin:([^\]]+)\]\]", text)))
    return {"text": text, "allowed_citations": allowed,
            "allowed_numbers": allowed_numbers,
            "allowed_claim_origins": claim_origins,
            "allowed_quantities": {
                origin: sorted(values) for origin, values in allowed_quantities.items()
            }}


def _sha256(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, default=str, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def content_run_id(country, iso3, assessment_year, input_records,
                   implementation, adapter):
    """Identify a run by immutable content and the adapter actually used."""
    return _sha256({
        "country": country,
        "iso3": iso3,
        "assessment_year": assessment_year,
        "input_sha256": {
            name: record["sha256"]
            for name, record in sorted(input_records.items())
        },
        "implementation_sha256": {
            name: record["sha256"]
            for name, record in sorted(implementation.items())
        },
        "adapter": {
            "mode": adapter.get("mode"),
            "resolved": adapter.get("resolved"),
        },
    })[:24]


def chapter_adapter_cache_identity(chapter, assessment, scans, foresight,
                                   country, llm):
    """Replay/live adapter identity for the exact request, when the adapter exposes it."""
    if str(chapter["n"]) == "A" or not hasattr(llm, "cache_identity"):
        return None
    detail = f"chapter {chapter['n']}"
    user_prompt = chapter_user_prompt(
        chapter, assessment, scans, foresight, country)
    exact_request_sha = V.json_call_request_sha256(
        SYSTEM, user_prompt, CHAPTER_SCHEMA, PASS, 8000, detail)
    return llm.cache_identity(PASS, detail, exact_request_sha)


def chapter_request_sha256(chapter, rows, assessment, scans, foresight,
                           country, iso3, llm):
    """Identity of everything that can change a cached chapter's meaning."""
    source_sha = hashlib.sha256(open(__file__, "rb").read()).hexdigest()
    model_sha = hashlib.sha256(open(MODEL_FILE, "rb").read()).hexdigest()
    if str(chapter["n"]) == "A":
        material = {
            "mode": "deterministic-annex",
            "rows": rows,
            "assessment": assessment,
            "scans": scans,
            "foresight": foresight,
        }
    else:
        pack = pack_for(chapter, assessment, scans, foresight)
        material = {
            "mode": "narrative-chapter",
            "system": SYSTEM,
            "schema": CHAPTER_SCHEMA,
            "chapter": chapter,
            "pack": pack["text"],
            "allowed_citations": pack["allowed_citations"],
            "allowed_numbers": sorted(pack["allowed_numbers"]),
            "allowed_claim_origins": pack["allowed_claim_origins"],
            "allowed_quantities": pack["allowed_quantities"],
            "vendor": getattr(llm, "vendor", None),
            "model": getattr(llm, "model", None),
            "adapter_cache_identity": chapter_adapter_cache_identity(
                chapter, assessment, scans, foresight, country, llm),
        }
    return _sha256({
        "generation_source_sha256": source_sha,
        "model_sha256": model_sha,
        "country": country,
        "iso3": iso3,
        "assessment_year": ASSESSMENT_YEAR,
        "material": material,
    })


def chapter_response(record):
    """Only vendor-authored fields; all derived QC fields are deliberately discarded."""
    return {key: record.get(key) for key in ("prose", "cites", "claims", "figures")}


def validate_chapter_response(response):
    """Validate replay and cached responses as strictly as live JSON-schema output."""
    if not isinstance(response, dict):
        raise V.VendorError("chapter response is not an object")
    if not isinstance(response.get("prose"), str) or not response["prose"].strip():
        raise V.VendorError("chapter response has no prose")
    cites = response.get("cites")
    if not isinstance(cites, dict):
        raise V.VendorError("chapter response cites is not an object")
    for kind in ("pillars", "indicators", "use_cases", "prerequisites"):
        if not isinstance(cites.get(kind), list) or not all(
                isinstance(value, str) for value in cites[kind]):
            raise V.VendorError(f"chapter response cites.{kind} is not a string array")
    claims = response.get("claims")
    if not isinstance(claims, list):
        raise V.VendorError("chapter response claims is not an array")
    for index, claim in enumerate(claims):
        if (not isinstance(claim, dict)
                or not isinstance(claim.get("text"), str)
                or claim.get("basis") not in {"evidence", "proposal"}
                or not isinstance(claim.get("source_refs"), list)
                or not all(isinstance(value, str) for value in claim["source_refs"])):
            raise V.VendorError(f"chapter response claim {index} is invalid")
    figures = response.get("figures")
    if not isinstance(figures, list):
        raise V.VendorError("chapter response figures is not an array")
    required = ("value", "what_it_is", "basis", "operation", "source_refs", "inputs",
                "rationale")
    for index, figure in enumerate(figures):
        if not isinstance(figure, dict) or any(key not in figure for key in required):
            raise V.VendorError(f"chapter response figure {index} is incomplete")
        if not all(isinstance(figure[key], str)
                   for key in ("value", "what_it_is", "basis", "operation", "rationale")):
            raise V.VendorError(f"chapter response figure {index} has invalid text fields")
        if not all(isinstance(figure[key], list)
                   and all(isinstance(value, str) for value in figure[key])
                   for key in ("source_refs", "inputs")):
            raise V.VendorError(f"chapter response figure {index} has invalid arrays")
        if figure["basis"] not in {
                "evidence", "calculation", "benchmark", "planning_assumption"}:
            raise V.VendorError(f"chapter response figure {index} has invalid basis")
        if figure["operation"] not in {
                "none", "sum", "difference", "product", "ratio", "percentage"}:
            raise V.VendorError(f"chapter response figure {index} has invalid operation")
    return response


def build_chapter_record(chapter, response, assessment, scans, foresight):
    """Build every QC field afresh from the raw model response and current pack."""
    ans = validate_chapter_response(response)
    prescriptive = chapter["kind"] == "prescriptive"
    pack = pack_for(chapter, assessment, scans, foresight)

    outside = (binding_gate(ans["cites"], pack["allowed_citations"])
               + prose_binding_gate(ans["prose"], pack["allowed_citations"])
               + claim_provenance_gate(
                   ans["prose"], ans["claims"], set(pack["allowed_claim_origins"]),
                   require_all=True, prescriptive=prescriptive))
    cited = [citation for kind in ("indicators", "prerequisites")
             for citation in (ans["cites"].get(kind) or [])]
    supported, unsupported, stray = fidelity_check(
        ans["prose"], ans["figures"], pack["allowed_numbers"],
        KNOWN_IDS, cited, pack["allowed_quantities"], prescriptive)

    provenance = (
        f"Chapter {chapter['n']} draws on "
        + ", ".join(filter(None, [
            f"pillars {', '.join(chapter['binding']['pillars'])}"
            if chapter["binding"]["pillars"] else "",
            f"indicators {', '.join(chapter['binding']['indicators'])}"
            if chapter["binding"]["indicators"] else "",
            f"use cases {', '.join(chapter['binding']['use_cases'])}"
            if chapter["binding"]["use_cases"] else "",
            f"prerequisites {', '.join(chapter['binding']['prerequisites'])}"
            if chapter["binding"]["prerequisites"] else "",
            f"derived: {', '.join(chapter['binding']['derived'])}"
            if chapter["binding"]["derived"] else "",
        ]))
        + ". "
        + ("Prescriptive: proposed, not evidenced."
           if prescriptive else "Diagnostic: reports what the assessment found."))

    return {
        "n": chapter["n"],
        "title": chapter["title"],
        "kind": chapter["kind"],
        "status": "proposed, not evidenced" if prescriptive else "evidenced by the assessment",
        "prose": ans["prose"],
        "cites": ans["cites"],
        "claims": ans["claims"],
        "figures": ans["figures"],
        "supported_figures": len(supported),
        "unsupported_figures": [figure["value"] for figure in unsupported],
        "stray_numbers": stray,
        "cited_outside_binding": outside,
        "provenance": provenance,
    }


def chapter_user_prompt(chapter, assessment, scans, foresight, country):
    """The exact prompt material whose hash binds an offline replay response."""
    prescriptive = chapter["kind"] == "prescriptive"
    pack = pack_for(chapter, assessment, scans, foresight)
    return (
        f"COUNTRY: {country}\nASSESSMENT YEAR: {ASSESSMENT_YEAR}\n"
        f"CHAPTER {chapter['n']}: {chapter['title']}\n"
        f"WHAT IT COVERS: {chapter['content']}\n"
        + (f"NOTE: {chapter['note']}\n" if chapter.get("note") else "")
        + f"\nEVIDENCE PACK — this is everything you may cite:\n{pack['text']}\n\n"
        + ("This is a PRESCRIPTIVE chapter. What it proposes is not evidenced by the "
           "assessment; it is a recommendation built on it. Write it as a proposal and do "
           "not present any recommendation as a finding.\n\n"
           if prescriptive else
           "This is a DIAGNOSTIC chapter. Report what the assessment found and nothing "
           "beyond it.\n\n")
        + "Write the chapter as continuous prose, several paragraphs. Rules:\n"
        + ("- Copy every complete prose sentence into `claims` and bind it to one or "
           "more exact [[origin:...]] ids from the pack with basis evidence. A diagnostic "
           "sentence without an exact source origin is not publishable.\n"
           if not prescriptive else
           "- Copy every complete prose sentence into `claims`. Classify a factual "
           "sentence as evidence and bind it to exact [[origin:...]] ids from the pack. "
           "Classify a recommendation as proposal, use no source_refs, and frame it "
           "explicitly as a proposal or recommendation.\n")
        + "- Every number in your prose must come from the pack above. If the pack does "
        "not carry a figure, write the sentence without one.\n"
        "- List every figure you used in `figures`, exactly as it appears in your prose.\n"
        "- Classify each figure as evidence, calculation, benchmark, or "
        "planning_assumption. Evidence and benchmarks must cite one or more exact "
        "[[origin:...]] ids from the pack in source_refs. Calculations must cite their "
        "origins, list exactly two numeric inputs, select their exact operation "
        "(sum, difference, product, ratio, or percentage), and explain the arithmetic "
        "in rationale. Every other figure must set operation to none. "
        "Only a prescriptive chapter may use a planning_assumption; it must have no "
        "source_refs and must explain the assumption in rationale.\n"
        "- List in `cites` only the ids that appear in the pack.\n"
        "- Where the pack shows a row as withheld or unverified, say so rather than "
        "treating it as a low score. A withheld level is not an absence.\n"
        "- Never compare this country to another, and never rank countries."
    )


def write_chapter(chapter, assessment, scans, foresight, country, llm, allowed=None):
    ans = llm.json_call(
        SYSTEM,
        chapter_user_prompt(chapter, assessment, scans, foresight, country),
        CHAPTER_SCHEMA, PASS, max_tokens=8000, detail=f"chapter {chapter['n']}")

    return build_chapter_record(chapter, ans, assessment, scans, foresight)


def build_annex_chapter(rows, assessment, scans, foresight, country, iso3):
    """Build the audit-trail chapter directly from the structured run record."""
    evidence = []
    for iid, model_row in MODEL.items():
        raw = rows[iid]
        derived = assessment["indicators"][iid]
        evidence.append({
            "id": iid,
            "name": model_row["name"],
            "pillar": model_row["pillar"],
            "layer": model_row["layer"],
            "use_cases": list(model_row["uc"]),
            "prerequisite": model_row["prereq"],
            "value": raw.get("value"),
            "class": raw.get("cls"),
            "level": raw.get("level"),
            "year": raw.get("year"),
            "stale": bool(derived.get("stale")),
            "source": {
                "title": raw.get("src") or "",
                "url": raw.get("url") or "",
                "tier": raw.get("tier") or "",
                "tier_detail": raw.get("tier_detail") or "",
            },
            "note": raw.get("note") or "",
            "definition_note": raw.get("defnote") or "",
            "definition_severity": raw.get("defsev") or "",
        })

    candidates = [dict(row, id=iid)
                  for iid, row in _candidate_input_rows(rows).items()]
    annex = {
        "schema_version": "damm.dar.annex/v1",
        "run_record": {
            "country": country,
            "iso3": iso3,
            "assessment_year": ASSESSMENT_YEAR,
            "model_version": SPEC["version"],
            "model_revision": SPEC["revision"],
            "model_status": SPEC.get("status"),
            "model_ratified": SPEC.get("ratified"),
        },
        "indicator_evidence": evidence,
        "candidate_rows": candidates,
        "derived_assessment": {
            key: assessment.get(key) for key in (
                "pillars", "layers", "leapfrog", "matrix", "prereq", "constraints",
                "kpi", "counts", "rated", "held", "verify", "refresh")
        },
        "country_findings": list((scans or {}).get("country_findings") or []),
        "international_pointers": list((scans or {}).get("international_pointers") or []),
        "initiative_register": list((scans or {}).get("register_entries") or []),
        "scan_abstentions": list((scans or {}).get("abstained") or []),
        "ai_digital_agriculture": dict((scans or {}).get("_ai_assessment") or {}),
        "investment_options": dict((scans or {}).get("_investment_options") or {}),
        "foresight": dict(foresight or {}),
        "method_record": {
            "config": SPEC.get("config"),
            "open_decisions": SPEC.get("open_decisions") or [],
            "prohibitions": PROHIBITIONS,
        },
    }
    chapter = next(c for c in OUTLINE if str(c["n"]) == "A")
    cites = {
        "pillars": list(assessment.get("pillars") or {}),
        "indicators": list(MODEL),
        "use_cases": list(assessment.get("matrix") or {}),
        "prerequisites": list(assessment.get("prereq") or {}),
    }
    return {
        "n": "A",
        "title": chapter["title"],
        "kind": chapter["kind"],
        "status": "deterministic audit trail",
        "prose": "This annex is generated directly from the structured run inputs.",
        "cites": cites,
        "figures": [],
        "supported_figures": 0,
        "unsupported_figures": [],
        "stray_numbers": [],
        "cited_outside_binding": binding_gate(cites, chapter["binding"], assessment),
        "provenance": ("Generated deterministically from the workflow-bound assessment "
                       "input, engine output, scans, AI assessment, investment appraisal, "
                       "foresight and model configuration; no "
                       "language model authored or summarised this annex."),
        "annex": annex,
    }


# ------------------------------------------------------- final-publication gate

_BINDING_RULE_ATTESTATION_FIELDS = frozenset({"id", "rule", "ratified", "decision"})
_INDICATOR_ATTESTATION_FIELDS = frozenset({
    "id", "name", "pillar", "layer", "use_cases", "tags", "prerequisite",
    "method", "direction", "thresholds",
})
_SHA256_TEXT = re.compile(r"^[0-9a-f]{64}$")
_ISO_DATE_TEXT = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_JOINT_REVIEWER_NAMES = {
    "katreyna": re.compile(r"^katreyna(?:\s+schroeder)?$"),
    "randeep": re.compile(r"^randeep(?:\s+sudan)?$"),
}
# Current country/area codes in the UN Statistics Division M49 English table, captured
# 26 August 2026: https://unstats.un.org/unsd/methodology/m49/
_ISO_3166_ALPHA3 = frozenset("""
ABW AFG AGO AIA ALA ALB AND ARE ARG ARM ASM ATA ATF ATG AUS AUT AZE BDI BEL BEN
BES BFA BGD BGR BHR BHS BIH BLM BLR BLZ BMU BOL BRA BRB BRN BTN BVT BWA CAF
CAN CCK CHE CHL CHN CIV CMR COD COG COK COL COM CPV CRI CUB CUW CXR CYM CYP
CZE DEU DJI DMA DNK DOM DZA ECU EGY ERI ESH ESP EST ETH FIN FJI FLK FRA FRO
FSM GAB GBR GEO GGY GHA GIB GIN GLP GMB GNB GNQ GRC GRD GRL GTM GUF GUM GUY
HKG HMD HND HRV HTI HUN IDN IMN IND IOT IRL IRN IRQ ISL ISR ITA JAM JEY JOR
JPN KAZ KEN KGZ KHM KIR KNA KOR KWT LAO LBN LBR LBY LCA LIE LKA LSO LTU LUX
LVA MAC MAF MAR MCO MDA MDG MDV MEX MHL MKD MLI MLT MMR MNE MNG MNP MOZ MRT
MSR MTQ MUS MWI MYS MYT NAM NCL NER NFK NGA NIC NIU NLD NOR NPL NRU NZL OMN
PAK PAN PCN PER PHL PLW PNG POL PRI PRK PRT PRY PSE PYF QAT REU ROU RUS RWA
SAU SDN SEN SGP SGS SHN SJM SLB SLE SLV SMR SOM SPM SRB SSD STP SUR SVK SVN
SWE SWZ SXM SYC SYR TCA TCD TGO THA TJK TKL TKM TLS TON TTO TUN TUR TUV TZA
UGA UKR UMI URY USA UZB VAT VCT VEN VGB VIR VNM VUT WLF WSM YEM ZAF ZMB ZWE
""".split())
_ISSUE_2_BASELINE_REVISION = 2
_ISSUE_2_DEFINITION_IDS = frozenset("""
1.1 1.3 1.5 1.6 1.7 1.8 2.1 2.5 2.7 2.11 3.3 3.4 3.5 3.6 3.7 3.8 3.9
3.10 3.11 4.2 4.3 4.4 4.6 4.7 4.9 5.3 5.4 5.7 5.8 5.12 6.4 6.9 6.12
6.13 6.14 7.2 7.12 8.2 8.5 8.6 8.9 8.11 8.12 8.17
""".split())
_RELEASE_ARTIFACT_KEYS = frozenset({
    "canonical_model", "engine", "reference_scorer", "workbook", "renderer",
    "application_fixtures",
})
_RELEASE_CHECK_KEYS = frozenset({
    "model_parity", "full_build", "application_tests", "single_source_parity",
})
_WORKBOOK_RUNTIME_COUNTRY = "Workbook parity fixture"
_WORKBOOK_RUNTIME_EVIDENCE_REF = "release/workbook-runtime-parity.json"
_WORKBOOK_RUNTIME_OBSERVATIONS_REF = (
    "release/inputs/workbook-observations.json")
_WORKBOOK_RUNTIME_PROFILES_REF = "release/inputs/workbook-profiles.json"
_WORKBOOK_RUNTIME_CHECK_FIELDS = (
    "runtime_country", "runtime_evidence_ref", "runtime_evidence_sha256",
    "observations_ref", "observations_sha256",
    "profiles_ref", "profiles_sha256",
)
_RELEASE_CHECK_COMMANDS = {
    "model_parity": "python3 model/test_model_parity.py",
    "full_build": "python3 gauntlet/loop-1/verify_end_to_end.py",
    "application_tests": (
        "python3 gauntlet/loop-1/research_pipeline/test_generate_dar.py"),
    "single_source_parity": (
        "python3 gauntlet/loop-1/verify_workbook_parity.py "
        "--workbook release/artifacts/workbook.bin "
        "--model release/artifacts/canonical_model.bin "
        "--observations release/inputs/workbook-observations.json "
        "--profiles release/inputs/workbook-profiles.json "
        "--country 'Workbook parity fixture' "
        "--output release/workbook-runtime-parity.json"),
}
_MAPPING_EFFECTS = frozenset({"gate", "delivery_risk", "none"})
_INTERVENTION_PROFILE_FIELDS = frozenset({
    "targeted_farmer_level_delivery",
    "cross_organization_agricultural_data_sharing",
    "cross_ministerial_delivery", "moag_led_or_owned", "uses_personal_data",
    "uses_farm_level_data", "ai_enabled",
})
_CALIBRATION_BASES = frozenset({
    "official_classification", "normative_target", "distributional",
    "expert_judgment", "hybrid",
})
_RATIFICATION_EVIDENCE_KEYS = frozenset({
    "joint_review", "decisions", "definition_catalog",
    "threshold_calibrations", "country_migration",
    "unseen_country_validation", "foresight_method", "release_verification",
})
_MANIFEST_EVIDENCE_KEYS = _RATIFICATION_EVIDENCE_KEYS - {"joint_review"}
_MAPPING_GATE_OUTCOMES = {
    "Absent": "Blocked", "Unverified": "Unverified",
    "Present (narrow)": "Partial", "Present": "no_change",
}
_MAPPING_RISK_OUTCOMES = {
    "Absent": "flag", "Unverified": "verify",
    "Present (narrow)": "flag_narrow", "Present": "no_change",
}
_NAMED_SERIES_CONTRACTS = {
    "1.1": ("NV.AGR.EMPL.KD", None),
    "1.3": ("SL.AGR.EMPL.ZS", None),
    "2.5": ("5GB", "monthly_price/(annual_gni_per_capita/12)*100"),
    "4.2": ("GCI", "raw/100"),
    "4.3": ("GOVERNMENT_AI_READINESS", None),
}
_METADATA_BINDING_IDS = frozenset(_NAMED_SERIES_CONTRACTS)
_DEFINITION_PLACEHOLDERS = frozenset({
    "published measurement unit", "national target population",
    "assessment reference period", "ratified indicator unit",
    "ratified definition", "model-default", "not specified", "tbd", "unknown",
})


def _indicator_attestation_is_complete(row):
    """Whether one exported indicator is structurally identical to its scoring rule."""
    if not _INDICATOR_ATTESTATION_FIELDS <= set(row):
        return False
    indicator_id = row.get("id")
    if not isinstance(indicator_id, str):
        return False
    engine_row = MODEL.get(indicator_id)
    if engine_row is None or not _present_text(row.get("name")):
        return False
    use_case_ids = set(SPEC.get("use_cases") or {})
    expected_use_cases = [item for item in engine_row["uc"] if item in use_case_ids]
    expected_tags = [item for item in engine_row["uc"] if item not in use_case_ids]
    expected_method = "threshold" if engine_row["kind"] == "t" else "ladder"
    expected_direction = {
        "H": "higher-is-better", "L": "lower-is-better", "": None,
    }[engine_row["dir"]]
    if (row.get("name") != engine_row["name"]
            or row.get("pillar") != engine_row["pillar"]
            or row.get("layer") != engine_row["layer"]
            or row.get("use_cases") != expected_use_cases
            or row.get("tags") != expected_tags
            or row.get("prerequisite") != (engine_row["prereq"] or None)
            or row.get("method") != expected_method
            or row.get("direction") != expected_direction
            or row.get("thresholds") != (engine_row["th"] or None)):
        return False
    if expected_method == "threshold":
        cuts = row["thresholds"]
        if (not isinstance(cuts, list) or len(cuts) != 4
                or any(not _finite_number(value) for value in cuts)):
            return False
        pairs = zip(cuts, cuts[1:])
        if expected_direction == "higher-is-better":
            return all(left < right for left, right in pairs)
        return all(left > right for left, right in pairs)
    return row.get("thresholds") is None and row.get("direction") is None


def _verified_record_bytes(record, evidence_root, *, ref_field="record_ref",
                           sha_field="sha256"):
    """Read a repo-local record only when its path and bytes match the manifest."""
    if (not isinstance(record, dict)
            or not _present_text(record.get(ref_field))
            or not isinstance(record.get(sha_field), str)
            or not _SHA256_TEXT.fullmatch(record[sha_field])
            or not _present_text(evidence_root)):
        return None
    reference = record[ref_field]
    if os.path.isabs(reference):
        return None
    root = os.path.realpath(evidence_root)
    path = os.path.realpath(os.path.join(root, reference))
    try:
        if os.path.commonpath((root, path)) != root or not os.path.isfile(path):
            return None
    except ValueError:
        return None
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
        if hashlib.sha256(raw).hexdigest() != record[sha_field]:
            return None
        return raw
    except OSError:
        return None


def _verified_json_record(record, evidence_root, *, ref_field="record_ref"):
    """Load a content-addressed repo-local JSON record."""
    raw = _verified_record_bytes(record, evidence_root, ref_field=ref_field)
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _ratifiable_model_projection(model):
    """Return the approval-bearing model without self-referential evidence fields."""
    ratifiable_model = dict(model)
    ratifiable_model.pop("ratification_evidence", None)
    ratifiable_model.pop("ratification_manifest_sha256", None)
    return ratifiable_model


def _canonical_sha256(payload):
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _model_ratification_sha256(model):
    return _canonical_sha256(_ratifiable_model_projection(model))


def _ratification_manifest_sha256(evidence):
    """Digest every non-joint evidence reference the reviewers approve.

    The digest is kept separate from the model digest to avoid a cycle: evidence payloads
    bind to the model digest, while the two approval source records bind to both digests.
    """
    if (not isinstance(evidence, dict)
            or not _MANIFEST_EVIDENCE_KEYS <= set(evidence)):
        return None
    return _canonical_sha256({key: evidence[key]
                              for key in sorted(_MANIFEST_EVIDENCE_KEYS)})


_REFERENCE_HASH_FIELDS = {
    "record_ref": "sha256", "artifact_ref": "sha256", "diff_ref": "sha256",
    "content_ref": "content_sha256", "log_ref": "log_sha256",
    "runtime_evidence_ref": "runtime_evidence_sha256",
    "observations_ref": "observations_sha256",
    "profiles_ref": "profiles_sha256",
}


def _hashed_references(payload):
    if isinstance(payload, dict):
        for ref_field, sha_field in _REFERENCE_HASH_FIELDS.items():
            if ref_field in payload and sha_field in payload:
                yield payload[ref_field], payload[sha_field]
        for value in payload.values():
            yield from _hashed_references(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _hashed_references(value)


def _evidence_tree_sha256(model, content_loader):
    """Digest every content-addressed evidence file reachable from the model.

    The release implementation digest cannot contain this value without becoming
    self-referential: release verification is itself an evidence file.  Instead the tag
    check compares this independently computed tree for the worktree and tagged commit.
    """
    evidence = model.get("ratification_evidence") if isinstance(model, dict) else None
    if not isinstance(evidence, dict):
        return None
    queue = list(_hashed_references(evidence))
    expected_by_path = {}
    content_by_path = {}
    while queue:
        reference, expected_sha256 = queue.pop()
        if (not isinstance(reference, str) or not reference.strip()
                or os.path.isabs(reference)
                or os.path.normpath(reference).startswith("..")
                or not isinstance(expected_sha256, str)
                or not _SHA256_TEXT.fullmatch(expected_sha256)):
            return None
        normalized = os.path.normpath(reference)
        prior = expected_by_path.get(normalized)
        if prior is not None:
            if prior != expected_sha256:
                return None
            continue
        raw = content_loader(normalized)
        if (not isinstance(raw, bytes)
                or hashlib.sha256(raw).hexdigest() != expected_sha256):
            return None
        expected_by_path[normalized] = expected_sha256
        content_by_path[normalized] = raw
        try:
            nested = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        queue.extend(_hashed_references(nested))
    if not content_by_path:
        return None
    digest = hashlib.sha256()
    for reference in sorted(content_by_path):
        encoded_reference = reference.encode("utf-8")
        raw = content_by_path[reference]
        digest.update(len(encoded_reference).to_bytes(4, "big"))
        digest.update(encoded_reference)
        digest.update(len(raw).to_bytes(8, "big"))
        digest.update(raw)
    return digest.hexdigest()


def _worktree_evidence_tree_sha256(model, evidence_root):
    root = os.path.realpath(evidence_root)

    def load(reference):
        path = os.path.realpath(os.path.join(root, reference))
        try:
            if os.path.commonpath((root, path)) != root:
                return None
            with open(path, "rb") as handle:
                return handle.read()
        except (OSError, ValueError):
            return None

    return _evidence_tree_sha256(model, load)


def _record_is_bound_to_model(payload, model):
    return (isinstance(payload, dict)
            and payload.get("model_version") == model.get("version")
            and type(payload.get("model_revision")) is int
            and payload["model_revision"] == model.get("revision")
            and payload.get("model_sha256") == _model_ratification_sha256(model))


def _mapping_predicate_is_valid(predicate):
    if not isinstance(predicate, dict) or not predicate:
        return False
    if set(predicate) == {"field", "equals"}:
        return (predicate["field"] in _INTERVENTION_PROFILE_FIELDS
                and type(predicate["equals"]) is bool)
    if len(predicate) == 1 and next(iter(predicate)) in {"any", "all"}:
        children = next(iter(predicate.values()))
        return (isinstance(children, list) and bool(children)
                and all(_mapping_predicate_is_valid(child) for child in children))
    return False


def _mapping_records_are_semantic(payload):
    mapping = payload.get("prerequisite_mapping") if isinstance(payload, dict) else None
    if not isinstance(mapping, dict):
        return False
    prerequisite_ids = {
        indicator_id for indicator_id, row in MODEL.items() if row["prereq"]
    }
    use_case_ids = set(SPEC.get("use_cases") or {})
    expected_pairs = {
        (prerequisite_id, use_case_id)
        for prerequisite_id in prerequisite_ids for use_case_id in use_case_ids
    }
    edges = mapping.get("edges")
    if (mapping.get("decision_id") != "13.3"
            or type(mapping.get("revision")) is not int
            or mapping["revision"] < 1
            or mapping.get("status") != "ratified"
            or mapping.get("ratified") is not True
            or set(mapping.get("use_case_ids") or []) != use_case_ids
            or set(mapping.get("prerequisite_ids") or []) != prerequisite_ids
            or mapping.get("status_precedence")
            != ["Blocked", "Unverified", "Partial", "Ready"]
            or mapping.get("conditional_policy") != {
                "missing_profile": "report_condition_without_mutating_base_status",
                "true": "activate_edge", "false": "ignore_edge",
            }
            or not isinstance(edges, list)
            or len(edges) != len(expected_pairs)
            or any(not isinstance(edge, dict) for edge in edges)
            or {(edge.get("prerequisite_id"), edge.get("use_case_id"))
                for edge in edges} != expected_pairs):
        return False
    for edge in edges:
        effect = edge.get("effect")
        applicability = edge.get("applicability")
        mode = applicability.get("mode") if isinstance(applicability, dict) else None
        status_effects = edge.get("on_prerequisite_status")
        if (effect not in _MAPPING_EFFECTS
                or mode not in {"always", "conditional", "never"}
                or (mode == "conditional"
                    and not _mapping_predicate_is_valid(
                        applicability.get("predicate")))
                or (mode != "conditional" and "predicate" in applicability)
                or (effect == "gate" and mode not in {"always", "conditional"})
                or (effect == "delivery_risk" and mode == "never")
                or (effect == "none" and mode != "never")
                or (effect == "gate" and status_effects != _MAPPING_GATE_OUTCOMES)
                or (effect == "delivery_risk"
                    and status_effects != _MAPPING_RISK_OUTCOMES)
                or (effect == "none" and "on_prerequisite_status" in edge)
                or not _present_text(edge.get("rationale"))
                or not isinstance(edge.get("basis"), list)
                or not edge["basis"]
                or any(not _present_text(item) for item in edge["basis"])
                or edge.get("decision_status") != "ratified"):
            return False
    effects = {edge["effect"] for edge in edges}
    return ({"gate", "delivery_risk", "none"} <= effects
            and any(edge["effect"] == "gate"
                    and edge["applicability"] == {"mode": "always"}
                    for edge in edges))


def _definition_decisions_are_semantic(payload):
    return _definition_catalog_is_semantic(
        payload, expected_ids=_ISSUE_2_DEFINITION_IDS)


def _specific_definition_text(value):
    if not _present_text(value):
        return False
    normalized = " ".join(value.casefold().split()).strip(" .")
    return len(normalized) >= 8 and normalized not in _DEFINITION_PLACEHOLDERS


def _preferred_series_satisfies_contract(indicator_id, entry):
    contract = _NAMED_SERIES_CONTRACTS.get(indicator_id)
    if contract is None:
        return True
    token, required_transform = contract
    series = entry["source_policy"]["preferred_series"]
    joined = " ".join(str(item) for item in series).upper().replace(" ", "_")
    transform = str(entry["measure"].get("transform") or "").lower().replace(" ", "")
    return token in joined and (required_transform is None
                                or transform == required_transform)


def _definition_catalog_is_semantic(payload, expected_ids=KNOWN_IDS):
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if (payload.get("catalog_status") != "ratified"
            or not _present_text(payload.get("catalog_version"))
            or not isinstance(entries, dict)
            or set(entries) != set(expected_ids)
            or any(not isinstance(entry, dict) for entry in entries.values())):
        return False
    for indicator_id, entry in entries.items():
        measure = entry.get("measure")
        source_policy = entry.get("source_policy")
        scoring = entry.get("scoring")
        decision = entry.get("decision")
        model_row = MODEL[indicator_id]
        preferred_series = (source_policy.get("preferred_series")
                            if isinstance(source_policy, dict) else None)
        inclusions = entry.get("inclusions")
        exclusions = entry.get("exclusions")
        if (not _present_text(entry.get("definition_version"))
                or entry.get("status") != "ratified"
                or (indicator_id in _ISSUE_2_DEFINITION_IDS
                    and entry.get("question_class") not in {
                        "falsehood", "construct-drift", "unit-ambiguity"})
                or entry.get("resolution_basis")
                not in {"metadata-binding", "reviewer-choice", "prior-ratification"}
                or (indicator_id in _METADATA_BINDING_IDS
                    and entry.get("resolution_basis") != "metadata-binding")
                or (indicator_id in _ISSUE_2_DEFINITION_IDS - _METADATA_BINDING_IDS
                    and entry.get("resolution_basis") != "reviewer-choice")
                or not _specific_definition_text(entry.get("construct"))
                or not _present_text(entry.get("display_name"))
                or not isinstance(measure, dict)
                or any(not _specific_definition_text(measure.get(field)) for field in (
                    "operational_definition", "unit", "population_scope",
                    "reference_period"))
                or not _present_text(measure.get("numerator"))
                or not _present_text(measure.get("denominator"))
                or not _present_text(measure.get("transform"))
                or not isinstance(source_policy, dict)
                or not isinstance(preferred_series, list)
                or not isinstance(source_policy.get("allowed_tiers"), list)
                or not source_policy["allowed_tiers"]
                or any(item not in SOURCE_TIERS
                       for item in source_policy["allowed_tiers"])
                or not _present_text(source_policy.get("fallback_rule"))
                or not _present_text(source_policy.get("minimum_confirmation"))
                or (entry.get("resolution_basis") == "metadata-binding"
                    and (not preferred_series
                         or any(not _present_text(item) for item in preferred_series)))
                or not isinstance(scoring, dict)
                or scoring.get("method")
                != ("threshold" if model_row["th"] else "ladder")
                or scoring.get("direction") != ({
                    "H": "higher-is-better", "L": "lower-is-better", "": None,
                }[model_row["dir"]])
                or (model_row["th"] and scoring.get("cuts") != model_row["th"])
                or not _present_text(scoring.get("missing_rule"))
                or not _present_text(scoring.get("mismatch_rule"))
                or not isinstance(inclusions, list) or not inclusions
                or any(not _present_text(item) for item in inclusions)
                or not isinstance(exclusions, list) or not exclusions
                or any(not _present_text(item) for item in exclusions)
                or not _present_text(entry.get("ambiguity_rule"))
                or not isinstance(entry.get("comparability_breaks"), list)
                or not isinstance(decision, dict)
                or not _present_text(decision.get("decision_id"))
                or not _present_text(decision.get("ratified_by"))
                or not _valid_iso_date(decision.get("ratified_on"))
                or not _present_text(decision.get("rationale"))
                or not _present_text(decision.get("open_question"))
                or not _present_text(decision.get("resolution"))
                or not isinstance(entry.get("citations"), list)
                or not entry["citations"]
                or any(not _present_text(item) for item in entry["citations"])):
            return False
        unit = measure["unit"].casefold()
        is_index = "index" in unit or "score" in unit
        if (model_row["th"] and not is_index
                and (measure["numerator"].casefold() == "not_applicable"
                     or measure["denominator"].casefold() == "not_applicable")):
            return False
        if not _preferred_series_satisfies_contract(indicator_id, entry):
            return False
        if (indicator_id == "8.6"
                and measure["transform"].casefold().replace(" ", "")
                in {"identity", "none", "not_applicable"}):
            return False
        if indicator_id in {"2.5", "4.3"} and not entry["comparability_breaks"]:
            return False
        if not model_row["th"]:
            anchors = scoring.get("anchors")
            if (not isinstance(anchors, dict)
                    or set(anchors) != {"L1", "L2", "L3", "L4", "L5"}
                    or any(not _present_text(value) for value in anchors.values())
                    or not _present_text(scoring.get("qualifying_object_test"))
                    or not _present_text(scoring.get("operating_test"))
                    or not _present_text(scoring.get("scale_test"))):
                return False
    return True


def _expected_threshold_intervals(model_row):
    cuts = model_row["th"]
    if model_row["dir"] == "H":
        lowers = [None] + cuts
        uppers = cuts + [None]
        return [
            {
                "level": level,
                "lower": ({"value": lowers[level - 1], "inclusive": True}
                          if lowers[level - 1] is not None else None),
                "upper": ({"value": uppers[level - 1], "inclusive": False}
                          if uppers[level - 1] is not None else None),
            }
            for level in range(1, 6)
        ]
    lowers = cuts + [None]
    uppers = [None] + cuts
    return [
        {
            "level": level,
            "lower": ({"value": lowers[level - 1], "inclusive": False}
                      if lowers[level - 1] is not None else None),
            "upper": ({"value": uppers[level - 1], "inclusive": True}
                      if uppers[level - 1] is not None else None),
        }
        for level in range(1, 6)
    ]


def _calibration_sources_are_semantic(sources):
    return (isinstance(sources, dict) and bool(sources)
            and all(_present_text(source_id)
                    and isinstance(source, dict)
                    and source.get("source_type") in {
                        "official_classification", "normative_target",
                        "frozen_dataset", "expert_panel_record", "hybrid_component",
                    }
                    and _specific_definition_text(source.get("publisher"))
                    and _specific_definition_text(source.get("title"))
                    and _valid_iso_date(source.get("accessed_on"))
                    and _present_text(source.get("record_ref"))
                    and isinstance(source.get("sha256"), str)
                    and bool(_SHA256_TEXT.fullmatch(source["sha256"]))
                    for source_id, source in sources.items()))


def _cut_rationales_are_complete(basis, cuts, sources):
    rationales = basis.get("cut_rationales") if isinstance(basis, dict) else None
    return (isinstance(rationales, list) and len(rationales) == len(cuts)
            and all(isinstance(item, dict)
                    and item.get("cut") == cut
                    and _specific_definition_text(item.get("rationale"))
                    and isinstance(item.get("source_ids"), list)
                    and bool(item["source_ids"])
                    and set(item["source_ids"]) <= set(sources)
                    for item, cut in zip(rationales, cuts)))


def _calibration_basis_is_semantic(basis, approval, cuts, sources):
    source_ids = basis.get("source_ids") if isinstance(basis, dict) else None
    if (not isinstance(basis, dict)
            or basis.get("kind") not in _CALIBRATION_BASES
            or not _specific_definition_text(basis.get("method"))
            or not _specific_definition_text(basis.get("rationale"))
            or not isinstance(source_ids, list) or not source_ids
            or not set(source_ids) <= set(sources)
            or not _cut_rationales_are_complete(basis, cuts, sources)):
        return False
    kind = basis["kind"]
    if kind == "official_classification":
        return (all(_specific_definition_text(basis.get(field)) for field in (
                    "publisher", "document_version", "locator"))
                and isinstance(basis.get("category_text"), list)
                and len(basis["category_text"]) >= 4
                and all(_present_text(item) for item in basis["category_text"])
                and isinstance(basis.get("source_ids"), list)
                and bool(basis["source_ids"]))
    if kind == "normative_target":
        return (all(_specific_definition_text(basis.get(field)) for field in (
                    "issuing_authority", "target", "translation_rule"))
                and type(basis.get("target_year")) is int
                and basis["target_year"] >= 2000)
    if kind == "distributional":
        return (isinstance(basis.get("dataset_sha256"), str)
                and bool(_SHA256_TEXT.fullmatch(basis["dataset_sha256"]))
                and all(_specific_definition_text(basis.get(field)) for field in (
                    "universe", "reference_period", "weights",
                    "missing_data_rule", "outlier_rule", "quantile_method")))
    if kind == "expert_judgment":
        panel = basis.get("panel")
        return (isinstance(panel, list) and len(panel) >= 2
                and all(_present_text(item) for item in panel)
                and approval.get("method_owner") in panel
                and _valid_iso_date(basis.get("reviewed_on"))
                and isinstance(basis.get("conflicts_considered"), list)
                and bool(basis["conflicts_considered"])
                and all(_specific_definition_text(item)
                        for item in basis["conflicts_considered"]))
    components = basis.get("components")
    return (isinstance(components, list) and len(components) >= 2
            and all(isinstance(item, dict)
                    and item.get("kind") in _CALIBRATION_BASES - {"hybrid"}
                    and _specific_definition_text(item.get("summary"))
                    for item in components)
            and _specific_definition_text(basis.get("combination_rule")))


def _calibration_records_are_semantic(payload, expected_ids):
    calibrations = (payload.get("threshold_calibrations")
                    if isinstance(payload, dict) else None)
    refs = (payload.get("indicator_calibration_refs")
            if isinstance(payload, dict) else None)
    sources = payload.get("calibration_sources") if isinstance(payload, dict) else None
    if (not _calibration_sources_are_semantic(sources)
            or not isinstance(calibrations, dict)
            or not isinstance(refs, dict)
            or set(refs) != set(expected_ids)
            or len(calibrations) != len(expected_ids)
            or set(refs.values()) != set(calibrations)):
        return False
    for indicator_id, calibration_id in refs.items():
        record = calibrations.get(calibration_id)
        if not isinstance(record, dict):
            return False
        model_row = MODEL[indicator_id]
        expected_direction = {
            "H": "higher-is-better", "L": "lower-is-better",
        }[model_row["dir"]]
        basis = record.get("basis")
        approval = record.get("approval")
        if (record.get("indicator_id") != indicator_id
                or not _present_text(record.get("construct_id"))
                or record.get("definition_decision") != "13.5"
                or not _present_text(record.get("calibration_decision"))
                or record.get("status") != "ratified"
                or not _present_text(record.get("unit"))
                or not _present_text(record.get("reading_role"))
                or not _present_text(record.get("score_polarity"))
                or record.get("direction") != expected_direction
                or record.get("intervals") != _expected_threshold_intervals(model_row)
                or not _calibration_basis_is_semantic(
                    basis, approval if isinstance(approval, dict) else {},
                    model_row["th"], sources)
                or not isinstance(record.get("supersedes"), dict)
                or not isinstance(record.get("validation_fixture_ids"), list)
                or not record["validation_fixture_ids"]
                or not isinstance(approval, dict)
                or not _present_text(approval.get("method_owner"))
                or approval.get("status") != "ratified"
                or not _valid_iso_date(approval.get("approved_on"))
                or not _present_text(approval.get("record_ref"))
                or not _valid_iso_date(record.get("created_on"))):
            return False
    return True


def _runtime_mapping_is_applied(model):
    """Probe the production engine with one ratified always-gate edge."""
    mapping = model.get("prerequisite_mapping")
    edges = mapping.get("edges") if isinstance(mapping, dict) else None
    gate = next((edge for edge in (edges or [])
                 if edge.get("effect") == "gate"
                 and edge.get("applicability") == {"mode": "always"}), None)
    if gate is None:
        return False
    definition_catalog = model.get("indicator_definitions")
    definitions = (definition_catalog.get("entries")
                   if isinstance(definition_catalog, dict) else None)
    calibration_refs = model.get("indicator_calibration_refs")
    model_indicators = model.get("indicators")
    indicator_by_id = {
        item.get("id"): item for item in model_indicators
        if (isinstance(model_indicators, list) and isinstance(item, dict)
            and isinstance(item.get("id"), str))
    } if isinstance(model_indicators, list) else {}
    if (not isinstance(definitions, dict)
            or set(definitions) != set(KNOWN_IDS)
            or set(indicator_by_id) != set(KNOWN_IDS)):
        return False
    rows = {}
    for indicator_id in KNOWN_IDS:
        indicator = indicator_by_id[indicator_id]
        definition = definitions[indicator_id]
        measure = definition["measure"]
        policy = definition["source_policy"]
        preferred = policy["preferred_series"]
        desired_level = (
            1 if indicator_id == gate["prerequisite_id"] else 3)
        if indicator.get("method") == "threshold":
            cuts = indicator["thresholds"]
            if desired_level == 1:
                value = (cuts[0] - 1
                         if indicator["direction"] == "higher-is-better"
                         else cuts[0] + 1)
            else:
                value = cuts[desired_level - 2]
            cls = "Measured"
        else:
            value, cls = "Ratification parity probe", "Documented"
        row = {
            "value": value, "cls": cls, "level": desired_level,
            "year": model.get("config", {}).get(
                "assessment_year", ASSESSMENT_YEAR),
            "src": "ratification-parity-probe",
            "note": "synthetic structural probe",
            "tier": policy["allowed_tiers"][0], "url": "",
        }
        metadata = {
            "definition_version": definition["definition_version"],
            "definition_sha256": _canonical_sha256(definition),
            "definition_match": True,
            "unit": measure["unit"],
            "population_scope": measure["population_scope"],
            "reference_period_rule": measure["reference_period"],
            "transform": measure["transform"],
            "geography": "synthetic national parity probe",
            "observation_period": str(ASSESSMENT_YEAR),
            "edition": "ratification parity fixture edition",
            "proxy": False,
            "source_record_sha256": hashlib.sha256(
                f"ratification-parity:{indicator_id}".encode()).hexdigest(),
            "construct_review_sha256": hashlib.sha256(
                f"ratification-parity-review:{indicator_id}".encode()
            ).hexdigest(),
            "numerator": (
                "not_applicable" if measure.get("numerator") == "not_applicable"
                else "Synthetic construct-matched numerator"),
            "denominator": (
                "not_applicable" if measure.get("denominator") == "not_applicable"
                else "Synthetic construct-matched denominator"),
            "source_series": (preferred[0] if preferred
                              else "ratification parity fallback series"),
            "fallback_justification": (
                "Synthetic structural probe mirrors the ratified definition."),
        }
        if isinstance(calibration_refs, dict) and indicator_id in calibration_refs:
            metadata["calibration_ref"] = calibration_refs[indicator_id]
        if cls == "Measured":
            transform = measure["transform"]
            if transform == "identity":
                metadata["transform_inputs"] = {"source_value": value}
            elif transform == "raw / 100":
                metadata["transform_inputs"] = {"source_value": value * 100}
            elif transform == (
                    "monthly_price / (annual_GNI_per_capita / 12) * 100"):
                metadata["transform_inputs"] = {
                    "monthly_price": value,
                    "annual_gni_per_capita": 1200,
                }
            elif transform == "max(male_rate - female_rate, 0)":
                metadata["transform_inputs"] = {
                    "male_rate": value, "female_rate": 0,
                }
        row["definition_metadata"] = metadata
        rows[indicator_id] = row
    try:
        output = engine_run(
            "Ratification parity probe", rows, refyear=ASSESSMENT_YEAR,
            model_spec=model, intervention_profiles={})
    except (KeyError, TypeError, ValueError):
        return False
    cell = output.get("matrix", {}).get(gate["use_case_id"], {})
    active_ids = {
        item.get("prerequisite_id") if isinstance(item, dict) else item
        for item in cell.get("active_gates", [])
    }
    return (output.get("model_version") == model.get("version")
            and output.get("model_revision") == model.get("revision")
            and output.get("prerequisite_mapping_revision")
            == mapping.get("revision")
            and cell.get("status") == "Blocked"
            and gate["prerequisite_id"] in active_ids)


def _ratified_artifacts_are_applied(
        model, decision_payloads, definition_payload, threshold_payload):
    """Prove approved choices are installed in canonical data and executable runtime."""
    decision_133 = decision_payloads.get("13.3")
    decision_135 = decision_payloads.get("13.5")
    decision_a1 = decision_payloads.get("13.6")
    mapping = (decision_133.get("prerequisite_mapping")
               if isinstance(decision_133, dict) else None)
    decision_definitions = (decision_135.get("entries")
                            if isinstance(decision_135, dict) else None)
    decision_a1 = decision_a1 if isinstance(decision_a1, dict) else {}
    definitions = (definition_payload.get("entries")
                   if isinstance(definition_payload, dict) else None)
    calibrations = (threshold_payload.get("threshold_calibrations")
                    if isinstance(threshold_payload, dict) else None)
    refs = (threshold_payload.get("indicator_calibration_refs")
            if isinstance(threshold_payload, dict) else None)
    indicators = model.get("indicators")
    if (not isinstance(mapping, dict)
            or model.get("prerequisite_mapping") != mapping
            or not _runtime_mapping_is_applied(model)
            or not isinstance(definitions, dict)
            or model.get("definition_catalog_version")
            != definition_payload.get("catalog_version")
            or model.get("indicator_definitions") != {
                "catalog_version": definition_payload.get("catalog_version"),
                "catalog_status": definition_payload.get("catalog_status"),
                "entries": definitions,
            }
            or not isinstance(calibrations, dict)
            or not isinstance(refs, dict)
            or model.get("indicator_calibration_refs") != refs
            or not isinstance(indicators, list)
            or len(indicators) != len(KNOWN_IDS)):
        return False
    by_id = {row.get("id"): row for row in indicators if isinstance(row, dict)}
    if set(by_id) != set(KNOWN_IDS):
        return False
    for indicator_id, row in by_id.items():
        definition = definitions.get(indicator_id)
        if (not isinstance(definition, dict)
                or row.get("definition_version")
                != definition.get("definition_version")
                or row.get("definition_status") != "ratified"):
            return False
        calibration_id = refs.get(indicator_id)
        if row.get("thresholds"):
            if (row.get("calibration_ref") != calibration_id
                    or calibration_id not in calibrations):
                return False
        elif "calibration_ref" in row:
            return False
    if (not isinstance(decision_definitions, dict)
            or any(decision_definitions.get(indicator_id)
                   != definitions.get(indicator_id)
                   for indicator_id in _ISSUE_2_DEFINITION_IDS)):
        return False
    a1_refs = decision_a1.get("indicator_calibration_refs")
    a1_records = decision_a1.get("threshold_calibrations")
    if not isinstance(a1_refs, dict) or not isinstance(a1_records, dict):
        return False
    return all(refs.get(indicator_id) == a1_refs.get(indicator_id)
               and calibrations.get(refs.get(indicator_id))
               == a1_records.get(a1_refs.get(indicator_id))
               for indicator_id in a1_refs)


def _approval_provenance_is_complete(payload):
    provenance = payload.get("provenance") if isinstance(payload, dict) else None
    verification = (provenance.get("verification")
                    if isinstance(provenance, dict) else None)
    return (isinstance(provenance, dict)
            and provenance.get("system") in {
                "google_drive", "signed_email", "signed_document",
                "git_signed_commit", "physical_record",
            }
            and _present_text(provenance.get("immutable_record_id"))
            and _present_text(provenance.get("revision_id"))
            and _valid_iso_date(provenance.get("captured_on"))
            and isinstance(verification, dict)
            and verification.get("method") in {
                "provider_revision", "detached_signature",
                "verified_commit_signature", "two_person_archive_check",
            }
            and _present_text(verification.get("verified_by"))
            and _valid_iso_date(verification.get("verified_on")))


def _joint_approval_sources_are_complete(
        approvals, model, evidence_root, manifest_sha256):
    for approval in approvals:
        source_record = approval.get("source_record")
        source_payload = _verified_json_record(source_record, evidence_root)
        if (not _record_is_bound_to_model(source_payload, model)
                or source_payload.get("evidence_manifest_sha256")
                != manifest_sha256
                or source_payload.get("reviewer") != approval.get("reviewer")
                or source_payload.get("approved_on") != approval.get("approved_on")
                or source_payload.get("approved") is not True
                or source_payload.get("decision_scope")
                != "DAMM Issue 2 ratification"
                or not _present_text(source_payload.get("source_record_id"))
                or not _approval_provenance_is_complete(source_payload)):
            return False
    return True


def _method_freeze_time(migration_payload, model, evidence_root):
    freeze_record = (migration_payload.get("method_freeze")
                     if isinstance(migration_payload, dict) else None)
    freeze_payload = _verified_json_record(freeze_record, evidence_root)
    approvals = (freeze_payload.get("approvals")
                 if isinstance(freeze_payload, dict) else None)
    if (not _record_is_bound_to_model(freeze_payload, model)
            or freeze_payload.get("kind") != "method_freeze"
            or freeze_payload.get("status") != "frozen"
            or not isinstance(approvals, list) or len(approvals) != 2):
        return None
    freeze_time = _parse_iso_datetime(freeze_payload.get("frozen_at"))
    if freeze_time is None:
        return None
    roles = set()
    for approval in approvals:
        reviewer = approval.get("reviewer") if isinstance(approval, dict) else None
        normalized = (" ".join(reviewer.casefold().split())
                      if _present_text(reviewer) else "")
        role = next((candidate for candidate, pattern in _JOINT_REVIEWER_NAMES.items()
                     if pattern.fullmatch(normalized)), None)
        source_payload = _verified_json_record(
            approval.get("source_record") if isinstance(approval, dict) else None,
            evidence_root)
        approval_time = _parse_iso_datetime(
            approval.get("approved_at") if isinstance(approval, dict) else None)
        if (role is None or approval_time is None or approval_time > freeze_time
                or not _record_is_bound_to_model(source_payload, model)
                or source_payload.get("reviewer") != reviewer
                or source_payload.get("approved_at") != approval.get("approved_at")
                or source_payload.get("approved") is not True
                or source_payload.get("decision_scope")
                != "DAMM Issue 2 method freeze"
                or not _present_text(source_payload.get("source_record_id"))
                or not _approval_provenance_is_complete(source_payload)):
            return None
        roles.add(role)
    return freeze_time if roles == set(_JOINT_REVIEWER_NAMES) else None


def _migration_timeline(migration_payload, model, evidence_root):
    freeze_time = _method_freeze_time(migration_payload, model, evidence_root)
    started = _parse_iso_datetime(
        migration_payload.get("started_at")
        if isinstance(migration_payload, dict) else None)
    completed = _parse_iso_datetime(
        migration_payload.get("completed_at")
        if isinstance(migration_payload, dict) else None)
    if (freeze_time is None or started is None or completed is None
            or not freeze_time < started < completed
            or migration_payload.get("accepted_on") != completed.date().isoformat()):
        return None
    return freeze_time, started, completed


def _tagged_record_matches(record, source_tag, tag_state):
    """Verify that a content-addressed migration artifact exists in the old tag."""
    if (not isinstance(record, dict)
            or not isinstance(source_tag, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}", source_tag)
            or ".." in source_tag
            or not isinstance(tag_state, dict)):
        return False
    reference = record.get("record_ref")
    expected_sha256 = record.get("sha256")
    if (not isinstance(reference, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", reference)
            or os.path.isabs(reference)
            or os.path.normpath(reference).startswith("..")
            or not isinstance(expected_sha256, str)
            or not _SHA256_TEXT.fullmatch(expected_sha256)):
        return False
    normalized = os.path.normpath(reference)
    artifact_sha256s = tag_state.get("artifact_sha256s")
    if isinstance(artifact_sha256s, dict):
        return artifact_sha256s.get(normalized) == expected_sha256
    if tag_state.get("resolved_from_git") is not True:
        return False
    resolved_commit = tag_state.get("commit")
    if (not isinstance(resolved_commit, str)
            or not re.fullmatch(r"[0-9a-f]{40}(?:[0-9a-f]{24})?", resolved_commit)):
        return False
    try:
        raw = subprocess.run(
            ["git", "show", f"{resolved_commit}:{normalized}"], cwd=REPO,
            check=True, capture_output=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return hashlib.sha256(raw).hexdigest() == expected_sha256


def _migration_baseline_model(
        migration_payload, model, evidence_root, available_release_tags=None):
    record = (migration_payload.get("baseline_model")
              if isinstance(migration_payload, dict) else None)
    baseline = _verified_json_record(record, evidence_root)
    commit = record.get("source_commit") if isinstance(record, dict) else None
    source_tag = record.get("source_tag") if isinstance(record, dict) else None
    release_tags = (_git_release_tags() if available_release_tags is None
                    else available_release_tags)
    tag_state = (release_tags.get(source_tag)
                 if isinstance(release_tags, dict) else None)
    if (not isinstance(baseline, dict)
            or baseline.get("version") != model.get("version")
            or baseline.get("revision") != _ISSUE_2_BASELINE_REVISION
            or baseline.get("ratified") is not False
            or baseline.get("status") != "draft for review"
            or not isinstance(baseline.get("indicators"), list)
            or len(baseline["indicators"]) != len(KNOWN_IDS)
            or record.get("model_sha256")
            != _model_ratification_sha256(baseline)
            or not isinstance(commit, str) or len(commit) != 40
            or any(character not in "0123456789abcdef" for character in commit)
            or not _present_text(source_tag)
            or not isinstance(tag_state, dict)
            or tag_state.get("commit") != commit
            or not isinstance(tag_state.get("tag_object_oid"), str)
            or not re.fullmatch(
                r"[0-9a-f]{40}(?:[0-9a-f]{24})?",
                tag_state["tag_object_oid"])
            or record.get("tag_object_oid")
            != tag_state.get("tag_object_oid")
            or tag_state.get("signature_verified") is not True
            or tag_state.get("signature_target") not in {"tag", "commit"}
            or not isinstance(tag_state.get("signature_evidence_sha256"), str)
            or not _SHA256_TEXT.fullmatch(
                tag_state["signature_evidence_sha256"])
            or record.get("signature_target")
            != tag_state.get("signature_target")
            or record.get("signature_evidence_sha256")
            != tag_state.get("signature_evidence_sha256")
            or not _present_text(tag_state.get("signer_fingerprint"))
            or record.get("authorized_signer_fingerprint")
            != tag_state.get("signer_fingerprint")
            or tag_state.get("model_sha256") != record.get("model_sha256")
            or not isinstance(record.get("implementation_sha256"), str)
            or not _SHA256_TEXT.fullmatch(record["implementation_sha256"])
            or tag_state.get("implementation_sha256")
            != record.get("implementation_sha256")
            or not _approval_provenance_is_complete(record)):
        return None
    return {
        "model": baseline,
        "source_commit": commit,
        "source_tag": source_tag,
        "implementation_sha256": record["implementation_sha256"],
        "tag_state": tag_state,
    }


def _migration_snapshot_is_complete(
        snapshot, country, revision, *, model=None,
        implementation_sha256=None, evidence_root=None):
    indicators = snapshot.get("indicators") if isinstance(snapshot, dict) else None
    if (not isinstance(snapshot, dict)
            or snapshot.get("country") != country
            or snapshot.get("model_version") != (model or SPEC).get("version")
            or snapshot.get("model_revision") != revision
            or not isinstance(snapshot.get("indicator_levels"), dict)
            or set(snapshot["indicator_levels"]) != set(KNOWN_IDS)
            or any(value not in {None, 1, 2, 3, 4, 5}
                   for value in snapshot["indicator_levels"].values())
            or not isinstance(indicators, dict)
            or set(indicators) != set(KNOWN_IDS)
            or any(not isinstance(row, dict)
                   or row.get("level") != snapshot["indicator_levels"][indicator_id]
                   or row.get("cls") not in EVIDENCE_CLASSES
                   or "value" not in row
                   or not _present_text(row.get("src"))
                   or not _present_text(row.get("unit"))
                   or not _present_text(row.get("population_scope"))
                   or not _present_text(row.get("reference_period"))
                   or not _present_text(row.get("source_series"))
                   or not _present_text(row.get("transform"))
                   for indicator_id, row in indicators.items())
            or not isinstance(snapshot.get("pillars"), dict)
            or set(snapshot["pillars"]) != set(SPEC.get("pillars") or {})
            or any(not isinstance(row, dict)
                   or not _finite_number(row.get("mean"))
                   or not _present_text(row.get("band"))
                   or type(row.get("rated")) is not int
                   for row in snapshot["pillars"].values())
            or not isinstance(snapshot.get("matrix"), dict)
            or set(snapshot["matrix"]) != set(SPEC.get("use_cases") or {})
            or any(not isinstance(cell, dict)
                   or cell.get("status") not in {
                       "Blocked", "Unverified", "Partial", "Ready"}
                   or not (isinstance(cell.get("status_reason"), dict)
                           or _present_text(cell.get("status_reason")))
                   for cell in snapshot["matrix"].values())):
        return False
    if model is not None and revision == model.get("revision"):
        engine_input = snapshot.get("engine_input")
        engine_output = snapshot.get("engine_output")
        reference_output = snapshot.get("reference_output")
        profiles = snapshot.get("intervention_profiles")
        if (snapshot.get("model_sha256") != _model_ratification_sha256(model)
                or not isinstance(implementation_sha256, str)
                or not _SHA256_TEXT.fullmatch(implementation_sha256)
                or snapshot.get("implementation_sha256")
                != implementation_sha256
                or profiles is None or not isinstance(profiles, dict)
                or assessment_input_errors(engine_input, spec=model)
                or not isinstance(engine_output, dict)
                or not isinstance(reference_output, dict)
                or snapshot.get("reference_output_sha256")
                != _canonical_sha256(reference_output)):
            return False
        try:
            replayed = engine_run(
                country, engine_input,
                refyear=model.get("config", {}).get(
                    "assessment_year", ASSESSMENT_YEAR),
                model_spec=model, intervention_profiles=profiles,
                project_unratified_model=model.get("ratified") is not True)
            reference_replayed = ReferenceScorer(model).run(
                engine_input, intervention_profiles=profiles)
        except (KeyError, TypeError, ValueError):
            return False
        if (_canonical_sha256(engine_output) != _canonical_sha256(replayed)
                or _canonical_sha256(reference_output)
                != _canonical_sha256(reference_replayed)
                or not _engine_reference_outputs_match(
                    replayed, reference_replayed)):
            return False
        if (model.get("ratified") is True
                and not _migration_release_observations_are_complete(
                    snapshot, model, country, evidence_root)):
            return False
        for indicator_id in KNOWN_IDS:
            row = indicators[indicator_id]
            source = engine_input[indicator_id]
            scored = engine_output.get("indicators", {}).get(indicator_id, {})
            metadata = source.get("definition_metadata")
            if (row.get("level") != scored.get("level")
                    or row.get("cls") != scored.get("cls")
                    or row.get("value") != source.get("value")
                    or row.get("src") != source.get("src")):
                return False
            if model.get("ratified") is True and (
                    not isinstance(metadata, dict)
                    or row.get("definition_metadata") != metadata
                    or row.get("unit") != metadata.get("unit")
                    or row.get("population_scope")
                    != metadata.get("population_scope")
                    or row.get("reference_period")
                    != metadata.get("observation_period")
                    or row.get("source_series") != metadata.get("source_series")
                    or row.get("transform") != metadata.get("transform")):
                return False
        for pillar_id, row in snapshot["pillars"].items():
            scored = engine_output.get("pillars", {}).get(pillar_id, {})
            if any(row.get(field) != scored.get(field)
                   for field in ("mean", "band", "rated")):
                return False
        for use_case_id, cell in snapshot["matrix"].items():
            scored = engine_output.get("matrix", {}).get(use_case_id, {})
            scored_reason = scored.get("status_reason", scored.get("why"))
            if (cell.get("status") != scored.get("status")
                    or cell.get("status_reason") != scored_reason):
                return False
    return True


def _migration_source_registry_is_complete(
        registry, model, country, evidence_root):
    if not isinstance(registry, dict) or not registry:
        return False
    for source_id, source in registry.items():
        payload = _verified_json_record(
            source, evidence_root)
        records = payload.get("records") if isinstance(payload, dict) else None
        if (not _present_text(source_id)
                or not isinstance(source, dict)
                or not _specific_definition_text(source.get("title"))
                or not _specific_definition_text(source.get("publisher"))
                or not _valid_iso_date(source.get("accessed_on"))
                or not _record_is_bound_to_model(payload, model)
                or payload.get("kind") != "migration_source_snapshot"
                or payload.get("country") != country
                or payload.get("title") != source.get("title")
                or payload.get("publisher") != source.get("publisher")
                or payload.get("captured_on") != source.get("accessed_on")
                or not _approval_provenance_is_complete(payload)
                or not isinstance(records, dict)
                or set(records) != set(KNOWN_IDS)
                or any(not isinstance(record, dict)
                       or not (_present_text(record.get("raw_value"))
                               or _finite_number(record.get("raw_value")))
                       or not _present_text(record.get("unit"))
                       or not _present_text(record.get("reference_period"))
                       or record.get("tier") not in SOURCE_TIERS
                       or not _present_text(record.get("url"))
                       or not re.match(r"^https?://", record["url"], re.I)
                       or not _present_text(record.get("source_series"))
                       or not _present_text(record.get("edition"))
                       or not _present_text(record.get("geography"))
                       or not (isinstance(record.get("transform_inputs"), dict)
                               or record.get("transform_inputs")
                               == "not_applicable")
                       or not _specific_definition_text(
                           record.get("evidence_excerpt"))
                       or not _unseen_source_capture_matches(
                           record, indicator_id, evidence_root)
                       or record.get("record_sha256")
                       != _canonical_sha256({
                           key: value for key, value in record.items()
                           if key != "record_sha256"})
                       for indicator_id, record in records.items())):
            return False
    return True


def _migration_release_observations_are_complete(
        snapshot, model, country, evidence_root):
    """Bind every current migration input to archived source and construct review."""
    source_registry = snapshot.get("source_registry")
    review_registry = snapshot.get("construct_review_registry")
    engine_input = snapshot.get("engine_input")
    definitions = model.get("indicator_definitions")
    entries = definitions.get("entries") if isinstance(definitions, dict) else None
    if (not _present_text(evidence_root)
            or not isinstance(source_registry, dict)
            or not isinstance(review_registry, dict)
            or set(review_registry) != set(KNOWN_IDS)
            or not isinstance(engine_input, dict)
            or set(engine_input) != set(KNOWN_IDS)
            or not isinstance(entries, dict)
            or set(entries) != set(KNOWN_IDS)):
        return False
    if not _migration_source_registry_is_complete(
            source_registry, model, country, evidence_root):
        return False
    source_payloads = {
        source_id: _verified_json_record(source, evidence_root)
        for source_id, source in source_registry.items()
    }
    for indicator_id in KNOWN_IDS:
        row = engine_input[indicator_id]
        metadata = row.get("definition_metadata")
        record = review_registry[indicator_id]
        review = _verified_json_record(record, evidence_root)
        matching_sources = [
            (source_id, source) for source_id, source in source_registry.items()
            if isinstance(metadata, dict)
            and source.get("sha256") == metadata.get("source_record_sha256")
        ]
        if len(matching_sources) != 1:
            return False
        source_id, source = matching_sources[0]
        source_indicator = source_payloads[source_id]["records"][indicator_id]
        expected_disposition = (
            "data_gap" if row.get("cls") == "Gap"
            else "held" if row.get("level") is None else "accepted")
        if (not isinstance(metadata, dict)
                or not isinstance(review, dict)
                or not _record_is_bound_to_model(review, model)
                or review.get("kind") != "construct_review"
                or review.get("country") != country
                or review.get("indicator_id") != indicator_id
                or not _present_text(review.get("reviewer"))
                or _parse_iso_datetime(review.get("reviewed_at")) is None
                or review.get("disposition") != expected_disposition
                or review.get("definition_sha256")
                != _canonical_sha256(entries[indicator_id])
                or review.get("definition_sha256")
                != metadata.get("definition_sha256")
                or review.get("source_record_sha256") != source.get("sha256")
                or review.get("source_indicator_record_sha256")
                != source_indicator.get("record_sha256")
                or source_indicator.get("raw_value") != row.get("value")
                or source_indicator.get("unit") != metadata.get("unit")
                or source_indicator.get("reference_period")
                != metadata.get("observation_period")
                or source_indicator.get("tier") != row.get("tier")
                or source_indicator.get("url") != row.get("url")
                or source_indicator.get("source_series")
                != metadata.get("source_series")
                or source_indicator.get("edition") != metadata.get("edition")
                or source_indicator.get("geography")
                != metadata.get("geography")
                or metadata.get("geography", "").casefold()
                != country.casefold()
                or source_indicator.get("transform_inputs")
                != metadata.get("transform_inputs", "not_applicable")
                or review.get("observation_sha256")
                != _canonical_sha256(
                    _construct_review_observation_projection(row))
                or not _specific_definition_text(review.get("review_note"))
                or not _approval_provenance_is_complete(review)
                or metadata.get("construct_review_sha256")
                != record.get("sha256")):
            return False
    return True


def _migration_expected_changes(old_snapshot, new_snapshot):
    """Return the exact normalized migration diff in stable path order."""
    changes = []

    def add(domain, path, before, after):
        if before != after:
            changes.append({
                "domain": domain, "path": path,
                "before": before, "after": after,
            })

    for indicator_id in sorted(KNOWN_IDS):
        add("levels", f"indicators.{indicator_id}.level",
            old_snapshot["indicator_levels"][indicator_id],
            new_snapshot["indicator_levels"][indicator_id])
    for pillar_id in sorted(SPEC.get("pillars") or {}):
        add("pillars", f"pillars.{pillar_id}.mean",
            old_snapshot["pillars"][pillar_id]["mean"],
            new_snapshot["pillars"][pillar_id]["mean"])
        add("pillars", f"pillars.{pillar_id}.rated",
            old_snapshot["pillars"][pillar_id]["rated"],
            new_snapshot["pillars"][pillar_id]["rated"])
        add("bands", f"pillars.{pillar_id}.band",
            old_snapshot["pillars"][pillar_id]["band"],
            new_snapshot["pillars"][pillar_id]["band"])
    for use_case_id in sorted(SPEC.get("use_cases") or {}):
        add("matrix", f"matrix.{use_case_id}.status",
            old_snapshot["matrix"][use_case_id]["status"],
            new_snapshot["matrix"][use_case_id]["status"])
        add("matrix", f"matrix.{use_case_id}.status_reason",
            old_snapshot["matrix"][use_case_id]["status_reason"],
            new_snapshot["matrix"][use_case_id]["status_reason"])
    return changes


def _migration_diffs_are_complete(
        payload, model, evidence_root, available_release_tags=None):
    diffs = payload.get("diffs") if isinstance(payload, dict) else None
    baseline_context = _migration_baseline_model(
        payload, model, evidence_root, available_release_tags)
    baseline_model = (baseline_context.get("model")
                      if isinstance(baseline_context, dict) else None)
    current_implementation_sha256 = _release_implementation_sha256(model)
    if (not isinstance(diffs, list) or len(diffs) != 2
            or any(not isinstance(item, dict) for item in diffs)
            or {item.get("id") for item in diffs} != {"EGY", "NGA"}
            or _migration_timeline(payload, model, evidence_root) is None
            or baseline_model is None
            or not isinstance(current_implementation_sha256, str)
            or not _SHA256_TEXT.fullmatch(current_implementation_sha256)):
        return False
    for item in diffs:
        diff_payload = _verified_json_record(
            item, evidence_root, ref_field="diff_ref")
        changes = diff_payload.get("changes") if isinstance(diff_payload, dict) else None
        change_domains = (diff_payload.get("change_domains")
                          if isinstance(diff_payload, dict) else None)
        old_record = (diff_payload.get("old_artifact")
                      if isinstance(diff_payload, dict) else None)
        new_record = (diff_payload.get("new_artifact")
                      if isinstance(diff_payload, dict) else None)
        old_payload = _verified_json_record(old_record, evidence_root)
        new_payload = _verified_json_record(new_record, evidence_root)
        old_complete = _migration_snapshot_is_complete(
            old_payload, item["id"], _ISSUE_2_BASELINE_REVISION,
            model=baseline_model,
            implementation_sha256=baseline_context[
                "implementation_sha256"], evidence_root=evidence_root)
        new_complete = _migration_snapshot_is_complete(
            new_payload, item["id"], model.get("revision"), model=model,
            implementation_sha256=current_implementation_sha256,
            evidence_root=evidence_root)
        expected_changes = (_migration_expected_changes(old_payload, new_payload)
                            if old_complete and new_complete else None)
        expected_domains = {
            domain: sum(change["domain"] == domain
                        for change in (expected_changes or []))
            for domain in ("levels", "pillars", "bands", "matrix")
        }
        if (not _record_is_bound_to_model(diff_payload, model)
                or diff_payload.get("country") != item["id"]
                or diff_payload.get("reviewed") is not True
                or not _present_text(diff_payload.get("reviewer"))
                or not _valid_iso_date(diff_payload.get("reviewed_on"))
                or not _specific_definition_text(
                    diff_payload.get("comparison_summary"))
                or not isinstance(changes, list)
                or any(not isinstance(change, dict)
                       or change.get("domain") not in {
                           "levels", "pillars", "bands", "matrix"}
                       or not _present_text(change.get("path"))
                       or "before" not in change or "after" not in change
                       or change["before"] == change["after"]
                       for change in changes)
                or not isinstance(change_domains, dict)
                or set(change_domains) != {"levels", "pillars", "bands", "matrix"}
                or any(type(value) is not int or value < 0
                       for value in change_domains.values())
                or sum(change_domains.values()) != len(changes)
                or not old_complete
                or not new_complete
                or not _tagged_record_matches(
                    old_record, baseline_context["source_tag"],
                    baseline_context["tag_state"])
                or changes != expected_changes
                or change_domains != expected_domains
                or old_record.get("sha256") == new_record.get("sha256")
                or type(item.get("change_count")) is not int
                or item["change_count"] != len(changes)
                or item.get("from_revision") != _ISSUE_2_BASELINE_REVISION
                or item.get("to_revision") != model.get("revision")
                or item.get("accepted") is not True):
            return False
    return True


def _unseen_source_capture_matches(
        record, indicator_id, evidence_root):
    """Verify the archived bytes behind one unseen-country source observation."""
    capture = record.get("captured_source") if isinstance(record, dict) else None
    raw = _verified_record_bytes(
        capture, evidence_root, ref_field="artifact_ref",
        sha_field="content_sha256")
    if (not isinstance(capture, dict)
            or capture.get("media_type") != "application/json"
            or type(capture.get("byte_length")) is not int
            or capture["byte_length"] <= 0
            or raw is None
            or len(raw) != capture["byte_length"]):
        return False
    try:
        captured = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    return captured == {
        "indicator_id": indicator_id,
        "raw_value": record.get("raw_value"),
        "unit": record.get("unit"),
        "reference_period": record.get("reference_period"),
        "tier": record.get("tier"),
        "url": record.get("url"),
        "source_series": record.get("source_series"),
        "edition": record.get("edition"),
        "geography": record.get("geography"),
        "transform_inputs": record.get("transform_inputs"),
    }


def _unseen_source_registry_is_complete(
        registry, model, evidence_root, iso3):
    if not isinstance(registry, dict) or not registry:
        return False
    for source_id, source in registry.items():
        payload = _verified_json_record(source, evidence_root)
        records = payload.get("records") if isinstance(payload, dict) else None
        if (not _present_text(source_id)
                or not isinstance(source, dict)
                or not _specific_definition_text(source.get("title"))
                or not _specific_definition_text(source.get("publisher"))
                or not _valid_iso_date(source.get("accessed_on"))
                or not _record_is_bound_to_model(payload, model)
                or payload.get("kind") != "unseen_country_source_snapshot"
                or payload.get("iso3") != iso3
                or payload.get("title") != source.get("title")
                or payload.get("publisher") != source.get("publisher")
                or payload.get("captured_on") != source.get("accessed_on")
                or not _approval_provenance_is_complete(payload)
                or not isinstance(records, dict)
                or set(records) != set(KNOWN_IDS)
                or any(not isinstance(record, dict)
                       or not (_present_text(record.get("raw_value"))
                               or _finite_number(record.get("raw_value")))
                       or not _present_text(record.get("unit"))
                       or not _present_text(record.get("reference_period"))
                       or record.get("tier") not in SOURCE_TIERS
                       or not _present_text(record.get("url"))
                       or not re.match(r"^https?://", record["url"], re.I)
                       or not _present_text(record.get("source_series"))
                       or not _present_text(record.get("edition"))
                       or not _present_text(record.get("geography"))
                       or not (isinstance(record.get("transform_inputs"), dict)
                               or record.get("transform_inputs")
                               == "not_applicable")
                       or not _specific_definition_text(
                           record.get("evidence_excerpt"))
                       or not _unseen_source_capture_matches(
                           record, indicator_id, evidence_root)
                       or record.get("record_sha256")
                       != _canonical_sha256({
                           key: value for key, value in record.items()
                           if key != "record_sha256"})
                       for indicator_id, record in records.items())):
            return False
    return True


def _construct_review_observation_projection(row):
    if not isinstance(row, dict):
        return None
    projection = dict(row)
    metadata = row.get("definition_metadata")
    if not isinstance(metadata, dict):
        return None
    projection["definition_metadata"] = dict(metadata)
    projection["definition_metadata"].pop("construct_review_sha256", None)
    return projection


def _unseen_construct_reviews_are_complete(
        registry, model, evidence_root, iso3, reviewer, engine_input,
        assessment_rows, source_registry, started, completed):
    definitions = model.get("indicator_definitions")
    entries = definitions.get("entries") if isinstance(definitions, dict) else None
    if (not isinstance(registry, dict)
            or set(registry) != set(KNOWN_IDS)
            or not isinstance(entries, dict)
            or set(entries) != set(KNOWN_IDS)):
        return False
    source_payloads = {
        source_id: _verified_json_record(source, evidence_root)
        for source_id, source in source_registry.items()
    }
    for indicator_id in KNOWN_IDS:
        record = registry.get(indicator_id)
        review = _verified_json_record(record, evidence_root)
        row = engine_input.get(indicator_id)
        assessment = assessment_rows.get(indicator_id)
        metadata = (row.get("definition_metadata")
                    if isinstance(row, dict) else None)
        source_id = (assessment.get("primary_source_id")
                     if isinstance(assessment, dict) else None)
        source = source_registry.get(source_id)
        source_payload = source_payloads.get(source_id)
        source_indicator = (source_payload.get("records", {}).get(indicator_id)
                            if isinstance(source_payload, dict) else None)
        reviewed_at = _parse_iso_datetime(
            review.get("reviewed_at") if isinstance(review, dict) else None)
        expected_disposition = (assessment.get("admissibility")
                                if isinstance(assessment, dict) else None)
        if (not isinstance(record, dict)
                or not isinstance(review, dict)
                or not isinstance(metadata, dict)
                or not isinstance(source, dict)
                or not isinstance(source_indicator, dict)
                or not _record_is_bound_to_model(review, model)
                or review.get("kind") != "construct_review"
                or review.get("iso3") != iso3
                or review.get("indicator_id") != indicator_id
                or review.get("reviewer") != reviewer
                or reviewed_at is None or not started <= reviewed_at <= completed
                or review.get("disposition") != expected_disposition
                or review.get("definition_sha256")
                != _canonical_sha256(entries[indicator_id])
                or review.get("definition_sha256")
                != metadata.get("definition_sha256")
                or review.get("source_record_sha256") != source.get("sha256")
                or review.get("source_record_sha256")
                != metadata.get("source_record_sha256")
                or review.get("source_indicator_record_sha256")
                != source_indicator.get("record_sha256")
                or review.get("observation_sha256")
                != _canonical_sha256(
                    _construct_review_observation_projection(row))
                or review.get("assessment_row_sha256")
                != _canonical_sha256(assessment)
                or not _specific_definition_text(review.get("review_note"))
                or not _approval_provenance_is_complete(review)
                or metadata.get("construct_review_sha256")
                != record.get("sha256")):
            return False
    return True


def _unseen_artifacts_are_complete(payload, model, evidence_root):
    artifacts = payload.get("artifacts") if isinstance(payload, dict) else None
    expected_kinds = {"assessment", "automation_run", "comparison"}
    if not isinstance(artifacts, dict) or set(artifacts) != expected_kinds:
        return False
    started = _parse_iso_datetime(payload.get("started_at"))
    completed = _parse_iso_datetime(payload.get("completed_at"))
    if started is None or completed is None or started >= completed:
        return False
    loaded = {}
    for kind, record in artifacts.items():
        artifact_payload = _verified_json_record(record, evidence_root)
        if (not _record_is_bound_to_model(artifact_payload, model)
                or artifact_payload.get("iso3") != payload.get("iso3")
                or artifact_payload.get("kind") != kind
                or artifact_payload.get("reviewed") is not True):
            return False
        loaded[kind] = artifact_payload
        rows = artifact_payload.get("rows")
        if (not isinstance(rows, dict) or set(rows) != set(KNOWN_IDS)
                or any(not isinstance(row, dict) for row in rows.values())):
            return False
        if kind == "assessment" and (
                artifact_payload.get("row_count") != len(KNOWN_IDS)
                or artifact_payload.get("source_reviewed") is not True
                or _parse_iso_datetime(artifact_payload.get("started_at"))
                is None
                or _parse_iso_datetime(artifact_payload.get("completed_at"))
                is None
                or not _unseen_source_registry_is_complete(
                    artifact_payload.get("source_registry"), model, evidence_root,
                    payload.get("iso3"))
                or any(row.get("human_level") not in {None, 1, 2, 3, 4, 5}
                       or row.get("admissibility") not in {
                           "accepted", "held", "data_gap"}
                       or "raw_value" not in row
                       or not (_present_text(row.get("raw_value"))
                               or _finite_number(row.get("raw_value")))
                       or (row.get("admissibility") == "accepted"
                           and row.get("human_level") not in {1, 2, 3, 4, 5})
                       or (row.get("admissibility") in {"held", "data_gap"}
                           and row.get("human_level") is not None)
                       or (row.get("admissibility") == "data_gap" and (
                           not _present_text(row.get("raw_value"))
                           or not row["raw_value"].lstrip().upper().startswith(
                               "DATA GAP")
                           or not row.get("source_ids")))
                       or not _present_text(row.get("unit"))
                       or not _present_text(row.get("reference_period"))
                       or not isinstance(row.get("source_ids"), list)
                       or (row.get("admissibility") == "accepted"
                           and not row["source_ids"])
                       or row.get("primary_source_id")
                       not in row.get("source_ids", [])
                       or not set(row.get("source_ids") or [])
                       <= set(artifact_payload.get("source_registry") or {})
                       or not _present_text(row.get("review_note"))
                       for row in rows.values())):
            return False
        if kind == "automation_run" and (
                artifact_payload.get("row_count") != len(KNOWN_IDS)
                or artifact_payload.get("completed") is not True
                or not _present_text(artifact_payload.get("run_id"))
                or _parse_iso_datetime(artifact_payload.get("started_at"))
                is None
                or _parse_iso_datetime(artifact_payload.get("completed_at"))
                is None
                or artifact_payload.get("refyear")
                != model.get("config", {}).get("assessment_year")
                or artifact_payload.get("implementation_sha256")
                != _release_implementation_sha256(model)
                or artifact_payload.get("engine_output_sha256")
                != _canonical_sha256(artifact_payload.get("engine_output"))
                or any(row.get("automation_level")
                       not in {None, 1, 2, 3, 4, 5}
                       or row.get("status") not in {
                           "scored", "held", "data_gap"}
                       or not isinstance(row.get("input_sha256"), str)
                       or not _SHA256_TEXT.fullmatch(row["input_sha256"])
                       or not _present_text(row.get("trace_id"))
                       for row in rows.values())):
            return False
        if kind == "comparison" and (
                artifact_payload.get("compared_rows") != len(KNOWN_IDS)
                or artifact_payload.get("accepted") is not True
                or artifact_payload.get("reviewer")
                != payload.get("independent_reviewer")
                or not _approval_provenance_is_complete(artifact_payload)
                or _parse_iso_datetime(artifact_payload.get("completed_at"))
                is None
                or not isinstance(artifact_payload.get("discrepancies"), list)
                or any(row.get("outcome") not in {
                           "match", "accepted_difference"}
                       or row.get("human_level") not in {None, 1, 2, 3, 4, 5}
                       or row.get("automation_level")
                       not in {None, 1, 2, 3, 4, 5}
                       or not isinstance(row.get("human_row_sha256"), str)
                       or not _SHA256_TEXT.fullmatch(row["human_row_sha256"])
                       or not isinstance(row.get("automation_row_sha256"), str)
                       or not _SHA256_TEXT.fullmatch(row["automation_row_sha256"])
                       or not _present_text(row.get("review_note"))
                       or (row.get("outcome") == "accepted_difference"
                           and not _specific_definition_text(
                               row.get("resolution")))
                       for row in rows.values())
                or set(artifact_payload["discrepancies"])
                != {indicator_id for indicator_id, row in rows.items()
                    if row["human_level"] != row["automation_level"]}
                or any((row["outcome"] == "match")
                       != (row["human_level"] == row["automation_level"])
                       for row in rows.values())):
            return False
    assessment_rows = loaded["assessment"]["rows"]
    automation_rows = loaded["automation_run"]["rows"]
    comparison_rows = loaded["comparison"]["rows"]
    engine_input = loaded["automation_run"].get("engine_input")
    engine_output = loaded["automation_run"].get("engine_output")
    intervention_profiles = loaded["automation_run"].get(
        "intervention_profiles")
    source_registry = loaded["assessment"].get("source_registry")
    source_payloads = {
        source_id: _verified_json_record(source, evidence_root)
        for source_id, source in source_registry.items()
    }
    assessment_started = _parse_iso_datetime(
        loaded["assessment"].get("started_at"))
    assessment_completed = _parse_iso_datetime(
        loaded["assessment"].get("completed_at"))
    automation_started = _parse_iso_datetime(
        loaded["automation_run"].get("started_at"))
    automation_completed = _parse_iso_datetime(
        loaded["automation_run"].get("completed_at"))
    comparison_completed = _parse_iso_datetime(
        loaded["comparison"].get("completed_at"))
    if not _unseen_construct_reviews_are_complete(
            loaded["assessment"].get("construct_review_registry"),
            model, evidence_root, payload.get("iso3"),
            payload.get("independent_reviewer"), engine_input,
            assessment_rows, source_registry, assessment_started,
            assessment_completed):
        return False
    if not (started == assessment_started < assessment_completed
            <= automation_started < automation_completed
            <= comparison_completed == completed):
        return False
    if (assessment_input_errors(engine_input, spec=model)
            or not isinstance(engine_output, dict)
            or not isinstance(intervention_profiles, dict)):
        return False
    try:
        replayed = engine_run(
            payload.get("country_name"), engine_input,
            refyear=loaded["automation_run"].get("refyear"),
            model_spec=model, intervention_profiles=intervention_profiles)
    except (KeyError, TypeError, ValueError):
        return False
    if _canonical_sha256(replayed) != _canonical_sha256(engine_output):
        return False
    threshold_ids = {
        item.get("id") for item in model.get("indicators", [])
        if isinstance(item, dict) and item.get("method") == "threshold"
    }
    calibration_refs = model.get("indicator_calibration_refs")
    if (len(threshold_ids) != 32
            or not isinstance(calibration_refs, dict)
            or set(calibration_refs) != threshold_ids
            or any(
                engine_input[indicator_id].get("cls") != "Measured"
                or not _finite_number(engine_input[indicator_id].get("value"))
                or engine_input[indicator_id].get("level")
                not in {1, 2, 3, 4, 5}
                or engine_output.get("indicators", {}).get(
                    indicator_id, {}).get("cls") != "Measured"
                or engine_output.get("indicators", {}).get(
                    indicator_id, {}).get("level") not in {1, 2, 3, 4, 5}
                or assessment_rows[indicator_id].get("admissibility")
                != "accepted"
                or assessment_rows[indicator_id].get("human_level")
                not in {1, 2, 3, 4, 5}
                or automation_rows[indicator_id].get("status") != "scored"
                or automation_rows[indicator_id].get("automation_level")
                not in {1, 2, 3, 4, 5}
                for indicator_id in threshold_ids)):
        return False
    return all(
        automation_rows[indicator_id]["input_sha256"]
        == _canonical_sha256(engine_input[indicator_id])
        and ((assessment_rows[indicator_id]["admissibility"] == "data_gap")
             == (engine_input[indicator_id]["cls"] == "Gap"))
        and (assessment_rows[indicator_id]["admissibility"] != "held"
             or (engine_input[indicator_id]["cls"] != "Gap"
                 and engine_input[indicator_id]["level"] is None))
        and assessment_rows[indicator_id]["raw_value"]
        == engine_input[indicator_id]["value"]
        and assessment_rows[indicator_id]["unit"]
        == engine_input[indicator_id]["definition_metadata"]["unit"]
        and assessment_rows[indicator_id]["reference_period"]
        == engine_input[indicator_id]["definition_metadata"][
            "observation_period"]
        and engine_input[indicator_id]["definition_metadata"]["geography"]
        .casefold() == payload.get("country_name", "").casefold()
        and engine_input[indicator_id]["definition_metadata"][
            "source_record_sha256"]
        == source_registry[
            assessment_rows[indicator_id]["primary_source_id"]]["sha256"]
        and source_payloads[
            assessment_rows[indicator_id]["primary_source_id"]]["records"][
                indicator_id]["raw_value"]
        == engine_input[indicator_id]["value"]
        and source_payloads[
            assessment_rows[indicator_id]["primary_source_id"]]["records"][
                indicator_id]["unit"]
        == engine_input[indicator_id]["definition_metadata"]["unit"]
        and source_payloads[
            assessment_rows[indicator_id]["primary_source_id"]]["records"][
                indicator_id]["reference_period"]
        == engine_input[indicator_id]["definition_metadata"][
            "observation_period"]
        and source_payloads[
            assessment_rows[indicator_id]["primary_source_id"]]["records"][
                indicator_id]["tier"]
        == engine_input[indicator_id]["tier"]
        and source_payloads[
            assessment_rows[indicator_id]["primary_source_id"]]["records"][
                indicator_id]["url"]
        == engine_input[indicator_id]["url"]
        and source_payloads[
            assessment_rows[indicator_id]["primary_source_id"]]["records"][
                indicator_id]["source_series"]
        == engine_input[indicator_id]["definition_metadata"]["source_series"]
        and source_payloads[
            assessment_rows[indicator_id]["primary_source_id"]]["records"][
                indicator_id]["edition"]
        == engine_input[indicator_id]["definition_metadata"]["edition"]
        and source_payloads[
            assessment_rows[indicator_id]["primary_source_id"]]["records"][
                indicator_id]["geography"]
        == engine_input[indicator_id]["definition_metadata"]["geography"]
        and source_payloads[
            assessment_rows[indicator_id]["primary_source_id"]]["records"][
                indicator_id]["transform_inputs"]
        == engine_input[indicator_id]["definition_metadata"].get(
            "transform_inputs", "not_applicable")
        and automation_rows[indicator_id]["automation_level"]
        == engine_output["indicators"][indicator_id]["level"]
        and automation_rows[indicator_id]["status"]
        == ("data_gap" if engine_output["indicators"][indicator_id]["cls"] == "Gap"
            else "held" if engine_output["indicators"][indicator_id]["level"] is None
            else "scored")
        and comparison_rows[indicator_id]["human_row_sha256"]
        == _canonical_sha256(assessment_rows[indicator_id])
        and comparison_rows[indicator_id]["automation_row_sha256"]
        == _canonical_sha256(automation_rows[indicator_id])
        and comparison_rows[indicator_id]["human_level"]
        == assessment_rows[indicator_id]["human_level"]
        and comparison_rows[indicator_id]["automation_level"]
        == automation_rows[indicator_id]["automation_level"]
        for indicator_id in KNOWN_IDS)


def _unseen_follows_migration(
        unseen_payload, migration_payload, model, evidence_root):
    timeline = _migration_timeline(migration_payload, model, evidence_root)
    unseen_started = _parse_iso_datetime(
        unseen_payload.get("started_at")
        if isinstance(unseen_payload, dict) else None)
    if timeline is None or unseen_started is None:
        return False
    freeze_record = migration_payload.get("method_freeze")
    return (timeline[2] < unseen_started
            and unseen_payload.get("method_freeze_sha256")
            == freeze_record.get("sha256")
            and unseen_payload.get("migration_payload_sha256")
            == _canonical_sha256(migration_payload))


def _xml_local_name(tag):
    return tag.rsplit("}", 1)[-1]


def _xlsx_rows(archive, path, shared_strings):
    root = ET.fromstring(archive.read(path))
    rows = []
    for row in (item for item in root.iter()
                if _xml_local_name(item.tag) == "row"):
        values = []
        for cell in (item for item in row
                     if _xml_local_name(item.tag) == "c"):
            cell_type = cell.get("t")
            value_node = next((item for item in cell.iter()
                               if _xml_local_name(item.tag) == "v"), None)
            if cell_type == "s" and value_node is not None:
                try:
                    value = shared_strings[int(value_node.text)]
                except (IndexError, TypeError, ValueError):
                    value = ""
            elif cell_type == "inlineStr":
                value = "".join(
                    item.text or "" for item in cell.iter()
                    if _xml_local_name(item.tag) == "t")
            else:
                value = value_node.text if value_node is not None else ""
            values.append(value or "")
        if values:
            rows.append(values)
    return root, rows


def _xlsx_cell_value(cell, shared_strings):
    cell_type = cell.get("t")
    value_node = next((item for item in cell.iter()
                       if _xml_local_name(item.tag) == "v"), None)
    if cell_type == "s" and value_node is not None:
        try:
            value = shared_strings[int(value_node.text)]
        except (IndexError, TypeError, ValueError):
            return ""
    elif cell_type == "inlineStr":
        value = "".join(
            item.text or "" for item in cell.iter()
            if _xml_local_name(item.tag) == "t")
    else:
        value = value_node.text if value_node is not None else ""
    return value or ""


def _xlsx_row_cells(row, shared_strings):
    row_number = row.get("r")
    if not isinstance(row_number, str) or not row_number.isdigit():
        return None
    cells = {}
    for cell in (item for item in row
                 if _xml_local_name(item.tag) == "c"):
        match = re.fullmatch(r"([A-Z]+)([1-9][0-9]*)", cell.get("r") or "")
        if match is None or match.group(2) != row_number:
            return None
        column = match.group(1)
        formulas = [item.text or "" for item in cell.iter()
                    if _xml_local_name(item.tag) == "f"]
        if column in cells or len(formulas) > 1:
            return None
        cells[column] = {
            "value": _xlsx_cell_value(cell, shared_strings),
            "formula": formulas[0] if formulas else None,
            "cell_type": cell.get("t"),
        }
    return cells


_WORKBOOK_USE_CASES = ("ADV", "SMF", "MKT", "SCM", "FIN", "AGI")
_WORKBOOK_PILLARS = ("A1", "C1", "C2", "C3", "C4", "E1", "O1")
_WORKBOOK_LAYERS = ("Foundation", "Enablers", "Transformation", "Outcomes")
_WORKBOOK_PROFILE_FIELDS = (
    "targeted_farmer_level_delivery",
    "cross_organization_agricultural_data_sharing",
    "cross_ministerial_delivery", "moag_led_or_owned",
    "uses_personal_data", "uses_farm_level_data", "ai_enabled",
)
_WORKBOOK_PROFILE_COLUMNS = dict(zip(
    _WORKBOOK_PROFILE_FIELDS, ("O", "P", "Q", "R", "S", "T", "U")))
_WORKBOOK_FIRST_INDICATOR_ROW = 2
_WORKBOOK_LAST_INDICATOR_ROW = _WORKBOOK_FIRST_INDICATOR_ROW + len(KNOWN_IDS) - 1
_WORKBOOK_PILLAR_ROW = 62
_WORKBOOK_LAYER_ROW = 72
_WORKBOOK_LEAPFROG_ROW = 78
_WORKBOOK_PREREQUISITE_ROW = 82
_WORKBOOK_MATRIX_ROW = 97
_WORKBOOK_MAPPING_ROW = 21


def _workbook_column_name(index):
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _xlsx_sheet_cells(root, shared_strings):
    cells = {}
    for row in (item for item in root.iter()
                if _xml_local_name(item.tag) == "row"):
        row_cells = _xlsx_row_cells(row, shared_strings)
        if row_cells is None:
            return None
        for column, payload in row_cells.items():
            reference = f"{column}{row.get('r')}"
            if reference in cells:
                return None
            cells[reference] = payload
    return cells


def _workbook_literal_matches(actual, expected):
    if type(expected) in (int, float):
        try:
            numeric = float(actual)
        except (TypeError, ValueError):
            return False
        return math.isfinite(numeric) and numeric == float(expected)
    return actual == ("" if expected is None else str(expected))


def _workbook_sheet_matches_manifest(
        root, shared_strings, expected_literals, expected_formulas):
    cells = _xlsx_sheet_cells(root, shared_strings)
    if cells is None:
        return False
    for reference, expected in expected_literals.items():
        cell = cells.get(reference)
        if (cell is None or cell["formula"] is not None
                or not _workbook_literal_matches(cell["value"], expected)):
            return False
    actual_formulas = {
        reference: cell["formula"] for reference, cell in cells.items()
        if cell["formula"] is not None
    }
    return actual_formulas == expected_formulas


def _workbook_expected_class_formula(row_number):
    return (
        f'IF($M{row_number}="","",IF(ISNUMBER($M{row_number}),"Measured",'
        f'IF(ISNUMBER(SEARCH("DATA GAP",UPPER($M{row_number}))),"Gap",'
        f'IF(AND($N{row_number}<>"",$P{row_number}<>"T5"),'
        f'"Documented","Judged"))))')


def _workbook_expected_level_formula(row_number):
    """Canonical executable scoring formula for column T of the release workbook."""
    return (
        f'IF($AC{row_number}<>"","",IF(OR($S{row_number}="",'
        f'$S{row_number}="Gap"),"",IF($S{row_number}="Measured",'
        f'IF($G{row_number}="threshold",1+'
        f'IF($H{row_number}="higher-is-better",'
        f'IF($M{row_number}>=$I{row_number},1,0)+'
        f'IF($M{row_number}>=$J{row_number},1,0)+'
        f'IF($M{row_number}>=$K{row_number},1,0)+'
        f'IF($M{row_number}>=$L{row_number},1,0),'
        f'IF($M{row_number}<=$I{row_number},1,0)+'
        f'IF($M{row_number}<=$J{row_number},1,0)+'
        f'IF($M{row_number}<=$K{row_number},1,0)+'
        f'IF($M{row_number}<=$L{row_number},1,0)),""),'
        f'IF($R{row_number}<>"",$R{row_number},""))))')


def _workbook_expected_stale_formula(row_number):
    return (
        f'IF(OR($S{row_number}="",$S{row_number}="Gap",$Q{row_number}=""),'
        f'"",IF($Q{row_number}<Config!$B$7-Config!$B$8,"STALE",""))')


def _workbook_expected_bearing_formula(row_number, use_case_id):
    return (
        f'IF(OR(ISNUMBER(SEARCH("ALL",$E{row_number})),'
        f'ISNUMBER(SEARCH("{use_case_id}",$E{row_number}))),1,0)')


def _workbook_expected_hold_formula(row_number):
    return f'IF($AB{row_number}="match","","HOLD")'


def _workbook_predicate_expression(predicate, profile_row):
    if not isinstance(predicate, dict):
        return None
    if set(predicate) == {"field", "equals"}:
        column = _WORKBOOK_PROFILE_COLUMNS.get(predicate.get("field"))
        if column is None or type(predicate.get("equals")) is not bool:
            return None
        expected = "true" if predicate["equals"] else "false"
        cell = f'${column}${profile_row}'
        return f'IF({cell}="",-1,IF({cell}="{expected}",1,0))'
    for operator in ("any", "all"):
        if set(predicate) != {operator}:
            continue
        children = predicate[operator]
        if not isinstance(children, list) or not children:
            return None
        expressions = [
            _workbook_predicate_expression(child, profile_row)
            for child in children
        ]
        if any(expression is None for expression in expressions):
            return None
        if operator == "any":
            return (f'IF(OR({",".join(f"({item})=1" for item in expressions)}),1,'
                    f'IF(OR({",".join(f"({item})=-1" for item in expressions)}),-1,0))')
        return (f'IF(OR({",".join(f"({item})=0" for item in expressions)}),0,'
                f'IF(OR({",".join(f"({item})=-1" for item in expressions)}),-1,1))')
    return None


def _workbook_config_manifest(model):
    mapping = model.get("prerequisite_mapping")
    config = model.get("config")
    bands = model.get("bands")
    if (not isinstance(mapping, dict) or not isinstance(config, dict)
            or not isinstance(bands, list) or len(bands) != 5):
        return None
    edges = mapping.get("edges")
    prerequisite_ids = mapping.get("prerequisite_ids")
    if (not isinstance(edges, list) or len(edges) != 72
            or not isinstance(prerequisite_ids, list)
            or len(prerequisite_ids) != 12):
        return None
    sorted_edges = sorted(edges, key=lambda item: (
        item.get("prerequisite_id", ""), item.get("use_case_id", "")))
    prerequisite_rows = {
        indicator_id: _WORKBOOK_PREREQUISITE_ROW + index
        for index, indicator_id in enumerate(sorted(prerequisite_ids))
    }
    literals = {
        "A1": "key", "B1": "value",
        "A2": "status: ratified", "B2": "ratified",
        "A3": f"model_version:{model.get('version')}", "B3": model.get("version"),
        "A4": f"model_revision:{model.get('revision')}", "B4": model.get("revision"),
        "A5": f"model_sha256:{_model_ratification_sha256(model)}",
        "B5": _model_ratification_sha256(model),
        "A6": f"prerequisite_mapping_revision:{mapping.get('revision')}",
        "B6": mapping.get("revision"),
        "A7": "assessment_year", "B7": config.get("assessment_year"),
        "A8": "staleness_years", "B8": config.get("staleness_years"),
        "A9": "readiness_threshold", "B9": config.get("readiness_threshold"),
        "A10": "leapfrog_threshold", "B10": config.get("leapfrog_threshold"),
        "A11": "rounding", "B11": config.get("rounding"),
        "A13": "band", "B13": "lo", "C13": "hi", "D13": "name",
        "N1": "use_case_id",
        "A20": "edge_id", "B20": "prerequisite_id", "C20": "use_case_id",
        "D20": "effect", "E20": "applicability", "F20": "Absent",
        "G20": "Unverified", "H20": "Present (narrow)", "I20": "Present",
        "J20": "edge_contract", "K20": "prerequisite_status",
        "L20": "predicate_state", "M20": "selected_action",
        "N20": "active_action", "O20": "delivery_risk", "P20": "gate_candidate",
    }
    for index, field in enumerate(_WORKBOOK_PROFILE_FIELDS, start=15):
        column = _workbook_column_name(index)
        literals[f"{column}1"] = field
    for index, use_case_id in enumerate(_WORKBOOK_USE_CASES, start=2):
        literals[f"N{index}"] = use_case_id
    for index, band in enumerate(bands, start=14):
        if not isinstance(band, dict):
            return None
        literals.update({
            f"A{index}": index - 13, f"B{index}": band.get("lo"),
            f"C{index}": band.get("hi"), f"D{index}": band.get("name"),
        })
    formulas = {}
    for index, edge in enumerate(sorted_edges, start=_WORKBOOK_MAPPING_ROW):
        if not isinstance(edge, dict):
            return None
        prerequisite_id = edge.get("prerequisite_id")
        use_case_id = edge.get("use_case_id")
        if (prerequisite_id not in prerequisite_rows
                or use_case_id not in _WORKBOOK_USE_CASES):
            return None
        applicability = edge.get("applicability")
        outcomes = edge.get("on_prerequisite_status") or {}
        mode = applicability.get("mode") if isinstance(applicability, dict) else None
        literals.update({
            f"A{index}": edge.get("id"), f"B{index}": prerequisite_id,
            f"C{index}": use_case_id, f"D{index}": edge.get("effect"),
            f"E{index}": json.dumps(
                applicability, sort_keys=True, separators=(",", ":")),
            f"F{index}": outcomes.get("Absent", ""),
            f"G{index}": outcomes.get("Unverified", ""),
            f"H{index}": outcomes.get("Present (narrow)", ""),
            f"I{index}": outcomes.get("Present", ""),
            f"J{index}": (
                f"mapping_edge_sha256:{edge.get('id')}:{_canonical_sha256(edge)}"),
        })
        formulas[f"K{index}"] = (
            f'INDEX(Scoring!$D${_WORKBOOK_PREREQUISITE_ROW}:'
            f'$D${_WORKBOOK_PREREQUISITE_ROW + 11},MATCH($B{index},'
            f'Scoring!$A${_WORKBOOK_PREREQUISITE_ROW}:'
            f'$A${_WORKBOOK_PREREQUISITE_ROW + 11},0))')
        if mode == "never":
            formulas[f"L{index}"] = '"inactive"'
        elif mode == "always":
            formulas[f"L{index}"] = '"active"'
        elif mode == "conditional":
            profile_row = 2 + _WORKBOOK_USE_CASES.index(use_case_id)
            expression = _workbook_predicate_expression(
                applicability.get("predicate"), profile_row)
            if expression is None:
                return None
            formulas[f"L{index}"] = (
                f'IF(({expression})=1,"active",'
                f'IF(({expression})=0,"inactive","unresolved"))')
        else:
            return None
        formulas[f"M{index}"] = (
            f'IF($K{index}="Absent",$F{index},IF($K{index}="Unverified",'
            f'$G{index},IF($K{index}="Present (narrow)",$H{index},$I{index})))')
        formulas[f"N{index}"] = (
            f'IF($L{index}="active",$M{index},"")')
        formulas[f"O{index}"] = (
            f'IF(AND($D{index}="delivery_risk",$L{index}="active",'
            f'$M{index}<>"no_change"),$M{index},"")')
        formulas[f"P{index}"] = (
            f'IF(AND($D{index}="gate",$L{index}="active",'
            f'$M{index}<>"no_change"),$M{index},"")')
    return literals, formulas


def _workbook_scoring_manifest(model):
    indicators = model.get("indicators")
    mapping = model.get("prerequisite_mapping")
    if not isinstance(indicators, list) or not isinstance(mapping, dict):
        return None
    indicator_by_id = {
        row.get("id"): row for row in indicators if isinstance(row, dict)
    }
    if set(indicator_by_id) != set(KNOWN_IDS):
        return None
    prerequisite_ids = mapping.get("prerequisite_ids")
    if not isinstance(prerequisite_ids, list) or len(prerequisite_ids) != 12:
        return None
    headers = (
        "indicator_id", "name", "pillar", "layer", "bearing_tokens",
        "prerequisite", "method", "direction", "cut_1", "cut_2", "cut_3",
        "cut_4", "value", "source", "url", "tier", "year", "assessor_level",
        "class", "level", "stale", "b_ADV", "b_SMF", "b_MKT", "b_SCM",
        "b_FIN", "b_AGI", "definition_match", "hold", "scoring_contract",
    )
    columns = (
        "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L",
        "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X",
        "Y", "Z", "AA", "AB", "AC", "AD",
    )
    literals = {f"{column}1": value for column, value in zip(columns, headers)}
    formulas = {}
    for offset, indicator_id in enumerate(sorted(KNOWN_IDS)):
        row_number = _WORKBOOK_FIRST_INDICATOR_ROW + offset
        indicator = indicator_by_id[indicator_id]
        thresholds = list(indicator.get("thresholds") or [])
        thresholds.extend([""] * (4 - len(thresholds)))
        values = {
            "A": indicator_id, "B": indicator.get("name"),
            "C": indicator.get("pillar"), "D": indicator.get("layer"),
            "E": ",".join((indicator.get("use_cases") or [])
                            + (indicator.get("tags") or [])),
            "F": indicator.get("prerequisite") or "",
            "G": indicator.get("method"), "H": indicator.get("direction") or "",
            "I": thresholds[0], "J": thresholds[1],
            "K": thresholds[2], "L": thresholds[3],
            "AD": _workbook_scoring_contract(model, indicator_id),
        }
        literals.update({f"{column}{row_number}": value
                         for column, value in values.items()})
        formulas[f"S{row_number}"] = _workbook_expected_class_formula(row_number)
        formulas[f"T{row_number}"] = _workbook_expected_level_formula(row_number)
        formulas[f"U{row_number}"] = _workbook_expected_stale_formula(row_number)
        for index, use_case_id in enumerate(_WORKBOOK_USE_CASES, start=22):
            column = _workbook_column_name(index)
            formulas[f"{column}{row_number}"] = (
                _workbook_expected_bearing_formula(row_number, use_case_id))
        formulas[f"AC{row_number}"] = _workbook_expected_hold_formula(row_number)

    first, last = _WORKBOOK_FIRST_INDICATOR_ROW, _WORKBOOK_LAST_INDICATOR_ROW
    pillar_headers = (
        "pillar", "n", "rated", "held", "mean", "band", "margin", "weak",
        "Measured", "Documented", "Judged", "Gap", "stale",
    )
    for index, value in enumerate(pillar_headers, start=1):
        literals[f"{_workbook_column_name(index)}61"] = value
    for index, pillar_id in enumerate(_WORKBOOK_PILLARS):
        row_number = _WORKBOOK_PILLAR_ROW + index
        literals[f"A{row_number}"] = pillar_id
        formulas[f"B{row_number}"] = f'COUNTIF($C${first}:$C${last},$A{row_number})'
        formulas[f"C{row_number}"] = (
            f'COUNTIFS($C${first}:$C${last},$A{row_number},'
            f'$T${first}:$T${last},">0")')
        formulas[f"D{row_number}"] = (
            f'COUNTIFS($C${first}:$C${last},$A{row_number},'
            f'$T${first}:$T${last},"",$S${first}:$S${last},"<>Gap")')
        formulas[f"E{row_number}"] = (
            f'IFERROR(ROUND(AVERAGEIF($C${first}:$C${last},$A{row_number},'
            f'$T${first}:$T${last}),2),"")')
        formulas[f"F{row_number}"] = (
            f'IF($E{row_number}="","Not rated",IF($E{row_number}<Config!$B$15,'
            f'Config!$D$14,IF($E{row_number}<Config!$B$16,Config!$D$15,'
            f'IF($E{row_number}<Config!$B$17,Config!$D$16,'
            f'IF($E{row_number}<Config!$B$18,Config!$D$17,Config!$D$18)))))')
        formulas[f"G{row_number}"] = (
            f'IF($E{row_number}="","",ROUND($E{row_number}-'
            f'MATCH($F{row_number},Config!$D$14:$D$18,0),2))')
        judged_rated = (
            f'COUNTIFS($C${first}:$C${last},$A{row_number},'
            f'$S${first}:$S${last},"Judged",$T${first}:$T${last},">0")')
        formulas[f"H{row_number}"] = (
            f'IF(({judged_rated}+$L{row_number}+$D{row_number})>'
            f'($C{row_number}-{judged_rated}),TRUE,FALSE)')
        for column, evidence_class in zip(("I", "J", "K", "L"),
                                          ("Measured", "Documented", "Judged", "Gap")):
            formulas[f"{column}{row_number}"] = (
                f'COUNTIFS($C${first}:$C${last},$A{row_number},'
                f'$S${first}:$S${last},"{evidence_class}")')
        formulas[f"M{row_number}"] = (
            f'COUNTIFS($C${first}:$C${last},$A{row_number},'
            f'$U${first}:$U${last},"STALE")')

    literals.update({"A71": "layer", "B71": "mean"})
    for index, layer in enumerate(_WORKBOOK_LAYERS):
        row_number = _WORKBOOK_LAYER_ROW + index
        literals[f"A{row_number}"] = layer
        formulas[f"B{row_number}"] = (
            f'IFERROR(ROUND(AVERAGEIF($D${first}:$D${last},$A{row_number},'
            f'$T${first}:$T${last}),2),"")')
    literals.update({
        f"A{_WORKBOOK_LEAPFROG_ROW}": "Foundation - Transformation",
        f"B{_WORKBOOK_LEAPFROG_ROW - 1}": "gap",
        f"C{_WORKBOOK_LEAPFROG_ROW - 1}": "flag",
        f"D{_WORKBOOK_LEAPFROG_ROW - 1}": "reading",
    })
    leap = _WORKBOOK_LEAPFROG_ROW
    formulas[f"B{leap}"] = (
        f'IF(OR($B${_WORKBOOK_LAYER_ROW}="",$B${_WORKBOOK_LAYER_ROW + 2}=""),'
        f'"",ROUND($B${_WORKBOOK_LAYER_ROW}-$B${_WORKBOOK_LAYER_ROW + 2},2))')
    formulas[f"C{leap}"] = (
        f'IF($B{leap}="",FALSE,ABS($B{leap})>Config!$B$10)')
    formulas[f"D{leap}"] = (
        f'IF($B{leap}="","No structural flag",IF($B{leap}<-Config!$B$10,'
        f'"Transformation running ahead of foundations — leapfrog fragility",'
        f'IF($B{leap}>Config!$B$10,'
        f'"Foundations ahead of ecosystem — unrealized potential",'
        f'"No structural flag")))')

    literals.update({"A81": "prerequisite_id", "B81": "name",
                     "C81": "scope", "D81": "status"})
    for index, indicator_id in enumerate(sorted(prerequisite_ids)):
        row_number = _WORKBOOK_PREREQUISITE_ROW + index
        indicator = indicator_by_id.get(indicator_id)
        if indicator is None:
            return None
        data_row = _WORKBOOK_FIRST_INDICATOR_ROW + sorted(KNOWN_IDS).index(indicator_id)
        literals.update({
            f"A{row_number}": indicator_id, f"B{row_number}": indicator.get("name"),
            f"C{row_number}": indicator.get("prerequisite"),
        })
        formulas[f"D{row_number}"] = (
            f'IF(OR($S${data_row}="Gap",$S${data_row}="",$T${data_row}=""),'
            f'"Unverified",IF($T${data_row}>=3,"Present",'
            f'IF($T${data_row}=2,"Present (narrow)","Absent")))')

    matrix_headers = (
        "use_case_id", "n_bearing", "basis_need", "basis_enabler",
        "basis_outcome", "mean_need", "mean_readiness", "mean_outcome",
        "status", "why", "mean_driven", "conditional_unresolved",
        "delivery_risk_count",
    )
    for index, value in enumerate(matrix_headers, start=1):
        literals[f"{_workbook_column_name(index)}96"] = value
    edge_rows = {
        use_case_id: [
            _WORKBOOK_MAPPING_ROW + index
            for index, edge in enumerate(sorted(
                mapping.get("edges") or [], key=lambda item: (
                    item.get("prerequisite_id", ""), item.get("use_case_id", ""))))
            if edge.get("use_case_id") == use_case_id
        ] for use_case_id in _WORKBOOK_USE_CASES
    }
    for index, use_case_id in enumerate(_WORKBOOK_USE_CASES):
        row_number = _WORKBOOK_MATRIX_ROW + index
        flag_column = _workbook_column_name(22 + index)
        literals[f"A{row_number}"] = use_case_id
        formulas[f"B{row_number}"] = (
            f'COUNTIFS(${flag_column}${first}:${flag_column}${last},1,'
            f'$T${first}:$T${last},">0")')
        formulas[f"C{row_number}"] = (
            f'COUNTIFS(${flag_column}${first}:${flag_column}${last},1,'
            f'$T${first}:$T${last},">0",$C${first}:$C${last},"A1")')
        formulas[f"D{row_number}"] = (
            f'COUNTIFS(${flag_column}${first}:${flag_column}${last},1,'
            f'$T${first}:$T${last},">0",$C${first}:$C${last},"<>A1",'
            f'$C${first}:$C${last},"<>O1")')
        formulas[f"E{row_number}"] = (
            f'COUNTIFS(${flag_column}${first}:${flag_column}${last},1,'
            f'$T${first}:$T${last},">0",$C${first}:$C${last},"O1")')
        for column, criterion in (("F", "A1"), ("H", "O1")):
            formulas[f"{column}{row_number}"] = (
                f'IFERROR(ROUND(AVERAGEIFS($T${first}:$T${last},'
                f'${flag_column}${first}:${flag_column}${last},1,'
                f'$C${first}:$C${last},"{criterion}"),2),"")')
        formulas[f"G{row_number}"] = (
            f'IFERROR(ROUND(AVERAGEIFS($T${first}:$T${last},'
            f'${flag_column}${first}:${flag_column}${last},1,'
            f'$C${first}:$C${last},"<>A1",$C${first}:$C${last},"<>O1"),2),"")')
        formulas[f"I{row_number}"] = (
            f'IF(COUNTIFS(Config!$C$21:$C$92,$A{row_number},Config!$P$21:$P$92,'
            f'"Blocked")>0,"Blocked",IF(COUNTIFS(Config!$C$21:$C$92,'
            f'$A{row_number},Config!$P$21:$P$92,"Unverified")>0,"Unverified",'
            f'IF(OR(COUNTIFS(Config!$C$21:$C$92,$A{row_number},'
            f'Config!$P$21:$P$92,"Partial")>0,AND($G{row_number}<>"",'
            f'$G{row_number}<Config!$B$9)),"Partial","Ready")))')
        driver_parts = [
            f'IF(Config!$P${edge_row}=$I{row_number},Config!$B${edge_row}&" ","")'
            for edge_row in edge_rows[use_case_id]
        ]
        driver_expression = (
            f'SUBSTITUTE(TRIM({"&".join(driver_parts)})," ",", ")'
            if driver_parts else '""'
        )
        formulas[f"J{row_number}"] = (
            f'IF($I{row_number}="Ready","",IF(TRIM({driver_expression})<>"",'
            f'TRIM({driver_expression}),IF(AND($I{row_number}="Partial",'
            f'$G{row_number}<>"",$G{row_number}<Config!$B$9),'
            f'"thin enablers","")))')
        formulas[f"K{row_number}"] = (
            f'IF(AND($I{row_number}="Partial",'
            f'$G{row_number}<>"",$G{row_number}<Config!$B$9),1,0)')
        formulas[f"L{row_number}"] = (
            f'COUNTIFS(Config!$C$21:$C$92,$A{row_number},'
            f'Config!$L$21:$L$92,"unresolved",Config!$D$21:$D$92,"<>none")')
        formulas[f"M{row_number}"] = (
            f'COUNTIFS(Config!$C$21:$C$92,$A{row_number},'
            f'Config!$O$21:$O$92,"flag")+'
            f'COUNTIFS(Config!$C$21:$C$92,$A{row_number},'
            f'Config!$O$21:$O$92,"verify")+'
            f'COUNTIFS(Config!$C$21:$C$92,$A{row_number},'
            f'Config!$O$21:$O$92,"flag_narrow")')
    return literals, formulas


def _workbook_definitions_manifest(model):
    catalog = model.get("indicator_definitions")
    entries = catalog.get("entries") if isinstance(catalog, dict) else None
    calibration_refs = model.get("indicator_calibration_refs")
    if not isinstance(entries, dict) or set(entries) != set(KNOWN_IDS):
        return None
    literals = {
        "A1": "indicator_id", "B1": "definition_version",
        "C1": "calibration_ref", "D1": "definition_sha256",
        "E1": "source_policy_sha256",
    }
    for index, indicator_id in enumerate(sorted(KNOWN_IDS), start=2):
        entry = entries[indicator_id]
        if not isinstance(entry, dict):
            return None
        calibration = (calibration_refs.get(indicator_id, "")
                       if isinstance(calibration_refs, dict) else "")
        literals.update({
            f"A{index}": indicator_id,
            f"B{index}": entry.get("definition_version"),
            f"C{index}": calibration,
            f"D{index}": _canonical_sha256(entry),
            f"E{index}": _canonical_sha256(entry.get("source_policy")),
        })
    return literals, {}


def _workbook_visuals_manifest(model):
    literals = {"A1": "pillar", "B1": "mean", "C1": "Measured",
                "D1": "Documented", "E1": "Judged", "F1": "Gap"}
    formulas = {}
    for index, pillar_id in enumerate(_WORKBOOK_PILLARS, start=2):
        scoring_row = _WORKBOOK_PILLAR_ROW + index - 2
        literals[f"A{index}"] = pillar_id
        for column, source in zip(("B", "C", "D", "E", "F"),
                                  ("E", "I", "J", "K", "L")):
            formulas[f"{column}{index}"] = f'Scoring!${source}${scoring_row}'
    literals.update({"A11": "layer", "B11": "mean"})
    for index, layer in enumerate(_WORKBOOK_LAYERS, start=12):
        literals[f"A{index}"] = layer
        formulas[f"B{index}"] = (
            f'Scoring!$B${_WORKBOOK_LAYER_ROW + index - 12}')
    literals.update({"A17": "level", "B17": "indicator_count"})
    for level in range(1, 6):
        row_number = 17 + level
        literals[f"A{row_number}"] = level
        formulas[f"B{row_number}"] = (
            f'COUNTIF(Scoring!$T${_WORKBOOK_FIRST_INDICATOR_ROW}:'
            f'$T${_WORKBOOK_LAST_INDICATOR_ROW},{level})')
    literals.update({"A24": "year", "B24": "readings"})
    assessment_year = model.get("config", {}).get("assessment_year")
    if type(assessment_year) is not int:
        return None
    for index, year in enumerate(range(assessment_year - 4, assessment_year + 1),
                                 start=25):
        literals[f"A{index}"] = year
        formulas[f"B{index}"] = (
            f'COUNTIFS(Scoring!$Q${_WORKBOOK_FIRST_INDICATOR_ROW}:'
            f'$Q${_WORKBOOK_LAST_INDICATOR_ROW},$A{index},'
            f'Scoring!$S${_WORKBOOK_FIRST_INDICATOR_ROW}:'
            f'$S${_WORKBOOK_LAST_INDICATOR_ROW},"<>Gap")')
    return literals, formulas


def _workbook_formula_manifest_summary(model):
    """Bind the exact executable surface without claiming spreadsheet recalculation."""
    sheet_formulas = {}
    for sheet_name, builder in (
            ("Config", _workbook_config_manifest),
            ("Scoring", _workbook_scoring_manifest),
            ("Visuals", _workbook_visuals_manifest)):
        manifest = builder(model)
        if manifest is None:
            return None
        sheet_formulas[sheet_name] = manifest[1]
    return {
        "formula_manifest_sha256": _canonical_sha256(sheet_formulas),
        "semantic_formula_count": sum(
            len(formulas) for formulas in sheet_formulas.values()),
        "verification_mode": "static_exact_formula_manifest",
        "runtime_recalculation": "external_release_boundary",
    }


def _workbook_runtime_evidence_is_complete(
        record, *, expected_country, expected_workbook_sha256,
        expected_model_file_sha256, expected_model_payload_sha256,
        expected_observations_file_sha256,
        expected_observations_payload_sha256,
        expected_profiles_file_sha256, expected_profiles_payload_sha256,
        expected_formula_manifest_sha256,
        expected_semantic_formula_count):
    """Dependency-light mirror of the runtime verifier's release predicate."""
    if not isinstance(record, dict):
        return False
    scope = record.get("scope")
    recalculator = record.get("recalculator")
    digest_fields = (
        "workbook_sha256", "recalculated_workbook_sha256", "model_file_sha256",
        "model_payload_sha256", "observations_file_sha256",
        "observations_payload_sha256", "profiles_file_sha256",
        "profiles_payload_sha256", "formula_manifest_sha256",
        "engine_projection_sha256", "reference_projection_sha256",
        "workbook_projection_sha256",
    )
    if (record.get("schema") != "damm.workbook-runtime-parity/v1"
            or record.get("status") != "passed"
            or record.get("country") != expected_country
            or any(
                not isinstance(record.get(field), str)
                or not _SHA256_TEXT.fullmatch(record[field])
                for field in digest_fields)
            or record.get("workbook_sha256") != expected_workbook_sha256
            or record.get("model_file_sha256")
            != expected_model_file_sha256
            or record.get("model_payload_sha256")
            != expected_model_payload_sha256
            or record.get("observations_file_sha256")
            != expected_observations_file_sha256
            or record.get("observations_payload_sha256")
            != expected_observations_payload_sha256
            or record.get("profiles_file_sha256")
            != expected_profiles_file_sha256
            or record.get("profiles_payload_sha256")
            != expected_profiles_payload_sha256
            or record.get("formula_manifest_sha256")
            != expected_formula_manifest_sha256
            or record.get("semantic_formula_count")
            != expected_semantic_formula_count
            or record.get("static_verification_mode")
            != "static_exact_formula_manifest"
            or record.get("runtime_recalculation_boundary")
            != "external_release_boundary"
            or record.get("engine_projection_sha256")
            != record.get("reference_projection_sha256")
            or record.get("engine_projection_sha256")
            != record.get("workbook_projection_sha256")
            or type(record.get("comparison_count")) is not int
            or record["comparison_count"] <= 0
            or type(record.get("mismatch_count")) is not int
            or record["mismatch_count"] != 0
            or record.get("mismatches") != []
            or record.get("mismatches_truncated") is not False
            or type(record.get("input_binding_comparison_count")) is not int
            or record["input_binding_comparison_count"] <= 0
            or type(record.get("input_binding_mismatch_count")) is not int
            or record["input_binding_mismatch_count"] != 0
            or record.get("input_binding_mismatches") != []
            or type(record.get("formula_error_count")) is not int
            or record["formula_error_count"] != 0
            or record.get("source_workbook_unchanged") is not True
            or not isinstance(recalculator, dict)
            or recalculator.get("implementation") != "LibreOffice"
            or not isinstance(recalculator.get("executable"), str)
            or not recalculator["executable"].strip()
            or type(recalculator.get("exit_code")) is not int
            or recalculator["exit_code"] != 0
            or not isinstance(recalculator.get("stdout_sha256"), str)
            or not _SHA256_TEXT.fullmatch(recalculator["stdout_sha256"])
            or not isinstance(recalculator.get("stderr_sha256"), str)
            or not _SHA256_TEXT.fullmatch(recalculator["stderr_sha256"])
            or not isinstance(scope, dict)
            or scope.get("indicators") != 57
            or scope.get("pillars") != 7
            or scope.get("layers") != 4
            or scope.get("prerequisites") != 12
            or scope.get("mapped_readiness_outputs") != 6
            or scope.get("mapping_edges") != 72
            or scope.get("indicator_outputs")
            != ["class", "level", "stale"]
            or scope.get("pillar_outputs") != [
                "n", "rated", "held", "mean", "band", "margin", "weak",
                "evidence.Measured", "evidence.Documented", "evidence.Judged",
                "evidence.Gap", "stale",
            ]
            or scope.get("leapfrog_outputs")
            != ["gap", "flag", "reading"]):
        return False
    return True


def _workbook_inputs_are_nondegenerate(scoring_cells, config_cells, model):
    classes = set()
    years = []
    has_hold = False
    for row_number in range(
            _WORKBOOK_FIRST_INDICATOR_ROW, _WORKBOOK_LAST_INDICATOR_ROW + 1):
        required = [f"{column}{row_number}" for column in ("M", "N", "O", "P", "Q", "R", "AB")]
        if any(reference not in scoring_cells
               or scoring_cells[reference]["formula"] is not None
               for reference in required):
            return False
        value_cell = scoring_cells[f"M{row_number}"]
        value = value_cell["value"]
        is_numeric = value_cell.get("cell_type") not in ("s", "str", "inlineStr", "b")
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            numeric_value = None
        if is_numeric and numeric_value is not None and math.isfinite(numeric_value):
            classes.add("Measured")
        elif "DATA GAP" in value.upper():
            classes.add("Gap")
        elif (scoring_cells[f"N{row_number}"]["value"]
              and scoring_cells[f"P{row_number}"]["value"] != "T5"):
            classes.add("Documented")
        elif value:
            classes.add("Judged")
        if scoring_cells[f"AB{row_number}"]["value"] != "match":
            has_hold = True
        year = scoring_cells[f"Q{row_number}"]["value"]
        try:
            years.append(int(float(year)))
        except (TypeError, ValueError):
            pass
    profile_values = []
    for row_number in range(2, 8):
        for column in _WORKBOOK_PROFILE_COLUMNS.values():
            cell = config_cells.get(f"{column}{row_number}")
            if (cell is None or cell["formula"] is not None
                    or cell["value"] not in ("", "true", "false")):
                return False
            profile_values.append(cell["value"])
    config = model.get("config", {})
    boundary = config.get("assessment_year", 0) - config.get("staleness_years", 0)
    return (classes == {"Measured", "Documented", "Judged", "Gap"}
            and has_hold and any(year < boundary for year in years)
            and any(year >= boundary for year in years)
            and {"", "true", "false"} <= set(profile_values))


def _workbook_scoring_contract(model, indicator_id):
    indicator = next((row for row in model.get("indicators", [])
                      if isinstance(row, dict) and row.get("id") == indicator_id), None)
    if indicator is None:
        return None
    return "scoring_contract_sha256:" + _canonical_sha256({
        "indicator_id": indicator_id,
        "method": indicator.get("method"),
        "direction": indicator.get("direction"),
        "thresholds": indicator.get("thresholds"),
        "definition_version": indicator.get("definition_version"),
        "calibration_ref": indicator.get("calibration_ref"),
    })


def _workbook_content_is_semantic(raw, model):
    required_sheets = {
        "Read Me", "Config", "Ladder", "Tiers", "Issues", "Scoring",
        "Definitions", "Visuals",
    }
    required_parts = {
        "[Content_Types].xml", "_rels/.rels", "xl/workbook.xml",
        "xl/_rels/workbook.xml.rels", "xl/styles.xml",
    }
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as workbook:
            names = set(workbook.namelist())
            if not required_parts <= names:
                return False
            unsafe_exact_parts = {
                "xl/connections.xml", "xl/vbaProject.bin",
                "xl/vbaProjectSignature.bin",
            }
            unsafe_part_prefixes = (
                "xl/activeX/", "xl/ctrlProps/", "xl/embeddings/",
                "xl/externalLinks/", "xl/queryTables/", "customUI/",
            )
            if (unsafe_exact_parts & names
                    or any(name.startswith(unsafe_part_prefixes)
                           for name in names)):
                return False
            content_types = workbook.read("[Content_Types].xml").lower()
            if any(token in content_types for token in (
                    b"macroenabled", b"vbaproject", b"activex",
                    b"oleobject")):
                return False
            for relationship_path in (
                    name for name in names if name.endswith(".rels")):
                relationship_root = ET.fromstring(
                    workbook.read(relationship_path))
                if any(
                        (item.get("TargetMode") or "").casefold() == "external"
                        for item in relationship_root.iter()
                        if _xml_local_name(item.tag) == "Relationship"):
                    return False
            workbook_root = ET.fromstring(workbook.read("xl/workbook.xml"))
            relationships_root = ET.fromstring(
                workbook.read("xl/_rels/workbook.xml.rels"))
            relationships = {
                item.get("Id"): item.get("Target")
                for item in relationships_root.iter()
                if _xml_local_name(item.tag) == "Relationship"
            }
            sheet_paths = {}
            for sheet in (item for item in workbook_root.iter()
                          if _xml_local_name(item.tag) == "sheet"):
                relationship_id = next(
                    (value for key, value in sheet.attrib.items()
                     if _xml_local_name(key) == "id"), None)
                target = relationships.get(relationship_id)
                if not _present_text(sheet.get("name")) or not _present_text(target):
                    return False
                path = (target.lstrip("/") if target.startswith("/")
                        else posixpath.normpath(posixpath.join("xl", target)))
                sheet_paths[sheet.get("name")] = path
            if set(sheet_paths) != required_sheets or not set(sheet_paths.values()) <= names:
                return False
            shared_strings = []
            if "xl/sharedStrings.xml" in names:
                shared_root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
                for item in (node for node in shared_root.iter()
                             if _xml_local_name(node.tag) == "si"):
                    shared_strings.append("".join(
                        node.text or "" for node in item.iter()
                        if _xml_local_name(node.tag) == "t"))
            sheet_rows = {}
            sheet_roots = {}
            for name, path in sheet_paths.items():
                root, rows = _xlsx_rows(workbook, path, shared_strings)
                if not rows:
                    return False
                sheet_roots[name], sheet_rows[name] = root, rows
    except (ET.ParseError, KeyError, OSError, zipfile.BadZipFile):
        return False

    all_text = "\n".join(
        value for rows in sheet_rows.values() for row in rows for value in row)
    normalized = all_text.casefold()
    model_digest = _model_ratification_sha256(model)
    mapping = model.get("prerequisite_mapping")
    edges = mapping.get("edges") if isinstance(mapping, dict) else None
    if ("draft for review" in normalized
            or "status: ratified" not in normalized
            or f"model_version:{model.get('version')}" not in all_text
            or f"model_revision:{model.get('revision')}" not in all_text
            or f"model_sha256:{model_digest}" not in all_text
            or not isinstance(edges, list)
            or f"prerequisite_mapping_revision:{mapping.get('revision')}"
            not in all_text):
        return False

    manifests = (
        _workbook_config_manifest(model),
        _workbook_scoring_manifest(model),
        _workbook_definitions_manifest(model),
        _workbook_visuals_manifest(model),
    )
    if any(manifest is None for manifest in manifests):
        return False
    for sheet_name, manifest in zip(
            ("Config", "Scoring", "Definitions", "Visuals"), manifests):
        if not _workbook_sheet_matches_manifest(
                sheet_roots[sheet_name], shared_strings, *manifest):
            return False
    for passive_sheet in ("Read Me", "Ladder", "Tiers", "Issues"):
        passive_cells = _xlsx_sheet_cells(
            sheet_roots[passive_sheet], shared_strings)
        if (passive_cells is None
                or any(cell["formula"] is not None
                       for cell in passive_cells.values())):
            return False
    scoring_cells = _xlsx_sheet_cells(sheet_roots["Scoring"], shared_strings)
    config_cells = _xlsx_sheet_cells(sheet_roots["Config"], shared_strings)
    return (scoring_cells is not None and config_cells is not None
            and _workbook_inputs_are_nondegenerate(
                scoring_cells, config_cells, model))


def _application_scenario_is_exercised(scenario, case_input, result, model):
    mapping = model.get("prerequisite_mapping")
    edges = mapping.get("edges") if isinstance(mapping, dict) else []
    observations = case_input.get("observations")
    output = result.get("engine_output") if isinstance(result, dict) else None
    if scenario == "definition_mismatch":
        definitions = model.get("indicator_definitions", {}).get("entries", {})
        mismatch_ids = [
            indicator_id for indicator_id, row in observations.items()
            if isinstance(row, dict)
            and isinstance(row.get("definition_metadata"), dict)
            and isinstance(definitions.get(indicator_id), dict)
            and row["definition_metadata"].get("definition_sha256")
            != _canonical_sha256(definitions[indicator_id])
        ]
        if len(mismatch_ids) != 1:
            return False
        expected_error = (
            f"invalid ratified observation {mismatch_ids[0]}: "
            "definition metadata differs from the ratified catalog")
        engine_error = (result.get("engine_error")
                        if isinstance(result, dict) else None)
        reference_error = (result.get("reference_error")
                           if isinstance(result, dict) else None)
        return (isinstance(engine_error, dict)
                and engine_error == reference_error
                and engine_error.get("error_type") == "ValueError"
                and engine_error.get("error") == expected_error)
    if not isinstance(output, dict):
        return False
    if scenario == "threshold_recompute":
        return any(
            row.get("cls") == "Measured" and row.get("level") is not None
            and output.get("indicators", {}).get(indicator_id, {}).get("level")
            != row.get("level")
            for indicator_id, row in observations.items())
    effect = "delivery_risk" if scenario == "delivery_risk" else "gate"
    mode = ("conditional" if scenario in {
        "conditional_false", "conditional_true"} else "always")
    edge = next((item for item in edges
                 if item.get("effect") == effect
                 and item.get("applicability", {}).get("mode") == mode), None)
    if edge is None:
        return False
    cell = output.get("matrix", {}).get(edge["use_case_id"], {})
    if scenario == "unconditional_gate":
        return any(item.get("prerequisite_id") == edge["prerequisite_id"]
                   and item.get("outcome") in {
                       "Blocked", "Unverified", "Partial"}
                   for item in cell.get("active_gates", []))
    if scenario in {"conditional_false", "conditional_true"}:
        expected_evaluation = ("inactive" if scenario == "conditional_false"
                               else "active")
        constraint_matches = any(
            item.get("prerequisite_id") == edge["prerequisite_id"]
            and item.get("evaluation") == expected_evaluation
            for item in cell.get("conditional_constraints", []))
        active = [item for item in cell.get("active_gates", [])
                  if item.get("prerequisite_id") == edge["prerequisite_id"]]
        return (constraint_matches and (
            not active if scenario == "conditional_false"
            else any(item.get("outcome") in {
                "Blocked", "Unverified", "Partial"} for item in active)))
    return any(item.get("prerequisite_id") == edge["prerequisite_id"]
               and item.get("action") != "no_change"
               for item in cell.get("delivery_risks", []))


def _engine_reference_outputs_match(engine_output, reference_output):
    if not isinstance(engine_output, dict) or not isinstance(reference_output, dict):
        return False
    scoring_fields = {
        "indicators", "pillars", "layers", "leapfrog", "prereq", "matrix",
        "constraints", "kpi", "verify", "refresh", "counts", "rated", "held",
    }
    version_fields = {
        "model_version", "model_revision", "prerequisite_mapping_revision",
    }
    expected_reference_fields = set(scoring_fields)
    if "prerequisite_mapping_revision" in reference_output:
        expected_reference_fields.update(version_fields)
    if (set(reference_output) != expected_reference_fields
            or not expected_reference_fields <= set(engine_output)):
        return False
    return all(
        _canonical_sha256(engine_output[field])
        == _canonical_sha256(reference_output[field])
        for field in expected_reference_fields)


def _application_fixtures_are_semantic(raw, model):
    try:
        fixtures = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    required_scenarios = {
        "unconditional_gate", "conditional_false", "conditional_true",
        "delivery_risk", "threshold_recompute", "definition_mismatch",
    }
    cases = fixtures.get("cases") if isinstance(fixtures, dict) else None
    if (fixtures.get("model_version") != model.get("version")
            or fixtures.get("model_revision") != model.get("revision")
            or fixtures.get("model_sha256") != _model_ratification_sha256(model)
            or fixtures.get("implementation_sha256")
            != _release_implementation_sha256(model)
            or not isinstance(cases, list) or len(cases) != len(required_scenarios)
            or {case.get("scenario") for case in cases
                if isinstance(case, dict)} != required_scenarios
            or len({case.get("id") for case in cases
                    if isinstance(case, dict)}) != len(cases)):
        return False
    for case in cases:
        case_input = case.get("input") if isinstance(case, dict) else None
        observations = (case_input.get("observations")
                        if isinstance(case_input, dict) else None)
        profiles = (case_input.get("intervention_profiles")
                    if isinstance(case_input, dict) else None)
        if (not _present_text(case.get("id"))
                or case.get("passed") is not True
                or not isinstance(case.get("assertions"), list)
                or not case["assertions"]
                or any(not _specific_definition_text(item)
                       for item in case["assertions"])
                or not isinstance(observations, dict)
                or set(observations) != set(KNOWN_IDS)
                or case_input.get("refyear")
                != model.get("config", {}).get("assessment_year")
                or not isinstance(profiles, dict)
                or case.get("input_sha256") != _canonical_sha256(case_input)
                or case.get("expected_sha256")
                != _canonical_sha256(case.get("expected"))
                or case.get("actual_sha256")
                != _canonical_sha256(case.get("actual"))):
            return False
        errors = assessment_input_errors(observations, spec=model)
        if case["scenario"] == "definition_mismatch":
            definitions = model.get("indicator_definitions", {}).get(
                "entries", {})
            mismatch_ids = [
                indicator_id for indicator_id, row in observations.items()
                if isinstance(row, dict)
                and isinstance(row.get("definition_metadata"), dict)
                and isinstance(definitions.get(indicator_id), dict)
                and row["definition_metadata"].get("definition_sha256")
                != _canonical_sha256(definitions[indicator_id])
            ]
            if (len(mismatch_ids) != 1
                    or errors != [
                        f"row {mismatch_ids[0]} definition_metadata "
                        "definition_sha256 does not match the model"]):
                return False
        elif case["scenario"] == "threshold_recompute":
            if (not errors
                    or any("Measured level does not match its thresholds" not in error
                           for error in errors)):
                return False
        elif errors:
            return False
        try:
            engine_output = engine_run(
                case_input.get("country"), observations,
                refyear=case_input["refyear"], model_spec=model,
                intervention_profiles=profiles)
        except (KeyError, TypeError, ValueError) as exc:
            engine_output = {"error_type": type(exc).__name__, "error": str(exc)}
        try:
            reference_output = ReferenceScorer(model).run(
                observations, intervention_profiles=profiles)
        except (KeyError, TypeError, ValueError) as exc:
            reference_output = {
                "error_type": type(exc).__name__, "error": str(exc),
            }
        if (isinstance(engine_output, dict) and "error_type" in engine_output
                or isinstance(reference_output, dict)
                and "error_type" in reference_output):
            replayed = {
                "engine_error": engine_output,
                "reference_error": reference_output,
            }
        else:
            replayed = {
                "engine_output": engine_output,
                "reference_output": reference_output,
            }
        if (_canonical_sha256(case.get("expected")) != _canonical_sha256(replayed)
                or _canonical_sha256(case.get("actual"))
                != _canonical_sha256(replayed)
                or ("engine_output" in replayed
                    and not _engine_reference_outputs_match(
                        replayed["engine_output"], replayed["reference_output"]))
                or not _application_scenario_is_exercised(
                    case["scenario"], case_input, replayed, model)):
            return False
    return True


def _release_artifact_content_is_semantic(artifact, raw, model):
    if artifact == "canonical_model":
        try:
            content = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False
        return content == _ratifiable_model_projection(model)
    code_paths = {
        "engine": ENGINE_FILE,
        "reference_scorer": REFERENCE_SCORER_FILE,
        "renderer": RENDERER_FILE,
    }
    if artifact in code_paths:
        try:
            with open(code_paths[artifact], "rb") as handle:
                return raw == handle.read()
        except OSError:
            return False
    if artifact == "workbook":
        return _workbook_content_is_semantic(raw, model)
    if artifact == "application_fixtures":
        return _application_fixtures_are_semantic(raw, model)
    return False


def _workbook_runtime_release_evidence_is_complete(
        check_payload, model, evidence_root, workbook_sha256,
        canonical_model_sha256, formula_summary):
    """Bind the runtime result to independently archived executable inputs."""
    if (not isinstance(check_payload, dict)
            or check_payload.get("runtime_country")
            != _WORKBOOK_RUNTIME_COUNTRY
            or check_payload.get("runtime_evidence_ref")
            != _WORKBOOK_RUNTIME_EVIDENCE_REF
            or check_payload.get("observations_ref")
            != _WORKBOOK_RUNTIME_OBSERVATIONS_REF
            or check_payload.get("profiles_ref")
            != _WORKBOOK_RUNTIME_PROFILES_REF):
        return False
    runtime_raw = _verified_record_bytes(
        check_payload, evidence_root, ref_field="runtime_evidence_ref",
        sha_field="runtime_evidence_sha256")
    observations_raw = _verified_record_bytes(
        check_payload, evidence_root, ref_field="observations_ref",
        sha_field="observations_sha256")
    profiles_raw = _verified_record_bytes(
        check_payload, evidence_root, ref_field="profiles_ref",
        sha_field="profiles_sha256")
    if any(raw is None for raw in (
            runtime_raw, observations_raw, profiles_raw)):
        return False
    try:
        runtime_record = json.loads(runtime_raw.decode("utf-8"))
        observations = json.loads(observations_raw.decode("utf-8"))
        profiles = json.loads(profiles_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    indicators = model.get("indicators")
    expected_indicator_ids = ({row.get("id") for row in indicators}
                              if isinstance(indicators, list)
                              and all(isinstance(row, dict)
                                      for row in indicators) else set())
    if (len(expected_indicator_ids) != 57
            or not isinstance(observations, dict)
            or set(observations) != expected_indicator_ids
            or any(not isinstance(row, dict)
                   for row in observations.values())
            or not isinstance(profiles, dict)
            or set(profiles) - set(_WORKBOOK_USE_CASES)
            or any(
                not isinstance(profile, dict)
                or set(profile) - _INTERVENTION_PROFILE_FIELDS
                or any(type(value) is not bool for value in profile.values())
                for profile in profiles.values())):
        return False
    model_payload_sha256 = _canonical_sha256(
        _ratifiable_model_projection(model))
    observations_payload_sha256 = _canonical_sha256(observations)
    profiles_payload_sha256 = _canonical_sha256(profiles)
    try:
        # The verifier file is itself implementation-digest-bound.  Reuse its canonical
        # projection instead of accepting scorer projection hashes asserted only by the
        # archived runtime JSON.
        from verify_workbook_parity import projection_from_score
        engine_projection = projection_from_score(
            engine_run(
                _WORKBOOK_RUNTIME_COUNTRY, observations, model_spec=model,
                intervention_profiles=profiles), model)
        reference_projection = projection_from_score(
            ReferenceScorer(model).run(
                observations, intervention_profiles=profiles), model)
        engine_projection_sha256 = _canonical_sha256(engine_projection)
        reference_projection_sha256 = _canonical_sha256(reference_projection)
    except Exception:
        return False
    if (runtime_record.get("engine_projection_sha256")
            != engine_projection_sha256
            or runtime_record.get("reference_projection_sha256")
            != reference_projection_sha256):
        return False
    return _workbook_runtime_evidence_is_complete(
        runtime_record,
        expected_country=_WORKBOOK_RUNTIME_COUNTRY,
        expected_workbook_sha256=workbook_sha256,
        expected_model_file_sha256=canonical_model_sha256,
        expected_model_payload_sha256=model_payload_sha256,
        expected_observations_file_sha256=check_payload["observations_sha256"],
        expected_observations_payload_sha256=observations_payload_sha256,
        expected_profiles_file_sha256=check_payload["profiles_sha256"],
        expected_profiles_payload_sha256=profiles_payload_sha256,
        expected_formula_manifest_sha256=(
            formula_summary["formula_manifest_sha256"]),
        expected_semantic_formula_count=(
            formula_summary["semantic_formula_count"]),
    )


def _release_check_log_is_semantic(
        raw, check_id, implementation_sha256, check_payload):
    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    result_started = (_parse_iso_datetime(result.get("started_at"))
                      if isinstance(result, dict) else None)
    result_completed = (_parse_iso_datetime(result.get("completed_at"))
                        if isinstance(result, dict) else None)
    complete = (isinstance(result, dict)
            and result.get("check") == check_id
            and result.get("exit_code") == 0
            and type(result.get("passed_checks")) is int
            and result["passed_checks"] > 0
            and result.get("failed_checks") == 0
            and result.get("passed_checks") == check_payload.get("passed_checks")
            and result.get("failed_checks") == check_payload.get("failed_checks")
            and result.get("exit_code") == check_payload.get("exit_code")
            and result.get("implementation_sha256") == implementation_sha256
            and result.get("run_id") == check_payload.get("run_id")
            and result.get("attestation_id")
            == check_payload.get("attestation_id")
            and result.get("started_at") == check_payload.get("started_at")
            and result.get("completed_at") == check_payload.get("completed_at")
            and result_started is not None and result_completed is not None
            and result_started < result_completed)
    if not complete:
        return False
    if check_id == "application_tests":
        return (result.get("fixture_sha256")
                == check_payload.get("fixture_sha256")
                and result.get("case_ids") == check_payload.get("case_ids")
                and result.get("case_count") == check_payload.get("case_count"))
    if check_id == "single_source_parity":
        return (result.get("workbook_sha256")
                == check_payload.get("workbook_sha256")
                and result.get("canonical_model_sha256")
                == check_payload.get("canonical_model_sha256")
                and result.get("formula_manifest_sha256")
                == check_payload.get("formula_manifest_sha256")
                and result.get("semantic_formula_count")
                == check_payload.get("semantic_formula_count")
                and result.get("verification_mode")
                == "static_exact_formula_manifest"
                and result.get("runtime_recalculation")
                == "external_release_boundary"
                and all(
                    result.get(field) == check_payload.get(field)
                    for field in _WORKBOOK_RUNTIME_CHECK_FIELDS))
    return True


def _release_records_are_complete(payload, model, evidence_root):
    artifact_versions = payload.get("artifact_versions")
    checks = payload.get("checks")
    if (not isinstance(artifact_versions, dict)
            or set(artifact_versions) != _RELEASE_ARTIFACT_KEYS
            or not isinstance(checks, dict)
            or set(checks) != _RELEASE_CHECK_KEYS):
        return False
    application_fixture_sha256 = None
    application_case_ids = None
    workbook_sha256 = None
    canonical_model_sha256 = None
    workbook_formula_summary = _workbook_formula_manifest_summary(model)
    if workbook_formula_summary is None:
        return False
    for artifact, record in artifact_versions.items():
        manifest = _verified_json_record(
            record, evidence_root, ref_field="artifact_ref")
        artifact_bytes = _verified_record_bytes(
            record, evidence_root, ref_field="content_ref",
            sha_field="content_sha256")
        if (not _record_is_bound_to_model(manifest, model)
                or manifest.get("artifact") != artifact
                or manifest.get("version") != record.get("version")
                or not _present_text(record.get("version"))
                or manifest.get("produced") is not True
                or artifact_bytes is None
                or not _release_artifact_content_is_semantic(
                    artifact, artifact_bytes, model)):
            return False
        if artifact == "application_fixtures":
            try:
                fixture_payload = json.loads(artifact_bytes.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return False
            application_fixture_sha256 = record.get("content_sha256")
            application_case_ids = sorted(
                case["id"] for case in fixture_payload["cases"])
        elif artifact == "workbook":
            workbook_sha256 = record.get("content_sha256")
        elif artifact == "canonical_model":
            canonical_model_sha256 = record.get("content_sha256")
    for check_id, record in checks.items():
        check_payload = _verified_json_record(record, evidence_root)
        log_bytes = _verified_record_bytes(
            record, evidence_root, ref_field="log_ref", sha_field="log_sha256")
        if (not _record_is_bound_to_model(check_payload, model)
                or check_payload.get("check") != check_id
                or check_payload.get("passed") is not True
                or check_payload.get("command") != _RELEASE_CHECK_COMMANDS[check_id]
                or not _present_text(check_payload.get("result_summary"))
                or not _present_text(check_payload.get("run_id"))
                or not _present_text(check_payload.get("attestation_id"))
                or not _approval_provenance_is_complete(check_payload)
                or _parse_iso_datetime(check_payload.get("started_at")) is None
                or _parse_iso_datetime(check_payload.get("completed_at")) is None
                or _parse_iso_datetime(check_payload["started_at"])
                >= _parse_iso_datetime(check_payload["completed_at"])
                or check_payload.get("exit_code") != 0
                or type(check_payload.get("passed_checks")) is not int
                or check_payload["passed_checks"] <= 0
                or check_payload.get("failed_checks") != 0
                or (check_id == "application_tests" and (
                    check_payload.get("fixture_sha256")
                    != application_fixture_sha256
                    or check_payload.get("case_ids") != application_case_ids
                    or check_payload.get("case_count")
                    != len(application_case_ids or [])))
                or (check_id == "single_source_parity" and (
                    check_payload.get("workbook_sha256") != workbook_sha256
                    or check_payload.get("canonical_model_sha256")
                    != canonical_model_sha256
                    or check_payload.get("passed_checks")
                    != workbook_formula_summary["semantic_formula_count"]
                    or any(
                        check_payload.get(field) != value
                        for field, value in workbook_formula_summary.items())))
                or (check_id == "single_source_parity"
                    and not _workbook_runtime_release_evidence_is_complete(
                        check_payload, model, evidence_root, workbook_sha256,
                        canonical_model_sha256, workbook_formula_summary))
                or log_bytes is None
                or not _release_check_log_is_semantic(
                    log_bytes, check_id, payload.get("implementation_sha256"),
                    check_payload)):
            return False
    return True


def _implementation_digest(model, content_loader):
    digest = hashlib.sha256()
    model_name = os.path.relpath(MODEL_FILE, REPO).encode("utf-8")
    model_content = json.dumps(
        _ratifiable_model_projection(model), sort_keys=True,
        separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    digest.update(len(model_name).to_bytes(4, "big"))
    digest.update(model_name)
    digest.update(len(model_content).to_bytes(8, "big"))
    digest.update(model_content)
    for path in sorted((
            ENGINE_FILE, REFERENCE_SCORER_FILE, MODEL_EXPORT_FILE,
            WORKBOOK_BUILDER_FILE, WORKBOOK_PARITY_FILE, RENDERER_FILE,
            os.path.abspath(__file__))):
        relative_path = os.path.relpath(path, REPO)
        content = content_loader(relative_path)
        if content is None:
            return None
        encoded_path = relative_path.encode("utf-8")
        digest.update(len(encoded_path).to_bytes(4, "big"))
        digest.update(encoded_path)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _release_implementation_sha256(model=None):
    """Digest ratifiable model data and the code paths whose parity is attested."""
    def load_worktree(relative_path):
        try:
            with open(os.path.join(REPO, relative_path), "rb") as handle:
                return handle.read()
        except OSError:
            return None

    return _implementation_digest(SPEC if model is None else model, load_worktree)


def _git_signature_fingerprint(transcript):
    """Return a stable GPG or SSH signer fingerprint from Git verifier output."""
    try:
        text = transcript.decode("utf-8", errors="replace")
    except AttributeError:
        return None
    gpg = re.search(r"\[GNUPG:\]\s+VALIDSIG\s+([0-9A-Fa-f]{40,64})\b", text)
    if gpg:
        return gpg.group(1).upper()
    ssh = re.search(
        r"\bkey\s+(SHA256:[A-Za-z0-9+/]+={0,2})\b", text,
        flags=re.IGNORECASE)
    return ssh.group(1) if ssh else None


def _git_release_tags():
    """Return tag targets plus cryptographic Git verification state.

    An annotated tag must itself verify.  A lightweight tag has no tag object to
    sign, so its target commit must verify instead.  The verifier transcript is
    represented by a digest: release evidence can bind the exact verification
    result without treating a locally asserted ``signed: true`` flag as proof.
    """
    try:
        tags = subprocess.run(
            ["git", "tag", "--list"], cwd=REPO, check=True,
            capture_output=True, text=True, timeout=10).stdout.splitlines()
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO, check=True,
            capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return {}
    states = {}
    model_relative = os.path.relpath(MODEL_FILE, REPO)
    for tag in (item.strip() for item in tags if item.strip()):
        try:
            # Resolve the mutable ref exactly once.  Every subsequent verification
            # and content read uses one of these immutable object ids, preventing a
            # concurrent tag-ref swap from composing unrelated trusted facts.
            tag_object_oid = subprocess.run(
                ["git", "rev-parse", "--verify", f"refs/tags/{tag}^{{object}}"],
                cwd=REPO, check=True, capture_output=True, text=True,
                timeout=10).stdout.strip()
            commit = subprocess.run(
                ["git", "rev-parse", "--verify", f"{tag_object_oid}^{{commit}}"],
                cwd=REPO, check=True,
                capture_output=True, text=True, timeout=10).stdout.strip()
            object_type = subprocess.run(
                ["git", "cat-file", "-t", tag_object_oid], cwd=REPO, check=True,
                capture_output=True, text=True, timeout=10).stdout.strip()
            signature_target = "tag" if object_type == "tag" else "commit"
            verification = subprocess.run(
                (["git", "verify-tag", "--raw", tag_object_oid]
                 if signature_target == "tag"
                 else ["git", "verify-commit", "--raw", commit]),
                cwd=REPO, check=False, capture_output=True, timeout=10)
            verification_transcript = (
                verification.stdout + b"\n" + verification.stderr)
            signer_fingerprint = _git_signature_fingerprint(
                verification_transcript)
            model_raw = subprocess.run(
                ["git", "show", f"{commit}:{model_relative}"], cwd=REPO,
                check=True,
                capture_output=True, timeout=10).stdout
            tag_model = json.loads(model_raw.decode("utf-8"))

            def load_tag(relative_path):
                try:
                    return subprocess.run(
                        ["git", "show", f"{commit}:{relative_path}"], cwd=REPO,
                        check=True, capture_output=True, timeout=10).stdout
                except (OSError, subprocess.SubprocessError):
                    return None

            tag_evidence = tag_model.get("ratification_evidence")
            tag_manifest_sha256 = _ratification_manifest_sha256(tag_evidence)
            states[tag] = {
                "commit": commit,
                "tag_object_oid": tag_object_oid,
                "is_head": commit == head,
                "resolved_from_git": True,
                "signature_verified": (
                    verification.returncode == 0
                    and signer_fingerprint is not None),
                "signature_target": signature_target,
                "signer_fingerprint": signer_fingerprint,
                "signature_evidence_sha256": hashlib.sha256(
                    verification_transcript).hexdigest(),
                "model_sha256": _model_ratification_sha256(tag_model),
                "implementation_sha256": _implementation_digest(tag_model, load_tag),
                "ratification_manifest_sha256": (
                    tag_model.get("ratification_manifest_sha256")
                    if tag_model.get("ratification_manifest_sha256")
                    == tag_manifest_sha256 else None),
                "ratification_evidence_sha256": (
                    _canonical_sha256(tag_evidence)
                    if isinstance(tag_evidence, dict) else None),
                "evidence_tree_sha256": _evidence_tree_sha256(
                    tag_model, load_tag),
            }
        except (OSError, subprocess.SubprocessError, UnicodeDecodeError,
                json.JSONDecodeError):
            continue
    return states


def _valid_iso_date(value):
    if not isinstance(value, str) or not _ISO_DATE_TEXT.fullmatch(value):
        return False
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return False
    return parsed <= datetime.now(timezone.utc).date()


def _parse_iso_datetime(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(
            value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    parsed = parsed.astimezone(timezone.utc)
    return parsed if parsed <= datetime.now(timezone.utc) else None


def _ratification_evidence_blockers(
        model, evidence_root, available_release_tags=None):
    """Validate the durable release evidence that booleans cannot represent."""
    evidence = model.get("ratification_evidence")
    if not isinstance(evidence, dict):
        return ["durable ratification evidence is missing or malformed"]

    blockers = []
    release_tags = (_git_release_tags() if available_release_tags is None
                    else available_release_tags)
    manifest_sha256 = _ratification_manifest_sha256(evidence)
    if (set(evidence) != set(_RATIFICATION_EVIDENCE_KEYS)
            or not isinstance(model.get("ratification_manifest_sha256"), str)
            or model.get("ratification_manifest_sha256") != manifest_sha256):
        blockers.append("ratification evidence manifest is incomplete or unbound")
    joint = evidence.get("joint_review")
    joint_payload = _verified_json_record(joint, evidence_root)
    approvals = (joint_payload.get("approvals")
                 if isinstance(joint_payload, dict) else None)
    approvals_are_records = (
        isinstance(approvals, list) and len(approvals) >= 2
        and all(isinstance(item, dict)
                and _present_text(item.get("reviewer")) for item in approvals))
    reviewer_names = ([" ".join(item["reviewer"].casefold().split())
                       for item in approvals] if approvals_are_records else [])
    reviewer_roles = {
        role for name in reviewer_names
        for role, pattern in _JOINT_REVIEWER_NAMES.items()
        if pattern.fullmatch(name)
    }
    dated_approvals = approvals_are_records and all(
        _valid_iso_date(item.get("approved_on"))
        for item in approvals)
    if (not _record_is_bound_to_model(joint_payload, model)
            or joint_payload.get("evidence_manifest_sha256") != manifest_sha256
            or not dated_approvals
            or reviewer_roles != set(_JOINT_REVIEWER_NAMES)
            or not _joint_approval_sources_are_complete(
                approvals, model, evidence_root, manifest_sha256)):
        blockers.append("joint Katreyna and Randeep ratification record is incomplete")

    decisions = evidence.get("decisions")
    decision_payloads = {}
    a1_threshold_ids = {
        indicator_id for indicator_id, row in MODEL.items()
        if row["pillar"] == "A1" and row["th"]
    }
    for decision_id, expected_count in (
            ("13.3", 72),
            ("13.5", len(_ISSUE_2_DEFINITION_IDS)),
            ("13.6", len(a1_threshold_ids))):
        record = decisions.get(decision_id) if isinstance(decisions, dict) else None
        payload = _verified_json_record(
            record, evidence_root, ref_field="artifact_ref")
        decision_payloads[decision_id] = payload
        semantic_records_complete = {
            "13.3": _mapping_records_are_semantic,
            "13.5": _definition_decisions_are_semantic,
            "13.6": lambda item: _calibration_records_are_semantic(
                item, a1_threshold_ids),
        }[decision_id]
        if (not _record_is_bound_to_model(payload, model)
                or not _valid_iso_date(payload.get("ratified_on"))
                or not semantic_records_complete(payload)
                or record.get("ratified") is not True
                or type(record.get("record_count")) is not int
                or record["record_count"] != expected_count):
            blockers.append(
                f"decision {decision_id} ratification artifact is incomplete")

    definition_record = evidence.get("definition_catalog")
    definition_payload = _verified_json_record(
        definition_record, evidence_root, ref_field="artifact_ref")
    if (not _record_is_bound_to_model(definition_payload, model)
            or not _valid_iso_date(definition_payload.get("ratified_on"))
            or not _definition_catalog_is_semantic(definition_payload)
            or definition_record.get("ratified") is not True
            or type(definition_record.get("record_count")) is not int
            or definition_record["record_count"] != len(KNOWN_IDS)):
        blockers.append("complete indicator-definition catalog is missing")

    threshold_record = evidence.get("threshold_calibrations")
    threshold_ids = {
        indicator_id for indicator_id, row in MODEL.items() if row["th"]
    }
    threshold_payload = _verified_json_record(
        threshold_record, evidence_root, ref_field="artifact_ref")
    threshold_calibrations = (
        threshold_payload.get("threshold_calibrations")
        if isinstance(threshold_payload, dict) else None)
    threshold_owners = {
        item.get("approval", {}).get("method_owner")
        for item in threshold_calibrations.values()
        if isinstance(item, dict)
    } if isinstance(threshold_calibrations, dict) else set()
    if (not _record_is_bound_to_model(threshold_payload, model)
            or not _valid_iso_date(threshold_payload.get("ratified_on"))
            or not _calibration_records_are_semantic(
                threshold_payload, threshold_ids)
            or threshold_record.get("ratified") is not True
            or type(threshold_record.get("record_count")) is not int
            or threshold_record["record_count"] != len(threshold_ids)
            or threshold_owners != {threshold_record.get("method_owner")}):
        blockers.append("complete threshold-calibration attestation is missing")

    if not _ratified_artifacts_are_applied(
            model, decision_payloads, definition_payload, threshold_payload):
        blockers.append(
            "ratified mapping, definitions, and calibrations are not applied to the runtime model")

    migration = evidence.get("country_migration")
    migration_payload = _verified_json_record(migration, evidence_root)
    countries = migration.get("countries") if isinstance(migration, dict) else None
    payload_countries = (migration_payload.get("countries")
                         if isinstance(migration_payload, dict) else None)
    if (not _record_is_bound_to_model(migration_payload, model)
            or migration_payload.get("accepted") is not True
            or not _valid_iso_date(migration_payload.get("accepted_on"))
            or not _migration_diffs_are_complete(
                migration_payload, model, evidence_root, release_tags)
            or payload_countries != countries
            or migration.get("accepted") is not True
            or not isinstance(countries, list)
            or len(countries) != 2
            or any(not isinstance(country, str) for country in countries)
            or set(countries) != {"EGY", "NGA"}):
        blockers.append("Egypt and Nigeria migration acceptance is incomplete")

    unseen = evidence.get("unseen_country_validation")
    unseen_payload = _verified_json_record(unseen, evidence_root)
    iso3 = str(unseen.get("iso3") or "") if isinstance(unseen, dict) else ""
    independent_reviewer = (unseen.get("independent_reviewer")
                            if isinstance(unseen, dict) else None)
    normalized_reviewer = (" ".join(independent_reviewer.casefold().split())
                           if _present_text(independent_reviewer) else "")
    reviewer_is_joint_holder = any(
        token in _JOINT_REVIEWER_NAMES for token in normalized_reviewer.split())
    if (not _record_is_bound_to_model(unseen_payload, model)
            or unseen_payload.get("iso3") != iso3
            or unseen_payload.get("human_shadowed") is not True
            or unseen_payload.get("independent_reviewer") != independent_reviewer
            or not _present_text(unseen_payload.get("country_name"))
            or not _present_text(unseen_payload.get("reviewer_organization"))
            or not _present_text(unseen_payload.get("independence_statement"))
            or not _valid_iso_date(unseen_payload.get("reviewed_on"))
            or not _unseen_artifacts_are_complete(
                unseen_payload, model, evidence_root)
            or not _unseen_follows_migration(
                unseen_payload, migration_payload, model, evidence_root)
            or iso3 not in _ISO_3166_ALPHA3
            or iso3 in {"EGY", "NGA", "BTN"}
            or unseen.get("human_shadowed") is not True
            or not _present_text(independent_reviewer)
            or reviewer_is_joint_holder):
        blockers.append("unseen-country independent human-shadow validation is incomplete")

    foresight_record = evidence.get("foresight_method")
    foresight_payload = _verified_json_record(
        foresight_record, evidence_root, ref_field="artifact_ref")
    if (not _record_is_bound_to_model(foresight_payload, model)
            or foresight_payload.get("ratified") is not True
            or foresight_payload.get("method") != model.get("foresight")
            or not _valid_iso_date(foresight_payload.get("ratified_on"))
            or not _present_text(foresight_payload.get("rationale"))):
        blockers.append("foresight ratification artifact is incomplete")

    release = evidence.get("release_verification")
    release_payload = _verified_json_record(release, evidence_root)
    release_tag = (release_payload.get("release_tag")
                   if isinstance(release_payload, dict) else None)
    tag_state = (release_tags.get(release_tag)
                 if isinstance(release_tags, dict) else None)
    current_implementation_sha256 = _release_implementation_sha256(model)
    current_evidence_sha256 = _canonical_sha256(evidence)
    current_evidence_tree_sha256 = _worktree_evidence_tree_sha256(
        model, evidence_root)
    if (not _record_is_bound_to_model(release_payload, model)
            or release_payload.get("single_source_verified") is not True
            or not _valid_iso_date(release_payload.get("verified_on"))
            or not _release_records_are_complete(
                release_payload, model, evidence_root)
            or not _present_text(release_tag)
            or not isinstance(tag_state, dict)
            or tag_state.get("is_head") is not True
            or not isinstance(tag_state.get("commit"), str)
            or not re.fullmatch(
                r"[0-9a-f]{40}(?:[0-9a-f]{24})?", tag_state["commit"])
            or not isinstance(tag_state.get("tag_object_oid"), str)
            or not re.fullmatch(
                r"[0-9a-f]{40}(?:[0-9a-f]{24})?",
                tag_state["tag_object_oid"])
            or tag_state.get("signature_verified") is not True
            or tag_state.get("signature_target") not in {"tag", "commit"}
            or not isinstance(tag_state.get("signature_evidence_sha256"), str)
            or not _SHA256_TEXT.fullmatch(
                tag_state["signature_evidence_sha256"])
            or "release_commit" in release_payload
            or release_payload.get("signature_target")
            != tag_state.get("signature_target")
            or not _present_text(tag_state.get("signer_fingerprint"))
            or release_payload.get("authorized_signer_fingerprint")
            != tag_state.get("signer_fingerprint")
            or tag_state.get("ratification_manifest_sha256")
            != model.get("ratification_manifest_sha256")
            or tag_state.get("ratification_evidence_sha256")
            != current_evidence_sha256
            or tag_state.get("evidence_tree_sha256")
            != current_evidence_tree_sha256
            or not isinstance(release_payload.get("implementation_sha256"), str)
            or release_payload["implementation_sha256"]
            != current_implementation_sha256
            or tag_state.get("implementation_sha256")
            != current_implementation_sha256):
        blockers.append("release verification and version evidence is incomplete")
    return blockers


def final_publication_blockers(
        reviewed, spec=None, *, evidence_root=REPO, available_release_tags=None):
    """Return every reason a complete DAR may not be labelled final.

    Narrative review and method ratification are independent gates.  A replay can prove
    that the exact inputs and prose were reviewed; it cannot ratify the model that scored
    those inputs.  Keep the checks explicit here so flipping the root ``ratified`` boolean
    alone cannot silently publish provisional definitions, thresholds, or binding rules.
    """
    model = SPEC if spec is None else spec
    blockers = []
    if not isinstance(model, dict):
        return ["model ratification record is missing or malformed"]
    if reviewed is not True:
        blockers.append("inputs and narrative have not both been reviewed")
    if model.get("ratified") is not True:
        blockers.append("model ratified is not true")
    if model.get("status") != "ratified":
        blockers.append("model status is not ratified")
    if (type(model.get("revision")) is not int
            or model["revision"] <= _ISSUE_2_BASELINE_REVISION):
        blockers.append("model revision was not bumped for ratification")

    decisions = model.get("open_decisions")
    if not isinstance(decisions, list):
        blockers.append("open-decisions attestation is missing or malformed")
    elif decisions:
        blockers.append("the model still carries open decisions")

    rules = model.get("binding_rules")
    expected_rules = {rule["id"]: rule for rule in SPEC.get("binding_rules") or []}
    if not isinstance(rules, list) or not rules:
        blockers.append("binding-rules attestation is missing or empty")
    elif (len(rules) != len(expected_rules)
          or any(not isinstance(rule, dict)
                 or not isinstance(rule.get("id"), str) for rule in rules)
          or {rule["id"] for rule in rules} != set(expected_rules)):
        blockers.append("binding-rules attestation is incomplete or malformed")
    elif any(not isinstance(rule, dict)
             or not _BINDING_RULE_ATTESTATION_FIELDS <= set(rule)
             for rule in rules):
        blockers.append("binding-rules attestation is incomplete or malformed")
    elif any(
            not _present_text(rule.get("rule"))
            or not _present_text(rule.get("decision"))
            or rule.get("rule") != expected_rules[rule["id"]]["rule"]
            or rule.get("decision") != expected_rules[rule["id"]]["decision"]
            for rule in rules):
        blockers.append("binding-rules attestation is incomplete or malformed")
    elif any(not isinstance(rule, dict) or rule.get("ratified") is not True
             for rule in rules):
        blockers.append("one or more binding rules are unratified")

    indicators = model.get("indicators")
    if not isinstance(indicators, list) or not indicators or any(
            not isinstance(row, dict) for row in indicators):
        blockers.append("indicator-ratification attestation is missing or malformed")
    elif (len(indicators) != len(KNOWN_IDS)
          or any(not isinstance(row.get("id"), str) for row in indicators)
          or {row["id"] for row in indicators} != KNOWN_IDS):
        blockers.append("indicator-ratification attestation is incomplete or malformed")
    elif any(not _indicator_attestation_is_complete(row) for row in indicators):
        blockers.append("indicator-ratification attestation is incomplete or malformed")
    else:
        if any("ratification" in row for row in indicators):
            blockers.append("one or more indicator definitions are unresolved")
        if any(row.get("thresholds_ratified") is not True
               for row in indicators if row.get("thresholds")):
            blockers.append("one or more indicator thresholds are unratified")

    foresight = model.get("foresight")
    expected_foresight = dict(SPEC.get("foresight") or {}, ratified=True)
    if (not isinstance(foresight, dict)
            or foresight.get("ratified") is not True
            or foresight != expected_foresight):
        blockers.append("the foresight method is unratified")
    blockers.extend(_ratification_evidence_blockers(
        model, evidence_root, available_release_tags))
    return blockers


# ------------------------------------------------------------------ render

def render_html(doc):
    c = html.escape
    final = doc.get("final") is True
    expected_status = "Final DAR" if final else "Draft DAR"
    actual_status = str(doc.get("status") or "")
    if not actual_status.startswith(expected_status):
        raise ValueError(
            f"document status {actual_status!r} contradicts final={final!r}")
    publication_label = ("Final Digital Agriculture Roadmap"
                         if final
                         else "Draft Digital Agriculture Roadmap")
    parts = [
        "<meta charset='utf-8'>",
        f"<title>{c(doc['country'])} — {publication_label}</title>",
        "<style>",
        "body{font:16px/1.65 Georgia,serif;max-width:820px;margin:40px auto;padding:0 20px;color:#1a1a1a}",
        "h1{font-size:2rem;margin-bottom:.2em}h2{margin-top:2.2em;border-bottom:1px solid #ddd;padding-bottom:.2em}",
        ".banner{background:#f4f2ec;border-left:3px solid #9aa;padding:.6em .9em;font:13px/1.5 system-ui;margin:.6em 0 1.2em}",
        ".proposed{background:#fff7e6;border-left:3px solid #d9a441}",
        ".status{display:inline-block;font:600 11px system-ui;text-transform:uppercase;letter-spacing:.06em;padding:.2em .5em;border-radius:3px;background:#eee}",
        ".status.proposed{background:#d9a441;color:#fff}",
        ".fid{font:13px/1.6 system-ui;background:#f4f2ec;padding:1em;margin:1.5em 0}",
        ".prohib{font:12px/1.6 system-ui;color:#666;border-top:1px solid #ddd;margin-top:3em;padding-top:1em}",
        "table{border-collapse:collapse;width:100%;font:12px/1.4 system-ui}",
        "th,td{border:1px solid #ddd;padding:.4em;vertical-align:top;text-align:left}",
        "pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f7f7f7;padding:1em;"
        "font:11px/1.45 ui-monospace,monospace}",
        "</style>",
        f"<h1>{c(doc['country'])} — {publication_label}</h1>",
        f"<p><em>{c(doc['status'])} DAMM {c(doc['model_version'])}, assessment year "
        f"{doc['assessment_year']}.</em></p>",
        "<div class='fid'>",
        f"<b>Figure traceability: {doc['fidelity']['rate']:.1%}</b> — "
        f"{doc['fidelity']['supported']} of {doc['fidelity']['claimed']} figures carry "
        "a validated evidence, calculation, benchmark or planning-assumption basis. ",
        "Every chapter states what it was allowed to draw on. Chapters marked "
        "<span class='status proposed'>proposed</span> are recommendations built on the "
        "assessment, not findings from it.",
        "</div>",
    ]
    if doc.get("final") is not True:
        blockers = [str(item) for item in doc.get("publication_blockers") or []]
        detail = ("<ul>" + "".join(f"<li>{c(item)}</li>" for item in blockers) + "</ul>"
                  if blockers else
                  " Final-publication criteria have not been met.")
        parts.append("<div class='banner proposed'><b>Publication hold.</b> "
                     + detail + "</div>")
    for ch in doc["chapters"]:
        prescriptive = ch["kind"] == "prescriptive"
        parts.append(f"<h2>{c(str(ch['n']))}. {c(ch['title'])} "
                     + (f"<span class='status proposed'>proposed, not evidenced</span>"
                        if prescriptive else "<span class='status'>evidenced</span>")
                     + "</h2>")
        parts.append(f"<div class='banner{" proposed" if prescriptive else ""}'>"
                     f"{c(ch['provenance'])}</div>")
        for para in ch["prose"].split("\n\n"):
            if para.strip():
                parts.append(f"<p>{c(para.strip())}</p>")
        annex = ch.get("annex")
        if annex:
            parts.append("<h3>Indicator evidence</h3><table><thead><tr>"
                         "<th>ID</th><th>Indicator</th><th>Value</th><th>Class</th>"
                         "<th>Level</th><th>Year</th><th>Source</th><th>Tier</th>"
                         "<th>Evidence note</th></tr></thead><tbody>")
            for row in annex["indicator_evidence"]:
                source = row["source"]
                source_text = c(source["title"])
                url = source.get("url") or ""
                if re.match(r"^https?://", url, re.I):
                    source_text += (f"<br><a href='{c(url, quote=True)}'>"
                                    f"{c(url)}</a>")
                parts.append(
                    "<tr>" + "".join(f"<td>{value}</td>" for value in (
                        c(row["id"]), c(row["name"]), c(str(row["value"])),
                        c(str(row["class"])), c(str(row["level"])),
                        c(str(row["year"])), source_text, c(source.get("tier") or ""),
                        c(row.get("note") or ""))) + "</tr>")
            parts.append("</tbody></table>")
            annex_sections = (
                ("Run record", annex.get("run_record") or {}),
                ("Complete indicator records", annex.get("indicator_evidence") or []),
                ("Candidate rows", annex.get("candidate_rows") or []),
                ("Derived assessment", annex.get("derived_assessment") or {}),
                ("Country findings", annex.get("country_findings") or []),
                ("International pointers", annex.get("international_pointers") or []),
                ("Initiative register", annex.get("initiative_register") or []),
                ("Scan abstentions", annex.get("scan_abstentions") or []),
                ("AI in digital agriculture", annex.get("ai_digital_agriculture") or {}),
                ("Investment options and cost-benefit analysis",
                 annex.get("investment_options") or {}),
                ("Foresight record", annex.get("foresight") or {}),
                ("Method record", annex.get("method_record") or {}),
            )
            for heading, value in annex_sections:
                rendered = c(json.dumps(
                    value, indent=2, ensure_ascii=False, default=str))
                parts.append(f"<h3>{c(heading)}</h3><pre>{rendered}</pre>")
    parts.append("<div class='prohib'><b>Standing prohibitions.</b> "
                 + c(" ".join(str(p) for p in PROHIBITIONS)) + "</div>")
    return "\n".join(parts)


# ------------------------------------------------------------------ main

def file_record(path, **extra):
    """Stable identity of one run input or implementation file."""
    with open(path, "rb") as handle:
        content = handle.read()
    record = {
        "file": os.path.basename(path),
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    record.update(extra)
    return record


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def input_identity_errors(label, data, country, iso3):
    """Metadata mismatches that would put one country's evidence in another's DAR."""
    if not isinstance(data, dict):
        return [f"{label} is not a JSON object"]
    errors = []
    actual_country = " ".join(str(data.get("country") or "").split()).casefold()
    expected_country = " ".join(country.split()).casefold()
    if actual_country != expected_country:
        errors.append(f"{label}.country={data.get('country')!r}, expected {country!r}")
    actual_iso = str(data.get("iso3") or "").strip().upper()
    if actual_iso != iso3:
        errors.append(f"{label}.iso3={data.get('iso3')!r}, expected {iso3!r}")
    try:
        actual_year = int(data.get("assessment_year"))
    except (TypeError, ValueError):
        actual_year = None
    if actual_year != ASSESSMENT_YEAR:
        errors.append(
            f"{label}.assessment_year={data.get('assessment_year')!r}, "
            f"expected {ASSESSMENT_YEAR}")
    return errors


def required_product_errors(scans, foresight, country):
    """A present sidecar is not complete unless its records satisfy the pass contract."""
    errors = []

    def text(record, key, label):
        if not isinstance(record.get(key), str) or not record[key].strip():
            errors.append(f"{label}.{key} is not a non-empty string")

    def string_array(record, key, label, *, nonempty=False):
        value = record.get(key)
        if (not isinstance(value, list)
                or any(not isinstance(item, str) or not item.strip() for item in value)
                or (nonempty and not value)):
            qualifier = "non-empty " if nonempty else ""
            errors.append(f"{label}.{key} is not a {qualifier}string array")

    scan_arrays = ("country_findings", "international_pointers", "register_entries",
                   "abstained")
    for key in scan_arrays:
        if not isinstance(scans.get(key), list):
            errors.append(f"scans.{key} is not an array")
    if not any(scans.get(key) for key in
               ("country_findings", "international_pointers", "register_entries")):
        errors.append("scans contains no findings, pointers or register entries")

    chapters_by_id = {str(chapter["n"]): chapter for chapter in OUTLINE
                      if chapter["kind"] == "prescriptive"}
    chapter_ids = set(chapters_by_id)
    expected_country = " ".join(country.split()).casefold()
    for key, lane in (("country_findings", "country"),
                      ("international_pointers", "international")):
        records = scans.get(key)
        if not isinstance(records, list):
            continue
        for index, record in enumerate(records):
            label = f"scans.{key}[{index}]"
            if not isinstance(record, dict):
                errors.append(f"{label} is not an object")
                continue
            for field in ("chapter_title", "statement", "quote", "why_it_matters",
                          "source_name", "source_url", "tier", "about_country"):
                text(record, field, label)
            if str(record.get("chapter") or "") not in chapter_ids:
                errors.append(f"{label}.chapter is not a prescriptive chapter id")
            elif record.get("chapter_title") != chapters_by_id[
                    str(record["chapter"])]["title"]:
                errors.append(f"{label}.chapter_title does not match the outline")
            if record.get("lane") != lane:
                errors.append(f"{label}.lane must be {lane!r}")
            if record.get("tier") not in {"T1", "T2", "T3", "T4", "T5"}:
                errors.append(f"{label}.tier is not T1-T5")
            year = record.get("published_year")
            if year is not None and (isinstance(year, bool) or not isinstance(year, int)):
                errors.append(f"{label}.published_year is not an integer or null")
            if lane == "international" and record.get("applies_to") != "dar_only":
                errors.append(f"{label}.applies_to must be 'dar_only'")
            actual_country = " ".join(
                str(record.get("about_country") or "").split()).casefold()
            if lane == "country" and actual_country != expected_country:
                errors.append(f"{label}.about_country does not match the run country")
            if lane == "international" and actual_country == expected_country:
                errors.append(f"{label}.about_country is the run country, not a precedent")

    register_records = scans.get("register_entries")
    if isinstance(register_records, list):
        for index, record in enumerate(register_records):
            label = f"scans.register_entries[{index}]"
            if not isinstance(record, dict):
                errors.append(f"{label} is not an object")
                continue
            for field in ("name", "lead", "status", "tier", "src", "src_url",
                          "verification_note"):
                text(record, field, label)
            string_array(record, "uc", label, nonempty=True)
            string_array(record, "overlap", label)
            if record.get("status") not in {
                    "Operating", "Piloting", "Announced", "Discontinued", "Unclear"}:
                errors.append(f"{label}.status is outside the scan vocabulary")
            tier = record.get("tier")
            if tier not in {"T1", "T2", "T3", "T4", "T5"}:
                errors.append(f"{label}.tier is not T1-T5")
            results_tier = record.get("results_tier")
            if results_tier not in {"", "T1", "T2", "T3"}:
                errors.append(f"{label}.results_tier is not blank or T1-T3")
            if tier in {"T4", "T5"} and results_tier:
                errors.append(f"{label}.results_tier is not allowed for {tier}")

    abstentions = scans.get("abstained")
    if isinstance(abstentions, list):
        for index, record in enumerate(abstentions):
            label = f"scans.abstained[{index}]"
            if not isinstance(record, dict):
                errors.append(f"{label} is not an object")
                continue
            text(record, "why", label)
            if record.get("lane") not in {"country", "international", "register"}:
                errors.append(f"{label}.lane is outside the scan vocabulary")
            if not isinstance(record.get("chapter"), (str, int)):
                errors.append(f"{label}.chapter is not a string or integer")

    expected_method = SPEC["foresight"]["method"]
    if foresight.get("method") != expected_method:
        errors.append("foresight.method does not match the declared model method")
    if foresight.get("method_ratified") is not SPEC["foresight"].get("ratified", False):
        errors.append("foresight.method_ratified does not match the model")

    scenarios = foresight.get("scenarios")
    scenario_names = set()
    if not isinstance(scenarios, list) or len(scenarios) != 3:
        errors.append("foresight.scenarios is not the required three-record array")
    else:
        for index, record in enumerate(scenarios):
            label = f"foresight.scenarios[{index}]"
            if not isinstance(record, dict):
                errors.append(f"{label} is not an object")
                continue
            for field in ("name", "narrative", "what_would_make_it_happen",
                          "implication_for_the_sector"):
                text(record, field, label)
            string_array(record, "drivers", label, nonempty=True)
            if isinstance(record.get("name"), str) and record["name"].strip():
                scenario_names.add(record["name"].strip())
        if len(scenario_names) != len(scenarios):
            errors.append("foresight scenario names are not unique")

    expected_scenario_status = (
        "Scenarios bound the uncertainty. They are plausible futures, not forecasts, "
        "and none of them is a recommendation.")
    if foresight.get("scenario_status") != expected_scenario_status:
        errors.append("foresight.scenario_status is not the required non-forecast status")

    preferred = foresight.get("preferred_future")
    if not isinstance(preferred, dict):
        errors.append("foresight.preferred_future is not an object")
    else:
        for field in ("name", "narrative", "what_is_being_chosen",
                      "who_would_have_to_agree"):
            text(preferred, field, "foresight.preferred_future")
        string_array(preferred, "drawn_from_scenarios",
                     "foresight.preferred_future", nonempty=True)
        drawn = preferred.get("drawn_from_scenarios")
        if isinstance(drawn, list) and any(
                name not in scenario_names for name in drawn if isinstance(name, str)):
            errors.append("foresight.preferred_future names an unknown scenario")

    expected_preferred_status = (
        "A normative selection — a claim about values, not a finding from evidence. "
        "It is proposed for decision, not asserted.")
    if foresight.get("preferred_future_status") != expected_preferred_status:
        errors.append("foresight.preferred_future_status is not the required normative status")

    candidate_pattern = re.compile(SPEC["candidate_indicators"]["id_pattern"])
    candidate_fields = SPEC["candidate_indicators"]["required_fields"]
    milestone_candidate_ids = []
    milestones = foresight.get("milestones")
    if not isinstance(milestones, list) or not milestones:
        errors.append("foresight.milestones is not a non-empty array")
    else:
        for index, record in enumerate(milestones):
            label = f"foresight.milestones[{index}]"
            if not isinstance(record, dict):
                errors.append(f"{label} is not an object")
                continue
            for field in ("statement", "indicator_id", "why_this_step"):
                text(record, field, label)
            level = record.get("target_level")
            if isinstance(level, bool) or not isinstance(level, int) or not 1 <= level <= 5:
                errors.append(f"{label}.target_level is not an integer from 1 to 5")
            year = record.get("target_year")
            if (isinstance(year, bool) or not isinstance(year, int)
                    or not ASSESSMENT_YEAR < year <= ASSESSMENT_YEAR + 15):
                errors.append(f"{label}.target_year is outside the foresight horizon")
            if not isinstance(record.get("binds_to_candidate"), bool):
                errors.append(f"{label}.binds_to_candidate is not boolean")
            provisional = record.get("provisional_because")
            if provisional is not None and not isinstance(provisional, str):
                errors.append(f"{label}.provisional_because is not a string or null")
            indicator_id = record.get("indicator_id")
            candidate = record.get("candidate_indicator")
            is_candidate = isinstance(indicator_id, str) and bool(
                candidate_pattern.fullmatch(indicator_id))
            if is_candidate:
                if not isinstance(candidate, dict):
                    errors.append(f"{label}.candidate_indicator is not an object")
                else:
                    for field in candidate_fields:
                        text(candidate, field, f"{label}.candidate_indicator")
                    if candidate.get("id") != indicator_id:
                        errors.append(f"{label}.candidate_indicator id does not match")
                    milestone_candidate_ids.append(candidate.get("id"))
                if record.get("binds_to_candidate") is not True:
                    errors.append(f"{label} does not mark its candidate binding")
            elif indicator_id not in MODEL:
                errors.append(f"{label}.indicator_id is not in the model or candidate namespace")
            elif candidate is not None or record.get("binds_to_candidate") is not False:
                errors.append(f"{label} incorrectly carries a candidate binding")

    candidates = foresight.get("candidate_indicators")
    if not isinstance(candidates, list):
        errors.append("foresight.candidate_indicators is not an array")
    else:
        ids = []
        for index, candidate in enumerate(candidates):
            label = f"foresight.candidate_indicators[{index}]"
            if not isinstance(candidate, dict):
                errors.append(f"{label} is not an object")
                continue
            for field in candidate_fields:
                text(candidate, field, label)
            cid = candidate.get("id")
            if not isinstance(cid, str) or not candidate_pattern.fullmatch(cid):
                errors.append(f"{label}.id is outside the candidate namespace")
            ids.append(cid)
        if ids != milestone_candidate_ids or len(ids) != len(set(ids)):
            errors.append("foresight candidate register does not match milestone bindings")

    refused = foresight.get("refused_milestones")
    if not isinstance(refused, list):
        errors.append("foresight.refused_milestones is not an array")
    else:
        for index, record in enumerate(refused):
            label = f"foresight.refused_milestones[{index}]"
            if not isinstance(record, dict):
                errors.append(f"{label} is not an object")
                continue
            text(record, "statement", label)
            text(record, "why", label)

    if foresight.get("candidate_status") != SPEC["candidate_indicators"]["disposition"]:
        errors.append("foresight.candidate_status does not match the model disposition")
    text(foresight, "note", "foresight")
    return errors


def supplemental_product_errors(ai, investment, country, iso3):
    """Validate the two canonical products the earlier generator did not consume."""
    errors = []
    expected_country = " ".join(country.split()).casefold()
    expected_iso = iso3.strip().upper()
    for label, product, schema in (
            ("ai_assessment", ai, "damm.ai-digital-agriculture/v1"),
            ("investment_options", investment, "damm.investment-options/v1")):
        if not isinstance(product, dict):
            errors.append(f"{label} is not an object")
            continue
        if product.get("schema_version") != schema:
            errors.append(f"{label}.schema_version is not {schema}")
        if " ".join(str(product.get("country") or "").split()).casefold() != expected_country:
            errors.append(f"{label}.country does not match the run country")
        if str(product.get("iso3") or "").upper() != expected_iso:
            errors.append(f"{label}.iso3 does not match the run ISO")
        if not isinstance(product.get("source_inventory"), list):
            errors.append(f"{label}.source_inventory is not an array")
    if isinstance(ai, dict):
        for section in ("as_is", "peer_experience", "recommended_agenda"):
            if not isinstance(ai.get(section), dict):
                errors.append(f"ai_assessment.{section} is not an object")
        if not ((ai.get("as_is") or {}).get("findings")):
            errors.append("ai_assessment.as_is has no verified finding")
        if not ((ai.get("peer_experience") or {}).get("findings")):
            errors.append("ai_assessment.peer_experience has no verified finding")
        if ((ai.get("recommended_agenda") or {}).get("status")
                != "proposed_for_post_completion_validation"):
            errors.append("ai_assessment recommendations are not marked proposed")
    if isinstance(investment, dict):
        if not isinstance(investment.get("options"), list) or not investment.get("options"):
            errors.append("investment_options.options is empty")
        if investment.get("decision_status") != "no_financing_decision_made":
            errors.append("investment_options purports to make a financing decision")
    return errors


def workflow_generation_input_errors(manifest, country, iso3, input_records):
    """Authorize Draft generation from completed machine stages, never Final publication.

    The legacy reviewed package remains valid for a reviewed replay. This envelope is a
    different authority: it proves that stages 1–6 of the canonical autonomous workflow
    completed against exact, hash-bound inputs. It authorizes a Draft only; `reviewed`
    remains false and the final-publication gate below remains unchanged.
    """
    errors = []
    if not isinstance(manifest, dict):
        return ["workflow manifest is not an object"]
    if manifest.get("schema_version") != "damm.workflow-run/v1":
        errors.append("workflow manifest schema_version is not damm.workflow-run/v1")
    if manifest.get("workflow_id") != "dar-canonical-v1":
        errors.append("workflow manifest workflow_id is not dar-canonical-v1")
    with open(WORKFLOW_FILE) as handle:
        contract = json.load(handle)
    if manifest.get("workflow_version") != contract.get("workflow_version"):
        errors.append("workflow manifest version does not match the canonical contract")
    if manifest.get("contract_sha256") != file_record(WORKFLOW_FILE)["sha256"]:
        errors.append("workflow manifest is not bound to the canonical contract bytes")
    if " ".join(str(manifest.get("country") or "").split()).casefold() != (
            " ".join(country.split()).casefold()):
        errors.append("workflow manifest country does not match the run country")
    if str(manifest.get("iso3") or "").upper() != iso3.strip().upper():
        errors.append("workflow manifest ISO does not match the run ISO")
    if manifest.get("status") not in {"running", "retrying"}:
        errors.append("workflow manifest is not an active Stage 7 workflow")
    snapshot = manifest.get("input_snapshot")
    if (not isinstance(snapshot, dict)
            or not re.fullmatch(r"[0-9a-f]{64}", str(snapshot.get("sha256") or ""))):
        errors.append("workflow manifest has no immutable input snapshot hash")

    stages = manifest.get("stages")
    if not isinstance(stages, list):
        errors.append("workflow manifest stages is not an array")
        return errors
    by_id = {stage.get("id"): stage for stage in stages if isinstance(stage, dict)}
    required_stages = [
        "damm_diagnostic", "country_research", "ai_digital_agriculture",
        "international_lessons", "strategic_foresight", "investment_options",
    ]
    for stage_id in required_stages:
        stage = by_id.get(stage_id)
        if not stage or stage.get("status") != "complete":
            errors.append(f"workflow stage {stage_id} is not complete")

    artifact_bindings = {
        "engine_input": ("damm_diagnostic", "engine_input"),
        "scans": ("international_lessons", "scans"),
        "ai_assessment": ("ai_digital_agriculture", "ai_assessment"),
        "foresight": ("strategic_foresight", "foresight"),
        "investment_options": ("investment_options", "investment_options"),
    }
    for input_name, (stage_id, artifact_key) in artifact_bindings.items():
        stage = by_id.get(stage_id) or {}
        artifacts = stage.get("artifacts")
        artifacts = artifacts if isinstance(artifacts, list) else []
        artifact = next((item for item in artifacts
                         if isinstance(item, dict) and item.get("key") == artifact_key), None)
        actual = input_records.get(input_name) or {}
        if not artifact:
            errors.append(f"workflow stage {stage_id} has no {artifact_key} artifact")
        elif artifact.get("sha256") != actual.get("sha256"):
            errors.append(f"{input_name} hash does not match workflow stage {stage_id}")
    return errors


def _preparse_output_target(argv):
    """Return one unambiguous ``--out`` value without accepting other arguments.

    The full parser may exit before ``main`` has paths with which to invalidate an old
    publication.  This deliberately recognizes only the documented long option forms;
    an absent value or conflicting repeated values is not a safe deletion target.
    """
    values = []
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument == "--":
            break
        if argument == "--out":
            if index + 1 >= len(argv) or argv[index + 1].startswith("-"):
                return None
            values.append(argv[index + 1])
            index += 2
            continue
        if argument.startswith("--out="):
            value = argument.split("=", 1)[1]
            if not value:
                return None
            values.append(value)
        index += 1
    return values[0] if values and len(set(values)) == 1 else None


def _run_output_path(output_target, suffix):
    return os.path.abspath(os.path.join(LOOP1, f"{output_target}_{suffix}"))


def _invalidate_parse_failed_publication(output_target):
    """Make a parse-failed invocation ineligible to leave an older DAR published."""
    manifest_path = _run_output_path(output_target, "dar_manifest.json")
    dar_paths = (
        _run_output_path(output_target, "dar.json"),
        _run_output_path(output_target, "dar.html"),
    )
    now = utc_now()
    marker = {
        "schema_version": 2,
        "run_id": None,
        "status": "blocked",
        "reason": {
            "code": "cli_parse_failed",
            "detail": "command-line arguments were invalid; no DAR was published",
        },
        "started_at": now,
        "finished_at": now,
        "reviewed": False,
        "artifacts": {"dar_json": None, "dar_html": None},
    }
    try:
        # Invalidate the commit marker before removing either artifact.  If this write
        # cannot be made durable, preserve the prior publication as one coherent unit.
        V.atomic_write_json(manifest_path, marker)
    except OSError as error:
        print(f"warning: could not invalidate prior DAR publication: {error}",
              file=sys.stderr)
        return False

    ok = True
    for path in dar_paths:
        try:
            if os.path.lexists(path):
                os.unlink(path)
        except OSError as error:
            ok = False
            print(f"warning: could not remove stale DAR artifact {path}: {error}",
                  file=sys.stderr)
    return ok


def main():
    argv = sys.argv[1:]
    preparse_output_target = _preparse_output_target(argv)
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", required=True)
    ap.add_argument("--iso", required=True)
    ap.add_argument("--out", required=True, help="basename of the research pass")
    ap.add_argument("--ceiling", type=float, default=500.0)
    ap.add_argument("--vendor", default="anthropic/claude-opus-5")
    ap.add_argument("--replay", help="versioned offline recording of chapter responses")
    ap.add_argument(
        "--workflow-manifest",
        help=("active damm.workflow-run/v1 manifest whose completed stages 1–6 "
              "authorize autonomous Draft generation; never authorizes Final publication"),
    )
    ap.add_argument("--resume", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as error:
        if error.code and preparse_output_target is not None:
            _invalidate_parse_failed_publication(preparse_output_target)
        raise
    a.country = " ".join(a.country.split())
    a.iso = a.iso.strip().upper()

    def run_path(suffix):
        return _run_output_path(a.out, suffix)

    state_path = run_path("generation_state.json")
    spend_path = run_path("generation_spend.json")
    manifest_path = run_path("dar_manifest.json")
    dar_json_path = run_path("dar.json")
    dar_html_path = run_path("dar.html")
    inp = run_path("g2_input.json")
    scans_path = run_path("scans.json")
    foresight_path = run_path("foresight.json")
    package_path = run_path("run_package.json")
    ai_path = run_path("ai_assessment.json")
    investment_path = run_path("investment_options.json")
    workflow_manifest_path = (os.path.abspath(a.workflow_manifest)
                              if a.workflow_manifest else None)
    workflow_mode = workflow_manifest_path is not None

    started_at = utc_now()
    state = {"schema_version": 3, "country": a.country, "iso3": a.iso,
             "chapters": {}, "request_sha256": {}, "response_sha256": {}}
    WI.bind_checkpoint_state(state, loaded=False)
    reused, regenerated = [], []
    input_records = {}
    reviewed = False
    final = False
    publication_blockers = []
    review = {"inputs": False, "narrative": False}
    implementation = {
        "generator": file_record(__file__),
        "engine": file_record(ENGINE_FILE),
        "model": file_record(MODEL_FILE),
        "adapter": file_record(VENDORS_FILE),
    }
    adapter = {
        "mode": "replay" if a.replay else "live",
        "requested": a.replay or a.vendor,
        "resolved": None,
    }
    run_id = content_run_id(
        a.country, a.iso, ASSESSMENT_YEAR, input_records, implementation, adapter)

    def write_manifest(status, reason, checks=None, artifacts=None):
        terminal = status not in ("running",)
        payload = {
            "schema_version": 2,
            "run_id": run_id,
            "status": status,
            "reason": reason,
            "started_at": started_at,
            "finished_at": utc_now() if terminal else None,
            "country": a.country,
            "iso3": a.iso,
            "assessment_year": ASSESSMENT_YEAR,
            "reviewed": reviewed,
            "review": dict(review),
            "model_ratified": SPEC.get("ratified") is True,
            "final": final,
            "publication_blockers": list(publication_blockers),
            "model_version": f"{SPEC['version']} rev{SPEC['revision']}",
            "execution": dict(adapter),
            "draft_authority": ("canonical_workflow" if workflow_mode
                                else "reviewed_run_package"),
            "inputs": dict(input_records),
            "implementation": implementation,
            "chapters": {
                "completed": len(state.get("chapters") or {}),
                "expected": len(OUTLINE),
                "ids": [str(chapter["n"]) for chapter in OUTLINE
                        if str(chapter["n"]) in (state.get("chapters") or {})],
                "reused": list(reused),
                "regenerated": list(regenerated),
                "request_sha256": dict(state.get("request_sha256") or {}),
                "response_sha256": dict(state.get("response_sha256") or {}),
            },
            "qc": [
                {"id": name.split()[0], "ok": bool(ok), "detail": detail}
                for name, ok, detail in (checks or []) if name.startswith("B")
            ],
            "artifacts": ({"dar_json": None, "dar_html": None}
                          if artifacts is None else artifacts),
        }
        V.atomic_write_json(manifest_path, payload)

    def block(code, detail):
        print(f"!! {detail}")
        write_manifest("blocked", {"code": code, "detail": detail})
        return 1

    # The manifest is the publication commit marker. Invalidate its status first, then
    # remove the exact prior publication targets; a crash can never leave a stale
    # "complete" marker pointing at artifacts this run already removed.
    try:
        write_manifest("running", None)
        for old_artifact in (dar_json_path, dar_html_path):
            if os.path.exists(old_artifact):
                os.unlink(old_artifact)
    except OSError as error:
        return block("publication_invalidation_failed", str(error))

    argument_errors = []
    if not a.country:
        argument_errors.append("country is empty")
    if not re.fullmatch(r"[A-Z]{3}", a.iso):
        argument_errors.append("ISO must be exactly three letters")
    if not str(a.out).strip():
        argument_errors.append("output basename is empty")
    if not (a.ceiling > 0 and a.ceiling < float("inf")):
        argument_errors.append("ceiling must be a finite positive number")
    if argument_errors:
        return block("invalid_argument", "; ".join(argument_errors))

    required = {
        "engine_input": inp,
        "scans": scans_path,
        "foresight": foresight_path,
    }
    if workflow_mode:
        required.update({
            "ai_assessment": ai_path,
            "investment_options": investment_path,
            "workflow_manifest": workflow_manifest_path,
        })
    else:
        required["run_package"] = package_path
    missing = [name for name, path in required.items() if not os.path.exists(path)]
    if missing:
        detail = ("canonical Draft DAR requires completed workflow stages 1–6; missing "
                  if workflow_mode else
                  "final DAR requires the reviewed engine input, scans and foresight; missing ")
        return block("required_input_missing", detail + ", ".join(missing))

    try:
        for name, path in required.items():
            input_records[name] = file_record(
                path, required=True,
                reviewed=(not workflow_mode and name == "engine_input"))
        rows = V.strict_json_load(inp)
        scans = V.strict_json_load(scans_path)
        foresight = V.strict_json_load(foresight_path)
        if workflow_mode:
            ai_assessment = V.strict_json_load(ai_path)
            investment_options = V.strict_json_load(investment_path)
            workflow_manifest = V.strict_json_load(workflow_manifest_path)
            package = None
        else:
            ai_assessment = None
            investment_options = None
            workflow_manifest = None
            package = V.strict_json_load(package_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return block("required_input_invalid", str(error))

    row_errors = assessment_input_errors(rows)
    if row_errors:
        return block("required_input_invalid", "; ".join(row_errors[:12]))

    identity_errors = (input_identity_errors("scans", scans, a.country, a.iso)
                       + input_identity_errors("foresight", foresight, a.country, a.iso))
    if not workflow_mode:
        identity_errors += input_identity_errors(
            "run_package", package, a.country, a.iso)
    if identity_errors:
        return block("input_identity_mismatch", "; ".join(identity_errors))
    product_errors = required_product_errors(scans, foresight, a.country)
    if workflow_mode:
        product_errors += supplemental_product_errors(
            ai_assessment, investment_options, a.country, a.iso)
    if product_errors:
        return block("required_product_incomplete", "; ".join(product_errors))
    if workflow_mode:
        workflow_errors = workflow_generation_input_errors(
            workflow_manifest, a.country, a.iso, input_records)
        if workflow_errors:
            return block("workflow_manifest_invalid", "; ".join(workflow_errors))
        # Attach rather than flatten. `pack_for` and the deterministic annex preserve
        # each product's separate status and provenance.
        scans = dict(scans)
        scans["_ai_assessment"] = ai_assessment
        scans["_investment_options"] = investment_options
        declared_files = {}
    else:
        if (package.get("schema_version") != "damm.dar-run-package/v1"
                or package.get("reviewed") is not True):
            return block("input_package_invalid",
                         "run package is not a reviewed damm.dar-run-package/v1 envelope")
        declared_files = package.get("files") or {}
        hash_errors = []
        for name in ("engine_input", "scans", "foresight"):
            declared_sha = (declared_files.get(name) or {}).get("sha256")
            actual_sha = input_records[name]["sha256"]
            if declared_sha != actual_sha:
                hash_errors.append(
                    f"{name} sha256 {actual_sha} does not match reviewed package {declared_sha}")
        if hash_errors:
            return block("input_package_mismatch", "; ".join(hash_errors))
        # This attests only to the deterministic inputs. The completed narrative is not
        # final until its exact reviewed replay is matched after adapter initialization.
        review["inputs"] = True

    if a.replay:
        replay_path = os.path.abspath(a.replay)
        if not os.path.exists(replay_path):
            return block("replay_invalid", f"no replay tape at {replay_path}")
        input_records["replay"] = file_record(replay_path, required=True)

    # Once every immutable input is known, the run id becomes content-based. The
    # adapter identity is finalized below after aliases/defaults have been resolved.
    run_id = content_run_id(
        a.country, a.iso, ASSESSMENT_YEAR, input_records, implementation, adapter)
    write_manifest("running", None)

    try:
        assessment = engine_run(
            a.country, rows, refyear=ASSESSMENT_YEAR, model_spec=SPEC,
            intervention_profiles={})
        V.require_finite_json(assessment)
    except Exception as error:
        return block("engine_failed", str(error))

    ledger = V.Ledger(ceiling=a.ceiling, label=f"{a.out}_generation")
    resume_state_exists = a.resume and os.path.exists(state_path)
    resume_spend_exists = a.resume and os.path.exists(spend_path)
    ledger.attach(spend_path)
    # A retry can have a journalled call but no generation state if the process died
    # before its first chapter checkpoint. Existing generation state embeds its own
    # ledger and follows the reconciliation path below; without state, the standalone
    # journal is the only authoritative account and must be carried now.
    carried = ledger.load(spend_path) if resume_spend_exists else 0
    try:
        if a.replay:
            llm = V.ReplayLLM(a.replay, ledger)
            adapter_label = f"replay/{llm.model}"
        else:
            V.load_env()
            vendor, _, model_name = a.vendor.partition("/")
            llm = V.LLM(vendor, ledger, model=model_name or None)
            adapter_label = f"{llm.vendor}/{llm.model}"
    except (Exception, SystemExit) as error:
        return block("adapter_initialization_failed", str(error))
    adapter["resolved"] = adapter_label
    if a.replay:
        declared_replay = (declared_files.get("replay") or {})
        review["narrative"] = bool(
            declared_replay.get("sha256") == input_records["replay"]["sha256"]
            and declared_replay.get("fixture_id") == llm.model)
    reviewed = review["inputs"] and review["narrative"]
    run_id = content_run_id(
        a.country, a.iso, ASSESSMENT_YEAR, input_records, implementation, adapter)
    write_manifest("running", None)

    resume_cache_reset = False
    if resume_state_exists:
        try:
            cached_state = V.strict_json_load(state_path)
            WI.bind_checkpoint_state(cached_state, loaded=True)
            identified = (cached_state.get("schema_version") == 3
                          and cached_state.get("country")
                          and cached_state.get("iso3"))
            if not identified:
                # Pre-v3 checkpoints are never trusted as chapter caches because they
                # cannot prove which country or request produced them. They are a safe
                # cache miss, not a permanent blocker: retain the separate spend ledger
                # and regenerate every chapter under the current contract.
                carried = ledger.load(spend_path)
                resume_cache_reset = True
                print("legacy or unidentified checkpoint ignored — regenerating all "
                      "chapters under state schema v3")
            else:
                if (" ".join(str(cached_state.get("country") or "").split()).casefold()
                        != a.country.casefold()
                        or str(cached_state.get("iso3") or "").upper() != a.iso):
                    return block("resume_identity_mismatch",
                                 "cached state country or ISO does not match this run")
                if not isinstance(cached_state.get("chapters"), dict):
                    raise ValueError("cached chapters is not an object")
                state = cached_state
                state.setdefault("request_sha256", {})
                state.setdefault("response_sha256", {})
                if state.get("ledger"):
                    carried = (ledger.reconcile(state["ledger"])
                               if resume_spend_exists
                               else ledger.restore(state["ledger"]))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            return block("resume_state_invalid", str(error))
        if not resume_cache_reset:
            print(f"resuming — {len(state['chapters'])} chapters already written, {carried} "
                  f"earlier vendor calls carried (${ledger.spent():.2f} spent)")

    total = len(OUTLINE)
    print(f"{a.country} ({a.iso}) · {total} outline chapters · vendor {adapter_label}")
    print(f"budget ${a.ceiling:.0f}, generation allocation "
          f"${a.ceiling * V.Ledger.ALLOCATION[PASS]:.0f} (decision G3)")
    print()
    sys.stdout.flush()

    def save():
        # State and spend carry the same snapshot, while each metered call is also
        # journalled immediately. Resume reconciles the two ordered call histories, so a
        # crash between either atomic write cannot reuse a paid chapter or lose spend.
        state["ledger"] = ledger.snapshot()
        V.atomic_write_json(state_path, state)
        V.atomic_write_json(spend_path, state["ledger"])

    if not a.resume or resume_cache_reset or not resume_state_exists:
        save()

    stopped = None
    for n, chapter in enumerate(OUTLINE, 1):
        key = str(chapter["n"])
        try:
            request_sha = chapter_request_sha256(
                chapter, rows, assessment, scans, foresight, a.country, a.iso, llm)
            adapter_identity = chapter_adapter_cache_identity(
                chapter, assessment, scans, foresight, a.country, llm)
            adapter_response_sha = ((adapter_identity or {}).get("response_sha256")
                                    if isinstance(adapter_identity, dict) else None)
        except Exception as error:
            stopped = {"code": "chapter_generation_failed", "detail": str(error),
                       "chapter": key}
            break
        if (key in state["chapters"]
                and state["request_sha256"].get(key) == request_sha):
            try:
                if key == "A":
                    rec = build_annex_chapter(rows, assessment, scans, foresight,
                                              a.country, a.iso)
                    actual_response_sha = _sha256(rec["annex"])
                else:
                    raw_response = chapter_response(state["chapters"][key])
                    actual_response_sha = _sha256(raw_response)
                    if (adapter_response_sha
                            and adapter_response_sha != actual_response_sha):
                        raise V.VendorError(
                            f"cached response for {key} differs from replay tape")
                    rec = build_chapter_record(
                        chapter, raw_response, assessment, scans, foresight)
                    expected_response_sha = state["response_sha256"].get(key)
                    if expected_response_sha and expected_response_sha != actual_response_sha:
                        rec["cache_integrity_error"] = {
                            "expected": expected_response_sha,
                            "actual": actual_response_sha,
                        }
                state["chapters"][key] = rec
                state["response_sha256"].setdefault(key, actual_response_sha)
                reused.append(key)
                continue
            except (KeyError, TypeError, V.VendorError):
                # A malformed cache is a miss, never a trusted shortcut around the
                # response schema or the current gates.
                pass
        state["chapters"].pop(key, None)
        state["request_sha256"].pop(key, None)
        state["response_sha256"].pop(key, None)
        t0 = time.time()
        try:
            if key == "A":
                rec = build_annex_chapter(rows, assessment, scans, foresight,
                                          a.country, a.iso)
            else:
                rec = write_chapter(chapter, assessment, scans, foresight,
                                    a.country, llm)
        except V.BudgetExhausted as e:
            stopped = {"code": "budget_exhausted", "detail": str(e), "chapter": key}
            break
        except Exception as e:
            print(f"!! chapter {key} failed: {str(e)[:120]}")
            sys.stdout.flush()
            stopped = {"code": "chapter_generation_failed", "detail": str(e),
                       "chapter": key}
            break
        state["chapters"][key] = rec
        state["request_sha256"][key] = request_sha
        state["response_sha256"][key] = _sha256(
            rec["annex"] if key == "A" else chapter_response(rec))
        regenerated.append(key)
        save()
        mark = "P" if rec["kind"] == "prescriptive" else " "
        flags = []
        if rec["cited_outside_binding"]:
            flags.append(f"{len(rec['cited_outside_binding'])} outside binding")
        if rec["unsupported_figures"]:
            flags.append(f"{len(rec['unsupported_figures'])} unsupported")
        if rec["stray_numbers"]:
            flags.append(f"{len(rec['stray_numbers'])} stray")
        print(f"{mark} [{n:2d}/{total}] {key:<12} written {rec['title'][:22]:<24} "
              f"{('; '.join(flags) or 'clean'):<36} $ {ledger.spent():5.2f} "
              f"{int(time.time() - t0):3d}s")
        sys.stdout.flush()

    if stopped:
        print(f"\n!! {stopped['detail']}")
        print("   Generation is incomplete. Chapters never reached are absent from the "
              "output, NOT written as empty.")
        save()
        write_manifest("incomplete", stopped)
        return 1

    # Persist canonicalized reused chapters before QC. Derived fields from a prior code
    # version or a hand-edited checkpoint never survive this point.
    save()

    chapters = [state["chapters"][str(c["n"])] for c in OUTLINE
                if str(c["n"]) in state["chapters"]]
    claimed = sum(len(c["figures"]) for c in chapters)
    supported = sum(c["supported_figures"] for c in chapters)
    publication_blockers = final_publication_blockers(reviewed)
    final = not publication_blockers
    doc = {
        "country": a.country,
        "iso3": a.iso,
        "assessment_year": ASSESSMENT_YEAR,
        "model_version": f"{SPEC['version']} rev{SPEC['revision']}",
        "status": ("Final DAR — reviewed inputs, reviewed narrative replay, and "
                   "ratified methodology."
                   if final else
                   "Draft DAR — final-publication criteria are not yet met."),
        "reviewed": reviewed,
        "method_ratified": SPEC.get("ratified") is True,
        "final": final,
        "publication_blockers": publication_blockers,
        "workflow": ({
            "workflow_id": workflow_manifest.get("workflow_id"),
            "workflow_version": workflow_manifest.get("workflow_version"),
            "input_snapshot_sha256": (workflow_manifest.get("input_snapshot") or {}).get("sha256"),
        } if workflow_mode else None),
        "chapters": chapters,
        "fidelity": {
            "claimed": claimed,
            "supported": supported,
            "unsupported": claimed - supported,
            "rate": (supported / claimed) if claimed else 1.0,
        },
        "prohibitions": PROHIBITIONS,
    }

    checks = qc_checks(doc)
    print()
    for name, ok, detail in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))
    failed = [n for n, ok, _ in checks if not ok]
    if failed:
        # Emit-blocking, exactly as the diagnostic's gate is. A document that fails its
        # own checks and is written anyway teaches everyone to ignore the checks.
        print(f"\n!! QC FAIL — the roadmap was NOT written: {'; '.join(failed)}")
        save()
        write_manifest("rejected", {
            "code": "qc_failed",
            "detail": "; ".join(failed),
        }, checks)
        return 1

    try:
        V.atomic_write_json(dar_json_path, doc)
        V.atomic_write_text(dar_html_path, render_html(doc))
        ledger.save(spend_path)
        artifacts = {
            "dar_json": file_record(dar_json_path),
            "dar_html": file_record(dar_html_path),
        }
        write_manifest("complete", None, checks, artifacts)
    except Exception as error:
        for partial in (dar_json_path, dar_html_path):
            if os.path.exists(partial):
                os.unlink(partial)
        return block("artifact_write_failed", str(error))

    print()
    print(f"wrote {a.out}_dar.json — {len(chapters)} chapters, fidelity "
          f"{doc['fidelity']['rate']:.1%} ({supported}/{claimed} figures)")
    s = ledger.summary()
    print(f"spend ${s['total']:.2f} of ${a.ceiling * V.Ledger.ALLOCATION[PASS]:.0f} "
          f"allocated (${a.ceiling:.0f} country ceiling), {s['calls']} vendor calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
