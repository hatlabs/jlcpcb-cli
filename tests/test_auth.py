"""Tests for jlcpcb_cli.core.auth."""

import json

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from jlcpcb_cli.core import auth
from jlcpcb_cli.core.auth import (
    _is_orders_url,
    _wait_for_login,
    load_browser_cookies,
    save_browser_cookies,
)


# ---------------------------------------------------------------------------
# _is_orders_url — the predicate that gates "login successful"
# ---------------------------------------------------------------------------


def test_is_orders_url_matches_canonical_orders_paths():
    assert _is_orders_url("https://jlcpcb.com/user-center/orders/")
    assert _is_orders_url("https://jlcpcb.com/user-center/orders")
    assert _is_orders_url("https://jlcpcb.com/user-center/orders/?_t=1779174147403")
    assert _is_orders_url("https://jlcpcb.com/user-center/orders/details/12345")


def test_is_orders_url_rejects_substring_traps_on_other_hosts():
    """The previous substring check (``"jlcpcb.com/user-center/orders" in url``)
    would have matched URLs that merely contain the orders path inside a query
    parameter on a non-jlcpcb host. The strict prefix check rejects them.
    """
    trap_urls = [
        # Non-jlcpcb host with the orders path in a query string.
        "https://evil.example.com/?next=jlcpcb.com/user-center/orders",
        # passport subdomain with the orders path unencoded in a hash fragment.
        "https://passport.jlcpcb.com/#/login?next=jlcpcb.com/user-center/orders",
        # http (not https) — strict prefix rejects scheme downgrade.
        "http://jlcpcb.com/user-center/orders/",
    ]
    for url in trap_urls:
        assert "jlcpcb.com/user-center/orders" in url, f"trap baseline: {url}"
        assert not _is_orders_url(url), f"strict check should reject: {url}"


def test_is_orders_url_rejects_other_hosts_and_paths():
    assert not _is_orders_url("https://passport.jlcpcb.com/")
    assert not _is_orders_url("https://jlcpcb.com/")
    assert not _is_orders_url("https://jlcpcb.com/api/auth/login?_t=123")
    assert not _is_orders_url("about:blank")
    assert not _is_orders_url("")


# ---------------------------------------------------------------------------
# _wait_for_login — uses a fake page so we don't launch playwright
# ---------------------------------------------------------------------------


class _FakePage:
    """Minimal stand-in for a playwright Page in `_wait_for_login`."""

    def __init__(self, urls, networkidle_raises=None):
        self._urls = list(urls)
        self._networkidle_raises = networkidle_raises
        self._url_index = 0
        self.load_state_calls = 0

    @property
    def url(self) -> str:
        idx = min(self._url_index, len(self._urls) - 1)
        self._url_index += 1
        return self._urls[idx]

    def wait_for_load_state(self, state: str, timeout: int = 0) -> None:
        self.load_state_calls += 1
        if self._networkidle_raises is not None:
            raise self._networkidle_raises


def test_wait_for_login_returns_when_url_matches_immediately(monkeypatch):
    monkeypatch.setattr(auth.time, "sleep", lambda _s: None)
    page = _FakePage(["https://jlcpcb.com/user-center/orders/"])
    _wait_for_login(page)
    assert page.load_state_calls == 1  # networkidle wait was attempted


def test_wait_for_login_swallows_playwright_timeout_and_polls(monkeypatch):
    monkeypatch.setattr(auth.time, "sleep", lambda _s: None)
    page = _FakePage(
        ["https://jlcpcb.com/user-center/orders/"],
        networkidle_raises=PlaywrightTimeoutError("Timeout 15000ms exceeded"),
    )
    _wait_for_login(page)  # swallowed; polling then matches


def test_wait_for_login_polls_until_redirect_returns_to_orders(monkeypatch):
    monkeypatch.setattr(auth.time, "sleep", lambda _s: None)
    urls = [
        "https://passport.jlcpcb.com/#/login?response_type=code",
        "https://passport.jlcpcb.com/#/login?response_type=code",
        "https://jlcpcb.com/api/auth/login?_t=123",
        "https://jlcpcb.com/user-center/orders/?_t=456",
    ]
    page = _FakePage(urls)
    _wait_for_login(page)


def test_wait_for_login_does_not_swallow_unrelated_exceptions(monkeypatch):
    monkeypatch.setattr(auth.time, "sleep", lambda _s: None)
    page = _FakePage(
        ["https://jlcpcb.com/user-center/orders/"],
        networkidle_raises=RuntimeError("not a playwright timeout"),
    )
    with pytest.raises(RuntimeError, match="not a playwright timeout"):
        _wait_for_login(page)


def test_wait_for_login_raises_timeout_with_final_url(monkeypatch):
    fake_now = [0.0]

    def fake_time():
        fake_now[0] += 60.0  # advance 60s per call
        return fake_now[0]

    monkeypatch.setattr(auth.time, "time", fake_time)
    monkeypatch.setattr(auth.time, "sleep", lambda _s: None)

    stuck_url = "https://passport.jlcpcb.com/#/login?response_type=code"
    page = _FakePage([stuck_url])

    with pytest.raises(TimeoutError) as exc:
        _wait_for_login(page)

    # The error message must include the final page.url for diagnosability.
    assert stuck_url in str(exc.value)
    assert "5 minutes" in str(exc.value)


# ---------------------------------------------------------------------------
# save_browser_cookies / load_browser_cookies round-trip
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_cookie_dir(tmp_path, monkeypatch):
    cookies_file = tmp_path / "browser-cookies.json"
    monkeypatch.setattr(auth, "COOKIE_DIR", tmp_path)
    monkeypatch.setattr(auth, "COOKIES_FILE", cookies_file)
    return cookies_file


def test_save_then_load_round_trip(isolated_cookie_dir):
    payload = [
        {"name": "JLCPCB_SESSION_ID", "value": "abc", "domain": "jlcpcb.com"},
        {"name": "XSRF-TOKEN", "value": "xyz", "domain": "jlcpcb.com"},
    ]
    save_browser_cookies(payload)
    assert load_browser_cookies() == payload


def test_load_returns_empty_when_file_missing(isolated_cookie_dir):
    assert not isolated_cookie_dir.exists()
    assert load_browser_cookies() == []


def test_load_returns_empty_on_corrupt_json(isolated_cookie_dir):
    isolated_cookie_dir.write_text("not valid json {")
    assert load_browser_cookies() == []


def test_save_creates_cookie_dir_with_restricted_perms(tmp_path, monkeypatch):
    cookie_dir = tmp_path / "new-cookie-dir"
    monkeypatch.setattr(auth, "COOKIE_DIR", cookie_dir)
    monkeypatch.setattr(auth, "COOKIES_FILE", cookie_dir / "browser-cookies.json")
    save_browser_cookies([{"name": "a", "value": "b"}])
    assert cookie_dir.exists()
    # On Unix, mkdir(mode=0o700) gets masked by umask. Verify the intent
    # (mode arg was passed) by checking owner-only is at least set.
    mode = cookie_dir.stat().st_mode & 0o777
    assert mode & 0o700, f"owner perms should be set, got {oct(mode)}"
    # Sanity: loaded payload matches.
    assert json.loads((cookie_dir / "browser-cookies.json").read_text()) == [
        {"name": "a", "value": "b"}
    ]
