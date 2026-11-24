"""Tests des révisions de l'opérateur (BF9) : chaque test verrouille un geste
de l'écran de révision.
"""

from decimal import Decimal

from concordance.comparison.engine import compare_analysis
from concordance.comparison.overrides import OverrideError


def doc(*lignes):
    return {"lignes": [dict(l) for l in lignes]}


def _paire(result, cle_produit, paire):
    p = next(p for p in result["produits"] if p["cle"] == cle_produit)
    return p, p["paires"].get(paire)


def test_resolution_ambiguite():
    """Geste 1 : glisser une ligne ambiguë sur la bonne ligne BC.

    Deux vis quasi identiques : sans révision, le moteur signale une
    ambiguïté ; avec l'affectation, la paire est verrouillée et l'autre ligne
    trouve son appariement naturellement."""
    bc = doc({"reference": "V1", "designation": "VIS ACIER M8"},
             {"reference": "V2", "designation": "VIS ACIER M8 LONGUE"})
    bl = doc({"designation": "VIS ACIER M8 STANDARD", "quantite": Decimal(10)},
             {"designation": "VIS ACIER M8 LG", "quantite": Decimal(5)})

    avant = compare_analysis({"BC": bc, "BL": bl})
    assert avant["ambiguites"], "le cas doit être ambigu sans révision"

    apres = compare_analysis({"BC": bc, "BL": bl},
                             overrides={"BC↔BL": {"affectations": {"0": [0]}}})
    assert not apres["ambiguites"], apres["ambiguites"]
    _, paire0 = _paire(apres, "BC:0", "BC↔BL")
    assert paire0["preuves"] == ["résolu par l'opérateur"]
    _, paire1 = _paire(apres, "BC:1", "BC↔BL")
    assert paire1["statut"] != "manquant", "l'autre ligne doit se rapprocher seule"


def test_reaffectation():
    """Geste 2 : glisser une ligne Facture d'un produit vers un autre.

    Le moteur apparie par référence R1->R1 ; l'opérateur, qui voit les
    documents, sait que la facture a permuté les codes. Sa décision prime,
    et le rapprochement automatique est rejoué autour d'elle."""
    bc = doc({"reference": "R1", "designation": "TUBE CUIVRE 12", "quantite": Decimal(4)},
             {"reference": "R2", "designation": "TUBE CUIVRE 14", "quantite": Decimal(6)})
    fa = doc({"reference": "R1", "designation": "TUBE CUIVRE 14", "quantite": Decimal(6)},
             {"reference": "R2", "designation": "TUBE CUIVRE 12", "quantite": Decimal(4)})

    apres = compare_analysis({"BC": bc, "Facture": fa},
                             overrides={"BC↔Facture":
                                        {"affectations": {"0": [1], "1": [0]}}})
    p0, paire0 = _paire(apres, "BC:0", "BC↔Facture")
    assert p0["lignes"]["Facture"]["lignes_source"] == [1]
    axe_qte = next(a for a in paire0["axes"] if a["champ"] == "quantite")
    assert axe_qte["statut"] == "conforme", axe_qte


def test_fusion_deux_lignes_vers_un_bc():
    """Geste 3 : empiler deux lignes BL dans la cellule d'un produit.

    Une commande de 100 livrée en deux fois (60 + 40) : chaque livraison
    seule serait un écart, la fusion révèle la conformité. Les quantités
    s'additionnent, les montants aussi."""
    bc = doc({"reference": "A100", "designation": "CABLE 3G2.5",
              "quantite": Decimal(100), "prixUnitaireHT": Decimal(2),
              "montantHT": Decimal(200)})
    bl = doc({"reference": "A100", "designation": "CABLE 3G2.5 LOT 1",
              "quantite": Decimal(60)},
             {"designation": "CABLE SOUPLE LOT 2", "quantite": Decimal(40)})

    apres = compare_analysis({"BC": bc, "BL": bl},
                             overrides={"BC↔BL": {"affectations": {"0": [0, 1]}}})
    p, paire = _paire(apres, "BC:0", "BC↔BL")
    ligne_bl = p["lignes"]["BL"]
    assert ligne_bl["fusionnee"] is True
    assert sorted(ligne_bl["lignes_source"]) == [0, 1]
    assert ligne_bl["quantite"] == Decimal(100)
    axe_qte = next(a for a in paire["axes"] if a["champ"] == "quantite")
    assert axe_qte["statut"] == "conforme", axe_qte
    assert apres["totaux"]["ecarts"] == 0


def test_detachement():
    """Geste 4 : glisser une ligne vers le bac « non rapprochées ».

    Le moteur appariait à tort ; détachée, la ligne devient « en trop » et le
    produit BC redevient « manquant » — deux signalements exacts plutôt qu'un
    faux écart de prix."""
    bc = doc({"reference": "K7", "designation": "JOINT TORIQUE 25MM",
              "quantite": Decimal(10)})
    bl = doc({"reference": "K7", "designation": "JOINT PLAT 25MM",
              "quantite": Decimal(10)})

    apres = compare_analysis({"BC": bc, "BL": bl},
                             overrides={"BC↔BL": {"detachees": [0]}})
    _, paire = _paire(apres, "BC:0", "BC↔BL")
    assert paire["statut"] == "manquant"
    hors = next(p for p in apres["produits"] if p["cle"].startswith("HORS_BC"))
    assert hors["paires"]["BC↔BL"]["message"] == "détachée par l'opérateur"
    assert hors["statut"] == "en_trop"


def test_detachee_jamais_candidate():
    """Une ligne détachée ne doit plus apparaître comme candidate d'une
    ambiguïté : l'opérateur l'a retirée du jeu."""
    bc = doc({"reference": "V1", "designation": "VIS ACIER M8"})
    bl = doc({"designation": "VIS ACIER M8 STANDARD", "quantite": Decimal(10)},
             {"designation": "VIS ACIER M8 SPECIALE", "quantite": Decimal(10)})

    avant = compare_analysis({"BC": bc, "BL": bl})
    assert avant["ambiguites"]

    apres = compare_analysis({"BC": bc, "BL": bl},
                             overrides={"BC↔BL": {"detachees": [1]}})
    assert not apres["ambiguites"], apres["ambiguites"]
    _, paire = _paire(apres, "BC:0", "BC↔BL")
    assert paire["statut"] in ("conforme", "écart", "non_comparable")


def test_deterministe():
    """BNF1 : mêmes documents, mêmes révisions -> même résultat, deux fois."""
    bc = doc({"reference": "V1", "designation": "VIS ACIER M8"},
             {"reference": "V2", "designation": "VIS ACIER M8 LONGUE"})
    bl = doc({"designation": "VIS ACIER M8 STANDARD", "quantite": Decimal(10)},
             {"designation": "VIS ACIER M8 LG", "quantite": Decimal(5)})
    ov = {"BC↔BL": {"affectations": {"0": [0]}}}
    a = compare_analysis({"BC": bc, "BL": bl}, overrides=ov)
    b = compare_analysis({"BC": bc, "BL": bl}, overrides=ov)
    assert a == b


def test_revisions_invalides():
    """Les conflits sont refusés avec un message, jamais arbitrés."""
    bc = doc({"reference": "A", "designation": "X"},
             {"reference": "B", "designation": "Y"})
    bl = doc({"designation": "X", "quantite": Decimal(1)},
             {"designation": "Y", "quantite": Decimal(1)})

    cas = [
        ({"BC↔BL": {"affectations": {"0": [0], "1": [0]}}},
         "affectée à deux lignes BC"),
        ({"BC↔BL": {"affectations": {"0": [0]}, "detachees": [0]}},
         "à la fois affectée et détachée"),
        ({"BC↔BL": {"affectations": {"9": [0]}}}, "n'existe pas"),
        ({"BC↔BL": {"affectations": {"0": [9]}}}, "n'existe pas"),
        ({"BC↔BL": {"affectations": {"0": []}}}, "liste non vide"),
        ({"BL↔Facture": {"affectations": {"0": [0]}}}, "paires non révisables"),
    ]
    for ov, fragment in cas:
        try:
            compare_analysis({"BC": bc, "BL": bl}, overrides=ov)
        except OverrideError as exc:
            assert fragment in str(exc), (fragment, str(exc))
        else:
            raise AssertionError(f"révision acceptée à tort : {ov}")


def test_fusion_sur_ligne_deja_autofusionnee():
    """Un index d'origine absorbé par une fusion automatique (doublon de
    référence) désigne la ligne canonique entière — l'affectation reste
    valide quel que soit l'index du doublon employé."""
    bc = doc({"reference": "A100", "designation": "CABLE", "quantite": Decimal(100)})
    bl = doc({"reference": "A100", "designation": "CABLE L1", "quantite": Decimal(30)},
             {"reference": "A100", "designation": "CABLE L2", "quantite": Decimal(30)},
             {"designation": "CABLE RESTE", "quantite": Decimal(40)})

    apres = compare_analysis(
        {"BC": bc, "BL": bl},
        overrides={"BC↔BL": {"affectations": {"0": [1, 2]}}})
    p, paire = _paire(apres, "BC:0", "BC↔BL")
    assert sorted(p["lignes"]["BL"]["lignes_source"]) == [0, 1, 2]
    assert p["lignes"]["BL"]["quantite"] == Decimal(100)
    axe_qte = next(a for a in paire["axes"] if a["champ"] == "quantite")
    assert axe_qte["statut"] == "conforme", axe_qte
