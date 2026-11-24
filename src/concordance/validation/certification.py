"""Certification : preuve arithmétique de bout en bout du document corrigé.

Chaque relation est enregistrée avec sa tolérance et son ratio d'écart, donc
lisible et vérifiable a posteriori. Deux natures de relations :
  - bloquantes : leur échec interdit la certification ;
  - indicatives : elles peuvent légitimement ne pas tenir (un net à payer
    diffère du TTC en cas d'acompte, de retenue ou d'arrondi commercial).
"""

from decimal import Decimal

from .tolerance import q3, quality, ratio


def _link(links, name, lhs, rhs, allowed, blocking=True):
    if lhs is None or rhs is None:
        links.append({"relation": name, "statut": "ignorée",
                      "raison": "valeur manquante", "bloquante": blocking})
        return None
    r = ratio(lhs, rhs, allowed)
    ok = r is not None and r <= 1
    links.append({"relation": name, "statut": "ok" if ok else "échec",
                  "gauche": str(q3(lhs)), "droite": str(q3(rhs)),
                  "écart": str(q3(abs(lhs - rhs))), "tolérance": str(q3(allowed)),
                  "ratio": str(q3(r)), "bloquante": blocking})
    return ok


def stamp_convention(nH, mtva, timbre, ttc, net_pay):
    """Le droit de timbre est tantôt inclus dans le total TTC, tantôt ajouté
    seulement au net à payer. Aucune convention n'est supposée : on retient
    celle qui referme le mieux les deux relations du document.

    Retourne (libellé, part du timbre dans le TTC, part dans le net à payer)."""
    if not timbre:
        return "sans droit de timbre", Decimal(0), Decimal(0)

    options = []
    for label, share in (("timbre inclus dans le totalTTC", timbre),
                         ("timbre ajouté après le totalTTC", Decimal(0))):
        gap = Decimal(0)
        if None not in (nH, mtva, ttc):
            gap += abs(nH + mtva + share - ttc)
        if None not in (ttc, net_pay):
            gap += abs(ttc + (timbre - share) - net_pay)
        options.append((gap, label, share))
    options.sort(key=lambda o: o[0])
    _, label, share = options[0]
    return label, share, timbre - share


def certify_document(doc, tol):
    """Rejoue toutes les relations sur le document corrigé.

    Retourne un certificat contenant les relations, les ratios d'écart et les
    notes de qualité utilisées par le score de confiance."""
    lines = doc.get("lignes") or []
    totals = doc.get("totaux") or {}
    links = []

    gross_sum = net_sum = Decimal(0)
    quantity = Decimal(0)
    have_gross = have_net = True
    n_net = 0

    for i, ln in enumerate(lines, 1):
        q, pu, mt = ln.get("quantite"), ln.get("prixUnitaireHT"), ln.get("montantHT")
        rem = ln.get("tauxRemise") or Decimal(0)
        if None in (q, pu):
            have_gross = False
        else:
            gross_sum += q * pu
            quantity += abs(q)
        if mt is None:
            have_net = False
        else:
            net_sum += mt
            n_net += 1
        if None not in (q, pu, mt):
            gross = q * pu
            allowed = tol.scaled(q, gross)
            if rem:
                allowed += tol.rate_slack(gross, rem)
            _link(links, f"ligne {i} : {q} x {pu} x (1 - {rem}%) = montantHT",
                  gross * (1 - rem / 100), mt, allowed)

    tH, nH = totals.get("totalHT"), totals.get("netHT")
    rem, tva = totals.get("remiseTotale"), totals.get("tauxTVA")
    mtva = totals.get("montantTVA")
    timbre, ttc = totals.get("timbreFiscal"), totals.get("totalTTC")
    net_pay = totals.get("netAPayer")

    if have_gross:
        _link(links, "Σ (quantité x PU) = totalHT", gross_sum, tH,
              tol.terms(quantity + 1, tH))
    if have_net:
        _link(links, "Σ montantHT = netHT", net_sum, nH, tol.sum_of(n_net, nH))
    if None not in (tH, rem):
        _link(links, "totalHT - remiseTotale = netHT", tH - rem, nH, tol.terms(3, nH))
    if None not in (nH, tva):
        _link(links, f"netHT x {tva}% = montantTVA", nH * tva / 100, mtva,
              tol.terms(tva / 100 + 1, mtva) + tol.rate_slack(nH, tva))

    convention, in_ttc, in_pay = stamp_convention(nH, mtva, timbre, ttc, net_pay)
    if None not in (nH, mtva):
        _link(links, "netHT + TVA + timbre = totalTTC" if in_ttc
              else "netHT + TVA = totalTTC",
              nH + mtva + in_ttc, ttc, tol.terms(4, ttc))
    if None not in (ttc, net_pay):
        _link(links, ("totalTTC + timbre = netAPayer" if in_pay
                      else "totalTTC = netAPayer") + " (indicatif)",
              ttc + in_pay, net_pay, tol.terms(3, ttc), blocking=False)

    blocking = [l for l in links if l["bloquante"] and l["statut"] != "ignorée"]
    applicable = bool(blocking)
    certified = applicable and all(l["statut"] == "ok" for l in blocking)

    line_notes = [quality(Decimal(l["ratio"])) for l in links
                  if l["statut"] != "ignorée" and l["relation"].startswith("ligne")]
    total_notes = [quality(Decimal(l["ratio"])) for l in links
                   if l["statut"] != "ignorée" and l["bloquante"]
                   and not l["relation"].startswith("ligne")]

    return {
        "certified": certified,
        "applicable": applicable,
        "convention_timbre": convention,
        "relations_ok": sum(1 for l in links if l["statut"] == "ok"),
        "relations_échec": sum(1 for l in links if l["statut"] == "échec"),
        "relations_ignorées": sum(1 for l in links if l["statut"] == "ignorée"),
        "notes_lignes": line_notes,
        "notes_totaux": total_notes,
        "links": links,
    }
