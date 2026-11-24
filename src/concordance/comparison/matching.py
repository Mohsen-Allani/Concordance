"""Rapprochement des lignes entre deux documents.

Le problème n'est pas de comparer deux lignes, c'est de savoir lesquelles se
correspondent. Trois niveaux de preuve, du plus sûr au plus faible :

  1. clé      les deux lignes partagent une référence explicite
  2. pont     un code de l'une se retrouve dans l'autre — sa force dépend
              de sa rareté dans les documents, pas de sa longueur
  3. texte    similarité des désignations

Deux règles gouvernent l'ensemble :

  Aucune quantité, aucun prix n'intervient dans le rapprochement. Ce sont
  précisément les grandeurs dont on cherche les écarts : s'en servir pour
  apparier reviendrait à ne plus jamais détecter d'erreur.

  En cas d'égalité, on n'apparie pas. Un faux appariement coûte plus cher
  qu'un appariement manquant : il fabrique un écart de prix entre deux
  produits différents, que personne ne saura expliquer.

L'affectation est gloutonne par preuve décroissante, et non optimale au sens
d'un couplage biparti : chaque appariement reste ainsi explicable par sa seule
preuve, ce qu'un optimum global ne permet pas. Limitation assumée.
"""

from decimal import Decimal
from difflib import SequenceMatcher

from .semantic import SemanticGate

SEUIL_TEXTE = Decimal("0.62")      # en deçà, une similarité textuelle ne prouve rien
MARGE_AMBIGUITE = Decimal("0.05")  # deux candidats plus proches que cela ne sont pas départagés
LONGUEUR_PONT = 3                  # en deçà, un fragment n'identifie rien
LONGUEUR_PONT_FORT = 4             # garde-fou : un code de 3 caractères, même unique,
                                   # reste une preuve faible (documents courts)

# Les preuves sont hiérarchisées, non additionnées. Un code partagé l'emporte
# toujours sur une ressemblance de texte, si frappante soit-elle : deux articles
# voisins d'un même fournisseur ont presque la même désignation, et c'est
# précisément le code qui les distingue.
NIVEAU_CLE = 3        # référence explicite commune
NIVEAU_PONT_FORT = 2  # code partagé, unique de chaque côté
NIVEAU_PONT_FAIBLE = 1
NIVEAU_TEXTE = 0

try:                                                    # accélère et affine si présent
    from rapidfuzz.fuzz import token_set_ratio as _rf
except ImportError:                                     # sinon, repli sans dépendance
    _rf = None


def similarity(a, b):
    """Similarité de deux désignations normalisées, dans [0, 1]."""
    if not a or not b:
        return Decimal(0)
    if _rf is not None:
        return Decimal(str(_rf(a, b) / 100)).quantize(Decimal("0.001"))
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return Decimal(0)
    jaccard = Decimal(len(ta & tb)) / Decimal(len(ta | tb))
    ordered = SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio()
    return max(jaccard, Decimal(str(ordered))).quantize(Decimal("0.001"))


class Rarete:
    """Rareté d'un code au sein d'un document : nombre de lignes qui le portent.

    Un code n'identifie une ligne que s'il est rare. « 8.8 » présent sur six
    lignes est un attribut de famille, pas une preuve ; « A7X9 » présent sur
    une seule ligne de chaque côté est presque une signature. La rareté se
    mesure sur les documents en présence — elle est donc recalculée à chaque
    analyse, et un même code peut être fort ici et faible ailleurs.
    """

    def __init__(self, lines):
        self._lines = lines
        self._cache = {}

    def count(self, token):
        if token not in self._cache:
            self._cache[token] = sum(1 for ln in self._lines if token in ln.haystack)
        return self._cache[token]

    def is_common(self, token):
        """Attribut de famille : porté par plus de la moitié des lignes.
        Le critère ne s'applique qu'aux documents d'au moins 4 lignes — sur un
        document minuscule, « la moitié » ne veut rien dire."""
        n = len(self._lines)
        return n >= 4 and self.count(token) > n // 2


def _bridge(a, b):
    """Codes de l'une retrouvés dans l'autre, par recherche de sous-chaîne dans
    la désignation compactée : un préfixe ou un espace ne doit pas suffire à
    faire manquer un pont."""
    shared = set()
    for token in a.codes:
        if len(token) >= LONGUEUR_PONT and token in b.haystack:
            shared.add(token)
    for token in b.codes:
        if len(token) >= LONGUEUR_PONT and token in a.haystack:
            shared.add(token)
    return shared


def evaluate(a, b, rarete_a=None, rarete_b=None, gate=None):
    """Niveau de preuve et score d'une paire candidate.

    Le résultat est un triplet (niveau, score, preuves) : on compare d'abord
    les niveaux, et le score ne départage qu'à niveau égal.

    Le veto sémantique ne s'exerce qu'au niveau texte : un code partagé est un
    fait, l'avis d'un modèle n'est qu'une opinion et ne peut pas le renverser.
    """
    proofs = []
    text = similarity(a.designation_norm, b.designation_norm)

    shared_keys = a.cles & b.cles
    if shared_keys:
        proofs.append(f"référence commune : {', '.join(sorted(shared_keys))}")
        return NIVEAU_CLE, Decimal(1), proofs

    shared = _bridge(a, b)
    if shared:
        retained = {t for t in shared
                    if not (rarete_a and rarete_a.is_common(t))
                    and not (rarete_b and rarete_b.is_common(t))}
        ignored = shared - retained
        if ignored:
            proofs.append(f"codes trop répandus, ignorés : {', '.join(sorted(ignored))}")
        if retained:
            fort = any(
                len(t) >= LONGUEUR_PONT_FORT
                and (rarete_a is None or rarete_a.count(t) <= 1)
                and (rarete_b is None or rarete_b.count(t) <= 1)
                for t in retained)
            detail = ", ".join(
                f"{t} ({(rarete_a.count(t) if rarete_a else '?')}×/"
                f"{(rarete_b.count(t) if rarete_b else '?')}×)"
                for t in sorted(retained))
            proofs.append(f"code commun : {detail}")
            if text >= SEUIL_TEXTE:
                proofs.append(f"désignations proches ({text})")
            niveau = NIVEAU_PONT_FORT if fort else NIVEAU_PONT_FAIBLE
            return niveau, max(text, Decimal("0.70")), proofs

    if text >= SEUIL_TEXTE:
        if gate is not None and gate.rejects(a.designation, b.designation):
            return NIVEAU_TEXTE, Decimal(0), \
                ["veto sémantique : désignations de sens différent"]
        proofs.append(f"désignations proches ({text})")
        return NIVEAU_TEXTE, text, proofs

    return NIVEAU_TEXTE, Decimal(0), proofs


class Appariement:
    """Résultat du rapprochement d'un document cible sur le document de
    référence."""

    def __init__(self):
        self.paires = {}        # index référence -> (index cible, score, preuves)
        self.ambigus = []       # cas non tranchés, laissés à l'humain
        self.ref_seuls = []
        self.cible_seuls = []


def _fields(ln):
    """Champs d'une ligne tels qu'ils doivent figurer dans un enregistrement
    d'ambiguïté : l'opérateur tranche sur ces valeurs, elles doivent donc être
    sous ses yeux, pas dans un autre fichier."""
    return {"reference": ln.reference, "designation": ln.designation,
            "quantite": ln.quantite, "unite": ln.unite,
            "prixUnitaireHT": ln.prixUnitaireHT, "montantHT": ln.montantHT}


def _ambiguity(reference, cible, i, candidats, motif):
    """Enregistrement exploitable par l'écran de révision et le rapport : les
    index permettent de rejouer la comparaison avec la décision de l'opérateur,
    les champs permettent de la prendre."""
    return {
        "reference_index": i,
        "reference": reference[i].libelle(),
        "lignes_source": list(reference[i].indices),
        "ligne_reference": _fields(reference[i]),
        "motif": motif,
        "candidats": [{"index": j, "libelle": cible[j].libelle(),
                       "lignes_source": list(cible[j].indices),
                       **_fields(cible[j])}
                      for j in sorted(candidats)],
    }


def match(reference, cible, gate=None, resolutions=None, exclusions=None):
    """Rapproche `cible` sur `reference`, sans jamais consulter les nombres.

    `resolutions` : {index référence -> index cible} — décisions prises par
    l'opérateur sur des ambiguïtés antérieures. Elles priment sur tout : la
    comparaison est rejouée avec ces paires verrouillées d'emblée.

    `exclusions` : index cibles détachés par l'opérateur — retirés du jeu
    avant toute passe, ils ne peuvent ni être appariés ni servir de candidats
    à une ambiguïté, et ressortent orphelins (« en trop »).

    Une ambiguïté ne condamne que la ligne de référence disputée : ses
    candidats restent libres, car aucun d'eux ne lui a jamais été attribué.
    Les retirer du jeu affamerait un appariement légitime plus bas dans la
    liste et fabriquerait un « manquant » fantôme.
    """
    result = Appariement()
    exclusions = set(exclusions or ())
    libres_ref = set(range(len(reference)))
    libres_cible = set(range(len(cible))) - exclusions
    disputes = {}   # index référence -> motif

    rarete_ref = Rarete(reference)
    rarete_cible = Rarete(cible)

    # --- passe 0 : décisions de l'opérateur, verrouillées ------------------
    for i, j in sorted((resolutions or {}).items()):
        if i in libres_ref and j in libres_cible:
            result.paires[i] = (j, Decimal(1), ["résolu par l'opérateur"])
            libres_ref.discard(i)
            libres_cible.discard(j)

    # --- passe 1 : références exactes, preuve la plus forte ---------------
    for i in sorted(libres_ref):
        candidats = [j for j in sorted(libres_cible) if reference[i].cles & cible[j].cles]
        if not candidats:
            continue
        if len(candidats) > 1:
            disputes[i] = "plusieurs lignes portent la même référence"
            continue
        j = candidats[0]
        _, score, proofs = evaluate(reference[i], cible[j], rarete_ref, rarete_cible)
        result.paires[i] = (j, score, proofs)
        libres_ref.discard(i)
        libres_cible.discard(j)
    libres_ref -= set(disputes)

    # --- passe 2 : ponts et similarité, résolution globale ----------------
    # La grille couvre toutes les paires restantes, disputes comprises : les
    # lignes disputées y figurent pour le calcul des rivaux, mais ne sont
    # jamais affectées automatiquement.
    grid = {}
    for i in sorted(libres_ref | set(disputes)):
        for j in sorted(libres_cible):
            niveau, score, proofs = evaluate(reference[i], cible[j],
                                             rarete_ref, rarete_cible, gate)
            if score > 0:
                grid[(i, j)] = (niveau, score, proofs)

    ordre = sorted(grid.items(), key=lambda kv: (-kv[1][0], -kv[1][1], kv[0][0], kv[0][1]))
    for (i, j), (niveau, score, proofs) in ordre:
        if i not in libres_ref or j not in libres_cible:
            continue
        rivaux = [(k, l) for (k, l), (n, s, _) in grid.items()
                  if (k == i) != (l == j)
                  and (k in libres_ref or k in disputes) and l in libres_cible
                  and n == niveau and s > score - MARGE_AMBIGUITE]
        if rivaux:
            disputes[i] = "plusieurs candidats trop proches pour être départagés"
            libres_ref.discard(i)
            continue                                    # j reste libre
        result.paires[i] = (j, score, proofs)
        libres_ref.discard(i)
        libres_cible.discard(j)

    # --- passe 3 : les disputes dont il ne reste qu'un candidat -----------
    # Les affectations de la passe 2 ont pu consommer tous les rivaux d'une
    # ligne disputée sauf un : le litige est alors résolu de fait. On itère
    # jusqu'à stabilité — chaque résolution peut en débloquer une autre.
    changed = True
    while changed:
        changed = False
        for i in sorted(disputes):
            cands = [(j, grid[(i, j)]) for j in sorted(libres_cible) if (i, j) in grid]
            if not cands:
                continue
            top = max(n for _, (n, _, _) in cands)
            best = max(s for _, (n, s, _) in cands if n == top)
            finalists = [j for j, (n, s, _) in cands
                         if n == top and s > best - MARGE_AMBIGUITE]
            if len(finalists) != 1:
                continue
            j = finalists[0]
            # un autre litige vise-t-il encore ce candidat ? Si oui, trancher
            # ici volerait un candidat encore disputé : on s'abstient.
            convoite = any((k, j) in grid for k in disputes if k != i)
            if convoite:
                continue
            niveau, score, proofs = grid[(i, j)]
            result.paires[i] = (j, score, proofs + ["litige résolu : dernier candidat restant"])
            del disputes[i]
            libres_cible.discard(j)
            changed = True

    # --- disputes restantes : signalées, jamais tranchées ------------------
    # Un candidat encore disputé n'est ni apparié ni orphelin : il attend la
    # décision de l'opérateur. Le compter « en trop » fabriquerait un faux
    # écart en plus de l'ambiguïté qui le concerne déjà.
    en_attente = set()
    for i in sorted(disputes):
        cands = [j for j in sorted(libres_cible) if (i, j) in grid]
        if not cands:                     # tous partis ailleurs : simple manquant
            libres_ref.add(i)
            continue
        result.ambigus.append(_ambiguity(reference, cible, i, cands, disputes[i]))
        en_attente.update(cands)

    result.ref_seuls = sorted(libres_ref)
    result.cible_seuls = sorted((libres_cible - en_attente) | exclusions)
    return result


__all__ = ["match", "evaluate", "similarity", "Appariement", "Rarete", "SemanticGate"]
