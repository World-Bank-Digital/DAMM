"""Shared candidate-indicator register rules for foresight producers and consumers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateRegistryConflict:
    milestone_index: int
    candidate_id: str
    reason: str


@dataclass(frozen=True)
class CandidateRegistry:
    indicators: tuple[dict, ...]
    conflicts: tuple[CandidateRegistryConflict, ...]


def build_candidate_registry(milestones):
    """Return one first-seen definition per candidate id and any conflicting reuse."""
    indicators = []
    conflicts = []
    definitions = {}
    for index, milestone in enumerate(milestones):
        if not isinstance(milestone, dict):
            continue
        candidate = milestone.get("candidate_indicator")
        if not isinstance(candidate, dict):
            continue
        candidate_id = candidate.get("id")
        if not isinstance(candidate_id, str) or not candidate_id:
            continue
        if candidate_id not in definitions:
            definition = dict(candidate)
            definitions[candidate_id] = definition
            indicators.append(definition)
        elif candidate != definitions[candidate_id]:
            conflicts.append(CandidateRegistryConflict(
                index,
                str(candidate_id),
                "conflicts with its earlier definition",
            ))
    return CandidateRegistry(tuple(indicators), tuple(conflicts))
