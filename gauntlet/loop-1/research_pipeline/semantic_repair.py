"""Shared protocol primitives for one bounded local-contract repair.

Provider schema acceptance is not the same thing as acceptance by a stage's local
semantic gates.  These helpers make the one allowed semantic repair a different,
deterministic request while leaving checkpoint ownership with the stage.
"""

import copy
import json

import vendors as V


REPAIR_SUFFIX = " [semantic repair 1/1]"


def _normalized_errors(errors):
    values = []
    for error in errors or ():
        text = " ".join(str(error or "").split())
        if text and text not in values:
            values.append(text)
    return tuple(values)


class SemanticResponseInvalid(ValueError):
    """A structured response failed a deterministic stage-owned contract."""

    def __init__(self, errors, *, refusals=()):
        self.errors = _normalized_errors(errors)
        if not self.errors:
            self.errors = ("local semantic contract rejected the response",)
        self.refusals = copy.deepcopy(list(refusals or ()))
        super().__init__("; ".join(self.errors))


class SemanticRepairExhausted(V.VendorError):
    """The only authorized semantic repair also failed local validation."""

    code = "semantic_repair_exhausted"

    def __init__(self, step_id, errors):
        self.step_id = str(step_id)
        self.errors = _normalized_errors(errors)
        super().__init__(
            f"{self.step_id} exhausted its single semantic repair: "
            + "; ".join(self.errors)
        )


def repair_detail(detail):
    return str(detail) + REPAIR_SUFFIX


def repair_user(original_user, original_response, errors):
    """Build the deterministic replacement request from bounded machine data."""
    payload = {
        "local_contract_errors": list(_normalized_errors(errors)),
        "rejected_response": copy.deepcopy(original_response),
    }
    return (
        str(original_user)
        + "\n\nSEMANTIC REPAIR (the only allowed repair for this unit):\n"
        + "The prior response satisfied the provider JSON schema but failed the local "
        + "publication contract below. Return one complete replacement object under the "
        + "same schema. Do not return a patch, commentary, or fields outside the schema.\n"
        + json.dumps(payload, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False, allow_nan=False)
    )


def response_sha256(response):
    return V.stable_json_sha256(response)


def stage_failure_exit(error, default=1):
    if isinstance(error, SemanticRepairExhausted):
        return V.NONRETRYABLE_STAGE_EXIT
    return V.stage_failure_exit(error, default)
