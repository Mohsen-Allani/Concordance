"""Échelles de tolérance.

Aucune tolérance n'est une constante monétaire : chaque écart admissible est
déduit (1) de la précision d'affichage réellement observée dans le document et
(2) de la magnitude des valeurs comparées. Un document au millime et un document
à l'unité n'obtiennent donc pas la même tolérance, et une ligne de 12 000 n'est
pas jugée avec la même marge qu'une ligne de 12.
"""

from collections import Counter
from decimal import Decimal

REL_FLOOR = Decimal("0.0005")     # part relative, absorbe l'échelle sur les gros montants
MATERIAL_REL = Decimal("0.01")    # écart jugé « matériel » (1 % de la magnitude du document)
MIN_QUANTUM = Decimal("0.001")
MAX_QUANTUM = Decimal("0.01")
DEFAULT_QUANTUM = Decimal("0.01")

_MONEY_LINE = ("prixUnitaireHT", "montantHT")
_MONEY_TOTAL = ("totalHT", "remiseTotale", "netHT", "montantTVA",
                "timbreFiscal", "totalTTC", "netAPayer")


def decimals(value):
    """Nombre de décimales réellement imprimées (conservé par Decimal(str))."""
    if not isinstance(value, Decimal):
        return None
    exp = value.as_tuple().exponent
    if not isinstance(exp, int):
        return None
    return -exp if exp < 0 else 0


def quantum_of(value, default=DEFAULT_QUANTUM):
    """Pas d'affichage d'une valeur isolée (ex. 5,25 -> 0.01)."""
    d = decimals(value)
    return default if d is None else Decimal(1).scaleb(-d)


def infer_quantum(doc):
    """Convention d'affichage du document = nombre de décimales le plus fréquent
    parmi ses valeurs monétaires."""
    counts = Counter()
    for line in doc.get("lignes") or []:
        for f in _MONEY_LINE:
            d = decimals(line.get(f))
            if d:
                counts[d] += 1
    totals = doc.get("totaux") or {}
    for f in _MONEY_TOTAL:
        d = decimals(totals.get(f))
        if d:
            counts[d] += 1
    if not counts:
        return DEFAULT_QUANTUM
    best = max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]
    return max(MIN_QUANTUM, min(MAX_QUANTUM, Decimal(1).scaleb(-best)))


class Tolerance:
    """Traduit une relation arithmétique en écart maximal admissible."""

    def __init__(self, quantum=DEFAULT_QUANTUM, rel=REL_FLOOR):
        self.quantum = quantum
        self.half = quantum / 2
        self.rel = rel

    @classmethod
    def infer(cls, doc):
        return cls(infer_quantum(doc))

    def terms(self, count, reference):
        """`count` valeurs arrondies interviennent dans la relation.
        Chacune peut dévier d'un demi-pas ; on ajoute un plancher relatif."""
        count = Decimal(count) if not isinstance(count, Decimal) else count
        ref = abs(reference) if reference is not None else Decimal(0)
        return max(count, Decimal(1)) * self.half + self.rel * ref

    def printed(self, reference):
        """Une valeur imprimée face à un calcul exact."""
        return self.terms(2, reference)

    def sum_of(self, n, reference):
        """n valeurs imprimées sommées, face à un total imprimé."""
        return self.terms(Decimal(n) + 1, reference)

    def scaled(self, factor, reference):
        """Une valeur unitaire imprimée multipliée par `factor` (l'arrondi du
        prix unitaire est multiplié par la quantité), face à une valeur imprimée."""
        return self.terms(abs(factor) + 1, reference)

    def rate_slack(self, base, rate):
        """Marge due à l'arrondi d'un taux imprimé (5 % peut valoir 5,4 %)."""
        if base is None or rate is None:
            return Decimal(0)
        return abs(base) * quantum_of(rate, Decimal(1)) / 200

    def material(self, scale):
        """Seuil au-delà duquel deux reconstructions concurrentes diffèrent
        vraiment, plutôt que par artefact d'arrondi."""
        return max(self.quantum, MATERIAL_REL * abs(scale or 0))


def close(a, b, tol):
    if a is None or b is None:
        return None
    return abs(a - b) <= tol


def ratio(a, b, tol):
    """Écart exprimé en multiples de la tolérance : <= 1 conforme, 3 = trois
    fois trop loin. C'est cette grandeur relative qui alimente le score."""
    if a is None or b is None or not tol:
        return None
    return abs(a - b) / tol


def quality(r):
    """Ratio -> note dans [0, 1], décroissance douce au-delà de la tolérance."""
    if r is None:
        return None
    excess = r - 1
    if excess <= 0:
        return Decimal(1)
    return Decimal(1) / (Decimal(1) + excess)


def q3(x):
    return None if x is None else Decimal(str(x)).quantize(Decimal("0.001"))
