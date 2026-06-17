"""Shared HTTP helpers for API queries and downloads."""

from __future__ import annotations

import json
import logging
import ssl
import time
import urllib.error
import urllib.request
from typing import Optional


def create_ssl_context() -> ssl.SSLContext:
    """Create SSL context with certifi when available."""
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


class HttpClient:
    """Small urllib-based client with retry support."""

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        user_agent: str = "affective-playlists/1.0",
        retries: int = 2,
        retry_delay: float = 0.25,
    ):
        self.logger = logger or logging.getLogger(__name__)
        self.user_agent = user_agent
        self.retries = retries
        self.retry_delay = retry_delay
        self.ssl_context = create_ssl_context()

    def _request(
        self,
        url: str,
        timeout: int,
        headers: Optional[dict] = None,
        data: Optional[bytes] = None,
    ) -> Optional[bytes]:
        req_headers = {"User-Agent": self.user_agent}
        if headers:
            req_headers.update(headers)

        last_error: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            try:
                req = urllib.request.Request(url, headers=req_headers, data=data)
                with urllib.request.urlopen(
                    req, timeout=timeout, context=self.ssl_context
                ) as response:
                    return response.read()
            except urllib.error.HTTPError as e:
                last_error = e
                # Retry transient service failures.
                if e.code in {429, 500, 502, 503, 504} and attempt < self.retries:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                break
            except (urllib.error.URLError, TimeoutError) as e:
                last_error = e
                if attempt < self.retries:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                break
            except Exception as e:
                last_error = e
                break

        self.logger.debug("event=http_request_failed url=%s error=%s", url, last_error)
        return None

    def fetch_text(
        self,
        url: str,
        timeout: int = 10,
        headers: Optional[dict] = None,
        data: Optional[bytes] = None,
        encoding: str = "utf-8",
    ) -> Optional[str]:
        payload = self._request(url, timeout=timeout, headers=headers, data=data)
        if payload is None:
            return None
        try:
            return payload.decode(encoding)
        except Exception as e:
            self.logger.debug("event=http_decode_failed url=%s error=%s", url, e)
            return None

    def fetch_json(
        self,
        url: str,
        timeout: int = 10,
        headers: Optional[dict] = None,
        data: Optional[bytes] = None,
    ) -> Optional[dict]:
        text = self.fetch_text(url, timeout=timeout, headers=headers, data=data)
        if text is None:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            self.logger.debug("event=http_json_decode_failed url=%s error=%s", url, e)
            return None

    def fetch_bytes(
        self,
        url: str,
        timeout: int = 10,
        headers: Optional[dict] = None,
        data: Optional[bytes] = None,
    ) -> Optional[bytes]:
        return self._request(url, timeout=timeout, headers=headers, data=data)
