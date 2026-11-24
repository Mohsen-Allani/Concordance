"""Tests de non-régression du moteur de rapprochement (L8).

Chaque test verrouille une décision de conception, pas un détail
d'implémentation.
"""

from decimal import Decimal

from concordance.comparison.canonical import canonicalize, strip_label
from concordance.comparison.engine import compare_analysis
from concordance.comparison.fields import combined_tolerance, compare_lines
from concordance.comparison.matching import match


def doc(*lignes):
    return {"lignes": [dict(l) for l in lignes]}


def lines(d, t):
    return canonicalize(d, t)


def test_codes_battent_le_texte():
    """Les deux cadenas : désignations BC identiques, seuls les codes tranchent."""
    bc = lines(doc(
        {"reference": "P1", "designation": "CADNA BLOCUS LAITON 60MM",
         "referencesDansDesignation": ["REF 2110160"]},
        {"reference": "P2", "designation": "CADNA BLOCUS LAITON 60MM",
         "referencesDansDesignation": ["ref 77600"]},
    ), "BC")
    fa = lines(doc(
        {"reference": "2110160", "designation": "CADENAS LAITON 60 MM"},
        {"reference": "77600", "designation": "CADENAS LAITON 60MM"},
    ), "Facture")
    r = match(bc, fa)
    assert r.paires[0][0] == 0 and r.paires[1][0] == 1, r.paires
    assert not r.ambigus


def test_etiquette_ref_retiree():
    assert strip_label("REF 2110160") == "2110160"
    assert strip_label("n° 4684008") == "4684008"
    assert strip_label("REFA123") == "REFA123"     # pas d'étiquette prouvée


def test_rarete_code_commun_est_faible():
    """« 8.8 » sur deux lignes de chaque côté ne doit pas produire un pont fort."""
    bc = lines(doc(
        {"reference": "A", "designation": "VIS TH GAL CL 8.8 M",
         "referencesDansDesignation": ["12*40"]},
        {"reference": "B", "designation": "VIS TH GAL 8.8 M",
         "referencesDansDesignation": ["10*40"]},
    ), "BC")
    fa = lines(doc(
        {"reference": "X", "designation": "VIS TH GAL M12*40 DIN 933 CL. 8.8"},
        {"reference": "Y", "designation": "VIS TH GAL M10*40 DIN 933 CL. 8.8"},
    ), "Facture")
    r = match(bc, fa)
    assert r.paires[0][0] == 0 and r.paires[1][0] == 1, r.paires


def test_ambiguite_ne_consomme_pas_les_candidats():
    """Deux lignes de référence disputent le même candidat : les deux sont
    signalées, le candidat n'est ni attribué ni compté « en trop »."""
    bc = lines(doc(
        {"reference": "R1", "designation": "MECHE ACIER RECTIFIE 5MM"},
        {"reference": "R2", "designation": "MECHE ACIER RECTIFIE 5MM"},
    ), "BC")
    fa = lines(doc(
        {"reference": "Z9", "designation": "MECHE ACIER RECTIFIE 5 MM"},
    ), "Facture")
    r = match(bc, fa)
    assert not r.paires
    assert len(r.ambigus) == 2
    assert r.cible_seuls == []          # en attente de révision, pas orphelin


def test_resolution_operateur():
    bc = lines(doc(
        {"reference": "R1", "designation": "MECHE ACIER RECTIFIE 5MM"},
        {"reference": "R2", "designation": "MECHE ACIER RECTIFIE 5MM"},
    ), "BC")
    fa = lines(doc(
        {"reference": "Z9", "designation": "MECHE ACIER RECTIFIE 5 MM"},
    ), "Facture")
    r = match(bc, fa, resolutions={0: 0})
    assert r.paires[0][0] == 0
    assert r.paires[0][2] == ["résolu par l'opérateur"]
    assert r.ref_seuls == [1]           # l'autre devient un vrai manquant
    assert not r.ambigus


def test_independance_de_l_ordre():
    """Le résultat ne doit pas dépendre de l'ordre des lignes du BC."""
    a = {"reference": "A", "designation": "RIVET POP",
         "referencesDansDesignation": ["4.8*16"]}
    b = {"reference": "B", "designation": "RIVET POP",
         "referencesDansDesignation": ["4*12.7"]}
    fa = lines(doc(
        {"reference": "X", "designation": "RIVET ALUMINIUM 4.8X16 MM"},
        {"reference": "Y", "designation": "RIVET ALUMINIUM 4X12.7 MM"},
    ), "Facture")
    r1 = match(lines(doc(a, b), "BC"), fa)
    r2 = match(lines(doc(b, a), "BC"), fa)
    assert r1.paires[0][0] == 0 and r1.paires[1][0] == 1
    assert r2.paires[0][0] == 1 and r2.paires[1][0] == 0


def test_sens_de_l_ecart_de_quantite():
    bc = lines(doc({"reference": "R", "designation": "VIS",
                    "quantite": Decimal(100)}), "BC")
    bl_sous = lines(doc({"reference": "R", "designation": "VIS",
                         "quantite": Decimal(60)}), "BL")
    bl_sur = lines(doc({"reference": "R", "designation": "VIS",
                        "quantite": Decimal(130)}), "BL")
    tol = combined_tolerance({}, {})
    ax = compare_lines(bc[0], bl_sous[0], tol)[0]
    assert ax["statut"] == "écart" and ax["nature"] == "SOUS_LIVRAISON"
    assert ax["ecart_signe"] == Decimal(-40)
    ax = compare_lines(bc[0], bl_sur[0], tol)[0]
    assert ax["nature"] == "SUR_LIVRAISON" and ax["ecart_signe"] == Decimal(30)


def test_engine_statut_ambigu():
    docs = {
        "BC": doc({"reference": "R1", "designation": "MECHE 5MM"},
                  {"reference": "R2", "designation": "MECHE 5MM"}),
        "Facture": doc({"reference": "Z9", "designation": "MECHE 5 MM"}),
    }
    r = compare_analysis(docs)
    statuts = sorted(p["statut"] for p in r["produits"])
    assert statuts == ["ambigu", "ambigu"], statuts
    assert r["totaux"]["ambigus"] == 2
