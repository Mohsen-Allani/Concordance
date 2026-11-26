# Concordance — interface React

Nouvelle interface web de Concordance (React 18 + Vite). Elle remplace
fonctionnellement l'interface historique de `src/concordance/webapp/static/`,
**qui reste en place et inchangée** : les deux coexistent.

Aucune ligne du backend n'a été modifiée. L'interface consomme l'API FastAPI
existante (voir `docs/api.md`).

## Démarrer

Prérequis : Node.js 18 ou plus, et le backend lancé (`docker compose up`,
port 8000).

```powershell
cd frontend
npm install      # la première fois seulement
npm run dev      # http://localhost:5173
```

Vite relaie toutes les requêtes `/api/...` vers `http://localhost:8000`
(voir `vite.config.js`). Pour un backend ailleurs, créer `frontend/.env.local` :

```
VITE_API_TARGET=http://autre-machine:8000
```

Version optimisée : `npm run build`, puis `npm run preview`
(http://localhost:4173, même relais vers l'API).

## Écrans

| Route | Écran |
|---|---|
| `/` | Page d'accueil publique : présentation du projet, problématique, solution, fonctionnement, résultats, fonctionnalités |
| `/connexion` | Connexion (compte créé par `concordance create-user`) |
| `/app` | Tableau de bord : bannière d'accueil, indicateurs, activité sur 8 semaines, répartition, file de révision |
| `/app/analyses/nouvelle` | Dépôt d'un PDF et suivi des 5 étapes du traitement |
| `/app/analyses` | Historique : filtres, recherche, tri, pagination |
| `/app/revisions` | File des analyses en attente de décision |
| `/app/analyses/:id` | Détail d'une analyse, en cinq onglets |

Identité visuelle : sarcelle profond et ambre, polices Plus Jakarta Sans et
JetBrains Mono (`src/styles/tokens.css`). Les illustrations de la page
d'accueil sont dessinées en code (`src/pages/landing/Illustrations.jsx`) :
aucune image externe. Pour ajouter des photos, les placer dans
`frontend/public/images/` et les référencer par `/images/nom.jpg`.

Onglets du détail :

- **Synthèse** : verdict global, indicateurs, parties, contrôles d'en-tête,
  documents, principaux écarts, synthèse par paire.
- **Rapprochement** : un produit par ligne, filtrable ; chaque produit se
  déplie sur ses lignes BC / BL / Facture, la comparaison champ par champ
  (écart, tolérance) et les preuves de l'appariement.
- **Montants** : comparaison des totaux entre documents, écart net facturé.
- **Documents** : en-tête, parties, totaux et toutes les lignes de chaque
  document avec leur situation dans le rapprochement.
- **Révision** : ambiguïtés à trancher, lignes non rapprochées, documents à
  vérifier, modifications en attente et piste d'audit.

## Révisions

Les gestes de l'opérateur (choisir un candidat, affecter, détacher, corriger
une valeur) sont accumulés localement, puis envoyés en une fois par
« Enregistrer et recalculer » (`PATCH /api/analyses/{id}/revisions`), au
format documenté dans `docs/api.md`. Le serveur rejoue la chaîne et renvoie
le nouvel état. Chaque geste en attente peut être retiré individuellement.

## Organisation

```
src/
  api/client.js        appels à l'API, jeton JWT
  context/             session (AuthContext), notifications (ToastContext)
  lib/                 formats, statuts, lecture de la comparaison, révisions
  components/          interface générique (ui/), structure (layout/), graphiques
  pages/               écrans ; pages/analysis/ : détail et ses onglets
  styles/              jetons de design et feuilles de style
```

## Différences avec l'ancienne interface

- Affectation par liste déroulante plutôt que glisser-déposer (plus fiable,
  accessible au clavier).
- Le détail des contrôles arithmétiques ligne à ligne (L7) n'est pas exposé
  par l'API actuelle : seuls le verdict et la confiance par document sont
  affichés.
