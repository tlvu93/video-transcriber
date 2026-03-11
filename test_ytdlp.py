import yt_dlp
import sys

def test_download(url):
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'quiet': False,
        'no_warnings': False,
        # Possible bypasses to uncomment if standard download fails:
        # 'cookiesfrombrowser': ('chrome',), # If running locally with a browser
        # 'username': 'oauth2', # Modern OAuth flow for YouTube
        # 'password': '',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Attempting to fetch info for: {url}")
            info = ydl.extract_info(url, download=False)
            print(f"Success! Found video: {info.get('title', 'Unknown Title')}")
            return True
    except Exception as e:
        print(f"Failed: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_download(sys.argv[1])
    else:
        print("Please provide a YouTube URL.")
