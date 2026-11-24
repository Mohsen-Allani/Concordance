"""Exécution du pipeline en tâche de fond et suivi de progression.

Un dépôt (BF2) crée un « job » identifié par un UUID ; le pipeline s'exécute
hors du cycle requête/réponse (BackgroundTasks, conformément à la conception
v1) et publie son avancement dans un registre en mémoire que l'interface
interroge par sondage. Le registre n'est pas persistant : la vérité durable
est en base (table analyse), le job n'est qu'un état d'exécution.
"""

import threading
import traceback
import uuid
from datetime import datetime

from concordance import pipeline

_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()

# Libellés des cinq étapes affichées (regroupement L0→L9 côté interface)
ETAPES = [
    "Lecture du document",          # L0–L2
    "Identification des pages",     # L3–L4
    "Extraction des données",       # L5
    "Contrôle et validation",       # L6–L7
    "Comparaison des documents",    # L8–L9
]

_client = None
_schemas = None


def _resources():
    """Client Gemini et schémas chargés une fois, réutilisés par tous les jobs."""
    global _client, _schemas
    if _client is None:
        _client = pipeline.make_client()
    if _schemas is None:
        _schemas = pipeline.load_schemas()
    return _client, _schemas


def create(nom_fichier: str, nb_octets: int) -> str:
    job_id = uuid.uuid4().hex
    with _LOCK:
        _JOBS[job_id] = {
            "id": job_id, "fichier": nom_fichier, "octets": nb_octets,
            "statut": "en cours", "etape": 0, "detail": "En file d'attente…",
            "id_analyse": None, "erreur": None,
            "debut": datetime.now().isoformat(timespec="seconds"),
        }
    return job_id


def get(job_id: str) -> dict | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        return dict(job) if job else None


def _set(job_id: str, **champs):
    with _LOCK:
        if job_id in _JOBS:
            _JOBS[job_id].update(champs)


def run(job_id: str, pdf_path, id_utilisateur: int):
    """Corps de la tâche de fond : le pipeline entier, du PDF à la base."""
    def progress(etape: int, detail: str):
        _set(job_id, etape=etape, detail=detail)

    try:
        client, schemas = _resources()
        summary = pipeline.process_pdf(client, pdf_path, schemas,
                              progress=progress, id_utilisateur=id_utilisateur)
        _set(job_id, statut="terminé", etape=5,
             detail="Analyse terminée", id_analyse=summary.get("id_analyse"),
             resume={"status": summary.get("status"),
                     "pages": summary.get("pages"),
                     "comparaison": summary.get("comparaison"),
                     "errors": summary.get("errors")})
    except Exception as exc:
        traceback.print_exc()
        _set(job_id, statut="erreur", erreur=str(exc),
             detail="Le traitement a échoué")
