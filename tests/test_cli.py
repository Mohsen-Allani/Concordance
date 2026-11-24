"""Ligne de commande : analyse des arguments et commandes sans réseau."""

import pytest

from concordance import __version__, cli, config, pipeline

from .data import NATIVE_EXTRACTIONS, NATIVE_PAGE_TYPES
from .fakes import FakeGemini


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_commande_obligatoire():
    with pytest.raises(SystemExit) as exc:
        cli.main([])
    assert exc.value.code == 2


def test_run_sans_base_de_donnees(workspace, monkeypatch, capsys):
    monkeypatch.setattr(pipeline, "make_client",
                        lambda: FakeGemini(NATIVE_PAGE_TYPES, NATIVE_EXTRACTIONS))
    monkeypatch.delenv("DATABASE_URL")
    assert cli.main(["run"]) == 0                       # défaut : samples/*.pdf
    sortie = capsys.readouterr()
    assert "4/4 conformes" in sortie.out
    assert "DATABASE_URL absent" in sortie.err


def test_run_avec_base(workspace, db, monkeypatch, capsys):
    monkeypatch.setattr(pipeline, "make_client",
                        lambda: FakeGemini(NATIVE_PAGE_TYPES, NATIVE_EXTRACTIONS))
    assert cli.main(["run", str(workspace / "samples" / "native_sample.pdf")]) == 0
    assert "enregistrée en base" in capsys.readouterr().out
    assert cli.main(["history"]) == 0
    assert "native_sample.pdf" in capsys.readouterr().out
    assert cli.main(["history", "1"]) == 0
    assert "BC  n°BC-2025/0142" in capsys.readouterr().out


def test_run_sans_pdf(workspace, capsys):
    (workspace / "samples" / "native_sample.pdf").unlink()
    assert cli.main(["run", "--no-db"]) == 1


def test_run_sans_cle_api(workspace, monkeypatch, capsys):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert cli.main(["run", "--no-db"]) == 2
    assert "GEMINI_API_KEY" in capsys.readouterr().err


def test_compare_report_revise(workspace, monkeypatch, capsys):
    monkeypatch.setattr(pipeline, "make_client",
                        lambda: FakeGemini(NATIVE_PAGE_TYPES, NATIVE_EXTRACTIONS))
    cli.main(["run", "--no-db"])
    capsys.readouterr()

    assert cli.main(["compare", "native_sample"]) == 0
    assert "BC↔BL" in capsys.readouterr().out
    assert cli.main(["revise", "native_sample"]) == 0
    assert cli.main(["revise", "inexistant"]) == 2
    rev = workspace / "rev.json"
    rev.write_text('{"BC↔BL": {"detachees": [0]}}', encoding="utf-8")
    assert cli.main(["revise", "native_sample", str(rev)]) == 0
    assert (config.OUTPUTS_DIR / "native_sample" / "comparison.json").is_file()
    assert cli.main(["report", "native_sample"]) == 0


def test_create_user(db, monkeypatch, capsys):
    saisies = iter(["motdepasse123", "motdepasse123"])
    monkeypatch.setattr(cli, "getpass", lambda prompt="": next(saisies))
    assert cli.main(["create-user", "Mohsen Allani", "m@x.tn", "--role", "admin"]) == 0
    assert "Utilisateur créé" in capsys.readouterr().out

    saisies = iter(["motdepasse123", "motdepasse123"])
    assert cli.main(["create-user", "Doublon", "m@x.tn"]) == 1
    assert "existe déjà" in capsys.readouterr().err


def test_create_user_saisies_differentes(db, monkeypatch, capsys):
    saisies = iter(["motdepasse123", "autre-chose-456"])
    monkeypatch.setattr(cli, "getpass", lambda prompt="": next(saisies))
    assert cli.main(["create-user", "A", "a@x.tn"]) == 1
    assert "diffèrent" in capsys.readouterr().err
