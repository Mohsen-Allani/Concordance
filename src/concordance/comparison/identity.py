"""Contrôles d'en-tête entre documents.

Aucun de ces contrôles ne bloque la comparaison. Le PDF déposé regroupe des
pièces censées se rapporter au même achat : ces vérifications confirment cette
hypothèse ou signalent qu'elle est peut-être fausse, sans jamais interrompre le
traitement.

Un contrôle ne s'exécute que si l'information est présente des deux côtés. Une
référence croisée absente est le cas courant, pas une anomalie.
"""

from .canonical import normalize_designation, normalize_identifier
from .matching import similarity

SEUIL_NOM = "0.75"          # en deçà, deux raisons sociales sont jugées différentes

ORDRE_ATTENDU = ("BC", "BL", "Facture")


def _check(nom, statut, message):
    return {"nom": nom, "statut": statut, "message": message}


def _party(role, a, b, type_a, type_b):
    """Compare deux tiers : matricule fiscal s'il est connu des deux côtés,
    raison sociale sinon."""
    pa, pb = (a.get(role) or {}), (b.get(role) or {})
    ma = normalize_identifier(pa.get("matriculeFiscal"))
    mb = normalize_identifier(pb.get("matriculeFiscal"))
    if ma and mb:
        if ma == mb:
            return _check(role, "ok", f"matricule fiscal identique ({pa.get('matriculeFiscal')})")
        return _check(role, "warning",
                      f"matricules fiscaux différents entre {type_a} et {type_b} : "
                      f"{pa.get('matriculeFiscal')} / {pb.get('matriculeFiscal')}")

    na, nb = pa.get("nom"), pb.get("nom")
    if not na or not nb:
        return _check(role, "ignoré", f"{role} absent d'au moins un document")
    score = similarity(normalize_designation(na), normalize_designation(nb))
    if score >= float(SEUIL_NOM):
        return _check(role, "ok", f"raisons sociales concordantes ({score})")
    return _check(role, "warning",
                  f"raisons sociales différentes entre {type_a} et {type_b} : "
                  f"« {na} » / « {nb} »")


def _cross_reference(source, type_source, cible, type_cible, champ):
    """Référence croisée : contrôlée seulement si elle est présente des deux
    côtés, et jamais bloquante."""
    citee = normalize_identifier((source.get("referencesLiees") or {}).get(champ))
    reelle = normalize_identifier(cible.get("numero"))
    if not citee or not reelle:
        return _check(f"référence {type_cible} dans {type_source}", "ignoré",
                      "référence non présente des deux côtés")
    if citee == reelle:
        return _check(f"référence {type_cible} dans {type_source}", "ok",
                      f"{type_source} cite bien {cible.get('numero')}")
    return _check(f"référence {type_cible} dans {type_source}", "warning",
                  f"{type_source} cite {(source.get('referencesLiees') or {}).get(champ)} "
                  f"alors que le {type_cible} porte {cible.get('numero')}")


def _dates(docs):
    """Un BL ne peut pas précéder son BC, ni une facture son BL."""
    checks = []
    presents = [(t, docs[t].get("date")) for t in ORDRE_ATTENDU
                if t in docs and docs[t].get("date")]
    for (ta, da), (tb, db) in zip(presents, presents[1:]):
        if db < da:
            checks.append(_check("chronologie", "warning",
                                 f"chronologie inversée : {tb} ({db}) avant {ta} ({da})"))
        else:
            checks.append(_check("chronologie", "ok", f"{ta} ({da}) puis {tb} ({db})"))
    return checks


def check_identity(docs):
    """`docs` : {type -> document validé}. Retourne la liste des contrôles."""
    checks = []
    types = [t for t in ORDRE_ATTENDU if t in docs]
    for ta, tb in zip(types, types[1:]):
        for role in ("fournisseur", "client"):
            checks.append(_party(role, docs[ta], docs[tb], ta, tb))

    if "BC" in docs and "BL" in docs:
        checks.append(_cross_reference(docs["BL"], "BL", docs["BC"], "BC", "numeroBC"))
    if "BC" in docs and "Facture" in docs:
        checks.append(_cross_reference(docs["Facture"], "Facture", docs["BC"], "BC", "numeroBC"))
    if "BL" in docs and "Facture" in docs:
        checks.append(_cross_reference(docs["Facture"], "Facture", docs["BL"], "BL", "numeroBL"))

    checks.extend(_dates(docs))
    return checks
