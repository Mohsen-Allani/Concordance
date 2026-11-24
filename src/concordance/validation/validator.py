"""Orchestration de L7.

Enchaînement : échelle de tolérance -> remise implicite -> contrôle des lignes
-> reconstruction des totaux -> document corrigé -> certification -> score.
Aucune étape ne décide seule du verdict : le verdict découle de la certification
et des anomalies structurelles, le score mesure la qualité.
"""

import copy

from .certification import certify_document
from .lines import consensus_discount, reconcile_lines
from .report import Check, ValidationReport
from .scoring import confidence
from .tolerance import Tolerance, close, q3
from .totals import CORE, reconcile_totals


def _discount_check(rate, implied, spread):
    if not implied:
        return None
    if rate == 0:
        return Check("remise lignes", "ok", "aucune remise implicite")
    if rate is not None:
        return Check("remise lignes", "recovered",
                     f"remise non étiquetée ≈ {q3(rate)}% sur {len(implied)} ligne(s)")
    return Check("remise lignes", "warning",
                 f"remises implicites divergentes (dispersion {q3(spread)} points)")


def _apply_solver(solver, corrected, checks, recovered, suggestions, tol):
    for k in CORE:
        read, best = solver.read.get(k), solver.best.get(k)
        if best is None:
            continue
        if read is None:
            if not best:
                continue
            recovered[k] = best
            checks.append(Check(f"totaux.{k}", "recovered", f"absent → reconstruit {best}"))
        elif not close(best, read, tol.material(solver.scale)):
            suggestions[k] = best
            checks.append(Check(f"totaux.{k}", "warning",
                                f"lu {read}, valeur cohérente {best}"))
        else:
            checks.append(Check(f"totaux.{k}", "ok", f"{read}"))

    corrected.setdefault("totaux", {})
    for k in CORE:
        if solver.best.get(k) is not None:
            corrected["totaux"][k] = solver.best[k]

    if solver.ambiguous:
        first = solver.alternatives[0]["champs_divergents"] if solver.alternatives else {}
        detail = ", ".join(f"{k} : {v[0]} ou {v[1]}" for k, v in first.items())
        checks.append(Check("solveur", "warning",
                            f"{len(solver.alternatives)} reconstruction(s) concurrente(s) "
                            f"sur des champs absents du document — {detail}"))


def validate_document(norm, doc_type=None):
    """Valide un document normalisé (L6) et retourne un ValidationReport."""
    checks, recovered, suggestions = [], {}, {}
    lines = norm.get("lignes") or []
    totals = norm.get("totaux") or {}
    tol = Tolerance.infer(norm)

    rate, implied, spread = consensus_discount(lines, tol)
    check = _discount_check(rate, implied, spread)
    if check:
        checks.append(check)

    monetary = bool(totals) or any(
        ln.get("prixUnitaireHT") is not None or ln.get("montantHT") is not None
        for ln in lines)
    line_checks, sums = reconcile_lines(lines, rate, tol, monetary)
    checks.extend(line_checks)

    corrected = copy.deepcopy(norm)
    solver = None
    if totals and (sums.gross is not None or sums.net is not None):
        solver = reconcile_totals(totals, sums, rate, tol)
        _apply_solver(solver, corrected, checks, recovered, suggestions, tol)

    if rate not in (None, 0):
        # Le consensus des lignes suffit à propager le taux : consensus_discount
        # ne renvoie un taux que si CHAQUE ligne mesurable implique le même taux
        # à son incertitude d'arrondi près. La confirmation par les totaux,
        # quand ils existent, reste consignée à titre informatif.
        if solver is not None and sums.gross is not None:
            expected_net = sums.gross * (1 - rate / 100)
            if close(solver.best.get("netHT"), expected_net,
                     tol.terms(sums.quantity + 1, expected_net)):
                checks.append(Check("remise ↔ totaux", "confirmed",
                                    f"remise {q3(rate)}% confirmée par le netHT reconstruit"))
            else:
                checks.append(Check("remise ↔ totaux", "warning",
                                    f"remise {q3(rate)}% déduite des lignes mais non "
                                    f"confirmée par les totaux"))
        recovered["tauxRemise"] = q3(rate)
        for ln in corrected.get("lignes") or []:
            if ln.get("tauxRemise") is None and None not in (
                    ln.get("quantite"), ln.get("prixUnitaireHT")):
                ln["tauxRemise"] = q3(rate)

    if not norm.get("numero"):
        checks.append(Check("numéro", "error", "numéro de document manquant"))
    if not (norm.get("fournisseur") or {}).get("nom"):
        checks.append(Check("fournisseur", "warning", "nom du fournisseur manquant"))
    if not lines:
        checks.append(Check("lignes", "error", "aucune ligne extraite"))

    certificate = certify_document(corrected, tol)
    if not certificate["applicable"]:
        checks.append(Check("certification", "ok",
                            "document sans contenu arithmétique — rien à certifier"))
    elif certificate["certified"]:
        checks.append(Check("certification", "ok",
                            f"chaîne complète vérifiée ({certificate['relations_ok']} relations)"))
    else:
        status = "error" if certificate["relations_échec"] else "warning"
        checks.append(Check("certification", status,
                            f"chaîne non certifiée : {certificate['relations_échec']} échec(s), "
                            f"{certificate['relations_ignorées']} relation(s) ignorée(s)"))

    score, components = confidence(corrected, doc_type, sums, certificate, solver)

    has_error = any(c.status == "error" for c in checks) or sums.unreconciled > 0
    not_certified = certificate["applicable"] and not certificate["certified"]
    # une ambiguïté n'est bloquante que si la chaîne arithmétique ne la tranche pas
    blocking_ambiguity = (solver is not None and solver.ambiguous
                          and not certificate["certified"])
    if has_error or not_certified or blocking_ambiguity:
        verdict = "review"
    elif suggestions:
        verdict = "corrected"
    else:
        verdict = "ok"

    solver_detail = {} if solver is None else {
        "relations_satisfaites": solver.satisfied,
        "relations_applicables": solver.applicable,
        "qualité": str(q3(solver.quality)),
        "coût_relatif_des_corrections": str(q3(solver.edit_cost)),
        "seuil_matérialité": str(q3(tol.material(solver.scale))),
        "champs_reconstruits": list(solver.reconstructed),
        "ambigu": solver.ambiguous,
        "ambiguïté_bloquante": blocking_ambiguity,
        "alternatives": solver.alternatives,
    }

    return ValidationReport(verdict=verdict, confidence=score, components=components,
                            checks=checks, recovered=recovered, suggestions=suggestions,
                            corrected_document=corrected, certificate=certificate,
                            solver=solver_detail)
