"""Authentification (BF1, BNF6) : OAuth2 password flow + JWT.

Conforme au document de conception : jetons JWT signés (secret dans
l'environnement, jamais codé en dur), mots de passe hachés avec bcrypt, jamais
stockés en clair. Toutes les routes /api (hors connexion et santé) sont
protégées par `current_user`.

bcrypt est utilisé directement. passlib, qui servait d'intermédiaire, n'est
plus maintenu et se casse avec bcrypt >= 4.1 ; les hachages `$2b$` qu'il avait
produits restent valides.
"""

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import select

from concordance import config
from concordance.db import new_session
from concordance.db.models import Utilisateur

ALGORITHM = "HS256"
MIN_SECRET_LENGTH = 16
BCRYPT_MAX_BYTES = 72       # limite de l'algorithme : au-delà, le mot de passe est tronqué

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

router = APIRouter(prefix="/api/auth", tags=["auth"])


def token_minutes() -> int:
    return int(os.environ.get("TOKEN_MINUTES", "480"))


def _secret() -> str:
    secret = config.require_env("SECRET_KEY", "par exemple : openssl rand -hex 32")
    if len(secret) < MIN_SECRET_LENGTH:
        raise config.MissingConfigError(
            f"SECRET_KEY trop courte (minimum {MIN_SECRET_LENGTH} caractères)")
    return secret


def _prepare(plain: str) -> bytes:
    return plain.encode("utf-8")[:BCRYPT_MAX_BYTES]


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_prepare(plain), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(plain), hashed.encode("ascii"))
    except ValueError:      # hachage mal formé en base
        return False


# Haché factice : vérifié quand l'e-mail est inconnu, pour que le temps de
# réponse ne révèle pas quels comptes existent.
_DUMMY_HASH = hash_password("mot-de-passe-factice")


def create_token(user: Utilisateur) -> str:
    payload = {
        "sub": str(user.id_utilisateur),
        "email": user.email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=token_minutes()),
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def current_user(token: str = Depends(oauth2_scheme)) -> Utilisateur:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Session invalide ou expirée",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, _secret(), algorithms=[ALGORITHM])
        uid = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise unauthorized from None
    with new_session() as session:
        user = session.get(Utilisateur, uid)
    if user is None:
        raise unauthorized
    return user


@router.post("/token")
def login(form: OAuth2PasswordRequestForm = Depends()):
    with new_session() as session:
        user = session.scalar(
            select(Utilisateur).where(Utilisateur.email == form.username))
    if user is None:
        verify_password(form.password, _DUMMY_HASH)
        ok = False
    else:
        ok = verify_password(form.password, user.mot_de_passe)
    if not ok:
        raise HTTPException(status_code=401,
                            detail="Adresse e-mail ou mot de passe incorrect")
    return {"access_token": create_token(user), "token_type": "bearer",
            "utilisateur": {"id": user.id_utilisateur, "nom": user.nom,
                            "email": user.email, "role": user.role}}


@router.get("/me")
def me(user: Utilisateur = Depends(current_user)):
    return {"id": user.id_utilisateur, "nom": user.nom,
            "email": user.email, "role": user.role}
