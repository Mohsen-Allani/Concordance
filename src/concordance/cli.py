"""Ligne de commande unique du projet.

    concordance run [pdf ...]            pipeline L0 -> L9 (appelle le modèle)
    concordance compare [dossier ...]    rejoue L6 -> L8, sans modèle
    concordance report [dossier ...]     rejoue L9 (rapport PDF), sans modèle
    concordance revise dossier [json]    rejoue L8 sous révisions (BF9)
    concordance history [id]             historique des analyses (BF11)
    concordance create-user NOM EMAIL    crée un compte utilisateur (BF1)
    concordance serve                    lance l'application web

Équivalent : `python -m concordance <commande>`.
"""

import argparse
import json
import sys
from getpass import getpass
from pathlib import Path

from concordance import __version__, config


def _print_summary(summary: dict) -> None:
    print(f"  {summary['status']}  ({summary['pages']} pages)")
    for d in summary["documents"]:
        print(f"    {d['type']}: {d['verdict']} (conf {d['confidence']})")
    c = summary.get("comparaison")
    if c:
        print(f"    comparaison: {c['conformes']}/{c['produits']} conformes, "
              f"{c['ecarts']} écart(s), {c['ambigus']} ambigu(s)")
    if summary.get("rapport"):
        print(f"    rapport: {summary['rapport']}")
    elif summary.get("rapport_erreur"):
        print(f"    ! rapport non généré : {summary['rapport_erreur']}")
    if summary.get("id_analyse"):
        print(f"    analyse n°{summary['id_analyse']} enregistrée en base")
    for e in summary["errors"]:
        print(f"  ! {e}")


def cmd_run(args) -> int:
    from concordance import pipeline

    pdfs = [Path(p) for p in args.pdf] or sorted(config.SAMPLES_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"Aucun PDF à traiter (dossier {config.SAMPLES_DIR}).", file=sys.stderr)
        return 1

    persist = not args.no_db
    if persist and not config.database_configured():
        print("DATABASE_URL absent : analyse non enregistrée en base "
              "(utiliser --no-db pour masquer ce message).", file=sys.stderr)
        persist = False

    client = pipeline.make_client()
    schemas = pipeline.load_schemas()
    failures = 0
    for pdf in pdfs:
        print(f"-> {pdf.name}")
        try:
            summary = pipeline.process_pdf(client, pdf, schemas, persist=persist)
        except Exception as exc:
            failures += 1
            print(f"  ÉCHEC : {exc}")
            continue
        _print_summary(summary)
    return 1 if failures else 0


def cmd_compare(args) -> int:
    from concordance import replay
    replay.compare_all(args.dossier)
    return 0


def cmd_report(args) -> int:
    from concordance import replay
    replay.report_all(args.dossier)
    return 0


def cmd_revise(args) -> int:
    from concordance import replay

    folder = config.OUTPUTS_DIR / args.dossier
    if not folder.is_dir():
        print(f"dossier introuvable : {folder}", file=sys.stderr)
        return 2
    revisions = None
    if args.revisions:
        revisions = json.loads(Path(args.revisions).read_text(encoding="utf-8"))
    return replay.revise_folder(folder, revisions)


def cmd_history(args) -> int:
    from concordance import history
    history.main(args.id)
    return 0


def cmd_create_user(args) -> int:
    from concordance import accounts

    # Le mot de passe est demandé au clavier (jamais en argument : il resterait
    # dans l'historique du shell).
    password = getpass("Mot de passe : ")
    if password != getpass("Confirmer : "):
        print("Les deux saisies diffèrent.", file=sys.stderr)
        return 1
    try:
        accounts.create_user(args.nom, args.email, password, args.role)
    except accounts.AccountError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Utilisateur créé : {args.nom} <{args.email}> ({args.role})")
    return 0


def cmd_serve(args) -> int:
    import uvicorn
    uvicorn.run("concordance.webapp.main:app", host=args.host, port=args.port,
                reload=args.reload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="concordance",
        description="Contrôle automatique de cohérence BC / BL / Facture.")
    parser.add_argument("--version", action="version", version=f"concordance {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="commande")

    p = sub.add_parser("run", help="traite des PDF (pipeline L0 à L9, appelle le modèle)")
    p.add_argument("pdf", nargs="*", help="PDF à traiter (défaut : samples/*.pdf)")
    p.add_argument("--no-db", action="store_true",
                   help="n'enregistre pas l'analyse en base de données")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("compare", help="rejoue L6 à L8 sur des extractions existantes")
    p.add_argument("dossier", nargs="*", help="dossiers de data/outputs/ (défaut : tous)")
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("report", help="régénère les rapports PDF (L9)")
    p.add_argument("dossier", nargs="*", help="dossiers de data/outputs/ (défaut : tous)")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("revise", help="rejoue la comparaison sous révisions de l'opérateur")
    p.add_argument("dossier", help="dossier de data/outputs/")
    p.add_argument("revisions", nargs="?",
                   help="fichier JSON de révisions (sans fichier : liste les lignes)")
    p.set_defaults(func=cmd_revise)

    p = sub.add_parser("history", help="historique des analyses enregistrées en base")
    p.add_argument("id", nargs="?", type=int, help="détail de l'analyse n°ID")
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("create-user", help="crée un compte utilisateur")
    p.add_argument("nom")
    p.add_argument("email")
    p.add_argument("--role", default="utilisateur")
    p.set_defaults(func=cmd_create_user)

    p = sub.add_parser("serve", help="lance l'application web")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--reload", action="store_true", help="rechargement automatique (dev)")
    p.set_defaults(func=cmd_serve)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except config.MissingConfigError as exc:
        print(f"Configuration manquante : {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
