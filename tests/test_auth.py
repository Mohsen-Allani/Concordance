"""Authentification (BF1, BNF6)."""

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import pytest

from concordance import accounts, config
from concordance.webapp import auth

from .conftest import USER_EMAIL, USER_PASSWORD


def test_hash_et_verification():
    h = auth.hash_password("motdepasse123")
    assert h != "motdepasse123" and h.startswith("$2")
    assert auth.verify_password("motdepasse123", h)
    assert not auth.verify_password("autre", h)


def test_mot_de_passe_long_et_accentue():
    """bcrypt tronque à 72 octets : aucune erreur, et la vérification reste stable."""
    pwd = "é" * 60            # 120 octets en UTF-8
    h = auth.hash_password(pwd)
    assert auth.verify_password(pwd, h)


def test_hachage_existant_reste_valide():
    """Un hachage $2b$ produit par passlib/bcrypt avant la migration doit passer."""
    ancien = bcrypt.hashpw(b"ancien-mot-de-passe", bcrypt.gensalt(rounds=4)).decode()
    assert auth.verify_password("ancien-mot-de-passe", ancien)


def test_hachage_mal_forme_refuse_sans_exception():
    assert auth.verify_password("x", "pas-un-hachage") is False


def test_connexion_et_profil(client, auth):
    r = client.get("/api/auth/me", headers=auth)
    assert r.status_code == 200 and r.json()["email"] == USER_EMAIL


def test_mauvais_mot_de_passe(client, auth):
    r = client.post("/api/auth/token", data={"username": USER_EMAIL, "password": "faux"})
    assert r.status_code == 401


def test_compte_inconnu(client, db):
    r = client.post("/api/auth/token", data={"username": "nobody@x.tn", "password": "x"})
    assert r.status_code == 401


def test_jeton_expire(client, auth):
    expire = jwt.encode({"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
                        os.environ["SECRET_KEY"], algorithm="HS256")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expire}"})
    assert r.status_code == 401


def test_jeton_signe_avec_un_autre_secret(client, auth):
    faux = jwt.encode({"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                      "un-autre-secret-0123456789abcdef-0123456789", algorithm="HS256")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {faux}"})
    assert r.status_code == 401


def test_secret_trop_court_refuse(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "court")
    with pytest.raises(config.MissingConfigError):
        auth._secret()


def test_secret_absent_refuse(monkeypatch):
    monkeypatch.delenv("SECRET_KEY")
    with pytest.raises(config.MissingConfigError):
        auth._secret()


def test_creation_de_compte(db):
    uid = accounts.create_user("A B", "a@b.tn", USER_PASSWORD)
    assert uid >= 1
    with pytest.raises(accounts.AccountError, match="existe déjà"):
        accounts.create_user("A B", "a@b.tn", USER_PASSWORD)
    with pytest.raises(accounts.AccountError, match="trop court"):
        accounts.create_user("C D", "c@d.tn", "court")
