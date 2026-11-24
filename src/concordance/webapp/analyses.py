"""Routes /api/analyses et /api/stats — le cœur applicatif de l'interface.

BF2  POST   /api/analyses                 dépôt du PDF, lancement en tâche de fond
     GET    /api/analyses/jobs/{job}      progression du traitement
BF11 GET    /api/analyses                 historique
     GET    /api/analyses/{id}            détail (documents + comparaison L8)
BF9  PATCH  /api/analyses/{id}/revisions  révision : rejeu L6→L9 sous contraintes
BF10 GET    /api/analyses/{id}/rapport    rapport PDF
     GET    /api/stats                    tableau de bord
"""

import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select

from concordance import config
from concordance.db import new_session
from concordance.db.models import Analyse, Utilisateur

from . import jobs
from .auth import current_user
from .revisions import apply_revisions

router = APIRouter(prefix="/api", tags=["analyses"])

TAILLE_MAX = 20 * 1024 * 1024      # 20 Mo, comme annoncé dans l'interface

ECARTS = ("écart", "manquant", "en_trop")


def _safe_stem(nom: str) -> str:
    stem = Path(nom).stem
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_") or "document"
    return stem[:80]


# ---------------------------------------------------------------- dépôt (BF2)

@router.post("/analyses")
async def deposer(background: BackgroundTasks,
                  fichier: UploadFile = File(...),
                  user: Utilisateur = Depends(current_user)):
    if (fichier.content_type or "").lower() not in ("application/pdf",
                                                    "application/x-pdf"):
        raise HTTPException(422, "Seul un document PDF est accepté")
    contenu = await fichier.read()
    if len(contenu) > TAILLE_MAX:
        raise HTTPException(413, "Fichier trop volumineux (20 Mo max.)")
    if not contenu.startswith(b"%PDF"):
        raise HTTPException(422, "Le fichier ne semble pas être un PDF valide")

    horodate = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"{_safe_stem(fichier.filename or 'document')}__{horodate}"
    config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = config.UPLOADS_DIR / f"{stem}.pdf"
    pdf_path.write_bytes(contenu)

    job_id = jobs.create(fichier.filename or pdf_path.name, len(contenu))
    background.add_task(jobs.run, job_id, pdf_path, user.id_utilisateur)
    return {"job": job_id, "fichier": fichier.filename}


@router.get("/analyses/jobs/{job_id}")
def progression(job_id: str, user: Utilisateur = Depends(current_user)):
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Traitement introuvable")
    return job


# --------------------------------------------------------- historique (BF11)

def _resume(a: Analyse) -> dict:
    t = (a.comparaison or {}).get("totaux") or {}
    return {
        "id": a.id_analyse,
        "fichier": Path(a.nom_fichier).name,
        "date": a.date_analyse.isoformat(timespec="minutes"),
        "statut": a.statut,
        "pages": a.nb_pages,
        "confiance": float(a.score_confiance) if a.score_confiance is not None else None,
        "documents": [d.type_document for d in a.documents],
        "totaux": t or None,
        "rapport": a.rapport is not None,
    }


@router.get("/analyses")
def historique(user: Utilisateur = Depends(current_user)):
    with new_session() as session:
        rows = session.scalars(
            select(Analyse).order_by(Analyse.date_analyse.desc())).all()
        return [_resume(a) for a in rows]


@router.get("/analyses/{id_analyse}")
def detail(id_analyse: int, user: Utilisateur = Depends(current_user)):
    with new_session() as session:
        a = session.get(Analyse, id_analyse)
        if a is None:
            raise HTTPException(404, "Analyse introuvable")
        documents = []
        for d in sorted(a.documents,
                        key=lambda x: {"BC": 0, "BL": 1, "Facture": 2}
                        .get(x.type_document, 3)):
            corrected = (d.validation or {}).get("corrected_document") or {}
            documents.append({
                "type": d.type_document,
                "numero": d.numero,
                "date": d.date_document.isoformat() if d.date_document else None,
                "devise": d.devise,
                "est_scanne": d.est_scanne,
                "verdict": d.verdict,
                "confiance": float(d.score_confiance)
                             if d.score_confiance is not None else None,
                "fournisseur": corrected.get("fournisseur"),
                "client": corrected.get("client"),
                "totaux": corrected.get("totaux"),
                "nb_lignes": len(d.lignes),
            })
        out = _resume(a)
        out.update({
            "erreurs": a.erreurs or [],
            "documents_detail": documents,
            "comparaison": a.comparaison,
            "revisions": a.revisions,
        })
        return out


# ------------------------------------------------------------ révision (BF9)

@router.patch("/analyses/{id_analyse}/revisions")
def reviser(id_analyse: int, revisions: dict,
            user: Utilisateur = Depends(current_user)):
    apply_revisions(id_analyse, revisions or {})
    return detail(id_analyse, user)


# ------------------------------------------------------------ rapport (BF10)

@router.get("/analyses/{id_analyse}/rapport")
def rapport(id_analyse: int, user: Utilisateur = Depends(current_user)):
    with new_session() as session:
        a = session.get(Analyse, id_analyse)
        if a is None or a.rapport is None:
            raise HTTPException(404, "Aucun rapport pour cette analyse")
        chemin = config.ROOT / a.rapport.chemin_fichier
        if not chemin.is_file():
            raise HTTPException(410, "Fichier du rapport introuvable sur le disque")
        nom = f"rapport_{Path(a.nom_fichier).stem}.pdf"
        return FileResponse(chemin, media_type="application/pdf", filename=nom)


# ------------------------------------------------------- tableau de bord

@router.get("/stats")
def stats(user: Utilisateur = Depends(current_user)):
    maintenant = datetime.now()
    debut_semaine = maintenant - timedelta(days=maintenant.weekday())
    debut_mois = maintenant.replace(day=1, hour=0, minute=0, second=0,
                                    microsecond=0)

    with new_session() as session:
        analyses = session.scalars(select(Analyse)).all()

        total = len(analyses)
        cette_semaine = sum(1 for a in analyses
                            if a.date_analyse.replace(tzinfo=None)
                            >= debut_semaine.replace(hour=0, minute=0,
                                                     second=0, microsecond=0))
        a_reviser = sum(1 for a in analyses
                        if a.statut == "en attente de révision")

        produits = conformes = 0
        ecarts_mois = ecarts_prix_mois = 0
        for a in analyses:
            t = (a.comparaison or {}).get("totaux") or {}
            produits += t.get("produits") or 0
            conformes += t.get("conformes") or 0
            if a.date_analyse.replace(tzinfo=None) >= debut_mois:
                for p in (a.comparaison or {}).get("produits") or []:
                    if p.get("statut") in ECARTS:
                        ecarts_mois += 1
                        for paire in (p.get("paires") or {}).values():
                            if any(ax.get("champ") == "prixUnitaireHT"
                                   and ax.get("statut") == "écart"
                                   for ax in paire.get("axes") or []):
                                ecarts_prix_mois += 1
                                break

        # Activité des 8 dernières semaines (semaine ISO)
        semaines = []
        for k in range(7, -1, -1):
            lundi = (debut_semaine - timedelta(weeks=k)).replace(
                hour=0, minute=0, second=0, microsecond=0)
            fin = lundi + timedelta(weeks=1)
            du_lot = [a for a in analyses
                      if lundi <= a.date_analyse.replace(tzinfo=None) < fin]
            avec_ecarts = sum(
                1 for a in du_lot
                if ((a.comparaison or {}).get("totaux") or {}).get("ecarts"))
            semaines.append({"label": f"S{lundi.isocalendar().week:02d}",
                             "analyses": len(du_lot),
                             "avec_ecarts": avec_ecarts})

        recentes = [_resume(a) for a in sorted(
            analyses, key=lambda x: x.date_analyse, reverse=True)[:5]]

    return {
        "total": total,
        "cette_semaine": cette_semaine,
        "a_reviser": a_reviser,
        "produits": produits,
        "conformes": conformes,
        "pct_conformes": round(100 * conformes / produits) if produits else None,
        "ecarts_mois": ecarts_mois,
        "ecarts_prix_mois": ecarts_prix_mois,
        "activite": semaines,
        "recentes": recentes,
    }
