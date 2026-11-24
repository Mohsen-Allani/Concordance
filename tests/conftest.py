"""Fixtures partagées.

Les variables d'environnement sont posées AVANT tout import de `concordance` :
les tests ne touchent jamais la base ni les clés de développement, même si un
fichier .env existe à la racine du projet (une variable déjà présente n'est
jamais écrasée par python-dotenv).
"""

import os
import shutil
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite://"                    # base en mémoire
os.environ["SECRET_KEY"] = "cle-de-test-0123456789abcdef-0123456789"
os.environ["CONCORDANCE_SEMANTIC_VETO"] = "0"                # pas de modèle d'embeddings
os.environ.pop("GEMINI_API_KEY", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from concordance import accounts, config  # noqa: E402
from concordance.db import Base, get_engine, reset_engine  # noqa: E402
from concordance.webapp.main import app  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
USER_EMAIL = "m.allani@entreprise.tn"
USER_PASSWORD = "motdepasse123"


@pytest.fixture
def db():
    """Base SQLite vierge, schéma créé depuis les modèles."""
    reset_engine()
    engine = get_engine()
    assert engine.dialect.name == "sqlite", "les tests ne doivent jamais viser une vraie base"
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    reset_engine()


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Racine de projet jetable : data/outputs, data/uploads et samples/ isolés."""
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "OUTPUTS_DIR", tmp_path / "data" / "outputs")
    monkeypatch.setattr(config, "UPLOADS_DIR", tmp_path / "data" / "uploads")
    monkeypatch.setattr(config, "SAMPLES_DIR", tmp_path / "samples")
    (tmp_path / "samples").mkdir()
    shutil.copy(REPO / "samples" / "native_sample.pdf", tmp_path / "samples")
    return tmp_path


@pytest.fixture
def client(db):
    return TestClient(app)


@pytest.fixture
def auth(client):
    """En-têtes d'authentification d'un utilisateur existant."""
    accounts.create_user("Mohsen Allani", USER_EMAIL, USER_PASSWORD)
    r = client.post("/api/auth/token",
                    data={"username": USER_EMAIL, "password": USER_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
