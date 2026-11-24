"""Concordance : contrôle automatique de cohérence BC / BL / Facture.

Pipeline L0 -> L9 (voir docs/architecture.md) :

    stages/      L0 à L6   ingestion, détection natif/scanné, prétraitement,
                           classification, regroupement, extraction, normalisation
    validation/  L7        solveur arithmétique, certification, score de confiance
    comparison/  L8        rapprochement trois voies ancré sur le bon de commande
    reporting/   L9        rapport PDF
    db/          L9        persistance PostgreSQL (SQLAlchemy 2.0)
    webapp/                API FastAPI et interface web
"""

__version__ = "1.0.0"
