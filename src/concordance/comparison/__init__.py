"""L8 — moteur de rapprochement et de comparaison des documents commerciaux."""

from decimal import Decimal

from .engine import compare_analysis
from .overrides import OverrideError
from .semantic import SemanticGate

__all__ = ["compare_analysis", "comparison_to_dict", "SemanticGate",
           "OverrideError"]


def _plain(o):
    if isinstance(o, dict):
        return {k: _plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set, frozenset)):
        return [_plain(x) for x in o]
    if isinstance(o, Decimal):
        return str(o)
    if hasattr(o, "isoformat"):
        return o.isoformat()
    return o


def comparison_to_dict(result):
    return _plain(result)
