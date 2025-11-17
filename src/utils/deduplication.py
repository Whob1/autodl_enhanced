"""Deduplication utilities for the Enhanced AutoDL Telegram Bot.

This module provides robust URL normalization and duplicate detection to prevent
downloading the same video multiple times. It uses multiple strategies:

1. URL normalization and hashing (handles different query parameter orders, etc.)
2. Video ID extraction for platform-specific deduplication
3. Filename-based duplicate detection for completed downloads
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Optional, Tuple
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse


def normalize_url(url: str) -> str:
    """Normalize a URL for consistent comparison.

    This handles:
    - Protocol normalization (https vs http)
    - Query parameter ordering
    - Removing tracking parameters
    - Lowercase domain names
    - Removing trailing slashes

    Parameters
    ----------
    url : str
        The URL to normalize

    Returns
    -------
    str
        The normalized URL
    """
    # Parse the URL
    parsed = urlparse(url.strip())

    # Normalize scheme (always use https if supported)
    scheme = parsed.scheme.lower()
    if scheme == 'http':
        scheme = 'https'

    # Normalize netloc (lowercase domain)
    netloc = parsed.netloc.lower()

    # Parse and sort query parameters, removing tracking params
    tracking_params = {
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
        'fbclid', 'gclid', 'ref', 'source', 'share'
    }

    query_dict = parse_qs(parsed.query)
    # Remove tracking parameters
    query_dict = {k: v for k, v in query_dict.items() if k not in tracking_params}
    # Sort by key for consistency
    sorted_query = urlencode(sorted(query_dict.items()), doseq=True)

    # Normalize path (remove trailing slash unless it's root)
    path = parsed.path.rstrip('/') if parsed.path != '/' else '/'

    # Reconstruct URL
    normalized = urlunparse((
        scheme,
        netloc,
        path,
        parsed.params,
        sorted_query,
        ''  # Remove fragment
    ))

    return normalized


def extract_video_id(url: str) -> Optional[str]:
    """Extract the video ID from a URL for platform-specific deduplication.

    Supports:
    - Pornhub (viewkey parameter)
    - YouTube (v parameter or short URL)
    - Xvideos (video ID in path)
    - Twitter/X (status ID)
    - Reddit (post ID)
    - And many more platforms

    Parameters
    ----------
    url : str
        The video URL

    Returns
    -------
    Optional[str]
        The video ID if found, None otherwise
    """
    url_lower = url.lower()
    parsed = urlparse(url)

    # Pornhub
    if 'pornhub.com' in url_lower:
        match = re.search(r'viewkey=([a-f0-9]+)', url, re.IGNORECASE)
        if match:
            return f"pornhub:{match.group(1)}"

    # YouTube
    if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
        if 'youtu.be' in url_lower:
            video_id = parsed.path.strip('/')
            return f"youtube:{video_id}"
        else:
            query = parse_qs(parsed.query)
            if 'v' in query:
                return f"youtube:{query['v'][0]}"

    # Xvideos
    if 'xvideos.com' in url_lower:
        match = re.search(r'/video([0-9]+)/', url)
        if match:
            return f"xvideos:{match.group(1)}"

    # Xhamster
    if 'xhamster.com' in url_lower:
        match = re.search(r'/videos/[^/]+-([0-9]+)', url)
        if match:
            return f"xhamster:{match.group(1)}"

    # Redtube
    if 'redtube.com' in url_lower:
        match = re.search(r'/([0-9]+)', url)
        if match:
            return f"redtube:{match.group(1)}"

    # Twitter/X
    if 'twitter.com' in url_lower or 'x.com' in url_lower:
        match = re.search(r'/status/([0-9]+)', url)
        if match:
            return f"twitter:{match.group(1)}"

    # Reddit
    if 'reddit.com' in url_lower:
        match = re.search(r'/comments/([a-z0-9]+)', url)
        if match:
            return f"reddit:{match.group(1)}"

    # Spankbang
    if 'spankbang.com' in url_lower:
        match = re.search(r'/([a-z0-9]+)/video/', url)
        if match:
            return f"spankbang:{match.group(1)}"

    # OnlyFans (if supported)
    if 'onlyfans.com' in url_lower:
        match = re.search(r'/([0-9]+)/', url)
        if match:
            return f"onlyfans:{match.group(1)}"

    # Generic fallback - use the full normalized URL
    return None


def compute_url_hash(url: str) -> str:
    """Compute a hash of the normalized URL for efficient storage and comparison.

    Parameters
    ----------
    url : str
        The URL to hash

    Returns
    -------
    str
        SHA256 hash of the normalized URL (hex string)
    """
    normalized = normalize_url(url)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def extract_filename_base(filepath: str) -> str:
    """Extract the base filename without extension for comparison.

    This normalizes filenames by:
    - Removing file extension
    - Removing common suffixes (quality markers, etc.)
    - Lowercasing
    - Removing special characters

    Parameters
    ----------
    filepath : str
        The file path

    Returns
    -------
    str
        Normalized base filename
    """
    if not filepath:
        return ""

    # Get just the filename
    filename = os.path.basename(filepath)

    # Remove extension
    base, _ = os.path.splitext(filename)

    # Remove common quality markers
    base = re.sub(r'[-_\s]*(1080p|720p|480p|360p|4k|hd|sd|uhd)[-_\s]*', '', base, flags=re.IGNORECASE)

    # Remove resolution markers like "1920x1080"
    base = re.sub(r'[-_\s]*\d{3,4}x\d{3,4}[-_\s]*', '', base)

    # Normalize whitespace and special characters
    base = re.sub(r'[^a-z0-9]+', ' ', base.lower())

    # Remove extra whitespace
    base = ' '.join(base.split())

    return base.strip()


def compute_filename_hash(filepath: str) -> str:
    """Compute a hash of the normalized filename for duplicate detection.

    Parameters
    ----------
    filepath : str
        The file path

    Returns
    -------
    str
        SHA256 hash of the normalized filename
    """
    base = extract_filename_base(filepath)
    return hashlib.sha256(base.encode('utf-8')).hexdigest()


def are_urls_duplicate(url1: str, url2: str) -> Tuple[bool, str]:
    """Check if two URLs are duplicates using multiple strategies.

    Returns True if:
    1. URLs have the same normalized form
    2. URLs have the same video ID

    Parameters
    ----------
    url1 : str
        First URL
    url2 : str
        Second URL

    Returns
    -------
    Tuple[bool, str]
        (is_duplicate, reason)
    """
    # Strategy 1: Normalized URL comparison
    norm1 = normalize_url(url1)
    norm2 = normalize_url(url2)

    if norm1 == norm2:
        return True, "identical_normalized_url"

    # Strategy 2: Video ID comparison
    vid1 = extract_video_id(url1)
    vid2 = extract_video_id(url2)

    if vid1 and vid2 and vid1 == vid2:
        return True, f"same_video_id:{vid1}"

    # Strategy 3: URL hash comparison (should be same as strategy 1, but explicit)
    hash1 = compute_url_hash(url1)
    hash2 = compute_url_hash(url2)

    if hash1 == hash2:
        return True, "identical_url_hash"

    return False, "not_duplicate"


def are_filenames_similar(filepath1: str, filepath2: str, threshold: float = 0.9) -> bool:
    """Check if two filenames are similar enough to be considered duplicates.

    This uses a simple character-based similarity check after normalization.

    Parameters
    ----------
    filepath1 : str
        First file path
    filepath2 : str
        Second file path
    threshold : float
        Similarity threshold (0.0 to 1.0)

    Returns
    -------
    bool
        True if filenames are similar enough
    """
    base1 = extract_filename_base(filepath1)
    base2 = extract_filename_base(filepath2)

    if not base1 or not base2:
        return False

    # Simple character overlap similarity
    set1 = set(base1.split())
    set2 = set(base2.split())

    if not set1 or not set2:
        return False

    intersection = len(set1 & set2)
    union = len(set1 | set2)

    similarity = intersection / union if union > 0 else 0

    return similarity >= threshold
