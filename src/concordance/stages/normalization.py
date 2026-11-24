import re
from decimal import Decimal, InvalidOperation

from dateutil import parser as dateparser

_DECIMAL_LINE_FIELDS = ("quantite", "prixUnitaireHT", "tauxRemise", "montantHT", "tauxTVA")
_DATE_LINE_FIELDS = ("dateLivraison",)
_DECIMAL_TOTAL_FIELDS = ("totalHT", "remiseTotale", "netHT", "tauxTVA",
                         "montantTVA", "timbreFiscal", "totalTTC", "netAPayer")


def parse_decimal(raw):
    if raw is None:
        return None
    s = str(raw).replace("\u00a0", " ").strip()
    cleaned = re.sub(r"[^0-9,.\-]", "", s)
    if cleaned in ("", "-", ".", ","):
        return None
    has_comma, has_dot = "," in cleaned, "." in cleaned
    if has_comma and has_dot:
        if cleaned.rfind(",") > cleaned.rfind("."):      # comma is decimal
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:                                            # dot is decimal
            cleaned = cleaned.replace(",", "")
    elif has_comma:
        cleaned = cleaned.replace(",", ".")
    elif cleaned.count(".") > 1:                         # multiple dots = thousands
        cleaned = cleaned.replace(".", "")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def parse_date(raw):
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        return dateparser.parse(s, dayfirst=True).date()
    except (ValueError, OverflowError, TypeError):
        return None


def _normalize_line(line):
    out = dict(line)
    for f in _DECIMAL_LINE_FIELDS:
        if f in out:
            out[f] = parse_decimal(out.get(f))
    for f in _DATE_LINE_FIELDS:
        if f in out:
            out[f] = parse_date(out.get(f))
    return out


def normalize_document(doc):
    out = dict(doc)
    out["date"] = parse_date(doc.get("date"))
    out["lignes"] = [_normalize_line(l) for l in (doc.get("lignes") or [])]
    if isinstance(doc.get("totaux"), dict):
        out["totaux"] = {k: (parse_decimal(v) if k in _DECIMAL_TOTAL_FIELDS else v)
                         for k, v in doc["totaux"].items()}
    if isinstance(doc.get("referencesLiees"), dict):
        refs = dict(doc["referencesLiees"])
        for k in ("dateBC", "dateBL"):
            if k in refs:
                refs[k] = parse_date(refs[k])
        out["referencesLiees"] = refs
    return out
