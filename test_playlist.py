#!/usr/bin/env python3
"""Test script to test playlist URL processing."""

import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from download_manager import is_playlist_url, extract_playlist_urls

async def test_playlist_detection():
    """Test playlist URL detection."""
    test_urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Single video
        "https://www.youtube.com/playlist?list=PLrAXtmRdnEQy9JvN8QKDQvh6K7r7bYHJL",  # YouTube playlist
        "https://www.pornhub.com/playlist/123456",  # Pornhub playlist
        "https://www.youtube.com/channel/UC1234567890",  # YouTube channel
        "https://www.youtube.com/user/username",  # YouTube user
    ]

    print("🧪 Testing playlist URL detection:")
    for url in test_urls:
        is_playlist = is_playlist_url(url)
        print(f"  {'🎵' if is_playlist else '🎬'} {url[:60]}... -> {'PLAYLIST' if is_playlist else 'VIDEO'}")

async def test_playlist_extraction():
    """Test playlist URL extraction."""
    # Test with a small YouTube playlist
    test_playlist = "https://www.youtube.com/playlist?list=PL4lCao7KL_QFVb7Iudeipvc2BCavECqzc"

    print(f"\n📋 Testing playlist extraction: {test_playlist}")
    try:
        video_urls = await extract_playlist_urls(test_playlist, max_videos=3)
        print(f"✅ Extracted {len(video_urls)} video URLs:")
        for i, url in enumerate(video_urls, 1):
            print(f"  {i}. {url}")
    except Exception as e:
        print(f"❌ Error extracting playlist: {e}")

if __name__ == "__main__":
    asyncio.run(test_playlist_detection())
    asyncio.run(test_playlist_extraction())
