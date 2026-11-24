"""Pipeline L0 -> L9 de bout en bout avec un faux client Gemini.

Le PDF natif de samples/ est traité en entier : rendu, détection, classification,
regroupement, extraction, validation, comparaison, rapport, persistance. Seul le
modèle est simulé ; tout le reste est le code réel.
"""

import json

import pytest

from concordance import config, pipeline, replay
from concordance.db import new_session
from concordance.db.models import Analyse
from concordance.reporting.generate import _weasyprint

from .data import NATIVE_EXTRACTIONS, NATIVE_PAGE_TYPES
from .fakes import FakeGemini


def faux_client(types=NATIVE_PAGE_TYPES):
    return FakeGemini(types, NATIVE_EXTRACTIONS)


@pytest.fixture
def analyse(workspace):
    """Pipeline exécuté une fois, sans base de données."""
    client = faux_client()
    summary = pipeline.process_pdf(client, workspace / "samples" / "native_sample.pdf",
                                   pipeline.load_schemas(), persist=False)
    return summary, client, config.OUTPUTS_DIR / "native_sample"


def test_pipeline_complet(analyse):
    summary, client, out = analyse
    assert summary["status"] == "ok" and summary["pages"] == 3
    assert [g["type"] for g in summary["groups"]] == ["BC", "BL", "Facture"]
    assert summary["errors"] == []
    assert client.calls == {"classification": 3, "extraction": 3}

    assert {d["type"]: d["verdict"] for d in summary["documents"]} == {
        "BC": "ok", "BL": "ok", "Facture": "ok"}
    assert summary["comparaison"] == {"produits": 4, "conformes": 4, "ecarts": 0, "ambigus": 0}


def test_artefacts_ecrits_sur_disque(analyse):
    _, _, out = analyse
    for nom in ("detection.json", "classification.json", "grouping.json",
                "comparison.json", "summary.json"):
        assert (out / nom).is_file(), nom
    assert len(list((out / "pages").glob("page_*.png"))) == 3
    assert {p.name for p in (out / "documents").glob("doc_*.json")
            if not p.stem.endswith("_validation")} == {
        "doc_01_BC.json", "doc_02_BL.json", "doc_03_Facture.json"}
    detection = json.loads((out / "detection.json").read_text(encoding="utf-8"))
    assert all(not d["scanned"] for d in detection)       # PDF natif : L2 jamais exécuté


def test_chemins_ecrits_en_relatif_et_posix(analyse):
    summary, _, _ = analyse
    assert summary["pdf"] == "samples/native_sample.pdf"


def test_rapport_pdf_ou_erreur_explicite(analyse):
    summary, _, out = analyse
    if _weasyprint() is False:
        assert summary["rapport"] is None and "WeasyPrint" in summary["rapport_erreur"]
    else:
        pdf = out / "rapport.pdf"
        assert summary["rapport"] == config.portable(pdf)
        data = pdf.read_bytes()
        assert data.startswith(b"%PDF-") and data.rstrip().endswith(b"%%EOF")


def test_persistance_en_base(workspace, db):
    summary = pipeline.process_pdf(faux_client(), workspace / "samples" / "native_sample.pdf",
                                   pipeline.load_schemas(), persist=True)
    assert summary["id_analyse"] >= 1
    with new_session() as session:
        a = session.get(Analyse, summary["id_analyse"])
        assert a.statut == "terminé" and a.nb_pages == 3
        assert sorted(d.type_document for d in a.documents) == ["BC", "BL", "Facture"]
        bc = next(d for d in a.documents if d.type_document == "BC")
        assert bc.numero == "BC-2025/0142" and len(bc.lignes) == 4
        assert bc.extraction_brute["numero"] == "BC-2025/0142"      # sortie brute archivée
        assert len(a.resultats) == 4


def test_hors_perimetre_sans_extraction(workspace):
    """Un PDF sans BC est refusé avant tout appel d'extraction (coût nul)."""
    client = faux_client(["BL", "Facture", "Facture"])
    summary = pipeline.process_pdf(client, workspace / "samples" / "native_sample.pdf",
                                   pipeline.load_schemas(), persist=False)
    assert summary["status"] == "hors périmètre"
    assert "aucune page BC trouvée" in summary["errors"]
    assert client.calls["extraction"] == 0 and summary["comparaison"] is None


def test_progression_notifiee(workspace):
    etapes = []
    pipeline.process_pdf(faux_client(), workspace / "samples" / "native_sample.pdf",
                         pipeline.load_schemas(), progress=lambda n, d: etapes.append(n),
                         persist=False)
    assert sorted(set(etapes)) == [1, 2, 3, 4, 5]


def test_schemas_charges_sans_cle_dollar_schema():
    schemas = pipeline.load_schemas()
    assert set(schemas) == {"BC", "BL", "Facture"}
    assert all("$schema" not in s for s in schemas.values())
    assert {s["title"] for s in schemas.values()} == set(NATIVE_EXTRACTIONS)


def test_client_sans_cle_api(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(config.MissingConfigError, match="GEMINI_API_KEY"):
        pipeline.make_client()


# ----------------------------------------------------------------- rejeu L6-L9

def test_rejeu_de_la_comparaison_est_identique(analyse):
    summary, _, out = analyse
    avant = json.loads((out / "comparison.json").read_text(encoding="utf-8"))
    replay.compare_folder(out)
    apres = json.loads((out / "comparison.json").read_text(encoding="utf-8"))
    assert avant == apres                                  # BNF1 : rejeu déterministe


def test_inspection_des_lignes(analyse, capsys):
    _, _, out = analyse
    assert replay.revise_folder(out, None) == 0
    sortie = capsys.readouterr().out
    assert "[0]" in sortie and "Tôle acier galvanisée" in sortie


def test_revision_rejouee_depuis_le_disque(analyse, capsys):
    _, _, out = analyse
    assert replay.revise_folder(out, {"BC↔BL": {"detachees": [0]}}) == 0
    comparison = json.loads((out / "comparison.json").read_text(encoding="utf-8"))
    assert comparison["totaux"]["ecarts"] == 2          # un manquant + un en trop
    assert replay.revise_folder(out, {"BC↔BL": {"affectations": {"99": [0]}}}) == 1
    assert "révision refusée" in capsys.readouterr().out


def test_dossier_sans_documents(workspace, capsys):
    vide = config.OUTPUTS_DIR / "vide"
    vide.mkdir(parents=True)
    replay.compare_all(["vide"])
    assert "aucun dossier documents/" in capsys.readouterr().out
