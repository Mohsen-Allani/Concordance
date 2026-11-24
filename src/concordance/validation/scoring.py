"""Score de confiance.

Le modèle ne fournit plus d'auto-évaluation : le score est intégralement
reconstruit à partir de faits mesurables. Quatre composantes, toutes exprimées
sur [0, 1] et toutes relatives :

  lignes      qualité moyenne des relations de ligne (écart rapporté à sa tolérance)
  totaux      qualité moyenne des relations du bloc des totaux
  complétude  proportion des informations attendues effectivement extraites
  stabilité   1 - part de la magnitude du document que le solveur a dû corriger

Une composante non applicable (un BL n'a pas de totaux) est retirée du calcul
et son poids redistribué, plutôt que comptée comme un échec.
"""

from decimal import Decimal

WEIGHTS = {
    "lignes": Decimal("0.35"),
    "totaux": Decimal("0.30"),
    "complétude": Decimal("0.20"),
    "stabilité": Decimal("0.15"),
}

AMBIGUITY_PENALTY = Decimal("0.15")   # doute résiduel du solveur : abaisse le score, ne bloque pas

_COMMON = ["numero", "date", "fournisseur.nom", "client.nom", "lignes"]
_BY_TYPE = {
    "BC": ["totaux.totalHT|totaux.netHT"],
    "BL": [],
    "FACTURE": ["totaux.totalHT|totaux.netHT", "totaux.totalTTC|totaux.netAPayer"],
}


def _get(doc, path):
    cur = doc
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _present(doc, spec):
    return any(_get(doc, p) not in (None, "", [], {}) for p in spec.split("|"))


def expected_fields(doc_type):
    key = (doc_type or "").upper()
    key = "FACTURE" if key.startswith("FACT") else key
    return _COMMON + _BY_TYPE.get(key, _BY_TYPE["FACTURE"])


def completeness(doc, doc_type, sums):
    """Part des informations attendues réellement présentes, en-tête et lignes."""
    specs = expected_fields(doc_type)
    header = Decimal(sum(1 for s in specs if _present(doc, s))) / len(specs)
    if sums.count == 0:
        return header
    return header * Decimal("0.6") + sums.filled * Decimal("0.4")


def _mean(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    return sum(values) / len(values)


def confidence(doc, doc_type, sums, certificate, solver):
    """Retourne (score, composantes) — les composantes sont conservées dans le
    rapport pour rendre le score explicable et calibrable."""
    components = {
        "lignes": _mean(certificate.get("notes_lignes")),
        "totaux": _mean(certificate.get("notes_totaux")),
        "complétude": completeness(doc, doc_type, sums),
        "stabilité": (max(Decimal(0), Decimal(1) - min(Decimal(1), solver.edit_cost))
                      if solver is not None else None),
    }

    usable = {k: v for k, v in components.items() if v is not None}
    if not usable:
        return 0.0, {}
    total_weight = sum(WEIGHTS[k] for k in usable)
    score = sum(WEIGHTS[k] * v for k, v in usable.items()) / total_weight
    score = max(Decimal(0), min(Decimal(1), score))

    detail = {k: float(round(v, 3)) for k, v in usable.items()}
    detail["poids"] = {k: float(WEIGHTS[k] / total_weight) for k in usable}

    if solver is not None and solver.ambiguous:
        score = max(Decimal(0), score - AMBIGUITY_PENALTY)
        detail["pénalité_ambiguïté"] = float(AMBIGUITY_PENALTY)

    return float(round(score, 3)), detail
