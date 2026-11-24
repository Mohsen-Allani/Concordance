"""Rapport PDF (BF10) — composition HTML/CSS rendue par WeasyPrint.

Le rapport est une projection de comparison.json et summary.json : il ne
recalcule rien. Toute divergence entre le rapport et les JSON serait un bug de
présentation, jamais une différence de fond — les deux artefacts restent donc
mutuellement vérifiables.

Le gabarit reçoit un contexte déjà mis en forme (build_context) : le HTML ne
contient aucune logique métier, seulement de l'affichage.
"""

import json
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from concordance import config

_TEMPLATES = Path(__file__).parent / "templates"

# Libellés d'affichage. Les clés internes (statuts, champs) restent la seule
# vérité ; le rapport ne fait que les traduire.
_STATUTS = {
    "conforme": ("Conforme", "ok"),
    "écart": ("Écart", "err"),
    "manquant": ("Manquant", "err"),
    "en_trop": ("En trop", "err"),
    "ambigu": ("À réviser", "warn"),
    "non_comparable": ("Non comparé", "mut"),
}
_VERDICTS_L7 = {"ok": "Validée", "corrected": "Corrigée", "review": "À réviser"}
_CHAMPS = {
    "quantite": "Quantité",
    "prixUnitaireHT": "Prix unitaire HT",
    "tauxRemise": "Remise (%)",
    "montantHT": "Montant HT",
}
_NATURES = {"SOUS_LIVRAISON": "sous-livraison", "SUR_LIVRAISON": "sur-livraison"}
_CHECKS = {"ok": ("Conforme", "ok"), "warning": ("Avertissement", "warn")}


def _statut(cle):
    label, css = _STATUTS.get(cle, (cle or "—", "mut"))
    return {"cle": cle, "label": label, "css": css}


def _verdict_global(comparison):
    if comparison.get("statut") == "impossible":
        return {"label": "Comparaison impossible", "css": "err",
                "detail": comparison.get("message", "")}
    t = comparison["totaux"]
    if t["ambigus"]:
        n = t["ambigus"]
        return {"label": "Révision requise", "css": "warn",
                "detail": f"{n} appariement{'s' if n > 1 else ''} à trancher"}
    if t["ecarts"]:
        n = t["ecarts"]
        return {"label": "Écarts détectés", "css": "err",
                "detail": f"{n} écart{'s' if n > 1 else ''} sur {t['produits']} produits"}
    return {"label": "Conforme", "css": "ok",
            "detail": f"{t['produits']} produits · aucun écart"}


def _fmt_qte(v):
    """Quantité sans décimales inutiles : « 4.000 » -> « 4 » (contrat commun
    avec l'interface web)."""
    if v is None:
        return None
    s = str(v)
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s.replace(".", ",")


def _fmt_montant(v):
    """Montant à 3 décimales fixes, virgule décimale (convention TND)."""
    if v is None:
        return None
    try:
        return f"{Decimal(str(v)):.3f}".replace(".", ",")
    except InvalidOperation:
        return str(v)


def _fmt_taux(v):
    """Taux nu, sans zéros inutiles (contrat commun avec l'interface web)."""
    return _fmt_qte(v)


def _cellule(ligne):
    """Ligne d'un document dans le registre : mêmes colonnes que le site."""
    if not ligne:
        return None
    return {"reference": ligne.get("reference") or "—",
            "designation": ligne.get("designation") or "—",
            "qte": _fmt_qte(ligne.get("quantite")),
            "unite": ligne.get("unite"),
            "pu": _fmt_montant(ligne.get("prixUnitaireHT")),
            "remise": _fmt_taux(ligne.get("tauxRemise")),
            "montant": _fmt_montant(ligne.get("montantHT")),
            "fusionnee": bool(ligne.get("fusionnee"))}


# ---------- synthèse des montants (miroir de la vue web) --------------------

_TOTAUX_CHAMPS = [
    ("totalHT",      "Total HT",      "money"),
    ("remiseTotale", "Remise totale", "money"),
    ("netHT",        "Net HT",        "money"),
    ("tauxTVA",      "Taux TVA (%)",  "rate"),
    ("montantTVA",   "Montant TVA",   "money"),
    ("timbreFiscal", "Timbre fiscal", "money"),
    ("totalTTC",     "Total TTC",     "money"),
    ("netAPayer",    "Net à payer",   "money"),
]

_ORDRE_DOCS = {"BC": 0, "BL": 1, "Facture": 2}


def _dec(v):
    if v is None or str(v).strip() == "":
        return None
    try:
        return Decimal(str(v))
    except InvalidOperation:
        return None


def _infos_documents(summary):
    """{type: {"totaux": …, "devise": …}} lu depuis summary. Les résumés
    antérieurs à ce champ sont complétés depuis le fichier de validation du
    document (repli), afin qu'un simple replay du rapport suffise."""
    infos = {}
    for d in summary.get("documents", []):
        tot, dev = d.get("totaux"), d.get("devise")
        if tot is None and d.get("document"):
            chemin = str(d["document"])
            if chemin.endswith(".json"):
                vp = config.ROOT / (chemin[:-len(".json")] + "_validation.json")
                try:
                    corrected = json.loads(vp.read_text(encoding="utf-8")) \
                        .get("corrected_document") or {}
                    tot = corrected.get("totaux")
                    dev = dev or corrected.get("devise")
                except (OSError, ValueError):
                    pass
        infos[d.get("type")] = {"totaux": tot or {}, "devise": dev}
    return infos


def _check_total(kind, valeurs):
    """Contrôle croisé d'un champ de totaux. BC en référence quand il porte le
    champ ; tolérance dérivée de la précision d'affichage la plus grossière,
    plancher relatif 0,05 % sur les montants — mêmes règles que la vue web."""
    presentes = [(t, _dec(v)) for t, v in valeurs if _dec(v) is not None]
    if len(presentes) < 2:
        return {"label": "Non comparé", "css": "mut"}
    ref = next(((t, v) for t, v in presentes if t == "BC"), presentes[0])
    exp = min(-v.as_tuple().exponent if v.as_tuple().exponent < 0 else 0
              for _, v in presentes)
    quantum = Decimal(1).scaleb(-exp)
    tol = quantum if kind == "rate" else max(quantum,
                                             abs(ref[1]) * Decimal("0.0005"))
    worst = Decimal(0)
    for t, v in presentes:
        if (t, v) == ref:
            continue
        delta = v - ref[1]
        if abs(delta) > tol and abs(delta) > abs(worst):
            worst = delta
    if worst == 0:
        return {"label": "Conforme", "css": "ok"}
    signe = "+" if worst > 0 else "−"
    abs_ = _fmt_taux(abs(worst)) if kind == "rate" else _fmt_montant(abs(worst))
    return {"label": f"Écart {signe}{abs_}", "css": "err"}


def _montants(summary, comparison):
    """Section « Synthèse des montants » : un champ par ligne, un document par
    colonne, contrôle croisé en dernière colonne."""
    infos = _infos_documents(summary)
    types = sorted(comparison.get("documents", {}),
                   key=lambda t: _ORDRE_DOCS.get(t, 3))
    docs = []
    for t in types:
        meta = comparison["documents"].get(t, {})
        docs.append({"type": t, "numero": meta.get("numero") or "—",
                     "date": meta.get("date") or "—",
                     "lignes": meta.get("lignes"),
                     "totaux": infos.get(t, {}).get("totaux") or {}})
    lignes = []
    for cle, label, kind in _TOTAUX_CHAMPS:
        if not any(d["totaux"].get(cle) is not None for d in docs):
            continue
        cellules = []
        for d in docs:
            v = d["totaux"].get(cle)
            cellules.append(None if v is None else
                            (_fmt_taux(v) if kind == "rate" else _fmt_montant(v)))
        lignes.append({"label": label, "cellules": cellules,
                       "resultat": _check_total(
                           kind, [(d["type"], d["totaux"].get(cle)) for d in docs])})
    devise = next((i.get("devise") for i in infos.values() if i.get("devise")),
                  None)
    return {"docs": docs, "lignes": lignes, "devise": devise} if lignes else None


def _ecart_net(comparison):
    """Écart net facturé / commandé sur les lignes rapprochées (pied de la
    synthèse) : somme des écarts signés de montant HT sur BC↔Facture, plus le
    montant BC des produits non facturés — même calcul que la vue web."""
    if "Facture" not in comparison.get("documents", {}):
        return None
    delta, non_facture = Decimal(0), Decimal(0)
    for p in comparison.get("produits", []):
        paire = (p.get("paires") or {}).get("BC↔Facture")
        if not paire:
            continue
        if paire.get("statut") == "manquant":
            m = _dec((p["lignes"].get("BC") or {}).get("montantHT"))
            if m is not None:
                non_facture += m
        for ax in paire.get("axes") or []:
            if ax.get("champ") == "montantHT" and ax.get("statut") == "écart":
                e = _dec(ax.get("ecart_signe"))
                if e is not None:
                    delta += e
    bits = []
    if delta:
        bits.append("surfacturation" if delta > 0 else "sous-facturation")
    if non_facture:
        bits.append(f"{_fmt_montant(non_facture)} non facturé")
    return {"delta": (("+" if delta > 0 else "−") + _fmt_montant(abs(delta)))
                     if delta else None,
            "css": "err" if delta else "mut",
            "mention": " · ".join(bits)}


def _axes(axes):
    rows = []
    for a in axes:
        motif = a.get("motif")
        if a.get("nature"):
            motif = _NATURES.get(a["nature"], a["nature"])
        rows.append({
            "champ": _CHAMPS.get(a["champ"], a["champ"]),
            "reference": a["valeurReference"],
            "comparee": a["valeurComparee"],
            "ecart": a.get("ecart_signe", a.get("ecart")),
            "tolerance": a.get("tolerance"),
            "statut": _statut(a["statut"]),
            "motif": motif,
        })
    return rows


def _ligne_amb(source, champs):
    """Ligne d'un tableau d'ambiguïté. Les anciens comparison.json ne portent
    pas encore les champs détaillés : ils s'affichent alors vides plutôt que
    de faire échouer le rendu."""
    champs = champs or {}
    return {"source": source,
            "reference": champs.get("reference") or "—",
            "designation": champs.get("designation") or "—",
            "quantite": _fmt_qte(champs.get("quantite")),
            "unite": champs.get("unite"),
            "pu": _fmt_montant(champs.get("prixUnitaireHT")),
            "montant": _fmt_montant(champs.get("montantHT"))}


def build_context(summary, comparison, generated=None):
    """Assemble le contexte du gabarit à partir des deux JSON de l'analyse."""
    generated = generated or datetime.now()
    paires = comparison.get("paires", [])
    types_presents = list(comparison.get("documents", {}).keys())

    # --- documents analysés ------------------------------------------------
    verdicts = {d["type"]: d for d in summary.get("documents", [])}
    documents = []
    for t, meta in comparison.get("documents", {}).items():
        v = verdicts.get(t, {})
        documents.append({
            "type": t,
            "numero": meta.get("numero") or "—",
            "date": meta.get("date") or "—",
            "lignes": meta.get("lignes"),
            "verdict": _VERDICTS_L7.get(v.get("verdict"), v.get("verdict", "—")),
            "confiance": v.get("confidence"),
        })

    # --- synthèse et contrôles d'en-tête -----------------------------------
    synthese = []
    for cle in paires:
        counts = comparison["synthese"].get(cle, {})
        synthese.append({
            "paire": cle.replace("↔", " ↔ "),
            "counts": [{"label": _STATUTS[k][0], "css": _STATUTS[k][1], "n": v}
                       for k, v in counts.items() if v],
        })

    entete = []
    for c in comparison.get("entete", []):
        if c["statut"] == "ignoré":
            continue
        label, css = _CHECKS.get(c["statut"], (c["statut"], "mut"))
        entete.append({"nom": c["nom"].capitalize(), "message": c["message"],
                       "statut": {"label": label, "css": css}})

    # --- registre : un bloc par produit, une ligne par document -----------
    _PAIRE_DE = {"BL": "BC↔BL", "Facture": "BC↔Facture"}
    _MANQUE = {"BL": "Non livré", "Facture": "Non facturé"}
    ordre_docs = sorted(types_presents, key=lambda t: _ORDRE_DOCS.get(t, 3))
    produits, ecarts, absents, vus = [], [], [], set()
    for num, p in enumerate(comparison.get("produits", []), start=1):
        fantomes = {}
        for t in ordre_docs:
            if t == "BC" or p["lignes"].get(t):
                continue
            paire = p["paires"].get(_PAIRE_DE.get(t, ""))
            if not paire:
                continue
            if paire.get("statut") == "manquant":
                fantomes[t] = _MANQUE[t]
            elif paire.get("statut") == "ambigu":
                fantomes[t] = "Ambigu — à trancher"
        row = {
            "num": num,
            "reference": p.get("reference") or "—",
            "designation": p.get("designation") or "—",
            "cellules": {t: _cellule(p["lignes"].get(t)) for t in ordre_docs},
            "fantomes": fantomes,
            "paires": {},
            "statut": _statut(p["statut"]),
        }
        for cle in paires:
            paire = p["paires"].get(cle)
            row["paires"][cle] = _statut(paire["statut"]) if paire else None
        produits.append(row)

        # Détail : uniquement les paires effectivement en écart. Les axes
        # conformes du même produit y figurent aussi — l'écart se lit dans
        # son contexte, pas isolé.
        if p["statut"] == "écart":
            blocs = []
            for cle in paires:
                paire = p["paires"].get(cle)
                if paire and paire.get("statut") == "écart":
                    blocs.append({"paire": cle.replace("↔", " ↔ "),
                                  "axes": _axes(paire.get("axes") or []),
                                  "preuves": paire.get("preuves") or []})
            ecarts.append({"num": num, "reference": row["reference"],
                           "designation": row["designation"], "blocs": blocs})

        elif p["statut"] in ("manquant", "en_trop"):
            present = [t for t in types_presents if p["lignes"].get(t)]
            absent = [t for t in types_presents if not p["lignes"].get(t)]
            t0 = present[0] if present else None
            ligne = p["lignes"].get(t0) if t0 else {}
            # Une même ligne d'origine ne figure qu'une fois (unicité par
            # document + lignes d'origine — même règle que la vue web).
            cle_vu = (t0, tuple((ligne or {}).get("lignes_source") or []))
            if cle_vu in vus:
                continue
            vus.add(cle_vu)
            c = _cellule(ligne) or {}
            absents.append({
                "num": num,
                "doc": t0 or "—",
                "reference": row["reference"],
                "designation": row["designation"],
                "quantite": c.get("qte"),
                "unite": c.get("unite"),
                "pu": c.get("pu"),
                "remise": c.get("remise"),
                "montant": c.get("montant"),
                "statut": row["statut"],
                "constat": (f"Présent au {', '.join(present)} — "
                            f"absent du {', '.join(absent)}"),
            })

    # --- ambiguïtés : les deux faces de chaque litige ----------------------
    ambiguites = []
    for a in comparison.get("ambiguites", []):
        gauche, droite = a["paire"].split("↔")
        lignes = [_ligne_amb(gauche, a.get("ligne_reference"))]
        for c in a["candidats"]:
            lignes.append(_ligne_amb(f"{droite} — candidat", c))
        ambiguites.append({"paire": a["paire"].replace("↔", " ↔ "),
                           "motif": a["motif"], "lignes": lignes})

    return {
        "titre": "Rapport de comparaison",
        "fichier": summary.get("pdf", "—"),
        "genere_le": generated.strftime("%d/%m/%Y %H:%M"),
        "verdict": _verdict_global(comparison),
        "reference_doc": comparison.get("document_reference", "BC"),
        "types_presents": ordre_docs,
        "montants": _montants(summary, comparison),
        "ecart_net": _ecart_net(comparison),
        "documents": documents,
        "paires": [c.replace("↔", " ↔ ") for c in paires],
        "paires_cles": paires,
        "synthese": synthese,
        "entete": entete,
        "produits": produits,
        "ecarts": ecarts,
        "absents": absents,
        "ambiguites": ambiguites,
    }


def render_html(context):
    env = Environment(loader=FileSystemLoader(_TEMPLATES),
                      autoescape=True)   # le gabarit se termine par .j2 : select_autoescape ne le reconnaîtrait pas
    return env.get_template("rapport.html.j2").render(**context)


_WEASYPRINT = None      # None : pas encore tenté · False : indisponible
_ERREUR = None


def _weasyprint():
    """Importe WeasyPrint une seule fois, succès comme échec.

    Python ne met pas en cache les imports ratés : sans cette mémoïsation,
    WeasyPrint réémettrait sa bannière d'erreur sur stderr à chaque document
    d'un même lot. L'import est différé pour que le reste du pipeline reste
    utilisable sans les bibliothèques système de Pango.
    """
    global _WEASYPRINT, _ERREUR
    if _WEASYPRINT is None:
        dll = getattr(config, "WEASYPRINT_DLL_DIR", None)
        if dll and Path(dll).is_dir():
            # Doit être posé avant l'import : WeasyPrint lit cette variable au
            # chargement de sa couche FFI, pas à l'appel de write_pdf.
            os.environ.setdefault("WEASYPRINT_DLL_DIRECTORIES", str(dll))
        try:
            from weasyprint import CSS, HTML
            _WEASYPRINT = (HTML, CSS)
        except Exception as exc:
            lignes = [l for l in str(exc).strip().splitlines() if l.strip()]
            _ERREUR = lignes[0] if lignes else exc.__class__.__name__
            _WEASYPRINT = False
    return _WEASYPRINT


def generate_report(summary, comparison, out_pdf: Path) -> Path:
    """Rend le rapport PDF. Lève RuntimeError si Pango est introuvable.

    L'appelant décide du sort de l'erreur : le pipeline la signale sans
    interrompre le lot, l'extraction déjà payée étant enregistrée en amont.
    """
    moteur = _weasyprint()
    if moteur is False:
        raise RuntimeError(
            f"WeasyPrint indisponible : {_ERREUR}. "
            "Installer Pango (MSYS2 : pacman -S mingw-w64-x86_64-pango) et "
            "renseigner WEASYPRINT_DLL_DIR dans .env (Windows).")
    HTML, CSS = moteur

    html = render_html(build_context(summary, comparison))
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html, base_url=str(_TEMPLATES)).write_pdf(
        str(out_pdf), stylesheets=[CSS(str(_TEMPLATES / "rapport.css"))])
    return out_pdf
