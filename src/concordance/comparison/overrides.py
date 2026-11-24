"""Révisions de l'opérateur (BF9) appliquées au rapprochement L8.

Toute intervention de l'écran de révision se ramène à une seule primitive :
« la ou les lignes X du document cible sont affectées à la ligne Y du BC —
ou à rien ». Résoudre une ambiguïté, corriger un appariement, fusionner deux
lignes livrées en une commandée, détacher une ligne : quatre gestes, une
structure.

Format (JSON, sérialisable, archivable en base comme piste d'audit) :

    {
      "BC↔BL":      {"affectations": {"0": [2, 4], "3": [1]}, "detachees": [5]},
      "BC↔Facture": {"affectations": {"2": [0]}}
    }

Les index sont ceux des lignes d'origine du document corrigé (position dans
document["lignes"]) — jamais les index canoniques, qui bougent à chaque fusion.
Une ligne d'origine absorbée par une fusion automatique (doublon de référence)
désigne la ligne canonique entière qui la contient.

Les révisions ne sont pas une modification du résultat : elles sont des
contraintes injectées avant le rapprochement, qui est ensuite rejoué en entier.
À documents et révisions identiques, le verdict est identique (BNF1).
"""

from .canonical import _merge

PAIRES_AUTORISEES = ("BC↔BL", "BC↔Facture")


class OverrideError(ValueError):
    """Révision invalide : l'erreur est destinée à l'utilisateur, pas au log."""


def _raw_to_canon(lignes):
    """Index d'origine -> index canonique. Plusieurs origines peuvent pointer
    la même ligne canonique (fusion automatique sur référence)."""
    mapping = {}
    for ci, ligne in enumerate(lignes):
        for ri in ligne.indices:
            mapping[ri] = ci
    return mapping


def _normalize_spec(paire, spec, map_ref, map_cible):
    """Traduit une révision d'une paire en index canoniques, en la validant."""
    affectations, detachees = {}, set()

    for bc_raw, cible_raws in (spec.get("affectations") or {}).items():
        try:
            bc_raw = int(bc_raw)
        except (TypeError, ValueError):
            raise OverrideError(f"{paire} : index BC invalide « {bc_raw} »")
        if bc_raw not in map_ref:
            raise OverrideError(f"{paire} : la ligne BC {bc_raw} n'existe pas")
        if not isinstance(cible_raws, (list, tuple)) or not cible_raws:
            raise OverrideError(
                f"{paire} : l'affectation de la ligne BC {bc_raw} doit être "
                f"une liste non vide d'index")
        bc = map_ref[bc_raw]
        if bc in affectations:
            raise OverrideError(
                f"{paire} : la ligne BC {bc_raw} reçoit deux affectations "
                f"(lignes d'origine fusionnées sur la même référence ?)")
        groupe = []
        for j in cible_raws:
            try:
                j = int(j)
            except (TypeError, ValueError):
                raise OverrideError(f"{paire} : index cible invalide « {j} »")
            if j not in map_cible:
                raise OverrideError(f"{paire} : la ligne cible {j} n'existe pas")
            cj = map_cible[j]
            if cj not in groupe:
                groupe.append(cj)
        affectations[bc] = sorted(groupe)

    for j in spec.get("detachees") or []:
        try:
            j = int(j)
        except (TypeError, ValueError):
            raise OverrideError(f"{paire} : index détaché invalide « {j} »")
        if j not in map_cible:
            raise OverrideError(f"{paire} : la ligne cible {j} n'existe pas")
        detachees.add(map_cible[j])

    # Une même ligne cible ne peut servir deux maîtres, ni être à la fois
    # affectée et détachée : le conflit est signalé, jamais arbitré ici.
    vues = {}
    for bc, groupe in affectations.items():
        for cj in groupe:
            if cj in vues:
                raise OverrideError(
                    f"{paire} : la ligne cible {cj} est affectée à deux "
                    f"lignes BC différentes")
            if cj in detachees:
                raise OverrideError(
                    f"{paire} : la ligne cible {cj} est à la fois affectée "
                    f"et détachée")
            vues[cj] = bc

    return affectations, detachees


def _rebuild_with_merges(lignes, affectations):
    """Fusionne les groupes d'affectation multi-lignes et renvoie la nouvelle
    liste avec la table de correspondance ancien -> nouvel index canonique.

    Chaque groupe est remplacé par sa fusion, placée à la position de son
    premier membre ; les quantités et montants s'additionnent, un prix
    divergent devient inconnu (mêmes règles que la fusion automatique)."""
    groupes = {min(g): g for g in affectations.values() if len(g) > 1}
    absorbe = {cj: tete for tete, g in groupes.items() for cj in g if cj != tete}

    rebuilt, remap = [], {}
    for ci, ligne in enumerate(lignes):
        if ci in absorbe:
            remap[ci] = None                       # résolu après la boucle
            continue
        if ci in groupes:
            rebuilt.append(_merge([lignes[j] for j in groupes[ci]]))
        else:
            rebuilt.append(ligne)
        remap[ci] = len(rebuilt) - 1
    for cj, tete in absorbe.items():
        remap[cj] = remap[tete]
    return rebuilt, remap


def prepare(lignes, overrides):
    """Applique les révisions aux lignes canoniques.

    lignes    : {type -> [LigneCanonique]} issu de canonicalize()
    overrides : structure documentée en tête de module (index d'origine)

    Renvoie (lignes, resolutions, exclusions) :
      lignes      — listes cibles éventuellement re-fusionnées
      resolutions — {paire -> {index canonique BC -> index canonique cible}}
      exclusions  — {paire -> ensemble d'index canoniques cibles détachés}
    """
    resolutions, exclusions = {}, {}
    if not overrides:
        return lignes, resolutions, exclusions

    inconnues = set(overrides) - set(PAIRES_AUTORISEES)
    if inconnues:
        raise OverrideError(
            f"paires non révisables : {', '.join(sorted(inconnues))} — "
            f"seules {' et '.join(PAIRES_AUTORISEES)} le sont")

    map_ref = _raw_to_canon(lignes["BC"]) if "BC" in lignes else {}
    lignes = dict(lignes)

    for paire in PAIRES_AUTORISEES:
        spec = overrides.get(paire)
        if not spec:
            continue
        cible = paire.split("↔")[1]
        if cible not in lignes:
            raise OverrideError(f"{paire} : aucun document {cible} dans l'analyse")

        affectations, detachees = _normalize_spec(
            paire, spec, map_ref, _raw_to_canon(lignes[cible]))

        rebuilt, remap = _rebuild_with_merges(lignes[cible], affectations)
        lignes[cible] = rebuilt
        resolutions[paire] = {bc: remap[g[0]] for bc, g in affectations.items()}
        exclusions[paire] = {remap[cj] for cj in detachees}

    return lignes, resolutions, exclusions


__all__ = ["prepare", "OverrideError", "PAIRES_AUTORISEES"]
