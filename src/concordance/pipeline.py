"""Orchestration du pipeline L0 -> L9 sur un PDF composite.

`process_pdf` enchaîne les étages (voir `concordance.stages`, puis
`validation`, `comparison`, `reporting`, `db`) et conserve chaque résultat
intermédiaire dans `data/outputs/<nom du pdf>/` : l'extraction par le modèle est
la seule étape coûteuse et non déterministe, tout le reste se rejoue
gratuitement à partir de ces artefacts (voir `concordance.replay`).
"""

import json
import os
from pathlib import Path

from concordance import config
from concordance.comparison import SemanticGate, compare_analysis, comparison_to_dict
from concordance.db import save_analysis
from concordance.reporting import generate_report
from concordance.stages.classification import classify_page
from concordance.stages.detection import is_native
from concordance.stages.extraction import extract_document
from concordance.stages.grouping import group_pages, validate_scope
from concordance.stages.ingestion import ingest
from concordance.stages.normalization import normalize_document
from concordance.stages.preprocessing import preprocess
from concordance.validation import report_to_dict, validate_document


def make_client():
    """Client Gemini, construit à partir de GEMINI_API_KEY."""
    from google import genai
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise config.MissingConfigError(
            "Définir GEMINI_API_KEY dans .env ou dans l'environnement "
            "(clé : https://aistudio.google.com/apikey)")
    return genai.Client(api_key=api_key)


def load_schemas() -> dict[str, dict]:
    """Schémas JSON d'extraction par type de document, prêts pour L5."""
    schemas = {}
    for doc_type, path in config.SCHEMAS.items():
        schema = json.loads(path.read_text(encoding="utf-8"))
        schema.pop("$schema", None)
        schemas[doc_type] = schema
    return schemas


def _save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8")


def process_pdf(client, pdf_path: Path, schemas: dict[str, dict],
                progress=None, id_utilisateur: int | None = None,
                persist: bool = True) -> dict:
    """`progress` : callable(étape:int 1..5, détail:str) — sans effet si None.
    Étapes : 1 lecture, 2 identification, 3 extraction, 4 validation,
    5 comparaison. L'interface web s'en sert ; la ligne de commande l'ignore.

    `persist` : enregistre l'analyse en base (L9). Désactivé, le pipeline ne
    nécessite aucune base de données et ne produit que les artefacts de
    data/outputs/."""
    notify = progress or (lambda n, d: None)
    out = config.OUTPUTS_DIR / pdf_path.stem
    notify(1, "Découpage et rendu des pages…")
    pages = ingest(pdf_path, out / "pages", config.RENDER_DPI)

    detection = []
    for p in pages:
        native = is_native(p["chars"], config.TEXT_THRESHOLD)
        image = Path(p["image"])   # absolu à ce stade ; seul le JSON écrit est relatif
        if not native:
            processed = image.with_name(image.stem + "_proc.png")
            preprocess(image, processed)
            image = processed
        detection.append({"page": p["page"], "scanned": not native,
                          "chars": p["chars"],
                          "image": config.portable(image)})
    _save(out / "detection.json", detection)
    nb_scan = sum(1 for d in detection if d["scanned"])
    notify(2, f"{len(pages)} page(s) rendue(s)"
              + (f" · {nb_scan} scannée(s) prétraitée(s)" if nb_scan else ""))

    classification = []
    for d in detection:
        notify(2, f"Identification de la page {d['page']}…")
        result = classify_page(client, config.MODEL, config.ROOT / d["image"])
        classification.append({"page": d["page"], "type": result.get("type"),
                               "confiance": result.get("confiance")})
    _save(out / "classification.json", classification)

    groups = group_pages([c["type"] for c in classification])
    errors = validate_scope(groups)
    _save(out / "grouping.json", {"groups": groups, "errors": errors})

    documents = []
    doc_details = []
    validated = {}
    scanned_by_page = {d["page"]: d["scanned"] for d in detection}
    if errors:
        status = "hors périmètre"
    else:
        status = "ok"
        image_by_page = {d["page"]: d["image"] for d in detection}
        for i, g in enumerate(groups):
            imgs = [config.ROOT / image_by_page[pg] for pg in g["pages"]]
            notify(3, f"Lecture du {g['type']} ({len(imgs)} page(s))…")
            data = extract_document(client, config.MODEL, imgs, schemas[g["type"]])
            base = out / "documents" / f"doc_{i + 1:02d}_{g['type']}"
            _save(base.with_suffix(".json"), data)

            notify(4, f"Contrôle arithmétique du {g['type']}…")
            report = validate_document(normalize_document(data), g["type"])
            report_dict = report_to_dict(report)
            _save(Path(str(base) + "_validation.json"), report_dict)

            validated[g["type"]] = report.corrected_document
            doc_details.append({
                "type": g["type"],
                "est_scanne": any(scanned_by_page[pg] for pg in g["pages"]),
                "extraction_brute": data,
                "validation": report_dict,
                "document": report_dict["corrected_document"],
            })
            corrected = report_dict["corrected_document"] or {}
            documents.append({
                "document": config.portable(base.with_suffix(".json")),
                "type": g["type"],
                "verdict": report.verdict,
                "confidence": report.confidence,
                "components": report.components,
                # Projections nécessaires au rapport (synthèse des montants) :
                # le rapport ne lit que summary + comparison, jamais la base.
                "devise": corrected.get("devise"),
                "totaux": corrected.get("totaux"),
            })

    comparison = None
    if len(validated) >= 2:
        notify(5, "Rapprochement ligne à ligne…")
        gate = SemanticGate.load() if config.SEMANTIC_VETO else None
        comparison = comparison_to_dict(compare_analysis(validated, gate))
        _save(out / "comparison.json", comparison)

    summary = {"pdf": config.portable(pdf_path), "pages": len(pages), "status": status,
               "groups": groups, "errors": errors, "documents": documents,
               "comparaison": None if comparison is None else comparison["totaux"]}

    # Le résumé est enregistré avant le rendu : à ce point, tout ce qui a
    # coûté un appel de modèle est acquis. Le rapport n'est qu'une projection,
    # rejouable à volonté par report.py — son échec ne doit rien détruire.
    _save(out / "summary.json", summary)

    if comparison is not None:
        try:
            rapport = generate_report(summary, comparison, out / "rapport.pdf")
            summary["rapport"] = config.portable(rapport)
        except Exception as exc:
            summary["rapport"] = None
            summary["rapport_erreur"] = str(exc)
        _save(out / "summary.json", summary)

    # L9 — persistance : une transaction pour toute l'analyse (BF11).
    if persist:
        verdicts = {d["verdict"] for d in documents}
        if status == "hors périmètre":
            statut_db = "hors périmètre"
        elif "review" in verdicts:
            statut_db = "en attente de révision"
        else:
            statut_db = "terminé"
        summary["id_analyse"] = save_analysis(summary, doc_details, comparison,
                                              statut_db, id_utilisateur)
    return summary
