"""Validation arithmétique (L7) : solveur, remise implicite, certification, score."""

import copy
from decimal import Decimal

from concordance.stages.normalization import normalize_document
from concordance.validation import validate_document
from concordance.validation.tolerance import Tolerance, infer_quantum, quality, ratio

from .data import NATIVE_EXTRACTIONS, SCENARIO_BC, ligne


def valider(raw, doc_type="BC"):
    return validate_document(normalize_document(copy.deepcopy(raw)), doc_type)


def statuts(report):
    return {c.name: c.status for c in report.checks}


def test_document_coherent_est_certifie():
    r = valider(NATIVE_EXTRACTIONS["BonCommandeExtrait"])
    assert r.verdict == "ok"
    assert r.certificate["certified"] is True
    assert r.certificate["relations_échec"] == 0
    assert r.confidence > 0.9


def test_bc_du_scenario_est_valide():
    r = valider(SCENARIO_BC)
    assert r.verdict == "ok" and r.certificate["certified"]


def test_ligne_incoherente_est_signalee_avec_correction_proposee():
    raw = copy.deepcopy(SCENARIO_BC)
    raw["lignes"][1]["montantHT"] = "385,600"            # 24 x 11,900 = 285,600
    r = valider(raw)
    assert r.verdict == "review"
    assert statuts(r)["ligne 2"] == "warning"
    assert "montantHT = 285.600" in next(c.message for c in r.checks if c.name == "ligne 2")


def test_total_ht_faux_est_detecte():
    raw = copy.deepcopy(SCENARIO_BC)
    raw["totaux"]["totalHT"] = "500,000"
    raw["totaux"]["netHT"] = "500,000"
    r = valider(raw)
    assert r.verdict in ("review", "corrected")
    assert r.certificate["relations_échec"] >= 1 or r.suggestions


def test_total_manquant_est_reconstruit():
    raw = copy.deepcopy(SCENARIO_BC)
    raw["totaux"] = {k: None for k in raw["totaux"]}
    raw["totaux"]["netHT"] = "432,400"
    r = valider(raw)
    assert r.recovered.get("totalHT") == Decimal("432.400")


def test_remise_implicite_est_retrouvee_puis_propagee():
    """Trois lignes remisées de 10 % sans colonne de remise : le consensus des
    lignes suffit à déduire le taux, qui est propagé."""
    raw = {"numero": "R1", "date": "01/01/2026",
           "fournisseur": {"nom": "F"}, "client": {"nom": "C"}, "devise": "TND",
           "lignes": [ligne("A", "ART A", "10", "100,000", "900,000"),
                      ligne("B", "ART B", "5", "40,000", "180,000"),
                      ligne("C", "ART C", "2", "50,000", "90,000")],
           "totaux": {"totalHT": "1 300,000", "netHT": "1 170,000"}}
    r = valider(raw)
    assert statuts(r)["remise lignes"] == "recovered"
    assert r.recovered["tauxRemise"] == Decimal("10.000")
    assert all(ln["tauxRemise"] == Decimal("10.000") for ln in r.corrected_document["lignes"])


def test_document_sans_numero_ni_lignes_est_a_reviser():
    r = valider({"numero": None, "date": None, "fournisseur": {"nom": None},
                 "client": {"nom": None}, "lignes": [], "totaux": {}})
    assert r.verdict == "review"
    assert statuts(r)["numéro"] == "error" and statuts(r)["lignes"] == "error"


def test_bl_sans_contenu_arithmetique_n_a_rien_a_certifier():
    r = valider(NATIVE_EXTRACTIONS["BonLivraisonExtrait"], "BL")
    assert r.certificate["applicable"] is False
    assert r.verdict == "ok"


def test_validation_est_deterministe():
    a = valider(SCENARIO_BC)
    b = valider(SCENARIO_BC)
    assert a.confidence == b.confidence and a.corrected_document == b.corrected_document


def test_la_validation_ne_modifie_pas_l_entree():
    raw = copy.deepcopy(SCENARIO_BC)
    avant = copy.deepcopy(raw)
    valider(raw)
    assert raw == avant


# ------------------------------------------------------------------ tolérances

def test_tolerance_deduite_de_la_precision_imprimee():
    """Aucune tolérance monétaire n'est codée en dur : elle suit les décimales
    imprimées dans le document."""
    millimes = normalize_document({"lignes": [{"prixUnitaireHT": "0,185"}], "totaux": {}})
    centimes = normalize_document({"lignes": [{"prixUnitaireHT": "85,50"}], "totaux": {}})
    assert infer_quantum(millimes) == Decimal("0.001")
    assert infer_quantum(centimes) == Decimal("0.01")
    tol_fin, tol_gros = Tolerance(Decimal("0.001")), Tolerance(Decimal("0.01"))
    assert tol_fin.terms(2, Decimal(100)) < tol_gros.terms(2, Decimal(100))


def test_tolerance_relative_aux_gros_montants():
    tol = Tolerance(Decimal("0.01"))
    assert tol.terms(2, Decimal(120000)) > tol.terms(2, Decimal(12))


def test_ratio_et_qualite():
    assert quality(ratio(Decimal(10), Decimal(10), Decimal("0.05"))) == 1
    assert quality(ratio(Decimal(10), Decimal(10.5), Decimal("0.05"))) < Decimal("0.2")
    assert ratio(None, Decimal(1), Decimal(1)) is None
