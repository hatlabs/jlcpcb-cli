"""HTTP client for JLCPCB web API endpoints.

Uses cookies saved during interactive browser login to authenticate
direct HTTP requests to jlcpcb.com.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
import uuid


class JlcpcbAPIError(Exception):
    """Error from JLCPCB API."""


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
        body = self._http_request(
            f"{BASE_URL}/api/overseas-core-platform/secret/update",
            data=json.dumps({"keyId": key_id}).encode(),
            headers={"x-xsrf-token": self._xsrf_token()},
        )
        secret = (body.get("data") or {}).get("keyId")
        if not secret:
            raise JlcpcbAPIError(
                f"Failed to obtain secret key: {json.dumps(body)[:200]}"
            )
        self._secret_key = secret
        return secret

    def _http_request(
        self,
        url: str,
        *,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict:
        hdrs = {
            "Cookie": self._cookie_header(),
            "User-Agent": _USER_AGENT,
        }
        if data is not None:
            hdrs["Content-Type"] = "application/json"
        if headers:
            hdrs.update(headers)

        req = urllib.request.Request(url, data=data, headers=hdrs)

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

    def _auth_headers(self) -> dict[str, str]:
        return {
            "x-xsrf-token": self._xsrf_token(),
            "secretkey": self._secret_key,
        }

    def _ensure_secret_key(self) -> None:
        if self._secret_key is None:
            self._refresh_secret_key()

    def _check_stale_key(self, result: dict) -> None:
        # JLCPCB returns success=false with code 401/403 when the secret
        # key has expired (30-minute TTL).
        if not result.get("success") and result.get("code") in (401, 403):
            raise _StaleSecretKeyError(
                f"Secret key rejected (code={result.get('code')})"
            )

    def api_post(self, path: str, data: dict) -> dict:
        """Make an authenticated POST to a JLCPCB web API endpoint."""
        self._ensure_secret_key()
        try:
            return self._do_api_post(path, data)
        except _StaleSecretKeyError:
            self._refresh_secret_key()
            return self._do_api_post(path, data)

    def _do_api_post(self, path: str, data: dict) -> dict:
        result = self._http_request(
            f"{BASE_URL}/api{path}",
            data=json.dumps(data).encode(),
            headers=self._auth_headers(),
        )
        self._check_stale_key(result)
        return result

    def api_get(self, path: str, params: dict[str, str] | None = None) -> dict:
        """Make an authenticated GET to a JLCPCB web API endpoint."""
        self._ensure_secret_key()
        try:
            return self._do_api_get(path, params)
        except _StaleSecretKeyError:
            self._refresh_secret_key()
            return self._do_api_get(path, params)

    def _do_api_get(self, path: str, params: dict[str, str] | None = None) -> dict:
        url = f"{BASE_URL}/api{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        result = self._http_request(url, headers=self._auth_headers())
        self._check_stale_key(result)
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
