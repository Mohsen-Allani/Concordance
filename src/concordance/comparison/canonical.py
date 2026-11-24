"""Projection des documents validés en lignes canoniques comparables.

Les trois types de documents n'ont pas les mêmes champs : un BL ne porte
généralement pas de prix, une facture porte une TVA par ligne. Plutôt que de
tester le type du document dans chaque comparaison, chaque ligne est projetée
dans une structure unique où un champ absent vaut None. La comparaison est
ensuite pilotée par la présence des champs, jamais par le type du document.

Rien n'est jamais supprimé d'une désignation : les codes et spécifications
qu'elle contient sont recopiés dans les clés candidates. Une clé surnuméraire
est sans effet — elle ne rencontrera aucune contrepartie — tandis qu'une
suppression détruirait une information qui n'existe nulle part ailleurs.
"""

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

# Séparateurs de dimension unifiés : 4.8X16, 4,8*16 et 4.8×16 désignent le même
# article selon le fournisseur qui l'imprime.
_DIM = {"×": "*", "X": "*", "·": "."}

# Unités connues ramenées à une forme unique. Une unité inconnue est conservée
# telle quelle plutôt que devinée ; ML n'est volontairement pas mappé, il
# désigne aussi bien le millilitre que le mètre linéaire.
_UNITS = {
    "PC": "PCE", "PCE": "PCE", "PCS": "PCE", "PIECE": "PCE", "PIECES": "PCE",
    "U": "PCE", "UN": "PCE", "UNITE": "PCE", "UNITES": "PCE", "EA": "PCE",
    "KG": "KG", "KGS": "KG", "KILO": "KG", "KILOS": "KG",
    "G": "G", "GR": "G", "GRAMME": "G", "GRAMMES": "G",
    "L": "L", "LT": "L", "LITRE": "L", "LITRES": "L",
    "M": "M", "MT": "M", "METRE": "M", "METRES": "M", "MTR": "M",
    "M2": "M2", "M²": "M2", "M3": "M3", "M³": "M3",
    "BTE": "BTE", "BOITE": "BTE", "BOX": "BTE",
    "JEU": "JEU", "JEUX": "JEU", "LOT": "LOT",
}

_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9./*+\-]*")

# Étiquettes qui précèdent un code sans en faire partie : « REF 2110160 »
# désigne le code 2110160. Sans ce retrait, la suppression des espaces
# souderait l'étiquette au code (REF2110160) et la clé ne rencontrerait
# jamais sa contrepartie. Le retrait exige un séparateur après l'étiquette :
# « REFA123 » n'est pas touché, rien ne prouve que REF y soit une étiquette.
_NOISE_LABEL = re.compile(r"^(?:REF|SPEC|NO?|NUM)[\s.:°#-]+", re.IGNORECASE)


def strip_label(value):
    """Retire une étiquette de tête (« ref », « n° »...) d'un code déclaré."""
    if value is None:
        return None
    return _NOISE_LABEL.sub("", str(value).strip()) or None


def _deaccent(text):
    stripped = unicodedata.normalize("NFKD", text)
    return "".join(c for c in stripped if not unicodedata.combining(c))


def normalize_key(value):
    """Forme canonique d'un code : casse, accents, séparateurs et zéros de tête
    neutralisés, afin que « ref 81105 TN » et « 81105TN » coïncident."""
    if value is None:
        return None
    text = _deaccent(str(value)).upper()
    for src, dst in _DIM.items():
        text = text.replace(src, dst)
    text = text.replace("X", "*")
    text = re.sub(r"[\s_,]+", "", text)
    text = re.sub(r"^0+(?=\d)", "", text)
    return text or None


def normalize_identifier(value):
    """Forme canonique d'un identifiant administratif (matricule fiscal, numéro
    de pièce). Toute ponctuation est retirée : « 31320K/A/M000 » et
    « 31320K/A/M/000 » désignent le même contribuable, et l'emplacement des
    barres varie d'un document à l'autre."""
    if value is None:
        return None
    text = re.sub(r"[^A-Z0-9]+", "", _deaccent(str(value)).upper())
    text = re.sub(r"^0+(?=\d)", "", text)
    return text or None


def normalize_unit(value):
    if value is None:
        return None
    text = re.sub(r"[\s.]+", "", _deaccent(str(value)).upper())
    return _UNITS.get(text, text) or None


def normalize_designation(value):
    """Désignation ramenée à une suite de mots comparables. Le texte d'origine
    est conservé intact dans la ligne canonique ; ceci n'en est qu'un index."""
    if value is None:
        return ""
    text = _deaccent(str(value)).upper()
    for src, dst in _DIM.items():
        text = text.replace(src, dst)
    text = re.sub(r"[^A-Z0-9./*+\-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_candidate_code(token):
    """Un fragment de désignation susceptible d'être un code ou une
    spécification, donc de servir de pont entre deux documents. Les nombres
    courts sont écartés : « 100 » se rencontre partout et n'identifie rien."""
    if len(token) < 3 or not any(c.isdigit() for c in token):
        return False
    if token.isdigit() and len(token) < 4:
        return False
    return True


def extract_codes(designation):
    """Codes et spécifications candidats trouvés dans une désignation."""
    found = []
    for raw in _TOKEN.findall(normalize_designation(designation)):
        key = normalize_key(raw)
        if key and _is_candidate_code(key) and key not in found:
            found.append(key)
    return found


@dataclass
class LigneCanonique:
    type_document: str
    indices: tuple = ()                  # lignes d'origine, plusieurs si fusion
    reference: str = None                # référence lue, non normalisée
    cles: frozenset = frozenset()        # références normalisées, pont exact
    ponts: frozenset = frozenset()       # codes trouvés dans la désignation
    designation: str = ""
    designation_norm: str = ""
    unite: str = None
    unite_norm: str = None
    quantite: Decimal = None
    prixUnitaireHT: Decimal = None
    tauxRemise: Decimal = None
    montantHT: Decimal = None
    fusionnee: bool = False

    @property
    def codes(self):
        """Tous les codes portés par la ligne, référence et désignation."""
        return set(self.cles) | set(self.ponts)

    @property
    def haystack(self):
        """Texte dans lequel un code venu de l'autre document est recherché.

        Les espaces sont retirés et les codes concaténés : « 4 MM » et « 4MM »
        deviennent alors la même chaîne, et « 12*40 » se retrouve dans
        « M12*40 ». La variabilité de frappe d'un fournisseur à l'autre porte
        presque toujours sur un espace ou un préfixe.
        """
        return (self.designation_norm.replace(" ", "")
                + "|" + "|".join(sorted(self.codes)))

    def libelle(self):
        return self.reference or self.designation or f"ligne {self.indices}"


def _to_line(doc_type, index, raw):
    declared = raw.get("referencesDansDesignation") or []
    ponts = {normalize_key(strip_label(r)) for r in declared}
    ponts.discard(None)
    ponts |= set(extract_codes(raw.get("designation")))
    cle = normalize_key(strip_label(raw.get("reference")))
    ponts.discard(cle)
    return LigneCanonique(
        type_document=doc_type,
        indices=(index,),
        reference=raw.get("reference"),
        cles=frozenset({cle}) if cle else frozenset(),
        ponts=frozenset(ponts),
        designation=raw.get("designation") or "",
        designation_norm=normalize_designation(raw.get("designation")),
        unite=raw.get("unite"),
        unite_norm=normalize_unit(raw.get("unite")),
        quantite=raw.get("quantite"),
        prixUnitaireHT=raw.get("prixUnitaireHT"),
        tauxRemise=raw.get("tauxRemise"),
        montantHT=raw.get("montantHT"),
    )


def _sum(values):
    present = [v for v in values if v is not None]
    return sum(present) if present else None


def _unanimous(values):
    """Valeur commune à toutes les lignes fusionnées, sinon None : une moyenne
    inventerait un prix qui n'est imprimé nulle part."""
    present = [v for v in values if v is not None]
    if not present or len(present) != len(values):
        return None
    return present[0] if all(v == present[0] for v in present) else None


def _merge(group):
    """Fusionne des lignes partageant la même référence. Les quantités et les
    montants s'additionnent ; un prix unitaire divergent devient inconnu plutôt
    que moyenné."""
    if len(group) == 1:
        return group[0]
    first = group[0]
    return LigneCanonique(
        type_document=first.type_document,
        indices=tuple(i for ln in group for i in ln.indices),
        reference=first.reference,
        cles=frozenset().union(*(ln.cles for ln in group)),
        ponts=frozenset().union(*(ln.ponts for ln in group)),
        designation=max((ln.designation for ln in group), key=len),
        designation_norm=max((ln.designation_norm for ln in group), key=len),
        unite=first.unite,
        unite_norm=_unanimous([ln.unite_norm for ln in group]),
        quantite=_sum([ln.quantite for ln in group]),
        prixUnitaireHT=_unanimous([ln.prixUnitaireHT for ln in group]),
        tauxRemise=_unanimous([ln.tauxRemise for ln in group]),
        montantHT=_sum([ln.montantHT for ln in group]),
        fusionnee=True,
    )


def canonicalize(doc, doc_type):
    """Document validé -> lignes canoniques, doublons de référence fusionnés.

    La fusion n'a lieu que sur une référence explicite et identique. Deux lignes
    sans référence ne sont jamais fusionnées sur leur seule désignation : rien
    ne garantit qu'il s'agisse du même article.
    """
    lines = [_to_line(doc_type, i, raw)
             for i, raw in enumerate(doc.get("lignes") or [])]

    order, buckets, loose = [], {}, []
    for line in lines:
        key = next(iter(line.cles), None)
        if key is None:
            loose.append(line)
            order.append(("loose", len(loose) - 1))
            continue
        if key not in buckets:
            buckets[key] = []
            order.append(("key", key))
        buckets[key].append(line)

    merged = []
    for kind, ref in order:
        merged.append(loose[ref] if kind == "loose" else _merge(buckets[ref]))
    return merged
