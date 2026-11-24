"""Étages unitaires du pipeline : regroupement (L4), normalisation (L6),
détection natif/scanné (L1), ingestion (L0) et prétraitement (L2)."""

from datetime import date
from decimal import Decimal

import numpy as np
import pytest

from concordance import config
from concordance.stages.detection import is_native
from concordance.stages.grouping import group_pages, validate_scope
from concordance.stages.ingestion import ingest
from concordance.stages.normalization import normalize_document, parse_date, parse_decimal

# ---------------------------------------------------------------- L4 grouping


def test_regroupement_conserve_l_ordre_d_apparition():
    groups = group_pages(["BC", "BC", "BL", "Facture", "BL"])
    assert groups == [{"type": "BC", "pages": [1, 2]},
                      {"type": "BL", "pages": [3, 5]},
                      {"type": "Facture", "pages": [4]}]


def test_perimetre_valide():
    assert validate_scope(group_pages(["BC", "BL"])) == []
    assert validate_scope(group_pages(["BC", "Facture"])) == []
    assert validate_scope(group_pages(["BC", "BL", "Facture"])) == []


def test_perimetre_sans_bc():
    assert "aucune page BC trouvée" in validate_scope(group_pages(["BL", "Facture"]))


def test_perimetre_sans_bl_ni_facture():
    erreurs = validate_scope(group_pages(["BC", "BC"]))
    assert any("au moins 1 BL ou 1 Facture" in e for e in erreurs)


def test_perimetre_page_non_reconnue():
    erreurs = validate_scope(group_pages(["BC", "BL", "AUTRE"]))
    assert erreurs == ["1 page(s) non reconnue(s)"]


# ------------------------------------------------------------ L6 normalisation

@pytest.mark.parametrize("brut, attendu", [
    ("37,500", Decimal("37.500")),
    ("1 282,50", Decimal("1282.50")),
    ("1 282,50", Decimal("1282.50")),
    ("1.234,567", Decimal("1234.567")),        # virgule décimale, point des milliers
    ("1,234.50", Decimal("1234.50")),          # point décimal, virgule des milliers
    ("1.234.567", Decimal("1234567")),         # plusieurs points : milliers
    ("-5,5", Decimal("-5.5")),
    ("19 %", Decimal("19")),
    ("3 276,05 DT", Decimal("3276.05")),
    (12, Decimal("12")),
])
def test_parse_decimal(brut, attendu):
    assert parse_decimal(brut) == attendu


@pytest.mark.parametrize("brut", [None, "", "  ", "abc", "-", "."])
def test_parse_decimal_valeurs_inexploitables(brut):
    assert parse_decimal(brut) is None


def test_parse_decimal_conserve_les_decimales_imprimees():
    """Les tolérances de L7 se déduisent du nombre de décimales imprimées."""
    assert parse_decimal("85,50").as_tuple().exponent == -2
    assert parse_decimal("0,185").as_tuple().exponent == -3


def test_parse_date_jour_en_premier():
    assert parse_date("12/07/2026") == date(2026, 7, 12)
    assert parse_date("31/07/2025") == date(2025, 7, 31)
    assert parse_date(None) is None
    assert parse_date("pas une date") is None


def test_normalize_document():
    brut = {"numero": "X", "date": "12/03/2025",
            "lignes": [{"quantite": "15", "prixUnitaireHT": "85,50",
                        "montantHT": "1 282,50", "tauxRemise": None,
                        "dateLivraison": "25/03/2025", "designation": "Tôle"}],
            "totaux": {"totalHT": "3 276,05", "tauxTVA": "19", "note": "x"},
            "referencesLiees": {"numeroBC": "BC-1", "dateBC": "01/03/2025"}}
    n = normalize_document(brut)
    ligne = n["lignes"][0]
    assert n["date"] == date(2025, 3, 12)
    assert ligne["montantHT"] == Decimal("1282.50") and ligne["tauxRemise"] is None
    assert ligne["dateLivraison"] == date(2025, 3, 25)
    assert n["totaux"]["totalHT"] == Decimal("3276.05") and n["totaux"]["note"] == "x"
    assert n["referencesLiees"]["dateBC"] == date(2025, 3, 1)
    assert brut["lignes"][0]["quantite"] == "15"      # l'entrée n'est pas modifiée


# ------------------------------------------------------- L1 détection, L0 rendu

def test_detection_natif_scanne():
    assert is_native(config.TEXT_THRESHOLD, config.TEXT_THRESHOLD)
    assert not is_native(config.TEXT_THRESHOLD - 1, config.TEXT_THRESHOLD)


def test_ingestion_du_pdf_natif(workspace, tmp_path):
    pages = ingest(workspace / "samples" / "native_sample.pdf", tmp_path / "pages", dpi=72)
    assert [p["page"] for p in pages] == [1, 2, 3]
    assert all(p["chars"] > config.TEXT_THRESHOLD for p in pages)
    assert all((tmp_path / "pages" / f"page_{i:02d}.png").is_file() for i in (1, 2, 3))


# ------------------------------------------------------------- L2 prétraitement

def test_pretraitement_redresse_et_ecrit_l_image(tmp_path):
    import cv2

    from concordance.stages.preprocessing import preprocess

    page = np.full((400, 300), 255, np.uint8)
    cv2.putText(page, "BON DE COMMANDE", (20, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.8, 0, 2)
    src, out = tmp_path / "scan.png", tmp_path / "scan_proc.png"
    cv2.imwrite(str(src), page)
    assert preprocess(src, out) == out
    img = cv2.imread(str(out), cv2.IMREAD_GRAYSCALE)
    assert img is not None and img.ndim == 2 and img.shape[0] >= 300
