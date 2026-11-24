"""Point d'entrée de l'application web.

    concordance serve --reload
    (ou : uvicorn concordance.webapp.main:app --reload)

Sert l'API sous /api et l'interface (fichiers statiques) à la racine.
Même origine pour les deux : aucun CORS à configurer en v1, et le jeton ne
transite jamais vers un autre domaine (BNF6).
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import analyses, auth

STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Concordance — contrôle des documents fournisseurs",
              docs_url="/api/docs", openapi_url="/api/openapi.json")

app.include_router(auth.router)
app.include_router(analyses.router)


@app.get("/api/health", tags=["health"])
def health():
    """Sonde de disponibilité (Docker, supervision). Ne touche pas la base."""
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
