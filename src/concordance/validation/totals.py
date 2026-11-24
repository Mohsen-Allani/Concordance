"""Solveur du bloc des totaux.

Cinq champs sont liés par des égalités comptables. Chaque champ reçoit des
valeurs candidates : celle qui a été lue, plus celles que les équations
permettent de déduire des autres. Toutes les combinaisons sont évaluées, et la
meilleure est celle qui satisfait le plus de relations en modifiant le moins la
lecture d'origine — « le moins » étant mesuré en proportion de la magnitude du
document, non en unités monétaires absolues.

L'ambiguïté est réservée au doute réel : une reconstruction concurrente ne
compte que si elle égale la meilleure sur les trois critères de classement, et
seuls les champs absents du document peuvent diverger. Un champ effectivement
lu constitue une preuve directe : aucune combinaison ne peut le remettre en
cause.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from itertools import product

from .tolerance import q3, quality, ratio

CORE = ("totalHT", "netHT", "remiseTotale", "tauxTVA", "montantTVA")

QUALITY_MARGIN = Decimal("0.02")    # en deçà, deux reconstructions sont de qualité équivalente
COST_MARGIN = Decimal("0.05")       # en deçà, deux reconstructions coûtent autant


@dataclass
class SolverResult:
    best: dict = field(default_factory=dict)
    read: dict = field(default_factory=dict)
    satisfied: int = 0
    applicable: int = 0
    quality: Decimal = Decimal(0)
    edit_cost: Decimal = Decimal(0)     # part de la magnitude du document modifiée
    ambiguous: bool = False
    alternatives: list = field(default_factory=list)
    scale: Decimal = Decimal(0)
    reconstructed: tuple = ()           # champs absents du document, donc devinés


def document_scale(totals, sums):
    """Magnitude de référence du document : sert d'échelle à tout ce qui est relatif."""
    values = [sums.gross, sums.net,
              totals.get("totalHT"), totals.get("netHT"), totals.get("totalTTC")]
    values = [abs(v) for v in values if v is not None]
    return max(values) if values else Decimal(0)


def _candidates(read, sums, rate):
    """Valeurs plausibles par champ : la lecture + toutes les déductions possibles."""
    cand = {k: [] for k in CORE}

    def add(k, v):
        if v is None:
            return
        v = q3(v)
        if v < 0 or v in cand[k]:
            return
        cand[k].append(v)

    for k in CORE:
        add(k, read[k])

    add("totalHT", sums.gross)
    if None not in (read["netHT"], read["remiseTotale"]):
        add("totalHT", read["netHT"] + read["remiseTotale"])

    add("netHT", sums.net)
    if None not in (read["totalHT"], read["remiseTotale"]):
        add("netHT", read["totalHT"] - read["remiseTotale"])
    if read["tauxTVA"] not in (None, 0) and read["montantTVA"] is not None:
        add("netHT", read["montantTVA"] / (read["tauxTVA"] / 100))

    add("remiseTotale", Decimal(0))
    if None not in (read["totalHT"], read["netHT"]):
        add("remiseTotale", read["totalHT"] - read["netHT"])
    if None not in (sums.gross, sums.net):
        add("remiseTotale", sums.gross - sums.net)
    if rate is not None and sums.gross is not None:
        add("remiseTotale", sums.gross * rate / 100)

    if read["netHT"] not in (None, 0) and read["montantTVA"] is not None:
        add("tauxTVA", read["montantTVA"] / read["netHT"] * 100)
    if sums.net not in (None, 0) and read["montantTVA"] is not None:
        add("tauxTVA", read["montantTVA"] / sums.net * 100)

    if None not in (read["netHT"], read["tauxTVA"]):
        add("montantTVA", read["netHT"] * read["tauxTVA"] / 100)
    if sums.net is not None and read["tauxTVA"] is not None:
        add("montantTVA", sums.net * read["tauxTVA"] / 100)

    for k in CORE:
        if not cand[k]:
            cand[k] = [read[k]]
    return cand


def _score(a, sums, rate, tol):
    """Nombre de relations satisfaites et qualité moyenne, tolérances propagées."""
    satisfied = applicable = 0
    total_quality = Decimal(0)

    def test(lhs, rhs, allowed):
        nonlocal satisfied, applicable, total_quality
        if lhs is None or rhs is None:
            return
        applicable += 1
        r = ratio(lhs, rhs, allowed)
        total_quality += quality(r)
        if r <= 1:
            satisfied += 1

    tH, nH, rem = a["totalHT"], a["netHT"], a["remiseTotale"]
    tva, mtva = a["tauxTVA"], a["montantTVA"]

    if sums.gross is not None:
        test(tH, sums.gross, tol.terms(sums.quantity + 1, tH))
    if sums.net is not None:
        test(nH, sums.net, tol.sum_of(sums.count, nH))
    if None not in (tH, rem):
        test(tH - rem, nH, tol.terms(3, nH))
    if None not in (nH, tva):
        test(nH * tva / 100, mtva,
             tol.terms(tva / 100 + 1, mtva) + tol.rate_slack(nH, tva))
    if rate is not None and sums.gross is not None:
        test(rem, sums.gross * rate / 100,
             tol.terms(sums.quantity + 1, rem) + tol.rate_slack(sums.gross, rate))

    mean = total_quality / applicable if applicable else Decimal(0)
    return satisfied, applicable, mean


def _edit_cost(assignment, read, scale, tol):
    """Coût d'une reconstruction : somme des écarts à la lecture, rapportée à
    la magnitude du document."""
    cost = Decimal(0)
    base = scale if scale else tol.quantum
    for k in CORE:
        rv, av = read.get(k), assignment.get(k)
        if rv is None or av is None or k == "tauxTVA":
            continue
        cost += abs(av - rv)
    return cost / base


def reconcile_totals(totals, sums, rate, tol):
    """Reconstruit le bloc des totaux et signale une ambiguïté matérielle."""
    read = {k: totals.get(k) for k in CORE}
    scale = document_scale(totals, sums)
    cand = _candidates(read, sums, rate)

    scored = []
    for combo in product(*(cand[k] for k in CORE)):
        a = dict(zip(CORE, combo))
        satisfied, applicable, mean = _score(a, sums, rate, tol)
        cost = _edit_cost(a, read, scale, tol)
        scored.append((satisfied, mean, -cost, a, applicable))

    scored.sort(key=lambda t: (t[0], t[1], t[2]), reverse=True)
    best_sat, best_quality, best_cost, best, applicable = scored[0]

    material = tol.material(scale)
    reconstructed = tuple(k for k in CORE if read.get(k) is None)

    ambiguous, alternatives = False, []
    for satisfied, mean, cost, a, _ in scored[1:]:
        if satisfied < best_sat:
            break
        if best_quality - mean > QUALITY_MARGIN:
            continue
        if best_cost - cost > COST_MARGIN:
            continue
        diverging = {k: (best[k], a[k]) for k in reconstructed
                     if None not in (best[k], a[k]) and abs(best[k] - a[k]) > material}
        if not diverging:
            continue
        ambiguous = True
        if len(alternatives) < 3:
            alternatives.append({
                "assignation": {k: str(a[k]) for k in CORE if a[k] is not None},
                "relations_satisfaites": satisfied,
                "qualité": str(q3(mean)),
                "coût_relatif": str(q3(-cost)),
                "champs_divergents": {k: [str(v[0]), str(v[1])] for k, v in diverging.items()},
            })

    return SolverResult(best=best, read=read, satisfied=best_sat, applicable=applicable,
                        quality=best_quality, edit_cost=-best_cost, ambiguous=ambiguous,
                        alternatives=alternatives, scale=scale, reconstructed=reconstructed)
