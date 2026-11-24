"""Gestion des comptes utilisateurs (BF1).

Il n'y a volontairement pas d'inscription publique : l'application est à usage
interne (service achat et comptabilité), les comptes sont créés par
l'administrateur avec `concordance create-user`.
"""

from sqlalchemy import select

from concordance.db import new_session
from concordance.db.models import Utilisateur
from concordance.webapp.auth import hash_password

MIN_PASSWORD_LENGTH = 8


class AccountError(ValueError):
    """Création de compte refusée ; le message est destiné à l'administrateur."""


def create_user(nom: str, email: str, password: str, role: str = "utilisateur") -> int:
    """Crée un compte et renvoie son identifiant. Le mot de passe est haché
    (bcrypt) avant toute écriture, jamais stocké en clair (BNF6)."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AccountError(
            f"Mot de passe trop court ({MIN_PASSWORD_LENGTH} caractères minimum).")
    with new_session() as session, session.begin():
        if session.scalar(select(Utilisateur).where(Utilisateur.email == email)):
            raise AccountError(f"Un compte existe déjà pour {email}.")
        user = Utilisateur(nom=nom, email=email, role=role,
                           mot_de_passe=hash_password(password))
        session.add(user)
        session.flush()
        return user.id_utilisateur
