"""Frozen optional-input manifest shared by canonical workflow stages."""

import hashlib
import json
import os
import re


SCHEMA_VERSION = "damm.uploads-manifest/v1"
CHECKPOINT_IDENTITY_FIELD = "checkpoint_identity_sha256"
BALANCED_EXCERPT_POLICY = "balanced-start-middle-end-v1"


def sha256_bytes(content):
    return hashlib.sha256(content).hexdigest()


def checkpoint_identity_sha256():
    """Return the coordinator-provided run/input binding, if this is a workflow call."""
    value = os.environ.get("DAMM_CHECKPOINT_BINDING_SHA256", "").strip()
    if value and not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("DAMM_CHECKPOINT_BINDING_SHA256 is not a SHA-256 digest")
    return value


def bind_checkpoint_state(state, *, loaded):
    """Bind reusable state to one canonical run input and reject legacy/foreign state."""
    if not isinstance(state, dict):
        raise ValueError("checkpoint state is not an object")
    identity = checkpoint_identity_sha256()
    if not identity:
        return state
    prior = str(state.get(CHECKPOINT_IDENTITY_FIELD) or "")
    if loaded and prior != identity:
        raise ValueError("checkpoint state is not bound to this workflow input")
    if not loaded and prior and prior != identity:
        raise ValueError("checkpoint state carries a different workflow input")
    state[CHECKPOINT_IDENTITY_FIELD] = identity
    return state


def balanced_text_excerpt(text, max_characters):
    """Return a deterministic whole-document excerpt and explicit character coverage.

    Short documents are carried in full. Longer documents contribute disjoint start,
    middle and end windows, rather than silently privileging their opening pages. The
    offsets are zero-based and ``end_character_exclusive`` follows normal Python slice
    semantics, so downstream artifacts can state exactly what the model was allowed to
    inspect.
    """
    if isinstance(max_characters, bool) or not isinstance(max_characters, int):
        raise ValueError("max_characters must be a positive integer")
    if max_characters <= 0:
        raise ValueError("max_characters must be a positive integer")

    source = str(text or "")
    source_characters = len(source)
    if source_characters <= max_characters:
        segments = ([{
            "label": "full",
            "start_character": 0,
            "end_character_exclusive": source_characters,
        }] if source_characters else [])
        return {
            "text": source,
            "verbatim_segments": [source] if source_characters else [],
            "coverage": {
                "policy": BALANCED_EXCERPT_POLICY,
                "mode": "full" if source_characters else "empty",
                "source_characters": source_characters,
                "included_source_characters": source_characters,
                "omitted_source_characters": 0,
                "segments": segments,
            },
        }

    base, remainder = divmod(max_characters, 3)
    sizes = [base + (1 if index < remainder else 0) for index in range(3)]
    start_size, middle_size, end_size = sizes
    end_start = source_characters - end_size
    # Split the omitted material evenly around the middle window. Since the source is
    # longer than the excerpt budget, these three windows are always disjoint.
    middle_start_min = start_size
    middle_start_max = end_start - middle_size
    middle_start = (middle_start_min + middle_start_max) // 2
    windows = [
        ("start", 0, start_size),
        ("middle", middle_start, middle_start + middle_size),
        ("end", end_start, source_characters),
    ]
    segments = [{
        "label": label,
        "start_character": start,
        "end_character_exclusive": end,
    } for label, start, end in windows]
    rendered = "\n\n".join(
        f"[{label.upper()} EXCERPT: source characters {start}-{end - 1} "
        f"of {source_characters}]\n{source[start:end]}"
        for label, start, end in windows
    )
    return {
        "text": rendered,
        # Synthetic range labels make the prompt legible but are not evidence. Consumers
        # that verify quotations use these exact source-only windows instead.
        "verbatim_segments": [source[start:end] for _, start, end in windows],
        "coverage": {
            "policy": BALANCED_EXCERPT_POLICY,
            "mode": "balanced_excerpt",
            "source_characters": source_characters,
            "included_source_characters": max_characters,
            "omitted_source_characters": source_characters - max_characters,
            "segments": segments,
        },
    }


def document_excerpt(upload, max_characters):
    """Build a balanced excerpt from one normalized upload document."""
    if not isinstance(upload, dict):
        raise ValueError("upload document is not an object")
    return balanced_text_excerpt(
        upload.get("extracted_text") or upload.get("content") or "",
        max_characters,
    )


def coverage_text(coverage):
    """Stable prompt/artifact representation of an excerpt's coverage metadata."""
    return json.dumps(coverage, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_upload_documents(manifest_path, kinds):
    """Return verified UTF-8 document extractions for the requested input kinds.

    DAR Studio freezes extracted text before launch. The hash is over those exact bytes;
    stages read only the frozen path and never ask a person for a late upload. A compact
    legacy envelope is accepted for historical fixtures, but production manifests use
    `damm.uploads-manifest/v1` and `documents`.
    """
    if not manifest_path:
        return []
    manifest_path = os.path.abspath(manifest_path)
    with open(manifest_path, "rb") as handle:
        manifest_bytes = handle.read()
    expected_manifest_sha = os.environ.get(
        "DAMM_UPLOADS_MANIFEST_SHA256", ""
    ).strip()
    if expected_manifest_sha:
        if not re.fullmatch(r"[0-9a-f]{64}", expected_manifest_sha):
            raise ValueError("DAMM_UPLOADS_MANIFEST_SHA256 is not a SHA-256 digest")
        if sha256_bytes(manifest_bytes) != expected_manifest_sha:
            raise ValueError("uploads manifest does not match the frozen launch input")
    try:
        payload = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("uploads manifest is not valid UTF-8 JSON") from error
    if not isinstance(payload, dict):
        raise ValueError("uploads manifest root is not an object")
    selected = set(kinds)
    if payload.get("schema_version") == SCHEMA_VERSION:
        rows = payload.get("documents")
        if not isinstance(rows, list):
            raise ValueError("uploads manifest documents is not an array")
        out = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict) or row.get("kind") not in selected:
                continue
            label = f"documents[{index}]"
            content_path = str(row.get("content_path") or "")
            expected_sha = str(row.get("content_sha256") or "")
            media_type = str(row.get("content_media_type") or "")
            if not content_path:
                raise ValueError(f"{label}.content_path is empty")
            portable = content_path.replace("\\", "/")
            parts = portable.split("/")
            if (
                portable != content_path
                or os.path.isabs(content_path)
                or any(part in {"", ".", ".."} for part in parts)
                or parts[:2] != ["inputs", "upload-content"]
            ):
                raise ValueError(
                    f"{label}.content_path is not a canonical upload-content path"
                )
            workspace = os.environ.get("DAMM_WORKFLOW_WORKSPACE", "").strip()
            if workspace:
                workspace = os.path.realpath(os.path.abspath(workspace))
            else:
                manifest_directory = os.path.dirname(manifest_path)
                if os.path.basename(manifest_directory) != "inputs":
                    raise ValueError(
                        "canonical uploads manifest must be below the workspace inputs directory"
                    )
                workspace = os.path.realpath(os.path.dirname(manifest_directory))
            unresolved = os.path.abspath(os.path.join(workspace, *parts))
            resolved = os.path.realpath(unresolved)
            try:
                contained = os.path.commonpath((workspace, resolved)) == workspace
            except ValueError:
                contained = False
            if not contained:
                raise ValueError(f"{label}.content_path escapes the workflow workspace")
            if unresolved != resolved:
                raise ValueError(f"{label}.content_path may not traverse a symbolic link")
            if not os.path.isfile(resolved):
                raise ValueError(f"{label}.content_path is not a regular file")
            content_path = resolved
            if media_type and media_type.split(";", 1)[0].strip() != "text/plain":
                raise ValueError(f"{label}.content_media_type is not text/plain")
            with open(content_path, "rb") as handle:
                raw = handle.read()
            actual_sha = sha256_bytes(raw)
            if expected_sha != actual_sha:
                raise ValueError(f"{label}.content_sha256 does not match the frozen text")
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError as error:
                raise ValueError(f"{label} frozen extraction is not UTF-8") from error
            out.append({
                "id": str(row.get("id") or ""),
                "filename": str(row.get("original_filename") or ""),
                "category": row.get("kind"),
                "mime_type": str((row.get("metadata") or {}).get("source_mime_type") or ""),
                "sha256": actual_sha,
                "extracted_text": text,
                "source_kind": "ttl_upload",
                "uploaded_at": str((row.get("metadata") or {}).get("uploaded_at") or ""),
            })
        return out

    # Historical fixture compatibility. These records already carry extracted text;
    # they are never emitted by the canonical app launcher.
    rows = payload.get("uploads") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError(f"uploads manifest schema_version is not {SCHEMA_VERSION}")
    return [dict(row, source_kind="ttl_upload") for row in rows
            if isinstance(row, dict) and row.get("category") in selected]
