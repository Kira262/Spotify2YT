import os
import time
import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth
import google_auth_oauthlib.flow
import googleapiclient.discovery

PROGRESS_FILE = "progress.txt"

# Load .env variables
load_dotenv()
print("[DEBUG] Loaded SPOTIFY_CLIENT_ID:", os.getenv("SPOTIFY_CLIENT_ID"))
print("[DEBUG] SPOTIFY_CLIENT_SECRET:", os.getenv("SPOTIFY_CLIENT_SECRET"))
print("[DEBUG] SPOTIFY_REDIRECT_URL:", os.getenv("SPOTIFY_REDIRECT_URL"))

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URL = os.getenv("SPOTIFY_REDIRECT_URL")
YOUTUBE_PLAYLIST_NAME = os.getenv("YOUTUBE_PLAYLIST_NAME", "Spotify Liked Songs")

# Validate environment variables
required = [SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URL]
if not all(required):
    raise EnvironmentError("Missing required .env variables")

# Spotify client
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URL,
    scope="user-library-read"
))

def get_spotify_liked_tracks():
    print("Fetching liked songs from Spotify...")
    results = []
    offset = 0
    while True:
        batch = sp.current_user_saved_tracks(limit=50, offset=offset)
        if not batch['items']:
            break
        results += batch['items']
        offset += 50
    print(f"Fetched {len(results)} liked songs from Spotify.")
    return [f"{item['track']['name']} {item['track']['artists'][0]['name']}" for item in results]

def get_youtube_service():
    scopes = ["https://www.googleapis.com/auth/youtube.force-ssl"]
    flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
        "client_secrets.json", scopes)
    creds = flow.run_local_server(port=8080, prompt='consent')
    return googleapiclient.discovery.build("youtube", "v3", credentials=creds)

def create_youtube_playlist(youtube, title):
    print(f"Creating YouTube playlist: {title}")
    request = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": "Automatically imported from Spotify Liked Songs"
            },
            "status": {
                "privacyStatus": "private"
            }
        }
    )
    response = request.execute()
    return response["id"]

def search_youtube_video(youtube, query):
    try:
        request = youtube.search().list(part="snippet", q=query, maxResults=1, type="video")
        response = request.execute()
        items = response.get("items")
        if items:
            return items[0]['id']['videoId']
    except Exception as e:
        print(f"Search failed for '{query}': {e}")
    return None

def add_video_to_playlist(youtube, playlist_id, video_id):
    try:
        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": video_id
                    }
                }
            }
        ).execute()
    except Exception as e:
        print(f"Failed to add video {video_id}: {e}")

def load_progress():
    if not os.path.exists(PROGRESS_FILE):
        return set()
    with open(PROGRESS_FILE, "r") as f:
        return set(map(int, f.read().splitlines()))

def save_progress(index):
    with open(PROGRESS_FILE, "a") as f:
        f.write(f"{index}\n")

def main():
    songs = get_spotify_liked_tracks()
    processed = load_progress()
    youtube = get_youtube_service()
    playlist_id = create_youtube_playlist(youtube, YOUTUBE_PLAYLIST_NAME)

    for i, song in enumerate(songs, 1):
        if i in processed:
            print(f"[{i}/{len(songs)}] Skipping already processed: {song}")
            continue

        print(f"[{i}/{len(songs)}] Searching: {song}")
        video_id = search_youtube_video(youtube, song)
        if video_id:
            add_video_to_playlist(youtube, playlist_id, video_id)
            print(f"Added: {song}")
        else:
            print(f"Not found: {song}")

        save_progress(i)
        time.sleep(1)  # Rate limiting

if __name__ == "__main__":
    main()
