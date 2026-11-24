"""Configuration centrale du projet.

Tout ce qui varie d'une machine à l'autre passe par des variables
d'environnement, lues dans l'environnement du processus ou dans un fichier
`.env` placé à la racine du projet (voir `.env.example`). Aucune valeur
sensible n'est codée en dur.

Les chemins sont ancrés sur la racine du projet, et non sur le répertoire
courant : le pipeline se comporte de la même façon quel que soit l'endroit
d'où il est lancé (BNF5).
"""

import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

PACKAGE_DIR = Path(__file__).resolve().parent


class MissingConfigError(RuntimeError):
    """Variable d'environnement obligatoire absente. Le message est destiné
    à l'utilisateur : il dit quoi renseigner et où."""


def _find_root() -> Path:
    """Racine du projet : CONCORDANCE_ROOT si défini, sinon le dépôt source
    (dossier contenant pyproject.toml), sinon le répertoire courant (cas d'une
    installation non éditable)."""
    forced = os.environ.get("CONCORDANCE_ROOT")
    if forced:
        return Path(forced).resolve()
    candidate = PACKAGE_DIR.parents[1]
    if (candidate / "pyproject.toml").is_file():
        return candidate
    return Path.cwd().resolve()


ROOT = _find_root()

# Le .env de la racine d'abord (indépendant du terminal), puis celui que
# trouve une recherche depuis le répertoire courant. Une variable déjà
# présente dans l'environnement n'est jamais écrasée.
load_dotenv(ROOT / ".env")
load_dotenv(find_dotenv(usecwd=True))

# --------------------------------------------------------------------- chemins

SAMPLES_DIR = ROOT / "samples"
DATA_DIR = Path(os.environ.get("CONCORDANCE_DATA_DIR") or ROOT / "data")
OUTPUTS_DIR = DATA_DIR / "outputs"     # artefacts de chaque analyse (JSON, pages, rapport)
UPLOADS_DIR = DATA_DIR / "uploads"     # PDF déposés via l'interface web (BF2)
SCHEMAS_DIR = PACKAGE_DIR / "schemas"  # schémas JSON transmis au Vision-LLM (L5)

SCHEMAS = {
    "BC": SCHEMAS_DIR / "bc_schema.json",
    "BL": SCHEMAS_DIR / "bl_schema.json",
    "Facture": SCHEMAS_DIR / "facture_schema.json",
}

# ----------------------------------------------------------------------- modèle

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

RENDER_DPI = 300
TEXT_THRESHOLD = 20   # en deçà, la page est traitée comme scannée

# Veto sémantique en L8 : actif si sentence-transformers est installé, ignoré
# silencieusement sinon. Il ne s'exerce qu'au niveau texte, jamais contre un code.
SEMANTIC_VETO = os.environ.get("CONCORDANCE_SEMANTIC_VETO", "1").lower() not in (
    "0", "false", "no", "off")

# -------------------------------------------------------------------- rapport

# L9 : WeasyPrint s'appuie sur Pango, une bibliothèque système absente de pip.
# Linux et macOS la trouvent seuls. Sous Windows, elle est fournie par MSYS2 et
# n'est pas dans le PATH : renseigner WEASYPRINT_DLL_DIR dans .env, ou laisser
# la détection ci-dessous trouver l'installation MSYS2 par défaut.


def _default_dll_dir() -> str | None:
    if os.name == "nt":
        msys = Path(r"C:\msys64\mingw64\bin")
        if msys.is_dir():
            return str(msys)
    return None


WEASYPRINT_DLL_DIR = os.environ.get("WEASYPRINT_DLL_DIR") or _default_dll_dir()


# ------------------------------------------------------------------- utilitaires

def portable(path):
    """Chemin tel qu'il doit être écrit dans un JSON : relatif à la racine et
    en séparateurs POSIX, afin qu'un rapport produit sous Windows reste lisible
    et rejouable ailleurs."""
    p = Path(path)
    p = p if p.is_absolute() else (ROOT / p)
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return p.resolve().as_posix()


def require_env(name: str, hint: str = "") -> str:
    """Valeur d'une variable d'environnement obligatoire, ou erreur explicite."""
    value = os.environ.get(name)
    if not value:
        raise MissingConfigError(f"Définir {name} dans .env ou dans l'environnement"
                                 + (f" ({hint})" if hint else ""))
    return value


def database_configured() -> bool:
    return bool(os.environ.get("DATABASE_URL"))
