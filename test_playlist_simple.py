#!/usr/bin/env python3
"""Simple test for playlist URL detection and extraction."""

import asyncio
from yt_dlp import YoutubeDL

def is_playlist_url(url: str) -> bool:
    """Check if URL is a playlist."""
    playlist_keywords = [
        'playlist', 'list=', 'playlist?list=', '/playlist/',
        'album', 'channel', 'user'
    ]
    url_lower = url.lower()
    return any(keyword in url_lower for keyword in playlist_keywords)

async def extract_playlist_urls_simple(url: str, max_videos: int = 5) -> list[str]:
    """Extract individual video URLs from a playlist URL."""
    try:
        # Use yt-dlp to extract playlist info without downloading
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,  # Don't download, just extract URLs
            "age_limit": 99,  # Allow adult content
            "ignoreerrors": True,  # Continue on errors
            "playlistend": max_videos,  # Limit number of videos
        }

        def extract_sync():
            with YoutubeDL(ydl_opts) as ydl:
                print(f"DEBUG: Extracting playlist info for {url}")
                info = ydl.extract_info(url, download=False)

                if not info:
                    print("DEBUG: No info returned from yt-dlp")
                    return []

                # Handle different playlist structures
                if 'entries' in info:
                    entries = info['entries']
                    print(f"DEBUG: Found {len(entries)} entries in playlist")
                elif isinstance(info, list):
                    entries = info
                    print(f"DEBUG: Info is list with {len(entries)} items")
                else:
                    print(f"DEBUG: Unexpected info structure: {type(info)}")
                    return []

                # Extract URLs from entries
                video_urls = []
                for i, entry in enumerate(entries):
                    if isinstance(entry, dict):
                        video_url = entry.get('url') or entry.get('webpage_url')
                        if video_url:
                            video_urls.append(video_url)
                            print(f"DEBUG: Extracted URL {i+1}: {video_url[:60]}...")
                        else:
                            print(f"DEBUG: No URL found in entry {i+1}")
                    elif isinstance(entry, str):
                        video_urls.append(entry)
                        print(f"DEBUG: String URL {i+1}: {entry[:60]}...")

                limited_urls = video_urls[:max_videos]
                print(f"DEBUG: Returning {len(limited_urls)} URLs (from {len(video_urls)} found)")
                return limited_urls

        # Run in thread pool to avoid blocking
        import concurrent.futures
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, extract_sync)
            return result

    except Exception as e:
        print(f"Error extracting playlist URLs: {e}")
        return []

# Test URLs
test_urls = [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Single video
    "https://www.youtube.com/playlist?list=PLrAXtmRdnEQy9JvN8QKDQvh6K7r7bYHJL",  # YouTube playlist
    "https://www.pornhub.com/playlist/48925601",  # Pornhub playlist
    "https://www.youtube.com/channel/UC1234567890",  # YouTube channel
    "https://www.youtube.com/user/username",  # YouTube user
]

async def main():
    print("🧪 Testing playlist URL detection:")
    for url in test_urls:
        is_playlist = is_playlist_url(url)
        print(f"  {'🎵' if is_playlist else '🎬'} {url[:60]}{'...' if len(url) > 60 else ''} -> {'PLAYLIST' if is_playlist else 'VIDEO'}")

    print("\n📋 Testing playlist extraction:")
    test_playlist = "https://www.pornhub.com/playlist/48925601"
    print(f"Extracting from: {test_playlist}")

    try:
        urls = await extract_playlist_urls_simple(test_playlist, max_videos=3)
        print(f"\n✅ Found {len(urls)} URLs:")
        for i, url in enumerate(urls, 1):
            print(f"  {i}. {url}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
