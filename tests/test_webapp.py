"""API web de bout en bout, sans appel de modèle ni PostgreSQL.

Une analyse réaliste est semée (extractions synthétiques -> L6 -> L7 -> L8 ->
persistance), puis l'API est exercée : tableau de bord, historique, détail,
révisions (correction de valeur, rapprochement, révision invalide), dépôt.
"""

import pytest

from concordance import config
from concordance.db import save_analysis
from concordance.webapp import jobs

from .data import SCENARIO, run_chain, seed_summary


@pytest.fixture
def analyse_id(db):
    _, doc_details, comparison = run_chain(SCENARIO)
    return save_analysis(seed_summary(comparison), doc_details, comparison, "terminé")


def test_sante_sans_authentification(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_routes_protegees_sans_jeton(client):
    for route in ("/api/stats", "/api/analyses", "/api/analyses/1", "/api/auth/me"):
        assert client.get(route).status_code == 401, route


def test_interface_servie(client):
    r = client.get("/")
    assert r.status_code == 200 and "Concordance" in r.text
    assert client.get("/static/app.js").status_code == 200


def test_tableau_de_bord(client, auth, analyse_id):
    r = client.get("/api/stats", headers=auth)
    assert r.status_code == 200
    s = r.json()
    assert s["total"] == 1 and s["produits"] == 3
    assert s["conformes"] == 1 and s["pct_conformes"] == 33
    assert len(s["activite"]) == 8 and len(s["recentes"]) == 1


def test_historique_et_detail(client, auth, analyse_id):
    r = client.get("/api/analyses", headers=auth)
    assert r.status_code == 200 and [a["id"] for a in r.json()] == [analyse_id]

    r = client.get(f"/api/analyses/{analyse_id}", headers=auth)
    assert r.status_code == 200
    d = r.json()
    assert [x["type"] for x in d["documents_detail"]] == ["BC", "BL", "Facture"]
    statuts = {p["cle"]: p["statut"] for p in d["comparaison"]["produits"]}
    assert statuts["BC:0"] == "conforme"
    assert statuts["BC:1"] == "écart"          # quantité au BL, prix à la facture
    assert statuts["BC:2"] == "manquant"       # TC-14 ni livré ni facturé


def test_analyse_inconnue(client, auth):
    assert client.get("/api/analyses/999", headers=auth).status_code == 404


def test_revision_correction_de_valeur(client, auth, analyse_id):
    """La quantité BL du cadenas était en réalité 24 (erreur de lecture) :
    l'écart de quantité disparaît, l'écart de prix de la facture demeure."""
    rev = {"corrections": {"BL": {"1": {"quantite": "24"}}}, "rapprochements": {}}
    r = client.patch(f"/api/analyses/{analyse_id}/revisions", headers=auth, json=rev)
    assert r.status_code == 200, r.text
    d = r.json()
    p1 = next(p for p in d["comparaison"]["produits"] if p["cle"] == "BC:1")
    qte = next(a for a in p1["paires"]["BC↔BL"]["axes"] if a["champ"] == "quantite")
    assert qte["statut"] == "conforme", qte
    prix = next(a for a in p1["paires"]["BC↔Facture"]["axes"]
                if a["champ"] == "prixUnitaireHT")
    assert prix["statut"] == "écart"
    assert d["revisions"]["corrections"]["BL"]["1"]["quantite"] == "24"


def test_revision_detachement(client, auth, analyse_id):
    rev = {"corrections": {}, "rapprochements": {"BC↔BL": {"detachees": [0]}}}
    r = client.patch(f"/api/analyses/{analyse_id}/revisions", headers=auth, json=rev)
    assert r.status_code == 200, r.text
    en_trop = [p for p in r.json()["comparaison"]["produits"] if p["statut"] == "en_trop"]
    assert any("détachée" in (p["paires"].get("BC↔BL", {}).get("message") or "")
               for p in en_trop)


@pytest.mark.parametrize("revision, fragment", [
    ({"rapprochements": {"BC↔BL": {"affectations": {"99": [0]}}}}, "n'existe pas"),
    ({"corrections": {"BL": {"1": {"quantite": "abc"}}}}, "quantité invalide"),
    ({"corrections": {"BL": {"1": {"prixUnitaireHT": "-3"}}}}, "négatif"),
    ({"corrections": {"BL": {"1": {"tauxRemise": "150"}}}}, "hors bornes"),
    ({"corrections": {"BL": {"1": {"numero": "X"}}}}, "non corrigeable"),
    ({"corrections": {"BL": {"42": {"quantite": "1"}}}}, "n'existe pas"),
])
def test_revision_invalide_renvoie_422(client, auth, analyse_id, revision, fragment):
    r = client.patch(f"/api/analyses/{analyse_id}/revisions", headers=auth, json=revision)
    assert r.status_code == 422, r.text
    assert fragment in r.json()["detail"]


def test_rapport_absent(client, auth, analyse_id):
    assert client.get(f"/api/analyses/{analyse_id}/rapport", headers=auth).status_code == 404


# ------------------------------------------------------------------ dépôt

@pytest.fixture
def depot(client, auth, workspace, monkeypatch):
    """Dépôt de PDF avec le pipeline neutralisé (aucun appel de modèle)."""
    lances = []
    monkeypatch.setattr(jobs, "run", lambda *args: lances.append(args))

    def envoyer(contenu, nom="bc.pdf", type_mime="application/pdf"):
        return client.post("/api/analyses", headers=auth,
                           files={"fichier": (nom, contenu, type_mime)})
    envoyer.lances = lances
    return envoyer


def test_depot_valide(depot, client, auth):
    r = depot(b"%PDF-1.4\n%contenu minimal\n", nom="Bon de commande é.pdf")
    assert r.status_code == 200, r.text
    job = r.json()["job"]
    assert len(depot.lances) == 1
    fichiers = list(config.UPLOADS_DIR.glob("*.pdf"))
    assert len(fichiers) == 1 and fichiers[0].name.startswith("Bon_de_commande_e__")

    suivi = client.get(f"/api/analyses/jobs/{job}", headers=auth)
    assert suivi.status_code == 200 and suivi.json()["statut"] == "en cours"


def test_depot_refuse_un_autre_type(depot):
    assert depot(b"PK\x03\x04", "x.zip", "application/zip").status_code == 422


def test_depot_refuse_un_faux_pdf(depot):
    assert depot(b"ceci n'est pas un pdf", "x.pdf").status_code == 422


def test_depot_refuse_un_fichier_trop_gros(depot, monkeypatch):
    from concordance.webapp import analyses
    monkeypatch.setattr(analyses, "TAILLE_MAX", 100)
    r = depot(b"%PDF-" + b"0" * 200)
    assert r.status_code == 413


def test_job_inconnu(client, auth):
    assert client.get("/api/analyses/jobs/inexistant", headers=auth).status_code == 404
