"""Orchestration du rapprochement trois voies (L8).

Tout est rapproché sur le Bon de Commande, jamais deux documents cibles entre
eux. La correspondance BL <-> Facture s'en déduit : si les deux pointent la même
ligne du BC, elles se correspondent. Trois rapprochements indépendants
pourraient se contredire — affirmer BL3 = BC1, Facture2 = BC1 et BL3 != Facture2
— et rendre le rapport inexploitable. En passant par le BC, la contradiction
devient impossible par construction.

Une ligne livrée ou facturée qui n'existe pas au BC ne disparaît pas : elle est
rapprochée des autres orphelines lors d'une passe résiduelle, puis signalée
comme « en trop » — une fois, et non une fois par document.
"""

from .canonical import canonicalize
from .fields import CONFORME, ECART, NON_COMPARABLE, combined_tolerance, compare_lines
from .identity import check_identity
from .matching import match
from .overrides import prepare as prepare_overrides

REFERENCE = "BC"
CIBLES = ("BL", "Facture")

MANQUANT = "manquant"
EN_TROP = "en_trop"
AMBIGU = "ambigu"


def _produit(cle):
    return {"cle": cle, "reference": None, "designation": None,
            "lignes": {}, "paires": {}, "statut": None, "origines": {}}


def _describe(line):
    return {
        "type": line.type_document,
        "lignes_source": list(line.indices),
        "fusionnee": line.fusionnee,
        "reference": line.reference,
        "designation": line.designation,
        "unite": line.unite,
        "quantite": line.quantite,
        "prixUnitaireHT": line.prixUnitaireHT,
        "tauxRemise": line.tauxRemise,
        "montantHT": line.montantHT,
    }


def _pair_status(axes):
    if any(a["statut"] == ECART for a in axes):
        return ECART
    if any(a["statut"] == CONFORME for a in axes):
        return CONFORME
    return NON_COMPARABLE


def _synthese(produits, gauche, droite):
    """Compte les issues d'une paire de documents."""
    counts = {CONFORME: 0, ECART: 0, MANQUANT: 0, EN_TROP: 0,
              AMBIGU: 0, NON_COMPARABLE: 0}
    cle = f"{gauche}↔{droite}"
    for p in produits:
        statut = (p["paires"].get(cle) or {}).get("statut")
        if statut in counts:
            counts[statut] += 1
    return counts


def compare_analysis(documents, gate=None, resolutions=None, overrides=None):
    """`documents` : {type -> document validé (corrected_document)}.

    `resolutions` : {"BC↔BL" | "BC↔Facture" -> {index ligne BC -> index ligne
    cible}} — décisions prises par l'opérateur sur des ambiguïtés signalées
    lors d'une exécution précédente. La comparaison est alors rejouée avec ces
    paires verrouillées. Les index sont ceux des lignes canoniques, publiés
    dans les enregistrements d'ambiguïté.

    `overrides` : révisions de l'opérateur au format documenté dans
    comparison/overrides.py — affectations (dont fusions) et détachements,
    en index de lignes d'origine. C'est le mécanisme complet, dont
    `resolutions` est un sous-ensemble historique ; en cas de conflit, les
    overrides priment.

    Retourne un dictionnaire prêt à être sérialisé et à alimenter le rapport.
    """
    resolutions = dict(resolutions or {})
    presents = {t: d for t, d in documents.items() if d}
    if REFERENCE not in presents:
        return {"statut": "impossible",
                "message": "aucun bon de commande : rien à quoi comparer",
                "entete": [], "produits": [], "synthese": {}, "ambiguites": []}

    cibles = [t for t in CIBLES if t in presents]
    if not cibles:
        return {"statut": "impossible",
                "message": "ni bon de livraison ni facture : rien à comparer",
                "entete": [], "produits": [], "synthese": {}, "ambiguites": []}

    lignes = {t: canonicalize(presents[t], t) for t in presents}
    tolerances = {t: combined_tolerance(presents[REFERENCE], presents[t]) for t in cibles}

    # --- révisions de l'opérateur : contraintes, pas résultats ------------
    # Les fusions réécrivent les listes cibles, les affectations deviennent
    # des paires verrouillées, les détachements des exclusions. Le
    # rapprochement est ensuite rejoué en entier sous ces contraintes.
    exclusions = {}
    if overrides:
        lignes, res_operateur, exclusions = prepare_overrides(lignes, overrides)
        for paire, mapping in res_operateur.items():
            fusion = dict(resolutions.get(paire) or {})
            fusion.update(mapping)
            resolutions[paire] = fusion

    # --- rapprochement de chaque cible sur le BC --------------------------
    appariements, ambiguites = {}, []
    for t in cibles:
        appariements[t] = match(lignes[REFERENCE], lignes[t], gate,
                                resolutions.get(f"{REFERENCE}↔{t}"),
                                exclusions.get(f"{REFERENCE}↔{t}"))
        for a in appariements[t].ambigus:
            ambiguites.append({"paire": f"{REFERENCE}↔{t}", **a})

    # --- un produit par ligne du BC ---------------------------------------
    produits = []
    index_par_bc = {}
    for i, ligne in enumerate(lignes[REFERENCE]):
        p = _produit(f"BC:{i}")
        p["reference"] = ligne.reference
        p["designation"] = ligne.designation
        p["lignes"][REFERENCE] = _describe(ligne)
        index_par_bc[i] = p
        produits.append(p)

    for t in cibles:
        appar = appariements[t]
        for i, (j, score, preuves) in sorted(appar.paires.items()):
            p = index_par_bc[i]
            cible_ligne = lignes[t][j]
            p["lignes"][t] = _describe(cible_ligne)
            axes = compare_lines(lignes[REFERENCE][i], cible_ligne, tolerances[t])
            p["paires"][f"{REFERENCE}↔{t}"] = {
                "statut": _pair_status(axes),
                "score_appariement": score,
                "preuves": preuves,
                "axes": axes,
            }
        for i in appar.ref_seuls:
            index_par_bc[i]["paires"][f"{REFERENCE}↔{t}"] = {
                "statut": MANQUANT,
                "message": f"présent au {REFERENCE}, absent du {t}",
            }
        for a in appar.ambigus:
            index_par_bc[a["reference_index"]]["paires"][f"{REFERENCE}↔{t}"] = {
                "statut": AMBIGU,
                "motif": a["motif"],
                "candidats": a["candidats"],
            }

    # --- passe résiduelle : orphelines des cibles entre elles -------------
    orphelines = {t: [lignes[t][j] for j in appariements[t].cible_seuls] for t in cibles}
    residuel = {}
    if len(cibles) == 2:
        a, b = cibles
        residuel = match(orphelines[a], orphelines[b], gate)

    if residuel:
        for amb in residuel.ambigus:
            ambiguites.append({"paire": f"{cibles[0]}↔{cibles[1]}", **amb})

    consommees = set()
    if residuel:
        a, b = cibles
        for ia, (ib, score, preuves) in sorted(residuel.paires.items()):
            la, lb = orphelines[a][ia], orphelines[b][ib]
            p = _produit(f"HORS_BC:{a}:{ia}")
            p["reference"] = la.reference
            p["designation"] = la.designation
            p["lignes"][a] = _describe(la)
            p["lignes"][b] = _describe(lb)
            axes = compare_lines(la, lb, combined_tolerance(presents[a], presents[b]))
            p["paires"][f"{a}↔{b}"] = {
                "statut": _pair_status(axes),
                "score_appariement": score,
                "preuves": preuves,
                "axes": axes,
            }
            for t in (a, b):
                p["paires"][f"{REFERENCE}↔{t}"] = {
                    "statut": EN_TROP,
                    "message": f"présent au {t}, absent du {REFERENCE}",
                }
            p["statut"] = EN_TROP
            produits.append(p)
            consommees.add((a, ia))
            consommees.add((b, ib))

    detachees = {t: {k for k, j in enumerate(appariements[t].cible_seuls)
                     if j in exclusions.get(f"{REFERENCE}↔{t}", ())}
                 for t in cibles}
    for t in cibles:
        for k, ligne in enumerate(orphelines[t]):
            if (t, k) in consommees:
                continue
            p = _produit(f"HORS_BC:{t}:{k}")
            p["reference"] = ligne.reference
            p["designation"] = ligne.designation
            p["lignes"][t] = _describe(ligne)
            p["paires"][f"{REFERENCE}↔{t}"] = {
                "statut": EN_TROP,
                "message": ("détachée par l'opérateur"
                            if k in detachees[t]
                            else f"présent au {t}, absent du {REFERENCE}"),
            }
            p["statut"] = EN_TROP
            produits.append(p)

    # --- BL <-> Facture déduit par composition à travers le BC ------------
    if len(cibles) == 2:
        a, b = cibles
        tol_ab = combined_tolerance(presents[a], presents[b])
        for p in produits:
            if a not in p["lignes"] or b not in p["lignes"] or not p["cle"].startswith("BC:"):
                continue
            i = int(p["cle"].split(":")[1])
            ja = appariements[a].paires[i][0]
            jb = appariements[b].paires[i][0]
            axes = compare_lines(lignes[a][ja], lignes[b][jb], tol_ab)
            p["paires"][f"{a}↔{b}"] = {
                "statut": _pair_status(axes),
                "deduit": f"les deux lignes pointent la même ligne du {REFERENCE}",
                "axes": axes,
            }

    for p in produits:
        if p["statut"] is None:
            statuts = {v.get("statut") for v in p["paires"].values()}
            if ECART in statuts:
                p["statut"] = ECART
            elif AMBIGU in statuts:
                p["statut"] = AMBIGU
            elif MANQUANT in statuts:
                p["statut"] = MANQUANT
            elif CONFORME in statuts:
                p["statut"] = CONFORME
            else:
                p["statut"] = NON_COMPARABLE

    paires = [f"{REFERENCE}↔{t}" for t in cibles]
    if len(cibles) == 2:
        paires.append(f"{cibles[0]}↔{cibles[1]}")

    synthese = {}
    for cle in paires:
        gauche, droite = cle.split("↔")
        synthese[cle] = _synthese(produits, gauche, droite)
    # Les ambiguïtés BC↔cible sont déjà comptées via le statut des produits ;
    # seules celles de la passe résiduelle s'ajoutent ici.
    for a in ambiguites:
        if a["paire"] in synthese and not a["paire"].startswith(REFERENCE):
            synthese[a["paire"]][AMBIGU] += 1

    global_ecarts = sum(1 for p in produits if p["statut"] in (ECART, MANQUANT, EN_TROP))
    return {
        "statut": "ok" if not global_ecarts and not ambiguites else "écarts",
        "revisions": overrides or None,
        "document_reference": REFERENCE,
        "documents": {t: {"numero": presents[t].get("numero"),
                          "date": presents[t].get("date"),
                          "lignes": len(lignes[t])} for t in presents},
        "entete": check_identity(presents),
        "paires": paires,
        "synthese": synthese,
        "ambiguites": ambiguites,
        "produits": produits,
        "totaux": {
            "produits": len(produits),
            "conformes": sum(1 for p in produits if p["statut"] == CONFORME),
            "ecarts": global_ecarts,
            "ambigus": len(ambiguites),
        },
    }
