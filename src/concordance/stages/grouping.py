def group_pages(page_types: list[str]) -> list[dict]:
    groups: dict[str, list[int]] = {}
    order: list[str] = []
    for idx, ptype in enumerate(page_types):
        page_no = idx + 1
        if ptype not in groups:
            groups[ptype] = []
            order.append(ptype)
        groups[ptype].append(page_no)
    return [{"type": t, "pages": groups[t]} for t in order]

def validate_scope(groups: list[dict]) -> list[str]:
    counts = {g["type"]: len(g["pages"]) for g in groups}
    errors = []

    if counts.get("BC", 0) == 0:
        errors.append("aucune page BC trouvée")
    if counts.get("AUTRE", 0) > 0:
        errors.append(f"{counts['AUTRE']} page(s) non reconnue(s)")
    if counts.get("BL", 0) == 0 and counts.get("Facture", 0) == 0:
        errors.append("attendu au moins 1 BL ou 1 Facture, aucun trouvé")

    return errors
