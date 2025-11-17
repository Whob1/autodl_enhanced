"""Validation utilities for the Enhanced AutoDL Telegram Bot.

This module contains helper functions used to validate user input,
specifically URLs provided via Telegram messages or files.
"""

from __future__ import annotations

import re
import html
from urllib.parse import urlparse, quote, unquote
from typing import List


_URL_REGEX = re.compile(
    r"https?://"
    r"(?:[a-zA-Z0-9\u00a1-\uffff](?:[a-zA-Z0-9\u00a1-\uffff-]{0,61}[a-zA-Z0-9\u00a1-\uffff])?\.)*"
    r"[a-zA-Z0-9\u00a1-\uffff](?:[a-zA-Z0-9\u00a1-\uffff-]{0,61}[a-zA-Z0-9\u00a1-\uffff])?"
    r"(?::\d{1,5})?"
    r"(?:[/?#][^\s\r\n]*)?",
    re.IGNORECASE | re.UNICODE
)
_MAGNET_REGEX = re.compile(r"magnet:\?[^\s\r\n]+", re.IGNORECASE)


def sanitize_url(url: str) -> str:
    """Sanitize a URL to prevent injection attacks.

    Parameters
    ----------
    url: str
        The URL to sanitize.

    Returns
    -------
    str
        The sanitized URL with dangerous characters removed or encoded.
    """
    if not url:
        return ""
    
    url = url.strip()
    url = html.unescape(url)
    url = url.replace('\r', '').replace('\n', '').replace('\t', '')
    url = ''.join(char for char in url if ord(char) >= 32 and ord(char) != 127)
    
    try:
        parsed = urlparse(url)
        if parsed.scheme == 'magnet':
            return url
        if parsed.scheme not in {'http', 'https'}:
            return ""
        if not parsed.netloc:
            return ""
        return url
    except Exception:
        return ""


def is_valid_url(url: str) -> bool:
    """Return True if the input string appears to be a valid URL.

    A URL is considered valid if it has a proper scheme (http or https)
    and a network location. This is a basic validation and does not
    guarantee that the URL is reachable.

    Parameters
    ----------
    url: str
        The URL to validate.

    Returns
    -------
    bool
        True if the URL appears to be valid, otherwise False.
    """
    if not url:
        return False
    url = url.strip()
    if len(url) > 2048:
        return False
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https", "magnet"}:
        return False
    if parsed.scheme in {"http", "https"}:
        if not parsed.netloc or len(parsed.netloc) > 253:
            return False
    else:
        if not parsed.query:
            return False
    return True


def extract_urls(text: str) -> List[str]:
    """Extract all HTTP/HTTPS URLs from a block of text.

    Parameters
    ----------
    text: str
        The text from which to extract URLs.

    Returns
    -------
    List[str]
        A list of all URLs found in the text.
    """
    if not text:
        return []
    urls = _URL_REGEX.findall(text)
    magnets = _MAGNET_REGEX.findall(text)
    return list(dict.fromkeys(urls + magnets))
