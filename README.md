# Weekly "100 Latest Likes" Spotify playlist

Every Monday morning, a free GitHub Action copies your 100 most recently liked songs into one playlist called **My 100 Latest Likes** (it creates the playlist the first time, then overwrites the same one each week, so the link never changes).

## Before you start: Spotify Premium

As of February 2026, Spotify requires the owner of any Web API app in Development Mode to have an active Premium subscription. If the subscription lapses, the app stops working. Check this first, because the whole approach depends on it.

## One-time setup (about 15 minutes)

### 1. Create a Spotify app

1. Go to https://developer.spotify.com/dashboard and log in.
2. Click **Create app**. Any name and description are fine.
3. Add this exact Redirect URI: `http://127.0.0.1:8888/callback` (it must say 127.0.0.1, not localhost).
4. Tick **Web API**, agree to the terms, and save.
5. Open the app's **Settings** and copy the **Client ID**. Click **View client secret** and copy that too.

### 2. Get your refresh token (on your own computer)

In a terminal, in the folder with these files:

```
python3 get_refresh_token.py
```

Paste the Client ID and Client Secret when asked. Your browser opens, you click **Agree**, and the terminal prints a long refresh token. Copy it. Treat it like a password.

### 3. Put the project on GitHub

1. Create a new **private** repository (private keeps your setup out of public view and avoids GitHub pausing scheduled jobs on inactive public repos).
2. Upload these files, keeping the folder structure: `sync_recent_likes.py`, `.github/workflows/weekly-likes.yml`. (`get_refresh_token.py` and this README are optional.)
3. In the repo go to **Settings > Secrets and variables > Actions > New repository secret** and add three secrets:
   - `SPOTIFY_CLIENT_ID`
   - `SPOTIFY_CLIENT_SECRET`
   - `SPOTIFY_REFRESH_TOKEN`

Never commit these values to a file.

### 4. Test it

Open the repo's **Actions** tab, choose **Weekly recent likes playlist**, and click **Run workflow**. In about 20 seconds you should see "Updated My 100 Latest Likes with 100 songs" in the log, and the playlist appears in Spotify (restart the app if it does not show up right away).

After that it runs by itself every Monday at 12:00 UTC (8 AM New York in summer, 7 AM in winter). Change the `cron` line in the workflow file to move it.

## Optional settings

Set these as `env` values in the workflow file next to `PLAYLIST_NAME`:

- `PLAYLIST_NAME`: rename the playlist. The script finds it by this exact name, so if you rename it in Spotify later, change it here too, or it will create a second one.
- `PLAYLIST_PUBLIC`: set to `"true"` if the newly created playlist should be public. Default is private.
- `TRACK_COUNT`: anything from 1 to 100.
- `PLAYLIST_ID`: pin to a specific existing playlist by its ID and skip the name lookup.

## Try it locally without changing anything

```
export SPOTIFY_CLIENT_ID=...  SPOTIFY_CLIENT_SECRET=...  SPOTIFY_REFRESH_TOKEN=...
python3 sync_recent_likes.py --dry-run
```

## Troubleshooting

- **invalid_grant**: the refresh token stopped working. Run `get_refresh_token.py` again and update the `SPOTIFY_REFRESH_TOKEN` secret.
- **403 errors**: confirm your account still has Premium, and that your Spotify email is listed under **User Management** in the app's settings on the developer dashboard.
- **Nothing changes in the playlist**: the script never wipes the playlist. If it finds zero liked songs, it leaves things alone.
- Local files and podcast episodes in your likes are skipped, since Spotify's API cannot add them to playlists.

## What it does, in plain terms

1. Trades the refresh token for a short-lived access token.
2. Reads your Liked Songs, newest first, until it has 100 (it checks the order and re-sorts if Spotify ever returns them differently).
3. Finds your playlist by name, or creates it.
4. Replaces the playlist contents with those 100 songs.
