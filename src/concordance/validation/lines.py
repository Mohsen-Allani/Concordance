"""Contrôle ligne à ligne.

Relation vérifiée : quantité x prixUnitaireHT x (1 - tauxRemise) = montantHT.
Quand aucune remise n'est étiquetée mais que les lignes s'écartent
systématiquement du produit brut, une remise implicite est déduite — à
condition que les lignes soient d'accord entre elles, l'accord étant jugé
avec l'incertitude d'arrondi propre à chaque ligne et non avec un seuil fixe.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from .report import Check
from .tolerance import q3, ratio


@dataclass
class LineSums:
    gross: Decimal = None          # Σ quantité x prix unitaire (None si incalculable)
    net: Decimal = None            # Σ montantHT (None si incalculable)
    quantity: Decimal = Decimal(0)  # Σ |quantité| : sert à propager l'arrondi des PU
    count: int = 0                 # nombre de lignes
    checked: int = 0               # lignes dont la relation a pu être testée
    unreconciled: int = 0          # lignes testées et fausses
    ratios: list = field(default_factory=list)
    filled: Decimal = Decimal(0)   # taux de remplissage moyen des cellules


def _median(xs):
    s = sorted(xs)
    n = len(s)
    if not n:
        return None
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def _rel_change(old, new, floor):
    scale = max(abs(old), abs(new), floor)
    return abs(new - old) / scale


def consensus_discount(lines, tol):
    """Taux de remise implicite commun aux lignes, ou None si elles divergent.

    Retourne (taux, observations, dispersion) où chaque observation est
    (index, taux impliqué, incertitude de ce taux)."""
    implied = []
    for i, ln in enumerate(lines, 1):
        q, pu, mt = ln.get("quantite"), ln.get("prixUnitaireHT"), ln.get("montantHT")
        if ln.get("tauxRemise") is not None or None in (q, pu, mt):
            continue
        gross = q * pu
        if gross <= 0:
            continue
        pct = (gross - mt) / gross * 100
        slack = tol.scaled(q, gross) / gross * 100
        implied.append((i, pct, slack))

    if not implied:
        return None, [], None

    pcts = [p for _, p, _ in implied]
    spread = max(pcts) - min(pcts)
    if all(abs(p) <= u for _, p, u in implied):
        return Decimal(0), implied, spread
    median = _median(pcts)
    if all(abs(p - median) <= u for _, p, u in implied):
        return median, implied, spread
    return None, implied, spread


def reconcile_lines(lines, rate, tol, monetary=True):
    """Teste chaque ligne et propose la correction la moins coûteuse.

    La correction retenue est celle qui demande le plus faible changement
    RELATIF de la valeur lue, sans préjuger du champ fautif."""
    checks = []
    sums = LineSums(count=len(lines))
    gross_sum, net_sum = Decimal(0), Decimal(0)
    gross_ok = net_ok = True
    cells, cells_filled = 0, 0

    for i, ln in enumerate(lines, 1):
        q, pu, mt = ln.get("quantite"), ln.get("prixUnitaireHT"), ln.get("montantHT")
        rem = ln.get("tauxRemise")

        for f in ("designation", "quantite"):
            cells += 1
            cells_filled += 1 if ln.get(f) not in (None, "", []) else 0
        if ln.get("reference") or ln.get("referencesDansDesignation"):
            cells_filled += 1
        cells += 1

        if q is None or pu is None:
            gross_ok = False
        else:
            gross_sum += q * pu
            sums.quantity += abs(q)
        if mt is None:
            net_ok = False
        else:
            net_sum += mt

        if None in (q, pu, mt):
            missing = [f for f, v in (("quantite", q), ("prixUnitaireHT", pu),
                                      ("montantHT", mt)) if v is None]
            if monetary or q is None:
                checks.append(Check(f"ligne {i}", "warning",
                                    f"non vérifiable, champ(s) absent(s) : {', '.join(missing)}"))
            continue

        gross = q * pu
        applied = rem if rem is not None else (rate if rate is not None else Decimal(0))
        expected = gross * (1 - applied / 100)
        allowed = tol.scaled(q, gross)
        if applied:
            allowed += tol.rate_slack(gross, rem if rem is not None else applied)

        r = ratio(expected, mt, allowed)
        sums.checked += 1
        sums.ratios.append(r)
        if r is not None and r <= 1:
            continue

        floor = tol.quantum
        cands = []
        if gross > 0:
            cands.append(("montantHT", expected, _rel_change(mt, expected, floor)))
        factor = 1 - applied / 100
        if pu and factor:
            v = mt / (pu * factor)
            cands.append(("quantite", v, _rel_change(q, v, Decimal(1))))
        if q and factor:
            v = mt / (q * factor)
            cands.append(("prixUnitaireHT", v, _rel_change(pu, v, floor)))

        if cands:
            cands.sort(key=lambda c: c[2])
            fld, val, cost = cands[0]
            checks.append(Check(
                f"ligne {i}", "warning",
                f"{q} x {pu} - {q3(applied)}% = {q3(expected)} ≠ {mt} "
                f"(écart {q3(r)}x la tolérance) ; correction la moins coûteuse "
                f"{fld} = {q3(val)} ({q3(cost * 100)}% de la valeur lue)"))
        else:
            checks.append(Check(f"ligne {i}", "error",
                                f"incohérente et non reconstructible ({q} x {pu} ≠ {mt})"))
        sums.unreconciled += 1

    sums.gross = gross_sum if gross_ok else None
    sums.net = net_sum if net_ok else None
    sums.filled = Decimal(cells_filled) / cells if cells else Decimal(0)
    return checks, sums
