"""
Script d'automatisation (étape 04) pour le TP LB Prod / artiste Wilson.

Récupère les stats de la chaîne et des vidéos via l'API YouTube, nettoie
les données, et les charge dans BigQuery (dataset youtube_artiste, projet
api-au-tableau-de-bord).

Lancement manuel :
    python3 collecte_youtube.py

Pensé pour être lancé automatiquement (GitHub Actions). Chaque exécution
remplace les tables BigQuery (WRITE_TRUNCATE) au lieu d'ajouter les lignes,
donc relancer le script ne crée jamais de doublons. Les logs sont écrits
dans logs/collecte.log.
"""

import logging
import os
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from google.cloud import bigquery

# Dossier où se trouve ce script, pour que les chemins marchent peu importe d'où on le lance
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Configuration des logs : écrit à la fois dans un fichier et à l'écran
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "collecte.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

CHANNEL_ID = "UCFXq9XWKAM4DMlPwQAiMcPg"
PROJECT_ID = "api-au-tableau-de-bord"
DATASET_ID = "youtube_artiste"
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


def get_api_key() -> str:
    # Charge .env si présent (en local) ; en GitHub Actions, la variable sera déjà définie autrement
    load_dotenv(BASE_DIR / ".env")
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise RuntimeError("YOUTUBE_API_KEY manquante (variable d'environnement ou .env)")
    return api_key


def fetch_channel_stats(api_key: str) -> pd.DataFrame:
    # Appel API : infos générales de la chaîne (abonnés, vues totales, nb vidéos)
    response = requests.get(
        f"{YOUTUBE_API_BASE}/channels",
        params={"part": "snippet,statistics", "id": CHANNEL_ID, "key": api_key},
    )
    response.raise_for_status()
    info = response.json()["items"][0]

    # On construit un petit tableau d'une seule ligne avec ce qui nous intéresse
    df = pd.DataFrame([{
        "channel_id": info["id"],
        "title": info["snippet"]["title"],
        "subscriber_count": int(info["statistics"]["subscriberCount"]),
        "view_count": int(info["statistics"]["viewCount"]),
        "video_count": int(info["statistics"]["videoCount"]),
    }])
    df["collected_at"] = pd.Timestamp.now(tz="UTC")
    logger.info("Chaîne récupérée : %s abonnés, %s vues", df["subscriber_count"][0], df["view_count"][0])
    return df


def fetch_uploads_playlist_id(api_key: str) -> str:
    # Chaque chaîne YouTube a une playlist spéciale "uploads" qui contient toutes ses vidéos
    response = requests.get(
        f"{YOUTUBE_API_BASE}/channels",
        params={"part": "contentDetails", "id": CHANNEL_ID, "key": api_key},
    )
    response.raise_for_status()
    return response.json()["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]


def fetch_video_ids(api_key: str, playlist_id: str) -> list[str]:
    # On récupère la liste des IDs vidéos de cette playlist, page par page (max 50 par appel)
    video_ids = []
    next_page_token = None

    while True:
        response = requests.get(
            f"{YOUTUBE_API_BASE}/playlistItems",
            params={
                "part": "contentDetails",
                "playlistId": playlist_id,
                "maxResults": 50,
                "pageToken": next_page_token,
                "key": api_key,
            },
        )
        response.raise_for_status()
        page = response.json()
        video_ids += [item["contentDetails"]["videoId"] for item in page["items"]]
        next_page_token = page.get("nextPageToken")
        if next_page_token is None:
            break  # plus de page suivante, on a tout récupéré

    logger.info("%d IDs de vidéos trouvés", len(video_ids))
    return video_ids


def fetch_videos_stats(api_key: str, video_ids: list[str]) -> pd.DataFrame:
    # Pour chaque lot de 50 vidéos (limite de l'API), on récupère les stats détaillées
    rows = []

    for i in range(0, len(video_ids), 50):
        batch_ids = video_ids[i:i + 50]
        response = requests.get(
            f"{YOUTUBE_API_BASE}/videos",
            params={"part": "snippet,statistics", "id": ",".join(batch_ids), "key": api_key},
        )
        response.raise_for_status()
        for video in response.json()["items"]:
            stats = video["statistics"]
            rows.append({
                "video_id": video["id"],
                "title": video["snippet"]["title"],
                "published_at": video["snippet"]["publishedAt"],
                "view_count": int(stats.get("viewCount", 0)),
                "like_count": int(stats.get("likeCount", 0)),
                "comment_count": int(stats.get("commentCount", 0)),
            })

    df = pd.DataFrame(rows)
    # Nettoyage : vraie date au lieu de texte, tri par nombre de vues
    df["published_at"] = pd.to_datetime(df["published_at"])
    df["collected_at"] = pd.Timestamp.now(tz="UTC")
    df = df.sort_values("view_count", ascending=False).reset_index(drop=True)

    # Contrôle qualité, comme dans les notebooks : valeurs manquantes et doublons
    missing = df.isna().sum().sum()
    duplicates = df.duplicated().sum()
    logger.info("%d vidéos récupérées, %d valeurs manquantes, %d doublons", len(df), missing, duplicates)
    return df


def load_to_bigquery(client: bigquery.Client, df: pd.DataFrame, table_name: str) -> None:
    # WRITE_TRUNCATE = on remplace toute la table à chaque fois, donc jamais de doublons
    # même si on relance le script plusieurs fois (exigence de l'étape 04 du TP)
    table_id = f"{PROJECT_ID}.{DATASET_ID}.{table_name}"
    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()
    logger.info("Table %s chargée (%d lignes, WRITE_TRUNCATE)", table_id, len(df))


def main() -> None:
    logger.info("=== Démarrage de la collecte ===")

    try:
        api_key = get_api_key()

        # Étape 1 : collecte (même logique que le notebook 01_collecte_youtube.ipynb)
        channel_df = fetch_channel_stats(api_key)
        playlist_id = fetch_uploads_playlist_id(api_key)
        video_ids = fetch_video_ids(api_key, playlist_id)
        videos_df = fetch_videos_stats(api_key, video_ids)

        # On garde aussi un export CSV, utile pour debug ou relecture rapide
        channel_df.to_csv(BASE_DIR / "data" / "channel_profile.csv", index=False)
        videos_df.to_csv(BASE_DIR / "data" / "videos.csv", index=False)

        # Étape 2 : chargement dans BigQuery (même logique que le notebook 02_bigquery.ipynb)
        client = bigquery.Client(project=PROJECT_ID)
        dataset = bigquery.Dataset(f"{PROJECT_ID}.{DATASET_ID}")
        dataset.location = "EU"
        client.create_dataset(dataset, exists_ok=True)

        load_to_bigquery(client, channel_df, "channel_profile")
        load_to_bigquery(client, videos_df, "videos")

        logger.info("=== Collecte terminée avec succès ===")
    except Exception:
        # On logue l'erreur complète avant de la relancer, pour qu'elle apparaisse
        # bien dans les logs GitHub Actions et pas seulement dans la console
        logger.exception("=== Échec de la collecte ===")
        raise


if __name__ == "__main__":
    main()
