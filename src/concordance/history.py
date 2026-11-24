"""Consultation de l'historique des analyses (BF11) en ligne de commande.

    concordance history           liste toutes les analyses
    concordance history 3         détail de l'analyse n°3
"""

from sqlalchemy import select

from concordance.db import Analyse, new_session


def list_analyses(session):
    rows = session.scalars(select(Analyse).order_by(Analyse.id_analyse)).all()
    if not rows:
        print("Aucune analyse enregistrée.")
        return
    print(f"{'id':>3}  {'date':<16}  {'statut':<24}  {'conf':>5}  fichier")
    for a in rows:
        conf = f"{a.score_confiance:.2f}" if a.score_confiance is not None else "  —"
        print(f"{a.id_analyse:>3}  {a.date_analyse:%Y-%m-%d %H:%M}  "
              f"{a.statut:<24}  {conf:>5}  {a.nom_fichier}")


def show_analysis(session, id_analyse: int):
    a = session.get(Analyse, id_analyse)
    if a is None:
        print(f"Analyse {id_analyse} introuvable.")
        return
    print(f"Analyse {a.id_analyse} — {a.nom_fichier}")
    print(f"  date : {a.date_analyse:%Y-%m-%d %H:%M}   statut : {a.statut}   "
          f"pages : {a.nb_pages}")
    for d in a.documents:
        print(f"  {d.type_document}  n°{d.numero or '—'}  du {d.date_document or '—'}  "
              f"fournisseur : {d.fournisseur or '—'}  "
              f"verdict : {d.verdict} ({d.score_confiance})  "
              f"[{len(d.lignes)} ligne(s)]")
    if a.resultats:
        print("  Comparaison :")
        for r in a.resultats:
            print(f"    {r.statut:<15} {r.reference or '—':<15} {r.designation or ''}")
    if a.rapport:
        print(f"  Rapport : {a.rapport.chemin_fichier}  "
              f"({a.rapport.nb_conformes} conformes, {a.rapport.nb_ecarts} écarts, "
              f"{a.rapport.nb_ambigus} ambigus)")
    if a.erreurs:
        for e in a.erreurs:
            print(f"  ! {e}")


def main(id_analyse: int | None = None) -> None:
    with new_session() as session:
        if id_analyse is not None:
            show_analysis(session, id_analyse)
        else:
            list_analyses(session)
