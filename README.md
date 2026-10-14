# LB Prod — Suivi YouTube de l'artiste Wilson

TP "De l'API au tableau de bord". Pipeline : API YouTube → Python → BigQuery → Data Studio.

## Cas d'usage

**LB Prod** est un label musical fictif qui produit plusieurs artistes, dont Wilson. LB Prod a besoin de suivre la performance digitale de ses artistes sur YouTube (abonnés, vues, engagement par clip) pour décider où investir en promotion, repérer les titres qui fonctionnent le mieux, et comprendre l'évolution de l'audience dans le temps.

## API utilisée

**YouTube Data API v3** (gratuite, clé API simple). Choisie après avoir testé l'API Spotify (bloquée sans abonnement Premium sur le compte créateur de l'app, même pour des données publiques) et Deezer (impossible d'identifier l'artiste de façon fiable parmi plusieurs profils homonymes).

## Architecture

```
API YouTube Data v3
       │
       ▼
collecte_youtube.py (Python)
  - appelle l'API (chaîne + vidéos)
  - nettoie les données (types, valeurs manquantes, doublons)
  - exporte en CSV (data/)
       │
       ▼
BigQuery (projet api-au-tableau-de-bord, dataset youtube_artiste)
  - table channel_profile
  - table videos
       │
       ▼
Data Studio (dashboard)
```

L'automatisation est gérée par **GitHub Actions** (`.github/workflows/collecte.yml`), planifiée pour tourner une fois par jour. Chaque exécution est visible dans l'onglet "Actions" du dépôt (preuve d'exécution).

## Installation

```bash
pip install -r requirements.txt
```

Variables d'environnement nécessaires (fichier `.env` en local, voir `.env.example`) :
- `YOUTUBE_API_KEY` : clé API YouTube Data v3

Pour BigQuery en local : être authentifié avec `gcloud auth application-default login`.

## Exécution

**Notebooks** (exploration, étapes 02 et 03 documentées pas à pas) :
- `notebooks/01_collecte_youtube.ipynb` — collecte et nettoyage
- `notebooks/02_bigquery.ipynb` — chargement BigQuery et requêtes SQL

**Requêtes SQL** (étape 03, extraites du notebook pour être exécutables indépendamment) :
- `sql/01_top_10_videos.sql`
- `sql/02_taux_engagement.sql`
- `sql/03_videos_par_annee.sql`

**Script d'automatisation** (étape 04, reprend la même logique en un seul fichier) :
```bash
python3 collecte_youtube.py
```

Les logs sont écrits dans `logs/collecte.log` (non versionné).

## Automatisation

GitHub Actions exécute `collecte_youtube.py` automatiquement tous les jours. Le chargement BigQuery utilise `WRITE_TRUNCATE` (remplace la table à chaque exécution), donc aucun doublon n'est créé même en cas de ré-exécution manuelle.

Authentification Google Cloud sans clé JSON stockée : **Workload Identity Federation**. GitHub Actions s'authentifie directement via le compte de service dédié `github-actions-youtube-artiste@api-au-tableau-de-bord.iam.gserviceaccount.com` (droits limités à BigQuery).

Secret utilisé par le workflow (configuré dans les paramètres du dépôt GitHub, jamais commité) :
- `YOUTUBE_API_KEY`

## Données

- `channel_profile` : 1 ligne, stats globales de la chaîne (abonnés, vues totales, nb vidéos)
- `videos` : 1 ligne par vidéo (titre, date de publication, vues, likes, commentaires)

Contrôles qualité appliqués : vérification du code HTTP, conversion des types (texte → nombres/dates), détection des valeurs manquantes et des doublons, horodatage de chaque collecte (`collected_at`).

## Dashboard

Lien Data Studio : _à ajouter_
