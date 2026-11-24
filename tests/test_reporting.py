"""Rapport PDF (BF10) : contexte d'affichage, rendu HTML, rendu PDF."""

import pytest

from concordance.reporting import build_context, generate_report, render_html
from concordance.reporting.generate import _weasyprint

from .data import SCENARIO, run_chain, seed_summary


@pytest.fixture(scope="module")
def entrees():
    _, _, comparison = run_chain(SCENARIO)
    return seed_summary(comparison), comparison


def test_verdict_global_ecarts(entrees):
    summary, comparison = entrees
    ctx = build_context(summary, comparison)
    assert ctx["verdict"]["label"] == "Écarts détectés"
    assert ctx["verdict"]["css"] == "err"


def test_rendu_html_contient_les_produits_et_echappe_le_html(entrees):
    summary, comparison = entrees
    html = render_html(build_context(summary, comparison))
    assert "CADENAS BLOCUS LAITON 60 MM" in html
    assert "<script" not in html


def test_html_echappe_les_designations_hostiles(entrees):
    summary, comparison = entrees
    import copy
    c = copy.deepcopy(comparison)
    c["produits"][0]["designation"] = "<script>alert(1)</script>"
    c["produits"][0]["lignes"]["BC"]["designation"] = "<script>alert(1)</script>"
    html = render_html(build_context(summary, c))
    assert "<script>alert(1)</script>" not in html


def test_comparaison_impossible_sans_bc():
    from concordance.comparison import compare_analysis, comparison_to_dict
    comparison = comparison_to_dict(compare_analysis({"BL": {"lignes": []}}))
    ctx = build_context({"documents": []}, comparison)
    assert ctx["verdict"]["label"] == "Comparaison impossible"


@pytest.mark.skipif(_weasyprint() is False, reason="WeasyPrint/Pango indisponible")
def test_generation_du_pdf(entrees, tmp_path):
    summary, comparison = entrees
    out = generate_report(summary, comparison, tmp_path / "sous" / "rapport.pdf")
    data = out.read_bytes()
    assert data.startswith(b"%PDF-") and data.rstrip().endswith(b"%%EOF")
