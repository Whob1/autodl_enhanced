"""
Cookie management utilities for yt-dlp.
Handles reading, merging, and appending cookies in Netscape format.
"""

import os
from pathlib import Path
from typing import Optional, Set, Tuple
import logging

logger = logging.getLogger(__name__)


class CookieManager:
    """Manages Netscape format cookies for yt-dlp."""

    NETSCAPE_HEADER = "# Netscape HTTP Cookie File\n# https://curl.haxx.se/rfc/cookie_spec.html\n# This is a generated file! Do not edit.\n\n"

    @staticmethod
    def _parse_cookie_line(line: str) -> Optional[Tuple[str, str, str, str, str, str, str]]:
        """
        Parse a Netscape cookie line.
        Format: domain flag path secure expiration name value
        Returns tuple of (domain, flag, path, secure, expiration, name, value) or None if invalid.
        """
        line = line.strip()
        if not line or line.startswith("#"):
            return None

        parts = line.split("\t")
        if len(parts) != 7:
            logger.warning(f"Invalid cookie line format: expected 7 tab-separated fields, got {len(parts)}")
            return None

        domain, flag, path, secure, expiration, name, value = parts
        
        if not domain or domain.startswith(" "):
            logger.warning(f"Invalid domain in cookie: '{domain}'")
            return None
        
        if flag not in ("TRUE", "FALSE"):
            logger.warning(f"Invalid flag value in cookie: expected TRUE or FALSE, got '{flag}'")
            return None
        
        if secure not in ("TRUE", "FALSE"):
            logger.warning(f"Invalid secure value in cookie: expected TRUE or FALSE, got '{secure}'")
            return None
        
        if not expiration.isdigit():
            logger.warning(f"Invalid expiration in cookie: expected numeric timestamp, got '{expiration}'")
            return None
        
        if not name or not name.strip():
            logger.warning(f"Invalid cookie name: empty or whitespace")
            return None

        return tuple(parts)

    @staticmethod
    def _get_cookie_key(cookie: Tuple) -> str:
        """
        Generate a unique key for a cookie (domain + name).
        Used to detect duplicates/updates.
        """
        domain, _, _, _, _, name, _ = cookie
        return f"{domain}|{name}"

    @staticmethod
    def read_cookies(file_path: Path) -> dict:
        """
        Read cookies from a Netscape format file.
        Returns dict of {cookie_key: cookie_tuple}
        """
        cookies = {}
        if not file_path.exists():
            return cookies

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                line_num = 0
                for line in f:
                    line_num += 1
                    cookie = CookieManager._parse_cookie_line(line)
                    if cookie:
                        key = CookieManager._get_cookie_key(cookie)
                        cookies[key] = cookie
                logger.info(f"Successfully read {len(cookies)} valid cookies from {file_path} ({line_num} lines total)")
        except Exception as e:
            logger.error(f"Error reading cookies from {file_path}: {e}")
            raise

        return cookies

    @staticmethod
    def write_cookies(file_path: Path, cookies: dict) -> bool:
        """
        Write cookies to a Netscape format file.
        Ensures parent directory exists.
        Returns True on success, False on failure.
        """
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(CookieManager.NETSCAPE_HEADER)
                for cookie in sorted(cookies.values(), key=lambda c: c[0]):
                    line = "\t".join(cookie) + "\n"
                    f.write(line)

            os.chmod(file_path, 0o600)
            
            logger.info(f"Wrote {len(cookies)} cookies to {file_path} with secure permissions (0600)")
            return True
        except Exception as e:
            logger.error(f"Error writing cookies to {file_path}: {e}")
            return False

    @staticmethod
    def merge_cookies(existing_dict: dict, new_dict: dict) -> dict:
        """
        Merge two cookie dictionaries.
        Cookies with same key in new_dict override those in existing_dict.
        Returns merged dictionary.
        """
        merged = existing_dict.copy()
        merged.update(new_dict)
        return merged

    @staticmethod
    def append_cookies(main_file: Path, source_file: Path) -> Tuple[bool, str]:
        """
        Append cookies from source_file to main_file.
        Cookies with same domain+name in source will override existing ones.
        Returns (success: bool, message: str)
        """
        if not source_file.exists():
            msg = f"Source cookie file not found: {source_file}"
            logger.error(msg)
            return False, msg

        try:
            existing = CookieManager.read_cookies(main_file)
            new_cookies = CookieManager.read_cookies(source_file)

            if not new_cookies:
                msg = f"No valid cookies found in {source_file}"
                logger.warning(msg)
                return False, msg

            new_count = 0
            updated_count = 0
            for key, cookie in new_cookies.items():
                if key in existing:
                    updated_count += 1
                else:
                    new_count += 1

            merged = CookieManager.merge_cookies(existing, new_cookies)

            if not CookieManager.write_cookies(main_file, merged):
                return False, "Failed to write merged cookies"

            msg = f"✅ Appended {new_count} new cookies, updated {updated_count} existing cookies"
            logger.info(msg)
            return True, msg

        except Exception as e:
            msg = f"Error appending cookies: {e}"
            logger.error(msg)
            return False, msg

    @staticmethod
    def get_cookies_summary(file_path: Path) -> dict:
        """
        Get summary statistics about cookies in a file.
        Returns dict with counts and domains.
        """
        cookies = CookieManager.read_cookies(file_path)

        if not cookies:
            return {"total": 0, "domains": []}

        domains = {}
        for cookie in cookies.values():
            domain = cookie[0]
            domains[domain] = domains.get(domain, 0) + 1

        return {
            "total": len(cookies),
            "domains": sorted(domains.items(), key=lambda x: x[1], reverse=True),
        }
