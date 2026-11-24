"""Révision humaine (BF9) côté web — corrections de valeurs et rapprochements.

Deux canaux, un seul principe : les révisions sont des contraintes, jamais des
résultats. Rien n'est retouché à la main dans la sortie ; la chaîne
déterministe L6→L8 est rejouée en entier sous ces contraintes (BNF1).

Format du corps PATCH /api/analyses/{id}/revisions :

    {
      "corrections":     {"BL": {"3": {"quantite": "60"}}},
      "rapprochements":  {"BC↔BL": {"affectations": {"0": [2, 4]},
                                    "detachees": [5]}}
    }

- corrections    : par type de document, par index de ligne d'origine, champs
                   réécrits comme CHAÎNES BRUTES (mêmes règles que L5) — la
                   normalisation (L6) et le solveur (L7) repassent derrière.
                   Elles s'appliquent à l'extraction brute archivée, ce qui
                   rend chaque rejeu identique à documents et révisions égaux.
- rapprochements : format de comparison/overrides.py, inchangé.

Le corps est l'état COMPLET des révisions de l'analyse (pas un delta) : il est
archivé tel quel dans analyse.revisions comme piste d'audit.
"""

import copy
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import HTTPException

from concordance import config
from concordance.comparison import OverrideError, SemanticGate, compare_analysis, comparison_to_dict
from concordance.db import new_session
from concordance.db.models import Analyse, Document, LigneProduit, Rapport, Resultat
from concordance.db.persistence import to_date, to_decimal
from concordance.reporting import generate_report
from concordance.stages.normalization import normalize_document
from concordance.validation import report_to_dict, validate_document

CHAMPS_CORRIGEABLES = {"reference", "designation", "unite", "quantite",
                       "prixUnitaireHT", "tauxRemise", "montantHT"}

_ENTIER = re.compile(r"^\d+$")
_LIBELLES = {"quantite": "quantité", "prixUnitaireHT": "prix unitaire HT",
             "tauxRemise": "remise", "montantHT": "montant HT"}


def _valider_valeur(champ: str, valeur, i: int):
    """Refuse toute valeur non conforme au schéma AVANT de toucher aux données.

    Une valeur vide efface le champ (comportement existant) ; une valeur non
    vide doit être valide pour son type — sinon 422 avec un message clair,
    jamais une erreur interne."""
    if valeur is None:
        return
    s = str(valeur).strip()
    if not s:
        return
    lib = _LIBELLES.get(champ, champ)
    if champ == "quantite":
        if not _ENTIER.match(s):
            raise HTTPException(422, f"ligne {i} : quantité invalide « {s} » "
                                     f"— entier positif attendu")
        return
    if champ in ("prixUnitaireHT", "montantHT", "tauxRemise"):
        num = s.replace("\u00a0", "").replace(" ", "").replace(",", ".")
        try:
            d = Decimal(num)
        except InvalidOperation:
            raise HTTPException(422, f"ligne {i} : {lib} invalide « {s} » "
                                     f"— valeur numérique attendue")
        if d < 0:
            raise HTTPException(422, f"ligne {i} : {lib} négatif refusé « {s} »")
        if champ == "tauxRemise" and d > 100:
            raise HTTPException(422, f"ligne {i} : remise « {s} » hors bornes "
                                     f"(0 à 100)")


def _appliquer_corrections(raw: dict, corr: dict) -> dict:
    """Réécrit les champs corrigés dans l'extraction brute (copie) et renvoie
    {index -> {champ -> valeur d'origine}} pour la piste d'audit ligne."""
    origines = {}
    lignes = raw.get("lignes") or []
    for idx, champs in corr.items():
        try:
            i = int(idx)
        except (TypeError, ValueError):
            raise HTTPException(422, f"index de ligne invalide « {idx} »")
        if not 0 <= i < len(lignes):
            raise HTTPException(422, f"la ligne {i} n'existe pas")
        if not isinstance(champs, dict):
            raise HTTPException(422, f"correction de la ligne {i} : objet attendu")
        for champ, valeur in champs.items():
            if champ not in CHAMPS_CORRIGEABLES:
                raise HTTPException(422, f"champ non corrigeable « {champ} »")
            _valider_valeur(champ, valeur, i)
            origines.setdefault(i, {})[champ] = lignes[i].get(champ)
            valeur = (str(valeur).strip() if valeur is not None else "")
            lignes[i][champ] = valeur or None
    return origines


def _reconstruire_lignes(doc: Document, corrected: dict, origines: dict):
    """Les lignes persistées reflètent le document corrigé courant ; la valeur
    d'origine reste attachée à la ligne révisée (modèle LigneProduit)."""
    doc.lignes.clear()
    for i, l in enumerate(corrected.get("lignes") or []):
        doc.lignes.append(LigneProduit(
            position=i + 1,
            reference=l.get("reference"),
            designation=l.get("designation"),
            unite=l.get("unite"),
            quantite=to_decimal(l.get("quantite")),
            prix_unitaire_ht=to_decimal(l.get("prixUnitaireHT")),
            taux_remise=to_decimal(l.get("tauxRemise")),
            montant_ht=to_decimal(l.get("montantHT")),
            corrige=i in origines,
            valeurs_origine=origines.get(i) or None,
        ))


def _regenerer_rapport(analyse: Analyse, comparison: dict):
    """Le rapport est une projection : on le rejoue comme revise.py le fait,
    sans jamais compromettre les données si le rendu échoue."""
    folder = config.OUTPUTS_DIR / Path(analyse.nom_fichier).stem
    summary_path = folder / "summary.json"
    if not summary_path.is_file():
        return
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["comparaison"] = comparison["totaux"]
    try:
        rapport = generate_report(summary, comparison, folder / "rapport.pdf")
        summary["rapport"] = config.portable(rapport)
        summary.pop("rapport_erreur", None)
    except Exception as exc:
        summary["rapport"], summary["rapport_erreur"] = None, str(exc)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                            encoding="utf-8")
    (folder / "comparison.json").write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")

    t = comparison["totaux"]
    if summary.get("rapport"):
        if analyse.rapport is None:
            analyse.rapport = Rapport(chemin_fichier=summary["rapport"])
        analyse.rapport.chemin_fichier = summary["rapport"]
        analyse.rapport.nb_conformes = t.get("conformes")
        analyse.rapport.nb_ecarts = t.get("ecarts")
        analyse.rapport.nb_ambigus = t.get("ambigus")


def apply_revisions(id_analyse: int, revisions: dict) -> dict:
    """Rejoue L6→L9 sous révisions et persiste le nouvel état. Renvoie la
    comparaison recalculée (même forme que analyse.comparaison)."""
    corrections = revisions.get("corrections") or {}
    rapprochements = revisions.get("rapprochements") or None

    with new_session() as session, session.begin():
        analyse = session.get(Analyse, id_analyse)
        if analyse is None:
            raise HTTPException(404, "Analyse introuvable")
        if not analyse.documents:
            raise HTTPException(409, "Analyse sans documents : rien à réviser")

        validated, scores = {}, []
        for doc in analyse.documents:
            corr = corrections.get(doc.type_document) or {}
            raw = copy.deepcopy(doc.extraction_brute) or {}
            origines = _appliquer_corrections(raw, corr) if corr else {}

            # L6 + L7 rejoués sur l'extraction (corrigée ou non) : le solveur
            # et le score restent cohérents avec les valeurs révisées.
            report = validate_document(normalize_document(raw), doc.type_document)
            report_dict = report_to_dict(report)
            corrected = report_dict["corrected_document"]

            doc.validation = report_dict
            doc.verdict = report.verdict
            doc.score_confiance = report.confidence
            doc.numero = corrected.get("numero")
            doc.date_document = to_date(corrected.get("date"))
            doc.fournisseur = (corrected.get("fournisseur") or {}).get("nom")
            doc.client = (corrected.get("client") or {}).get("nom")
            doc.devise = corrected.get("devise")
            _reconstruire_lignes(doc, corrected, origines)

            validated[doc.type_document] = report.corrected_document
            if report.confidence is not None:
                scores.append(report.confidence)

        if len(validated) < 2:
            raise HTTPException(409, "Moins de deux documents : comparaison impossible")

        gate = SemanticGate.load() if config.SEMANTIC_VETO else None
        try:
            comparison = comparison_to_dict(
                compare_analysis(validated, gate, overrides=rapprochements))
        except OverrideError as exc:
            raise HTTPException(422, f"Révision refusée : {exc}")

        analyse.comparaison = comparison
        analyse.revisions = revisions or None
        if scores:
            analyse.score_confiance = min(scores)

        analyse.resultats.clear()
        for p in comparison.get("produits", []):
            analyse.resultats.append(Resultat(
                cle_produit=p.get("cle"),
                reference=p.get("reference"),
                designation=p.get("designation"),
                statut=p.get("statut") or "non comparable",
                detail={"paires": p.get("paires"), "origines": p.get("origines")},
            ))

        verdicts = {d.verdict for d in analyse.documents}
        en_attente = bool(comparison.get("ambiguites")) or "review" in verdicts
        analyse.statut = "en attente de révision" if en_attente else "terminé"

        _regenerer_rapport(analyse, comparison)
        return comparison
