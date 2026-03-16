"""HTTP client for JLCPCB web API endpoints.

Replaces the headless browser client. Uses cookies saved during login
to authenticate direct HTTP requests.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
import uuid

from jlcpcb_cli.core.client import JlcpcbAPIError


class _StaleSecretKeyError(JlcpcbAPIError):
    """Raised when the secret key appears stale and should be refreshed."""

BASE_URL = "https://jlcpcb.com"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

_web_client_instance = None


class WebClient:
    """Makes authenticated API calls to jlcpcb.com via direct HTTP."""

    def __init__(self, cookies: list[dict]):
        self._cookies = {c["name"]: c["value"] for c in cookies}
        self._secret_key: str | None = None

    def _cookie_header(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self._cookies.items())

    def _xsrf_token(self) -> str:
        token = self._cookies.get("XSRF-TOKEN")
        if not token:
            raise JlcpcbAPIError(
                "No XSRF-TOKEN cookie. Run 'jlcpcb-cli login' to re-authenticate."
            )
        return urllib.parse.unquote(token)

    def _refresh_secret_key(self) -> str:
        key_id = uuid.uuid4().hex
        body = self._http_post(
            f"{BASE_URL}/api/overseas-core-platform/secret/update",
            {"keyId": key_id},
            headers={"x-xsrf-token": self._xsrf_token()},
        )
        secret = (body.get("data") or {}).get("keyId")
        if not secret:
            raise JlcpcbAPIError(
                f"Failed to obtain secret key: {json.dumps(body)[:200]}"
            )
        self._secret_key = secret
        return secret

    def _http_post(
        self,
        url: str,
        data: dict,
        *,
        headers: dict[str, str] | None = None,
    ) -> dict:
        hdrs = {
            "Cookie": self._cookie_header(),
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        }
        if headers:
            hdrs.update(headers)

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode(),
            headers=hdrs,
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 460:
                raise JlcpcbAPIError(
                    "Session expired (HTTP 460). "
                    "Run 'jlcpcb-cli login' to re-authenticate."
                ) from e
            raise JlcpcbAPIError(
                f"HTTP {e.code}: {e.read().decode()[:200]}"
            ) from e
        except urllib.error.URLError as e:
            raise JlcpcbAPIError(f"Connection error: {e.reason}") from e

    def api_post(self, path: str, data: dict) -> dict:
        """Make an authenticated POST to a JLCPCB web API endpoint.

        Handles XSRF token and secret key automatically.
        On auth failure, retries once with a fresh secret key.
        """
        if self._secret_key is None:
            self._refresh_secret_key()

        try:
            return self._do_api_post(path, data)
        except _StaleSecretKeyError:
            self._refresh_secret_key()
            return self._do_api_post(path, data)

    def _do_api_post(self, path: str, data: dict) -> dict:
        result = self._http_post(
            f"{BASE_URL}/api{path}",
            data,
            headers={
                "x-xsrf-token": self._xsrf_token(),
                "secretkey": self._secret_key,
            },
        )
        # JLCPCB returns success=false with code 401/403 when the secret
        # key has expired (30-minute TTL).
        if not result.get("success") and result.get("code") in (401, 403):
            raise _StaleSecretKeyError(
                f"Secret key rejected (code={result.get('code')})"
            )
        return result


def get_web_client() -> WebClient:
    """Get or create the singleton web client."""
    global _web_client_instance
    if _web_client_instance is None:
        from jlcpcb_cli.core.auth import load_browser_cookies

        cookies = load_browser_cookies()
        if not cookies:
            raise JlcpcbAPIError(
                "No saved cookies. Run 'jlcpcb-cli login' first."
            )
        _web_client_instance = WebClient(cookies)
    return _web_client_instance
