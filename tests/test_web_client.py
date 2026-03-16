"""Tests for WebClient auth error handling."""

from unittest.mock import patch

import pytest

from jlcpcb_cli.core.web_client import JlcpcbAPIError, WebClient


def _make_client() -> WebClient:
    """Create a WebClient with fake cookies."""
    cookies = [
        {"name": "XSRF-TOKEN", "value": "fake-xsrf"},
        {"name": "JLCPCB_SESSION_ID", "value": "fake-session"},
    ]
    return WebClient(cookies)


def _mock_http(responses: list[dict]):
    """Patch _http_request to return responses in order."""
    it = iter(responses)
    return patch.object(
        WebClient,
        "_http_request",
        side_effect=lambda *a, **kw: next(it),
    )


class TestCheckSuccess:
    def test_success_true_passes(self):
        WebClient._check_success({"success": True, "data": {}})

    def test_no_success_field_passes(self):
        # Some endpoints may not include "success" at all
        WebClient._check_success({"data": {}})

    def test_success_false_raises(self):
        with pytest.raises(JlcpcbAPIError, match="API error.*code=500"):
            WebClient._check_success(
                {"success": False, "code": 500, "message": "Internal error"}
            )

    def test_success_false_uses_msg_field(self):
        with pytest.raises(JlcpcbAPIError, match="something broke"):
            WebClient._check_success(
                {"success": False, "code": 999, "msg": "something broke"}
            )

    def test_success_false_unknown_error(self):
        with pytest.raises(JlcpcbAPIError, match="unknown error"):
            WebClient._check_success({"success": False})


class TestApiPostErrorHandling:
    def test_success_false_raises_after_fresh_key(self):
        """API returns success:false with non-auth code — should raise."""
        client = _make_client()
        secret_resp = {"data": {"keyId": "secret123"}}
        fail_resp = {"success": False, "code": 500, "message": "Server error"}

        with _mock_http([secret_resp, fail_resp]):
            with pytest.raises(JlcpcbAPIError, match="API error.*code=500"):
                client.api_post("/test", {})

    def test_stale_key_then_success_false_raises(self):
        """Stale key retry succeeds, but new response is still a failure."""
        client = _make_client()
        secret_resp = {"data": {"keyId": "secret123"}}
        stale_resp = {"success": False, "code": 401}
        new_secret_resp = {"data": {"keyId": "secret456"}}
        fail_resp = {"success": False, "code": 500, "message": "Server error"}

        with _mock_http([secret_resp, stale_resp, new_secret_resp, fail_resp]):
            with pytest.raises(JlcpcbAPIError, match="API error.*code=500"):
                client.api_post("/test", {})

    def test_stale_key_then_success_passes(self):
        """Stale key retry succeeds with valid data."""
        client = _make_client()
        secret_resp = {"data": {"keyId": "secret123"}}
        stale_resp = {"success": False, "code": 403}
        new_secret_resp = {"data": {"keyId": "secret456"}}
        ok_resp = {"success": True, "data": {"list": [{"id": 1}]}}

        with _mock_http([secret_resp, stale_resp, new_secret_resp, ok_resp]):
            result = client.api_post("/test", {})
            assert result["data"]["list"][0]["id"] == 1


class TestApiGetErrorHandling:
    def test_success_false_raises(self):
        client = _make_client()
        secret_resp = {"data": {"keyId": "secret123"}}
        fail_resp = {"success": False, "code": 403, "message": "Forbidden"}

        # code 403 on first call triggers stale key retry;
        # if retry also returns non-auth failure, it should raise
        new_secret_resp = {"data": {"keyId": "secret456"}}
        fail_resp2 = {"success": False, "code": 500, "message": "Server error"}

        with _mock_http([secret_resp, fail_resp, new_secret_resp, fail_resp2]):
            with pytest.raises(JlcpcbAPIError, match="API error.*code=500"):
                client.api_get("/test")
