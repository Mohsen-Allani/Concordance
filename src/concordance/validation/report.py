"""Structures de sortie de L7 et sérialisation JSON."""

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class Check:
    name: str
    status: str            # ok | recovered | confirmed | warning | error
    message: str


@dataclass
class ValidationReport:
    verdict: str           # ok | corrected | review
    confidence: float
    components: dict = field(default_factory=dict)
    checks: list = field(default_factory=list)
    recovered: dict = field(default_factory=dict)
    suggestions: dict = field(default_factory=dict)
    corrected_document: dict = field(default_factory=dict)
    certificate: dict = field(default_factory=dict)
    solver: dict = field(default_factory=dict)


def _plain(o):
    if isinstance(o, dict):
        return {k: _plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_plain(x) for x in o]
    if isinstance(o, Decimal):
        return str(o)
    if hasattr(o, "isoformat"):
        return o.isoformat()
    return o


def report_to_dict(r):
    return {
        "verdict": r.verdict,
        "confidence": r.confidence,
        "components": _plain(r.components),
        "recovered": _plain(r.recovered),
        "suggestions": _plain(r.suggestions),
        "checks": [{"name": c.name, "status": c.status, "message": c.message}
                   for c in r.checks],
        "solver": _plain(r.solver),
        "certificate": _plain(r.certificate),
        "corrected_document": _plain(r.corrected_document),
    }
