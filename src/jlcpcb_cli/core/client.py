"""JLCPCB HTTP client with cookie-based authentication."""

import http.cookiejar
import json
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field

from jlcpcb_cli.core import auth

BASE_URL = "https://jlcpcb.com"


class JlcpcbAPIError(Exception):
    """Error from JLCPCB API."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _hex_encode_uuid(u: str) -> str:
    """Hex-encode a UUID string (each byte of the ASCII representation)."""
    return u.encode("ascii").hex()


@dataclass
class JlcpcbClient:
    cookie_jar: http.cookiejar.MozillaCookieJar = field(default_factory=auth.load_cookies)
    _opener: urllib.request.OpenerDirector | None = field(
        default=None, init=False, repr=False
    )
    _secret_key: str | None = field(default=None, init=False, repr=False)

    @property
    def opener(self) -> urllib.request.OpenerDirector:
        if self._opener is None:
            cookie_handler = urllib.request.HTTPCookieProcessor(self.cookie_jar)
            self._opener = urllib.request.build_opener(cookie_handler)
        return self._opener

    @property
    def xsrf_token(self) -> str | None:
        return auth.get_xsrf_token(self.cookie_jar)

    def _ensure_session(self) -> None:
        """Check session validity before making requests."""
        if not auth.has_valid_session(self.cookie_jar):
            self._session_expired()

    def _get_secret_key(self) -> str:
        """Obtain a secret key from the JLCPCB API.

        The protocol:
        1. Generate a random UUID, hex-encode it
        2. POST to /api/overseas-core-platform/secret/update with {"keyId": hex_uuid}
        3. Use the RESPONSE keyId (different from what we sent) as the secretkey header
        """
        if self._secret_key is not None:
            return self._secret_key

        key_id = _hex_encode_uuid(str(uuid.uuid4()))

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "jlcpcb-cli/0.1.0",
            "Referer": "https://jlcpcb.com/user-center/orders/",
        }

        xsrf = self.xsrf_token
        if xsrf:
            headers["x-xsrf-token"] = xsrf

        body = json.dumps({"keyId": key_id}).encode()
        req = urllib.request.Request(
            f"{BASE_URL}/api/overseas-core-platform/secret/update",
            data=body,
            headers=headers,
            method="POST",
        )

        try:
            with self.opener.open(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (302, 401, 403):
                self._session_expired()
            raise JlcpcbAPIError(
                f"secret/update failed: HTTP {e.code}", status_code=e.code
            ) from e
        except urllib.error.URLError as e:
            raise JlcpcbAPIError(f"Connection error: {e.reason}") from e

        if not result.get("success"):
            code = result.get("code")
            msg = result.get("message", "unknown error")
            raise JlcpcbAPIError(f"secret/update failed: {msg} (code={code})")

        self._secret_key = result["data"]["keyId"]
        return self._secret_key

    def _invalidate_secret_key(self) -> None:
        """Invalidate the cached secret key, forcing re-acquisition."""
        self._secret_key = None

    def api_post(self, path: str, data: dict) -> dict:
        """Make an authenticated POST request to a JLCPCB API endpoint.

        Handles the secret key protocol and XSRF token automatically.
        """
        self._ensure_session()
        try:
            return self._do_api_post(path, data)
        except JlcpcbAPIError as e:
            if e.status_code in (302, 401, 403):
                self._session_expired()
            # Retry once on secret key expiry (code 29003)
            if "29003" in str(e):
                self._invalidate_secret_key()
                return self._do_api_post(path, data)
            raise

    def api_get(self, path: str, params: dict | None = None) -> dict:
        """Make an authenticated GET request to a JLCPCB API endpoint."""
        self._ensure_session()

        url = f"{BASE_URL}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        headers = {
            "Accept": "application/json",
            "User-Agent": "jlcpcb-cli/0.1.0",
            "Referer": "https://jlcpcb.com/user-center/orders/",
        }

        xsrf = self.xsrf_token
        if xsrf:
            headers["x-xsrf-token"] = xsrf

        secret_key = self._get_secret_key()
        headers["secretkey"] = secret_key

        req = urllib.request.Request(url, headers=headers)

        try:
            with self.opener.open(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (302, 401, 403):
                self._session_expired()
            raise JlcpcbAPIError(
                f"HTTP {e.code}", status_code=e.code
            ) from e
        except urllib.error.URLError as e:
            raise JlcpcbAPIError(f"Connection error: {e.reason}") from e

        if not result.get("success"):
            code = result.get("code")
            msg = result.get("message", "unknown error")
            raise JlcpcbAPIError(f"API error: {msg} (code={code})")

        return result

    def _do_api_post(self, path: str, data: dict) -> dict:
        """Execute an authenticated POST request."""
        url = f"{BASE_URL}{path}"

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "jlcpcb-cli/0.1.0",
            "Referer": "https://jlcpcb.com/user-center/orders/",
        }

        xsrf = self.xsrf_token
        if xsrf:
            headers["x-xsrf-token"] = xsrf

        secret_key = self._get_secret_key()
        headers["secretkey"] = secret_key

        body = json.dumps(data).encode()
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")

        try:
            with self.opener.open(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (302, 401, 403):
                self._session_expired()
            raise JlcpcbAPIError(
                f"HTTP {e.code}", status_code=e.code
            ) from e
        except urllib.error.URLError as e:
            raise JlcpcbAPIError(f"Connection error: {e.reason}") from e

        if not result.get("success"):
            code = result.get("code")
            msg = result.get("message", "unknown error")
            raise JlcpcbAPIError(f"API error: {msg} (code={code})")

        return result

    def _session_expired(self) -> None:
        """Raise an error indicating session expiry."""
        raise JlcpcbAPIError(
            "Session expired. Run 'jlcpcb-cli login' to re-authenticate."
        )
