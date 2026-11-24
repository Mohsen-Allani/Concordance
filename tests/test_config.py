"""Configuration et chemins portables (BNF5)."""

from concordance import config


def test_portable_relatif_a_la_racine(workspace):
    p = workspace / "data" / "outputs" / "x" / "rapport.pdf"
    assert config.portable(p) == "data/outputs/x/rapport.pdf"
    assert config.portable("samples/a.pdf") == "samples/a.pdf"


def test_portable_hors_racine_reste_absolu(workspace, tmp_path_factory):
    ailleurs = tmp_path_factory.mktemp("autre") / "f.pdf"
    assert config.portable(ailleurs) == ailleurs.resolve().as_posix()


def test_schemas_embarques_dans_le_paquet():
    assert all(p.is_file() for p in config.SCHEMAS.values())
    assert config.SCHEMAS_DIR.parent == config.PACKAGE_DIR


def test_variable_obligatoire_absente(monkeypatch):
    import pytest
    monkeypatch.delenv("UNE_VARIABLE_ABSENTE", raising=False)
    with pytest.raises(config.MissingConfigError, match="UNE_VARIABLE_ABSENTE"):
        config.require_env("UNE_VARIABLE_ABSENTE")
