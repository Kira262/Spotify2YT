import os
import time
import json
import pickle
import logging
import asyncio
import aiohttp  # type: ignore
from typing import Set, List, Dict, Any, Optional, Tuple

import spotipy  # type: ignore
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth  # type: ignore
import google_auth_oauthlib.flow  # type: ignore
import googleapiclient.discovery  # type: ignore
from google.auth.transport.requests import Request  # type: ignore
from google.oauth2.credentials import Credentials  # type: ignore

# --- Configuration ---
PROGRESS_FILE = "progress.json"
CREDENTIALS_FILE = "youtube_credentials.pickle"
LOG_FILE = "migration.log"
RETRY_ATTEMPTS = 3
RETRY_DELAY = 5  # Increased base delay for async context
CONCURRENT_REQUESTS = 10  # Max number of parallel API requests

# Global flag to track quota exhaustion
quota_exceeded = False

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# --- Load Environment Variables ---
load_dotenv()
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URL = os.getenv("SPOTIFY_REDIRECT_URL")
YOUTUBE_PLAYLIST_NAME = os.getenv("YOUTUBE_PLAYLIST_NAME", "Spotify Liked Songs")

# --- Synchronous Setup Functions (Run once at the start) ---


def get_spotify_liked_tracks() -> List[str]:
    """Synchronously fetches all liked tracks from Spotify."""
    logger.info("Fetching liked songs from Spotify...")
    # (The rest of this function is unchanged as it's a one-time sync operation)
    sp = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URL,
            scope="user-library-read",
            cache_path=".spotify_cache",
        )
    )
    results = []
    offset = 0
    while True:
        try:
            batch = sp.current_user_saved_tracks(limit=50, offset=offset)
            if not batch["items"]:
                break
            results.extend(batch["items"])
            offset += 50
        except Exception as e:
            logger.error(f"Error fetching Spotify tracks: {e}")
            break

    logger.info(f"Fetched {len(results)} liked songs.")
    songs = []
    for item in results:
        track = item.get("track")
        if track and track.get("name"):
            artists = " ".join([artist["name"] for artist in track["artists"]])
            songs.append(f"{track['name']} {artists}")
    return songs


def get_youtube_credentials() -> Credentials:
    """Synchronously handles YouTube authentication and token refreshing."""
    creds = None
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired YouTube credentials...")
            creds.refresh(Request())
        else:
            logger.info("Performing fresh authentication with YouTube...")
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                "client_secrets.json",
                ["https://www.googleapis.com/auth/youtube.force-ssl"],
            )
            creds = flow.run_local_server(port=8080, prompt="consent")
        with open(CREDENTIALS_FILE, "wb") as f:
            pickle.dump(creds, f)
    return creds


def get_or_create_youtube_playlist(creds: Credentials, title: str) -> str:
    """Uses the synchronous client to find/create the playlist ID."""
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)
    # (This function is unchanged as it's a one-time sync operation)
    next_page_token = None
    while True:
        request = youtube.playlists().list(
            part="snippet", mine=True, maxResults=50, pageToken=next_page_token
        )
        response = request.execute()
        for item in response.get("items", []):
            if item["snippet"]["title"].strip().lower() == title.strip().lower():
                logger.info(f"Found existing playlist: '{title}'")
                return item["id"]
        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    logger.info(f"Creating new YouTube playlist: '{title}'")
    request = youtube.playlists().insert(
        part="snippet,status",
        body={"snippet": {"title": title}, "status": {"privacyStatus": "private"}},
    )
    response = request.execute()
    return response["id"]


# --- Asynchronous Core Functions ---


async def async_search_youtube(
    session: aiohttp.ClientSession, query: str, creds: Credentials
) -> Optional[str]:
    """Asynchronously searches YouTube using aiohttp."""
    global quota_exceeded

    if quota_exceeded:
        return None

    url = "https://www.googleapis.com/youtube/v3/search"
    headers = {"Authorization": f"Bearer {creds.token}"}
    params = {"part": "snippet", "q": query, "maxResults": 5, "type": "video"}

    for attempt in range(RETRY_ATTEMPTS):
        try:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    items = data.get("items", [])
                    if not items:
                        return None
                    # Simple scoring, could be enhanced
                    best_item = max(
                        items,
                        key=lambda item: (
                            0 if "live" in item["snippet"]["title"].lower() else 1
                        ),
                    )
                    return best_item["id"]["videoId"]
                elif response.status in [403, 429]:  # Rate limit / Quota
                    if attempt == RETRY_ATTEMPTS - 1:  # Last attempt failed
                        logger.error(
                            f"Quota exceeded after all retries for '{query}'. Stopping processing."
                        )
                        quota_exceeded = True
                        return None
                    wait = RETRY_DELAY * (2**attempt)
                    logger.warning(
                        f"Search API limit hit for '{query}'. Waiting {wait}s."
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(
                        f"Search for '{query}' failed with status {response.status}: {await response.text()}"
                    )
                    return None
        except aiohttp.ClientError as e:
            logger.error(f"Network error during search for '{query}': {e}")
            if attempt < RETRY_ATTEMPTS - 1:
                await asyncio.sleep(RETRY_DELAY)
    return None


async def async_add_to_playlist(
    session: aiohttp.ClientSession, playlist_id: str, video_id: str, creds: Credentials
) -> bool:
    """Asynchronously adds a video to a playlist."""
    global quota_exceeded

    if quota_exceeded:
        return False

    url = "https://www.googleapis.com/youtube/v3/playlistItems"
    headers = {"Authorization": f"Bearer {creds.token}"}
    json_body = {
        "snippet": {
            "playlistId": playlist_id,
            "resourceId": {"kind": "youtube#video", "videoId": video_id},
        }
    }
    params = {"part": "snippet"}

    for attempt in range(RETRY_ATTEMPTS):
        try:
            async with session.post(
                url, headers=headers, params=params, json=json_body
            ) as response:
                if response.status == 200:
                    return True
                if response.status == 409:  # Already exists
                    logger.info(f"Video {video_id} is already in the playlist.")
                    return True
                elif response.status in [403, 429]:
                    if attempt == RETRY_ATTEMPTS - 1:  # Last attempt failed
                        logger.error(
                            f"Quota exceeded after all retries for video {video_id}. Stopping processing."
                        )
                        quota_exceeded = True
                        return False
                    wait = RETRY_DELAY * (2**attempt)
                    logger.warning(
                        f"Add API limit hit for video {video_id}. Waiting {wait}s."
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(
                        f"Failed to add video {video_id} with status {response.status}: {await response.text()}"
                    )
                    return False
        except aiohttp.ClientError as e:
            logger.error(f"Network error adding video {video_id}: {e}")
            if attempt < RETRY_ATTEMPTS - 1:
                await asyncio.sleep(RETRY_DELAY)
    return False


async def process_song_worker(
    semaphore: asyncio.Semaphore,
    session: aiohttp.ClientSession,
    song: Dict[str, Any],
    playlist_id: str,
    creds: Credentials,
) -> Dict[str, Any]:
    """A worker that processes a single song, respecting the semaphore."""
    global quota_exceeded

    async with semaphore:
        if quota_exceeded:
            logger.info(
                f"[{song['id']}/{song['total']}] Skipping due to quota exceeded: {song['query']}"
            )
            song.update({"status": "quota_exceeded", "video_id": None})
            return song

        logger.info(f"[{song['id']}/{song['total']}] Processing: {song['query']}")
        video_id = await async_search_youtube(session, song["query"], creds)

        if quota_exceeded:
            song.update({"status": "quota_exceeded", "video_id": None})
            return song

        if video_id:
            if await async_add_to_playlist(session, playlist_id, video_id, creds):
                logger.info(f"--> ✓ Added: {song['query']}")
                song.update({"status": "added", "video_id": video_id})
            else:
                if quota_exceeded:
                    song.update({"status": "quota_exceeded", "video_id": video_id})
                else:
                    logger.warning(f"--> ✗ Failed to add: {song['query']}")
                    song.update({"status": "failed_to_add", "video_id": video_id})
        else:
            if quota_exceeded:
                song.update({"status": "quota_exceeded", "video_id": None})
            else:
                logger.warning(f"--> ✗ Not found: {song['query']}")
                song.update({"status": "not_found", "video_id": None})

        return song


# --- Main Execution ---


def load_progress() -> Tuple[Set[int], dict]:
    # (This function is unchanged)
    if not os.path.exists(PROGRESS_FILE):
        return set(), {}
    try:
        with open(PROGRESS_FILE, "r") as f:
            data = json.load(f)
            return set(data.get("processed_indices", [])), data.get("songs", {})
    except Exception as e:
        logger.warning(f"Could not load progress file: {e}")
        return set(), {}


def save_progress(processed_indices: Set[int], song_data: dict):
    # (This function is unchanged)
    try:
        with open(PROGRESS_FILE, "w") as f:
            json.dump(
                {
                    "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "processed_indices": sorted(list(processed_indices)),
                    "songs": song_data,
                },
                f,
                indent=4,
            )
    except Exception as e:
        logger.error(f"Failed to save progress: {e}")


async def main():
    """Main async function to orchestrate the migration."""
    global quota_exceeded
    quota_exceeded = False  # Reset quota flag at start

    try:
        # --- 1. Synchronous Setup ---
        spotify_songs = get_spotify_liked_tracks()
        if not spotify_songs:
            logger.info("No songs to process. Exiting.")
            return

        youtube_creds = get_youtube_credentials()
        playlist_id = get_or_create_youtube_playlist(
            youtube_creds, YOUTUBE_PLAYLIST_NAME
        )
        processed_indices, song_data = load_progress()

        # --- 2. Prepare Tasks for Concurrent Execution ---
        tasks = []
        songs_to_process = []
        for i, query in enumerate(spotify_songs, 1):
            if i not in processed_indices:
                songs_to_process.append(
                    {"id": i, "total": len(spotify_songs), "query": query}
                )

        if not songs_to_process:
            logger.info("All songs have already been processed. Nothing to do.")
            return

        logger.info(
            f"Starting concurrent migration of {len(songs_to_process)} songs..."
        )
        semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

        async with aiohttp.ClientSession() as session:
            for song in songs_to_process:
                if quota_exceeded:
                    logger.info("Quota exceeded, stopping task creation.")
                    break
                task = process_song_worker(
                    semaphore, session, song, playlist_id, youtube_creds
                )
                tasks.append(task)

            # --- 3. Run Tasks Concurrently ---
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # --- 4. Process Results and Save ---
                for res in results:
                    if isinstance(res, Exception):
                        logger.error(f"Task failed with exception: {res}")
                        continue
                    processed_indices.add(res["id"])
                    song_data[str(res["id"])] = res

                save_progress(processed_indices, song_data)

                if quota_exceeded:
                    logger.info(
                        "Migration stopped due to quota exceeded. Progress has been saved."
                    )
            else:
                logger.info("No tasks were created due to quota exceeded.")

    except Exception as e:
        logger.critical(f"An unrecoverable error occurred: {e}", exc_info=True)
    finally:
        logger.info("Migration process finished.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nProcess interrupted by user.")
