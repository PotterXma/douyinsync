"""YouTube Upload Test - Outputs to file"""
import os, sys, json, logging, traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

# Log to file
logging.basicConfig(
    filename=str(PROJECT_ROOT / "test_upload.log"),
    level=logging.DEBUG,
    format="%(asctime)s | %(message)s",
    encoding="utf-8"
)
log = logging.getLogger("test")
log.addHandler(logging.StreamHandler())  # also print

def main():
    log.info("=== YouTube Upload Test START ===")
    
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    client_secrets = PROJECT_ROOT / "client_secret.json"
    
    # Find token
    token_paths = [
        PROJECT_ROOT / "youtube_token.json",
        PROJECT_ROOT / "dist" / "DouyinSync" / "youtube_token.json"
    ]
    
    creds = None
    for tf in token_paths:
        if tf.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(tf), SCOPES)
                log.info(f"Loaded token from: {tf}")
                break
            except Exception as e:
                log.warning(f"Bad token at {tf}: {e}")
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            log.info("Refreshing expired token...")
            try:
                creds.refresh(Request())
                log.info("Token refreshed OK")
            except Exception as e:
                log.warning(f"Refresh failed: {e}")
                creds = None
        
        if not creds:
            log.info("Browser auth needed...")
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), SCOPES)
            creds = flow.run_local_server(port=0, open_browser=True)
            log.info("Browser auth OK")
        
        for tf in token_paths:
            try:
                tf.parent.mkdir(parents=True, exist_ok=True)
                with open(tf, 'w') as f:
                    f.write(creds.to_json())
                log.info(f"Token saved: {tf}")
            except:
                pass
    
    # Build client using credentials directly (NOT httplib2)
    from googleapiclient.discovery import build
    
    log.info("Building YouTube client with credentials (no httplib2)...")
    try:
        youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
        log.info("YouTube client OK")
    except Exception as e:
        log.error(f"Build failed: {e}\n{traceback.format_exc()}")
        return
    
    # Find video
    video = None
    for d in [PROJECT_ROOT / "dist" / "DouyinSync" / "downloads", PROJECT_ROOT / "downloads"]:
        if d.exists():
            for mp4 in d.rglob("*.mp4"):
                if mp4.stat().st_size > 100*1024:
                    video = mp4
                    break
        if video:
            break
    
    if not video:
        log.error("No video found!")
        return
    
    size_mb = video.stat().st_size / 1024 / 1024
    log.info(f"Video: {video.name} ({size_mb:.1f} MB)")
    
    # Upload
    from googleapiclient.http import MediaFileUpload
    
    body = {
        'snippet': {
            'title': video.stem[:100],
            'description': 'auto test',
            'categoryId': '22'
        },
        'status': {
            'privacyStatus': 'private',
            'selfDeclaredMadeForKids': False
        }
    }
    
    media = MediaFileUpload(str(video), chunksize=2*1024*1024, resumable=True)
    
    log.info("Starting upload...")
    try:
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                log.info(f"Progress: {int(status.progress()*100)}%")
        
        yt_id = response.get('id')
        log.info(f"SUCCESS! Video ID: {yt_id}")
        log.info(f"URL: https://youtu.be/{yt_id}")
        
    except Exception as e:
        log.error(f"Upload FAILED: {e}")
        log.error(traceback.format_exc())
    
    log.info("=== YouTube Upload Test END ===")

if __name__ == "__main__":
    main()
