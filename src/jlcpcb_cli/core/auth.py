"""Authentication — browser login for web API endpoints.

Playwright is imported lazily inside ``login`` and ``_wait_for_login`` so
non-login CLI subcommands (e.g. ``--help``, ``orders list``) don't pay the
import cost.
"""

import json
import time
from pathlib import Path

COOKIE_DIR = Path.home() / ".jlcpcb-cli"
CHROME_PROFILE_DIR = COOKIE_DIR / "chrome-profile"
COOKIES_FILE = COOKIE_DIR / "browser-cookies.json"
STORAGE_STATE_FILE = COOKIE_DIR / "storage-state.json"

ORDERS_URL = "https://jlcpcb.com/user-center/orders"

# JLCPCB sets this cookie only after a successful login; it is absent for
# anonymous visitors. It is the authoritative "logged in" signal — far more
# robust than the post-login URL, which does not reliably land on the orders
# page (the redirect target varies, so a URL check times out while the user
# is in fact authenticated).
AUTH_COOKIE = "jlc_session_customer_code"


def _ensure_dirs() -> None:
    COOKIE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)


def save_browser_cookies(cookies: list[dict]) -> None:
    """Save browser cookies to a JSON file."""
    _ensure_dirs()
    COOKIES_FILE.write_text(json.dumps(cookies))


def load_browser_cookies() -> list[dict]:
    """Load saved browser cookies."""
    if not COOKIES_FILE.exists():
        return []
    try:
        return json.loads(COOKIES_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def _has_auth_cookie(cookies: list[dict]) -> bool:
    """Return True if the authenticated-session cookie is present and non-empty."""
    return any(c.get("name") == AUTH_COOKIE and c.get("value") for c in cookies)


def login() -> None:
    """Launch browser for interactive JLCPCB login.

    Saves all cookies (including httpOnly) to a JSON file
    that the HTTP client can load for subsequent API calls.
    """
    from playwright.sync_api import sync_playwright

    _ensure_dirs()

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(CHROME_PROFILE_DIR),
            headless=False,
            args=["--no-first-run", "--no-default-browser-check"],
        )

        try:
            page = context.pages[0] if context.pages else context.new_page()

            # The persistent profile retains jlc_session_customer_code across
            # runs (login even rewrites it to a far-future expiry). Left in
            # place it would satisfy the cookie check below before the user
            # authenticates — a false "login successful" against a session the
            # server may have long since invalidated. Clear it so only a real
            # login this run can set it again; a still-valid session simply
            # re-issues it on the navigation below.
            context.clear_cookies(name=AUTH_COOKIE)

            page.goto(f"{ORDERS_URL}/")

            print("Please log in via the browser window.")
            print("Waiting for login to complete (up to 5 minutes)...")

            _wait_for_login(context, page)

            # Wait for post-login API calls to complete
            page.wait_for_timeout(2000)

            # Convert session cookies (expires=-1) to persistent cookies
            # so they survive browser restarts. Playwright's persistent
            # context doesn't restore session cookies (unlike Chrome).
            FAR_FUTURE = 2147483647  # 2038-01-19
            cookies = context.cookies()
            session_cookies = [c for c in cookies if c.get("expires", -1) <= 0]
            if session_cookies:
                for c in session_cookies:
                    c["expires"] = FAR_FUTURE
                context.clear_cookies()
                context.add_cookies(cookies)

            # Save cookies to JSON for the HTTP client
            save_browser_cookies(cookies)
            print(f"Login successful. {len(cookies)} cookies saved.")
        finally:
            context.close()


def _wait_for_login(context, page) -> None:
    """Wait for the user to complete login, detected via the session cookie.

    JLCPCB performs a client-side JS redirect to passport.jlcpcb.com for
    unauthenticated requests. Wait for networkidle first so any pending
    redirect settles, then poll the browser context for the auth cookie —
    which appears only once the user has actually logged in, regardless of
    which page the post-login redirect lands on.

    Raises:
        TimeoutError: if login is not completed within 5 minutes.
    """
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except PlaywrightTimeoutError:
        pass  # Page may never reach idle; fall through to polling.

    timeout = 300
    start = time.time()
    while time.time() - start < timeout:
        if _has_auth_cookie(context.cookies()):
            return
        time.sleep(1)
    raise TimeoutError(
        f"Login timed out after 5 minutes (last URL: {page.url})"
    )
