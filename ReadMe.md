# Spotify to YouTube Playlist Transfer

A Python application that automatically transfers your liked songs from Spotify to a YouTube playlist. This tool fetches all your Spotify liked songs and searches for them on YouTube, then adds the found videos to a new YouTube playlist.

## Features

- ✅ Fetches all your Spotify liked songs
- ✅ Automatically searches for corresponding videos on YouTube
- ✅ Creates a new YouTube playlist with your transferred songs
- ✅ Progress tracking with resume capability
- ✅ Rate limiting to respect API quotas
- ✅ Error handling for failed searches and additions

## Prerequisites

Before running this application, you need to set up API credentials for both Spotify and YouTube:

### 1. Spotify API Setup

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Log in with your Spotify account
3. Click "Create an App"
4. Fill in the app name and description
5. Note down your **Client ID** and **Client Secret**
6. In your app settings, add `http://localhost:8888/callback` as a redirect URI

### 2. YouTube API Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the YouTube Data API v3
4. Go to "Credentials" and create OAuth 2.0 Client IDs
5. Choose "Desktop application" as the application type
6. Download the JSON file and rename it to `client_secrets.json`
7. Place the `client_secrets.json` file in the project directory

## Installation

1. **Clone or download this repository**

   ```cmd
   git clone <repository-url>
   cd transferSongs
   ```

2. **Install required Python packages**

   ```cmd
   pip install spotipy google-auth-oauthlib google-api-python-client python-dotenv
   ```

3. **Create environment file**

   Create a `.env` file in the project directory with the following content:

   ```env
   SPOTIFY_CLIENT_ID=your_spotify_client_id_here
   SPOTIFY_CLIENT_SECRET=your_spotify_client_secret_here
   SPOTIFY_REDIRECT_URL=http://localhost:8888/callback
   YOUTUBE_PLAYLIST_NAME=Spotify Liked Songs
   ```

   Replace the Spotify credentials with your actual values from step 1.

4. **Place your YouTube credentials**

   Ensure your `client_secrets.json` file (from step 2) is in the project directory.

## Usage

1. **Run the application**

   ```cmd
   python songs.py
   ```

2. **Authentication Process**

   - The application will first prompt you to authenticate with Spotify
   - A browser window will open for Spotify login
   - After Spotify authentication, you'll be prompted for YouTube authentication
   - Another browser window will open for Google/YouTube login
   - Grant the necessary permissions for both services

3. **Transfer Process**
   - The app will fetch all your Spotify liked songs
   - It will create a new YouTube playlist (private by default)
   - Each song will be searched on YouTube and added to the playlist
   - Progress is displayed in the console
   - The process includes 1-second delays between requests to respect API limits

## File Structure

```text
transferSongs/
│
├── songs.py              # Main application script
├── client_secrets.json   # YouTube API credentials (you need to add this)
├── .env                  # Environment variables (you need to create this)
├── ReadMe.md            # This documentation
└── progress.txt         # Auto-generated progress tracking file
```

## Configuration Options

You can customize the following settings in your `.env` file:

- `YOUTUBE_PLAYLIST_NAME`: Name of the YouTube playlist to create (default: "Spotify Liked Songs")
- `SPOTIFY_REDIRECT_URL`: Should match your Spotify app settings (default: `http://localhost:8888/callback`)

## Resume Capability

The application automatically tracks progress in `progress.txt`. If the process is interrupted:

- Simply run `python songs.py` again
- The application will skip already processed songs
- It will continue from where it left off

To start fresh, delete the `progress.txt` file before running.

## Troubleshooting

### Common Issues

1. **"Missing required .env variables" error**

   - Ensure your `.env` file exists and contains all required variables
   - Check that variable names match exactly (case-sensitive)

2. **Spotify authentication fails**

   - Verify your Client ID and Client Secret are correct
   - Ensure the redirect URI in your Spotify app matches your `.env` file

3. **YouTube authentication fails**

   - Check that `client_secrets.json` is in the correct location
   - Ensure YouTube Data API v3 is enabled in Google Cloud Console

4. **"Some songs not found" on YouTube**

   - This is normal - not all Spotify songs may be available on YouTube
   - The application will continue with other songs

5. **API rate limiting**
   - The application includes built-in delays
   - If you encounter limits, wait and run again (it will resume automatically)

### Debug Mode

The application includes debug output for Spotify credentials. Check the console output for:

```text
[DEBUG] Loaded SPOTIFY_CLIENT_ID: your_client_id
[DEBUG] SPOTIFY_CLIENT_SECRET: GOCSPX-...
[DEBUG] SPOTIFY_REDIRECT_URL: http://localhost:8888/callback
```

## Security Notes

- Keep your `.env` file private (add it to `.gitignore` if using version control)
- Don't share your `client_secrets.json` file
- The created YouTube playlist is private by default
- Your credentials are only used locally and not shared

## Dependencies

- `spotipy` - Spotify Web API wrapper
- `google-auth-oauthlib` - Google OAuth 2.0 authentication
- `google-api-python-client` - YouTube Data API client
- `python-dotenv` - Environment variable management

## Limitations

- Only transfers liked songs (not custom playlists)
- YouTube search may not always find exact matches
- Respects API rate limits (may take time for large libraries)
- Requires manual authentication for both services

## License

This project is for personal use. Make sure to comply with Spotify and YouTube's terms of service when using their APIs.

---

Enjoy your transferred playlist! 🎵
