"""Documents synthétiques partagés par les tests.

Deux jeux : un scénario avec écarts (SCENARIO_*), qui exerce toute la chaîne
L6 -> L8, et les extractions du PDF natif de samples/ (NATIVE_*), telles que
le Vision-LLM les renverrait.
"""

import copy

from concordance.comparison import compare_analysis, comparison_to_dict
from concordance.stages.normalization import normalize_document
from concordance.validation import report_to_dict, validate_document

FOUR = {"nom": "STÉ QUINCAILLERIE DU CENTRE", "code": None,
        "matriculeFiscal": "1284563/A/M/000", "adresse": "Z.I. Kairouan Sud"}
CLI = {"nom": "SOTUFAB Industrie", "code": None,
       "matriculeFiscal": "0731205/B/P/000", "adresse": "Route de Sfax km 4"}

TOTAUX_VIDES = {"totalHT": None, "remiseTotale": None, "netHT": None, "tauxTVA": None,
                "montantTVA": None, "timbreFiscal": None, "totalTTC": None,
                "netAPayer": None}


def ligne(ref, des, q, pu, mt, rem=None):
    return {"reference": ref, "referencesDansDesignation": [],
            "designation": des, "unite": "pcs", "quantite": q,
            "prixUnitaireHT": pu, "tauxRemise": rem, "montantHT": mt,
            "tauxTVA": None, "dateLivraison": None}


# --------------------------------------------------------------- scénario

SCENARIO_BC = {
    "numero": "2214", "date": "12/07/2026", "fournisseur": FOUR, "client": CLI,
    "devise": "TND",
    "lignes": [
        ligne("VIS-1240", "VIS TH GAL CL 8.8 M12x40", "200", "0,185", "37,000"),
        ligne("2110160", "CADENAS BLOCUS LAITON 60 MM", "24", "11,900", "285,600"),
        ligne("TC-14", "TUBE CUIVRE D14 barre 4 m", "6", "18,300", "109,800"),
    ],
    "totaux": {**TOTAUX_VIDES, "totalHT": "432,400", "netHT": "432,400"},
}

SCENARIO_BL = {
    "numero": "L-4471", "date": "21/07/2026", "fournisseur": FOUR, "client": CLI,
    "referencesLiees": {"numeroBC": "2214"}, "devise": None,
    "lignes": [
        ligne("VIS-1240", "VIS TH GAL M12x40", "200", None, None),
        ligne("2110160", "CADENAS LAITON 60MM", "20", None, None),   # écart de quantité
    ],
}

SCENARIO_FA = {
    "numero": "F2026-412", "date": "24/07/2026", "fournisseur": FOUR,
    "client": CLI, "referencesLiees": {"numeroBC": "2214"}, "devise": "TND",
    "lignes": [
        ligne("VIS-1240", "VIS TH GAL M12X40 DIN 933", "200", "0,185", "37,000"),
        ligne("2110160", "CADENAS LAITON 60 MM", "24", "12,500", "300,000"),  # écart de prix
    ],
    "totaux": {**TOTAUX_VIDES, "totalHT": "337,000", "netHT": "337,000"},
}

SCENARIO = {"BC": SCENARIO_BC, "BL": SCENARIO_BL, "Facture": SCENARIO_FA}


def run_chain(raws):
    """Extractions brutes -> L6 -> L7 -> L8. Renvoie (validated, doc_details,
    comparison) dans la forme attendue par `save_analysis`."""
    validated, doc_details = {}, []
    for doc_type, raw in raws.items():
        report = validate_document(normalize_document(copy.deepcopy(raw)), doc_type)
        rd = report_to_dict(report)
        validated[doc_type] = report.corrected_document
        doc_details.append({"type": doc_type, "est_scanne": False,
                            "extraction_brute": raw, "validation": rd,
                            "document": rd["corrected_document"]})
    comparison = comparison_to_dict(compare_analysis(validated))
    return validated, doc_details, comparison


def seed_summary(comparison):
    return {"pdf": "uploads/BC-2214_quincaillerie__test.pdf", "pages": 5,
            "status": "ok", "groups": [], "errors": [], "documents": [],
            "comparaison": comparison["totaux"]}


# ------------------------------------------------- PDF natif de samples/

_TUNIMETAL = {"nom": "Société TUNIMETAL SARL", "code": None,
              "matriculeFiscal": "1234567/A/M/000",
              "adresse": "Zone Industrielle Charguia II, 2035 Tunis, Tunisie"}
_BIZERTE = {"nom": "Atelier Mécanique Bizerte SA", "code": None,
            "matriculeFiscal": "9876543/B/N/000",
            "adresse": "Route de Mateur, 7000 Bizerte, Tunisie"}

_ARTICLES = [
    ("Tôle acier galvanisée 2mm — 1000x2000", "15", "85,50", "1 282,50"),
    ("Profilé IPN 100 — longueur 6m", "8", "142,00", "1 136,00"),
    ("Boulons HM 12x40 inox — boîte 100 pcs", "25", "18,75", "468,75"),
    ("Électrode soudure rutile 3.2mm — 5kg", "12", "32,40", "388,80"),
]
_TOTAUX_NATIF = {**TOTAUX_VIDES, "totalHT": "3 276,05", "netHT": "3 276,05",
                 "tauxTVA": "19", "montantTVA": "622,45", "totalTTC": "3 898,50"}


def _entete(numero, date):
    return {"numero": numero, "date": date, "fournisseur": _TUNIMETAL,
            "client": _BIZERTE, "devise": "TND"}


NATIVE_EXTRACTIONS = {
    "BonCommandeExtrait": {
        **_entete("BC-2025/0142", "12/03/2025"),
        "lignes": [ligne(None, d, q, pu, mt) for d, q, pu, mt in _ARTICLES],
        "totaux": _TOTAUX_NATIF,
    },
    "BonLivraisonExtrait": {
        **_entete("BL-2025/0287", "18/03/2025"),
        "referencesLiees": {"numeroBC": "BC-2025/0142"},
        "lignes": [ligne(None, d, q, None, None) for d, q, _, _ in _ARTICLES],
    },
    "FactureExtrait": {
        **_entete("FA-2025/0531", "20/03/2025"),
        "referencesLiees": {"numeroBC": "BC-2025/0142", "numeroBL": "BL-2025/0287"},
        "lignes": [ligne(None, d, q, pu, mt) for d, q, pu, mt in _ARTICLES],
        "totaux": _TOTAUX_NATIF,
    },
}
NATIVE_PAGE_TYPES = ["BC", "BL", "Facture"]
