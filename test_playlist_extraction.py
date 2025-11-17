#!/usr/bin/env python3
"""Test playlist extraction with debugging."""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

async def test_playlist_extraction():
    """Test playlist extraction."""
    from download_manager import extract_playlist_urls

    # Test with the same URL that was failing
    test_url = "https://www.pornhub.com/playlist/48925601"

    print(f"Testing playlist extraction for: {test_url}")
    print("This will show debug output from the extraction process...")

    try:
        urls = await extract_playlist_urls(test_url, max_videos=5)  # Test with small limit
        print(f"\n✅ Extraction completed. Found {len(urls)} URLs:")
        for i, url in enumerate(urls, 1):
            print(f"  {i}. {url}")
    except Exception as e:
        print(f"❌ Extraction failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_playlist_extraction())
