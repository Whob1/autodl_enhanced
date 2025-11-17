"""Simple aria2 JSON-RPC wrapper for submitting magnet downloads."""

from __future__ import annotations

import uuid
from typing import Optional

import requests

from .utils.logger import get_logger


class Aria2Manager:
    """Minimal aria2c JSON-RPC client for magnet submissions."""

    def __init__(
        self,
        rpc_url: str,
        secret: Optional[str] = None,
        timeout: float = 30.0,
        download_dir: Optional[str] = None,
    ):
        self.rpc_url = rpc_url
        self.secret = secret.strip() if secret else ""
        self.timeout = timeout
        self.download_dir = download_dir
        self.logger = get_logger(self.__class__.__name__)

    def add_magnet(self, magnet_link: str) -> str:
        """Send a magnet link to aria2 via JSON-RPC."""
        if not self.rpc_url:
            raise RuntimeError("aria2 RPC URL is not configured.")
        payload: dict = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "aria2.addUri",
            "params": [],
        }

        if self.secret:
            payload["params"].append(f"token:{self.secret}")
        payload["params"].append([magnet_link])
        options = {}
        if self.download_dir:
            options["dir"] = self.download_dir
        if options:
            payload["params"].append(options)

        try:
            response = requests.post(self.rpc_url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                error = data["error"].get("message", str(data["error"]))
                self.logger.error("aria2 returned error: %s", error)
                raise RuntimeError(f"aria2 RPC error: {error}")
            gid = data.get("result")
            self.logger.info("Submitted magnet to aria2: gid=%s", gid)
            return gid or ""
        except requests.RequestException as exc:
            self.logger.error("Failed to submit magnet to aria2: %s", exc)
            raise RuntimeError(f"aria2 RPC request failed: {exc}") from exc
