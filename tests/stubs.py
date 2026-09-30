"""Shared helpers for offline test backends that answer discovery stages."""

from reviscope.discovery import BLIND_SPOT_PROMPT, requested_checks


def is_blind_spot(instruction: str) -> bool:
    return instruction.startswith(BLIND_SPOT_PROMPT)


def discovery_payload(instruction: str, findings: list) -> dict:
    """A DiscoveryResponse body whose coverage checks are all not_applicable, so it never marks a run partial."""
    return {"findings": findings, "search_incomplete": False,
            "checks": [{"check": name, "status": "not_applicable", "rationale": "Offline test stub."}
                       for name in requested_checks(instruction)]}
