"""Écriture d'une analyse complète en base (L9).

Une seule transaction par analyse : soit tout est enregistré, soit rien.
Les fichiers JSON de outputs/ restent des artefacts de débogage ; la base
devient la source de vérité pour l'historique (BF11).
"""

from datetime import date
from decimal import Decimal, InvalidOperation

from .models import Analyse, Document, LigneProduit, Rapport, Resultat
from .session import new_session


def to_decimal(v):
    """Les documents corrigés portent des Decimal sérialisés en chaînes."""
    if v is None or isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except InvalidOperation:
        return None


def save_analysis(summary: dict, doc_details: list[dict],
                  comparison: dict | None, statut: str,
                  id_utilisateur: int | None = None) -> int:
    """Enregistre l'analyse et renvoie son id.

    summary       : dict produit par process_pdf
    doc_details   : par document : type, est_scanne, extraction_brute (L5),
                    validation (rapport L7 sérialisé), document (corrigé, L7)
    comparison    : sortie complète de L8 (ou None)
    id_utilisateur: auteur de l'analyse (BF1) — None depuis la ligne de commande
    """
    with new_session() as session, session.begin():
        analyse = Analyse(
            nom_fichier=summary["pdf"],
            statut=statut,
            id_utilisateur=id_utilisateur,
            nb_pages=summary.get("pages"),
            erreurs=summary.get("errors") or None,
            comparaison=comparison,
        )

        scores = []
        for d in doc_details:
            corrected = d.get("document") or {}
            validation = d.get("validation") or {}
            fournisseur = (corrected.get("fournisseur") or {}).get("nom")
            client = (corrected.get("client") or {}).get("nom")
            doc = Document(
                type_document=d["type"],
                numero=corrected.get("numero"),
                date_document=to_date(corrected.get("date")),
                fournisseur=fournisseur,
                client=client,
                devise=corrected.get("devise"),
                est_scanne=d.get("est_scanne"),
                verdict=validation.get("verdict"),
                score_confiance=validation.get("confidence"),
                extraction_brute=d.get("extraction_brute"),
                validation=validation,
            )
            if validation.get("confidence") is not None:
                scores.append(validation["confidence"])
            for i, l in enumerate(corrected.get("lignes") or [], start=1):
                doc.lignes.append(LigneProduit(
                    position=i,
                    reference=l.get("reference"),
                    designation=l.get("designation"),
                    unite=l.get("unite"),
                    quantite=to_decimal(l.get("quantite")),
                    prix_unitaire_ht=to_decimal(l.get("prixUnitaireHT")),
                    taux_remise=to_decimal(l.get("tauxRemise")),
                    montant_ht=to_decimal(l.get("montantHT")),
                ))
            analyse.documents.append(doc)

        if scores:
            analyse.score_confiance = min(scores)

        if comparison:
            for p in comparison.get("produits", []):
                analyse.resultats.append(Resultat(
                    cle_produit=p.get("cle"),
                    reference=p.get("reference"),
                    designation=p.get("designation"),
                    statut=p.get("statut") or "non comparable",
                    detail={"paires": p.get("paires"),
                            "origines": p.get("origines")},
                ))

        if summary.get("rapport"):
            t = (comparison or {}).get("totaux") or {}
            analyse.rapport = Rapport(
                chemin_fichier=summary["rapport"],
                nb_conformes=t.get("conformes"),
                nb_ecarts=t.get("ecarts"),
                nb_ambigus=t.get("ambigus"),
            )

        session.add(analyse)
        session.flush()
        return analyse.id_analyse


def to_date(v):
    """Le document corrigé porte des dates ISO (chaînes) ou des objets date."""
    if v is None or hasattr(v, "isoformat") and not isinstance(v, str):
        return v
    try:
        return date.fromisoformat(str(v))
    except ValueError:
        return None
