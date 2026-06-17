"""Tests for jlcpcb_cli.core.auth."""

import json

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from jlcpcb_cli.core import auth
from jlcpcb_cli.core.auth import (
    _has_auth_cookie,
    _wait_for_login,
    load_browser_cookies,
    save_browser_cookies,
)


def _cookie(name, value="x"):
    return {"name": name, "value": value, "domain": "jlcpcb.com"}


# ---------------------------------------------------------------------------
# _has_auth_cookie — the predicate that gates "login successful"
# ---------------------------------------------------------------------------


def test_has_auth_cookie_true_when_session_cookie_present():
    cookies = [_cookie("XSRF-TOKEN"), _cookie("jlc_session_customer_code", "tok")]
    assert _has_auth_cookie(cookies)


def test_has_auth_cookie_false_when_absent():
    # XSRF-TOKEN is set for anonymous visitors too, so it must not count.
    assert not _has_auth_cookie([_cookie("XSRF-TOKEN"), _cookie("_ga")])
    assert not _has_auth_cookie([])


def test_has_auth_cookie_false_when_value_empty():
    assert not _has_auth_cookie([_cookie("jlc_session_customer_code", "")])


# ---------------------------------------------------------------------------
# _wait_for_login — fakes context+page so we don't launch playwright
# ---------------------------------------------------------------------------


class _FakePage:
    """Minimal stand-in for a playwright Page in `_wait_for_login`."""

    def __init__(self, url="https://passport.jlcpcb.com/#/login", networkidle_raises=None):
        self._url = url
        self._networkidle_raises = networkidle_raises
        self.load_state_calls = 0

    @property
    def url(self) -> str:
        return self._url

    def wait_for_load_state(self, state: str, timeout: int = 0) -> None:
        self.load_state_calls += 1
        if self._networkidle_raises is not None:
            raise self._networkidle_raises


class _FakeContext:
    """Returns a successive cookie list on each `cookies()` call."""

    def __init__(self, cookie_snapshots):
        self._snapshots = list(cookie_snapshots)
        self._index = 0

    def cookies(self):
        snap = self._snapshots[min(self._index, len(self._snapshots) - 1)]
        self._index += 1
        return snap


_AUTH = [_cookie("jlc_session_customer_code", "tok")]


def test_wait_for_login_returns_when_cookie_present_immediately(monkeypatch):
    monkeypatch.setattr(auth.time, "sleep", lambda _s: None)
    page = _FakePage()
    _wait_for_login(_FakeContext([_AUTH]), page)
    assert page.load_state_calls == 1  # networkidle wait was attempted


def test_wait_for_login_swallows_playwright_timeout_and_polls(monkeypatch):
    monkeypatch.setattr(auth.time, "sleep", lambda _s: None)
    page = _FakePage(
        networkidle_raises=PlaywrightTimeoutError("Timeout 15000ms exceeded"),
    )
    _wait_for_login(_FakeContext([_AUTH]), page)  # swallowed; cookie then matches


def test_wait_for_login_polls_until_cookie_appears(monkeypatch):
    monkeypatch.setattr(auth.time, "sleep", lambda _s: None)
    ctx = _FakeContext([[], [_cookie("XSRF-TOKEN")], _AUTH])
    _wait_for_login(ctx, _FakePage())


def test_wait_for_login_does_not_swallow_unrelated_exceptions(monkeypatch):
    monkeypatch.setattr(auth.time, "sleep", lambda _s: None)
    page = _FakePage(networkidle_raises=RuntimeError("not a playwright timeout"))
    with pytest.raises(RuntimeError, match="not a playwright timeout"):
        _wait_for_login(_FakeContext([_AUTH]), page)


def test_wait_for_login_raises_timeout_with_final_url(monkeypatch):
    fake_now = [0.0]

    def fake_time():
        fake_now[0] += 60.0  # advance 60s per call
        return fake_now[0]

    monkeypatch.setattr(auth.time, "time", fake_time)
    monkeypatch.setattr(auth.time, "sleep", lambda _s: None)

    stuck_url = "https://passport.jlcpcb.com/#/login?response_type=code"
    page = _FakePage(url=stuck_url)

    with pytest.raises(TimeoutError) as exc:
        _wait_for_login(_FakeContext([[]]), page)

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
