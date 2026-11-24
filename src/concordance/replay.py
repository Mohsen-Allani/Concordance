"""Rejeu des étages déterministes sur des analyses déjà extraites.

L'extraction (L5) est la seule étape coûteuse et la seule non déterministe. La
conserver sur disque permet de retravailler la normalisation, la validation, la
comparaison et le rapport autant de fois que nécessaire, à coût nul et sur des
entrées strictement identiques. Aucune fonction de ce module n'appelle le
modèle.

    concordance compare [dossier ...]        rejoue L6 -> L8
    concordance report  [dossier ...]        rejoue L9 (rapport PDF)
    concordance revise  dossier [fichier]    rejoue L8 sous révisions (BF9)

Un « dossier » est un sous-dossier de data/outputs/ (le nom du PDF traité).

Format du fichier de révisions (index = lignes d'origine, affichés par
`concordance revise dossier`, sans fichier) :

    {
      "BC↔BL":      {"affectations": {"0": [2, 4]}, "detachees": [5]},
      "BC↔Facture": {"affectations": {"1": [0]}}
    }
"""

import json
from pathlib import Path

from concordance import config
from concordance.comparison import OverrideError, SemanticGate, compare_analysis, comparison_to_dict
from concordance.comparison.canonical import canonicalize
from concordance.reporting import generate_report
from concordance.stages.normalization import normalize_document
from concordance.validation import validate_document

TYPES = ("BC", "BL", "Facture")


def output_folders(names: list[str] | None = None) -> list[Path]:
    """Dossiers d'analyse demandés, ou tous ceux de data/outputs/."""
    if names:
        return [config.OUTPUTS_DIR / n for n in names]
    if not config.OUTPUTS_DIR.is_dir():
        return []
    return sorted(p for p in config.OUTPUTS_DIR.iterdir() if p.is_dir())


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- L6 -> L8

def load_documents(folder: Path):
    """Extractions brutes -> documents validés, indexés par type."""
    validated, verdicts = {}, {}
    for path in sorted((folder / "documents").glob("doc_*.json")):
        if path.stem.endswith("_validation"):
            continue
        doc_type = next((t for t in TYPES if path.stem.endswith(t)), None)
        if doc_type is None:
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        report = validate_document(normalize_document(raw), doc_type)
        validated[doc_type] = report.corrected_document
        verdicts[doc_type] = (report.verdict, report.confidence)
    return validated, verdicts


def compare_folder(folder: Path, gate=None):
    """Rejoue L6 -> L8 sur un dossier et réécrit comparison.json."""
    validated, verdicts = load_documents(folder)
    if len(validated) < 2:
        print(f"{folder.name}: {len(validated)} document(s), comparaison impossible")
        return None

    result = compare_analysis(validated, gate)
    out = folder / "comparison.json"
    _write_json(out, comparison_to_dict(result))

    print(f"\n=== {folder.name}")
    for t, (verdict, conf) in verdicts.items():
        print(f"  {t:8} {verdict} (confiance {conf})")
    for check in result["entete"]:
        if check["statut"] != "ignoré":
            print(f"  [{check['statut']}] {check['nom']} : {check['message']}")
    for cle, counts in result["synthese"].items():
        detail = ", ".join(f"{k} {v}" for k, v in counts.items() if v)
        print(f"  {cle} : {detail or 'aucun produit'}")
    print(f"  -> {config.portable(out)}")
    return result


def compare_all(names: list[str] | None = None) -> None:
    gate = SemanticGate.load() if config.SEMANTIC_VETO else None
    for folder in output_folders(names):
        if not (folder / "documents").is_dir():
            print(f"{folder.name}: aucun dossier documents/")
            continue
        compare_folder(folder, gate)


# --------------------------------------------------------------------- L9

def report_folder(folder: Path) -> Path | None:
    """Rejoue L9 : régénère rapport.pdf depuis summary.json et comparison.json."""
    summary_path = folder / "summary.json"
    comparison_path = folder / "comparison.json"
    if not comparison_path.is_file():
        print(f"{folder.name}: pas de comparison.json, lancer `concordance compare` d'abord")
        return None
    summary = json.loads(summary_path.read_text(encoding="utf-8")) \
        if summary_path.is_file() else {}
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    out = generate_report(summary, comparison, folder / "rapport.pdf")
    print(f"{folder.name}: -> {config.portable(out)}")
    return out


def report_all(names: list[str] | None = None) -> None:
    for folder in output_folders(names):
        report_folder(folder)


# ------------------------------------------------------------- révisions (BF9)

def inspect_folder(folder: Path, validated=None) -> None:
    """Lignes de chaque document avec leurs index d'origine, puis l'état de la
    dernière comparaison : tout ce qu'il faut pour écrire une révision."""
    if validated is None:
        validated, _ = load_documents(folder)
    comparison_path = folder / "comparison.json"

    for t, doc in validated.items():
        print(f"\n{t} : {doc.get('numero') or 'sans numéro'}")
        for i, ligne in enumerate(doc.get("lignes") or []):
            ref = ligne.get("reference") or "-"
            print(f"  [{i}] {ref:<14} {ligne.get('designation') or ''}"
                  f"  (qté {ligne.get('quantite')})")
        for ln in (ln for ln in canonicalize(doc, t) if ln.fusionnee):
            print(f"      fusion automatique : lignes {list(ln.indices)} "
                  f"(référence {ln.reference})")

    if not comparison_path.is_file():
        return
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    ambigus = comparison.get("ambiguites") or []
    if ambigus:
        print("\nAmbiguïtés en attente :")
        for a in ambigus:
            print(f"  {a['paire']} : BC « {a['reference']} » : {a['motif']}")
            for c in a["candidats"]:
                print(f"      candidat [{c.get('lignes_source', c['index'])}] "
                      f"{c.get('reference') or '-'}  {c.get('designation') or ''}")
    en_trop = [p for p in comparison.get("produits") or []
               if p.get("statut") == "en_trop"]
    if en_trop:
        print("\nEn trop :")
        for p in en_trop:
            for t, ligne in p["lignes"].items():
                print(f"  {t} lignes {ligne['lignes_source']} : "
                      f"{p.get('reference') or '-'}  {p.get('designation') or ''}")


def revise_folder(folder: Path, revisions: dict | None) -> int:
    """Rejoue L8 sous révisions de l'opérateur, réécrit comparison.json et le
    rapport. Sans révisions, affiche seulement les lignes et leurs index."""
    validated, _ = load_documents(folder)
    if len(validated) < 2:
        print(f"{folder.name}: {len(validated)} document(s), comparaison impossible")
        return 1

    if revisions is None:
        inspect_folder(folder, validated)
        return 0

    gate = SemanticGate.load() if config.SEMANTIC_VETO else None
    try:
        result = comparison_to_dict(
            compare_analysis(validated, gate, overrides=revisions))
    except OverrideError as exc:
        print(f"révision refusée : {exc}")
        return 1

    out = folder / "comparison.json"
    _write_json(out, result)
    t = result["totaux"]
    print(f"{folder.name}: {t['conformes']}/{t['produits']} conformes, "
          f"{t['ecarts']} écart(s), {t['ambigus']} ambigu(s)  -> {out}")

    # Le rapport est une projection : on le rejoue comme `report` le ferait.
    summary_path = folder / "summary.json"
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["comparaison"] = t
        try:
            rapport = generate_report(summary, result, folder / "rapport.pdf")
            summary["rapport"] = config.portable(rapport)
            print(f"  rapport régénéré : {summary['rapport']}")
        except Exception as exc:
            summary["rapport"], summary["rapport_erreur"] = None, str(exc)
            print(f"  ! rapport non régénéré : {exc}")
        _write_json(summary_path, summary)
    return 0
