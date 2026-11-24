"""Comparaison de deux lignes déjà rapprochées.

Rien n'est recalculé ni redérivé : les valeurs comparées sont celles que L7 a
validées et, le cas échéant, reconstruites. Une remise non étiquetée a déjà été
retrouvée en amont ; ici on compare ce qui est écrit.

La comparaison est pilotée par la présence des champs, pas par le type du
document. Un champ absent d'un côté rend son axe non comparable — ce n'est pas
un écart. Un BL sans prix ne produit donc aucun écart de prix, sans qu'aucune
règle propre au BL n'ait à être écrite.
"""

from decimal import Decimal

from concordance.validation.tolerance import Tolerance, infer_quantum, quantum_of

# Ordre d'affichage et correspondance avec le type de résultat persisté.
AXES = (
    ("quantite", "QUANTITE"),
    ("prixUnitaireHT", "PRIX"),
    ("tauxRemise", "REMISE"),
    ("montantHT", "MONTANT"),
)

CONFORME = "conforme"
ECART = "écart"
NON_COMPARABLE = "non_comparable"


def combined_tolerance(*docs):
    """Tolérance commune à plusieurs documents : on retient le pas d'affichage
    le plus grossier. Un document imprimé au centime ne peut pas être jugé avec
    la finesse d'un document imprimé au millime."""
    quanta = [infer_quantum(d) for d in docs if d]
    return Tolerance(max(quanta) if quanta else infer_quantum({}))


def units_conflict(a, b):
    """Vrai seulement si les deux unités sont connues et différentes. Une unité
    absente d'un côté n'est qu'une information manquante ; deux unités
    contradictoires rendent les quantités incomparables."""
    return (a.unite_norm is not None and b.unite_norm is not None
            and a.unite_norm != b.unite_norm)


def _tolerance_for(champ, tol, a, b, reference):
    if champ == "quantite":
        return Decimal(0)                       # égalité stricte, valeur numérique
    if champ == "tauxRemise":
        return max(quantum_of(a, Decimal("0.01")), quantum_of(b, Decimal("0.01")))
    return tol.terms(2, reference)              # deux valeurs imprimées face à face


def compare_lines(ref, cmp_, tol):
    """Retourne un axe de comparaison par champ, dans l'ordre d'affichage."""
    conflit = units_conflict(ref, cmp_)
    axes = []
    for champ, type_resultat in AXES:
        a, b = getattr(ref, champ), getattr(cmp_, champ)
        axe = {
            "champ": champ,
            "type": type_resultat,
            "valeurReference": a,
            "valeurComparee": b,
            "ecart": None,
            "tolerance": None,
            "statut": NON_COMPARABLE,
            "motif": None,
        }
        if champ == "quantite" and conflit:
            axe["motif"] = (f"unités différentes : {ref.unite_norm} / {cmp_.unite_norm}")
            axes.append(axe)
            continue
        if a is None or b is None:
            axe["motif"] = "valeur absente d'un des deux documents"
            axes.append(axe)
            continue
        limite = _tolerance_for(champ, tol, a, b, a)
        ecart = abs(a - b)
        axe["ecart"] = ecart
        axe["ecart_signe"] = b - a          # comparé − référence : signe = sens
        axe["tolerance"] = limite
        axe["statut"] = CONFORME if ecart <= limite else ECART
        # Une quantité livrée inférieure au BC est une livraison partielle —
        # un fait courant du commerce ; une quantité supérieure est une
        # sur-livraison, autrement plus grave. Même statut d'écart, mais la
        # nature les distingue pour le rapport et l'interface.
        if champ == "quantite" and axe["statut"] == ECART:
            axe["nature"] = "SUR_LIVRAISON" if b > a else "SOUS_LIVRAISON"
        axes.append(axe)
    return axes


def line_status(axes):
    """Statut d'ensemble d'une paire de lignes."""
    if any(a["statut"] == ECART for a in axes):
        return ECART
    if any(a["statut"] == CONFORME for a in axes):
        return CONFORME
    return NON_COMPARABLE
