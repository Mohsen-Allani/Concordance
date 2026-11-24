"""Modèle relationnel — six tables (L9, BF11).

Principe : colonnes relationnelles pour ce qui se filtre et se compare,
colonnes JSONB pour ce qui s'archive et se rejoue (sortie brute du modèle,
rapport de validation, détail complet de la comparaison). Le JSONB évolue
avec les prompts sans imposer de migration.

Montants en NUMERIC, jamais en float (BNF1).
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# JSONB sous PostgreSQL (indexable, schéma de production) ; JSON générique
# ailleurs, ce qui permet de tester l'application sur SQLite sans PostgreSQL.
JsonType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class Utilisateur(Base):
    __tablename__ = "utilisateur"

    id_utilisateur: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    mot_de_passe: Mapped[str] = mapped_column(String(200))   # hash bcrypt, jamais en clair
    role: Mapped[str] = mapped_column(String(30), default="utilisateur")

    analyses: Mapped[list["Analyse"]] = relationship(back_populates="utilisateur")


class Analyse(Base):
    __tablename__ = "analyse"

    id_analyse: Mapped[int] = mapped_column(primary_key=True)
    nom_fichier: Mapped[str] = mapped_column(String(255))
    date_analyse: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                   server_default=func.now())
    # en cours | en attente de révision | terminé | erreur | hors périmètre
    statut: Mapped[str] = mapped_column(String(30), default="en cours")
    score_confiance: Mapped[float | None] = mapped_column(Numeric(4, 3))
    nb_pages: Mapped[int | None] = mapped_column(Integer)
    # Détail complet de L8 (produits, paires, axes, ambiguïtés) : rejouable
    comparaison: Mapped[dict | None] = mapped_column(JsonType)
    # Révisions de l'opérateur (BF9) au format comparison/overrides.py : la
    # comparaison stockée est le résultat de leur application — les conserver
    # rend l'analyse rejouable et l'intervention humaine auditable
    revisions: Mapped[dict | None] = mapped_column(JsonType)
    erreurs: Mapped[list | None] = mapped_column(JsonType)

    id_utilisateur: Mapped[int | None] = mapped_column(
        ForeignKey("utilisateur.id_utilisateur"))

    utilisateur: Mapped["Utilisateur | None"] = relationship(back_populates="analyses")
    documents: Mapped[list["Document"]] = relationship(
        back_populates="analyse", cascade="all, delete-orphan")
    resultats: Mapped[list["Resultat"]] = relationship(
        back_populates="analyse", cascade="all, delete-orphan")
    rapport: Mapped["Rapport | None"] = relationship(
        back_populates="analyse", uselist=False, cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "document"

    id_document: Mapped[int] = mapped_column(primary_key=True)
    type_document: Mapped[str] = mapped_column(String(10))       # BC | BL | Facture
    numero: Mapped[str | None] = mapped_column(String(80))
    date_document: Mapped[date | None] = mapped_column(Date)
    fournisseur: Mapped[str | None] = mapped_column(String(200))
    client: Mapped[str | None] = mapped_column(String(200))
    devise: Mapped[str | None] = mapped_column(String(10))
    est_scanne: Mapped[bool | None] = mapped_column(Boolean)
    verdict: Mapped[str | None] = mapped_column(String(20))      # ok | corrected | review
    score_confiance: Mapped[float | None] = mapped_column(Numeric(4, 3))
    extraction_brute: Mapped[dict | None] = mapped_column(JsonType)  # sortie L5 — audit
    validation: Mapped[dict | None] = mapped_column(JsonType)        # rapport L7 (solveur inclus)

    id_analyse: Mapped[int] = mapped_column(ForeignKey("analyse.id_analyse"))

    analyse: Mapped["Analyse"] = relationship(back_populates="documents")
    lignes: Mapped[list["LigneProduit"]] = relationship(
        back_populates="document", cascade="all, delete-orphan")


class LigneProduit(Base):
    __tablename__ = "ligne_produit"

    id_ligne: Mapped[int] = mapped_column(primary_key=True)
    position: Mapped[int] = mapped_column(Integer)               # ordre dans le document
    reference: Mapped[str | None] = mapped_column(String(120))
    designation: Mapped[str | None] = mapped_column(Text)
    unite: Mapped[str | None] = mapped_column(String(30))
    quantite: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    prix_unitaire_ht: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    taux_remise: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    montant_ht: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    # Révision humaine (BF9) : la valeur d'origine reste, la correction s'ajoute
    corrige: Mapped[bool] = mapped_column(Boolean, default=False)
    valeurs_origine: Mapped[dict | None] = mapped_column(JsonType)

    id_document: Mapped[int] = mapped_column(ForeignKey("document.id_document"))

    document: Mapped["Document"] = relationship(back_populates="lignes")


class Resultat(Base):
    __tablename__ = "resultat"

    id_resultat: Mapped[int] = mapped_column(primary_key=True)
    cle_produit: Mapped[str] = mapped_column(String(40))          # ex. BC:3
    reference: Mapped[str | None] = mapped_column(String(120))
    designation: Mapped[str | None] = mapped_column(Text)
    # conforme | écart | ambigu | manquant | en trop | non comparable
    statut: Mapped[str] = mapped_column(String(30))
    detail: Mapped[dict | None] = mapped_column(JsonType)            # paires + axes du produit

    id_analyse: Mapped[int] = mapped_column(ForeignKey("analyse.id_analyse"))

    analyse: Mapped["Analyse"] = relationship(back_populates="resultats")


class Rapport(Base):
    __tablename__ = "rapport"

    id_rapport: Mapped[int] = mapped_column(primary_key=True)
    date_generation: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                      server_default=func.now())
    chemin_fichier: Mapped[str] = mapped_column(String(500))
    nb_conformes: Mapped[int | None] = mapped_column(Integer)
    nb_ecarts: Mapped[int | None] = mapped_column(Integer)
    nb_ambigus: Mapped[int | None] = mapped_column(Integer)

    id_analyse: Mapped[int] = mapped_column(ForeignKey("analyse.id_analyse"),
                                            unique=True)

    analyse: Mapped["Analyse"] = relationship(back_populates="rapport")
