"""JLCPCB official API client with HMAC-SHA256 request signing."""

import base64
import hashlib
import hmac
import json
import os
import random
import string
import time
import urllib.error
import urllib.request

BASE_URL = "https://open.jlcpcb.com"


class JlcpcbAPIError(Exception):
    """Error from JLCPCB API."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _nonce(length: int = 32) -> str:
    """Generate a random nonce string."""
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def _sign(secret_key: str, method: str, path: str, timestamp: str, nonce: str, body: str) -> str:
    """Generate HMAC-SHA256 signature for the request."""
    string_to_sign = f"{method}\n{path}\n{timestamp}\n{nonce}\n{body}\n"
    sig = hmac.new(
        secret_key.encode(), string_to_sign.encode(), hashlib.sha256
    ).digest()
    return base64.b64encode(sig).decode()


class JlcpcbClient:
    """JLCPCB API client using the official open API."""

    def __init__(
        self,
        app_id: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
    ):
        self.app_id = app_id or os.environ.get("JLCPCB_APP_ID", "")
        self.access_key = access_key or os.environ.get("JLCPCB_ACCESS_KEY", "")
        self.secret_key = secret_key or os.environ.get("JLCPCB_SECRET_KEY", "")

        if not all([self.app_id, self.access_key, self.secret_key]):
            raise JlcpcbAPIError(
                "Missing API credentials. Set JLCPCB_APP_ID, JLCPCB_ACCESS_KEY, "
                "and JLCPCB_SECRET_KEY environment variables."
            )

    def api_post(self, path: str, data: dict) -> dict:
        """Make a signed POST request to the JLCPCB API."""
        timestamp = str(int(time.time()))
        nonce = _nonce()
        body = json.dumps(data)

        signature = _sign(self.secret_key, "POST", path, timestamp, nonce, body)

        auth = (
            f'JOP appid="{self.app_id}",'
            f'accesskey="{self.access_key}",'
            f'nonce="{nonce}",'
            f'timestamp="{timestamp}",'
            f'signature="{signature}"'
        )

        req = urllib.request.Request(
            BASE_URL + path,
            data=body.encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": auth,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            try:
                err = json.loads(e.read().decode())
                msg = err.get("message", f"HTTP {e.code}")
                code = err.get("code", e.code)
            except Exception:
                msg = f"HTTP {e.code}"
                code = e.code
            raise JlcpcbAPIError(
                f"API error: {msg} (code={code})", status_code=e.code
            ) from e
        except urllib.error.URLError as e:
            raise JlcpcbAPIError(f"Connection error: {e.reason}") from e

        if not result.get("success"):
            code = result.get("code")
            msg = result.get("message", "unknown error")
            raise JlcpcbAPIError(f"API error: {msg} (code={code})")

        return result

    def download_file(self, path: str, output_path: "Path") -> None:
        """Download a file from JLCPCB."""
        from pathlib import Path
        output_path = Path(output_path)

        url = path if path.startswith("http") else f"https://jlcpcb.com{path}"

        req = urllib.request.Request(url, headers={
            "User-Agent": "jlcpcb-cli/0.1.0",
        })

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                output_path.write_bytes(resp.read())
        except urllib.error.HTTPError as e:
            raise JlcpcbAPIError(
                f"Download failed: HTTP {e.code}", status_code=e.code
            ) from e
        except urllib.error.URLError as e:
            raise JlcpcbAPIError(f"Download failed: {e.reason}") from e

    def close(self) -> None:
        """No-op — kept for interface compatibility."""
        pass
