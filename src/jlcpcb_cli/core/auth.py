"""Authentication — browser login for web API endpoints."""

import json
import time
from pathlib import Path

COOKIE_DIR = Path.home() / ".jlcpcb-cli"
CHROME_PROFILE_DIR = COOKIE_DIR / "chrome-profile"
COOKIES_FILE = COOKIE_DIR / "browser-cookies.json"
STORAGE_STATE_FILE = COOKIE_DIR / "storage-state.json"


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
            page.goto("https://jlcpcb.com/user-center/orders/")

            print("Please log in via the browser window.")
            print("Waiting for order page to load (up to 5 minutes)...")

            _wait_for_login(page)

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


def _wait_for_login(page) -> None:
    """Wait for the user to complete login and reach the orders page."""
    timeout = 300
    start = time.time()
    while time.time() - start < timeout:
        url = page.url
        if "jlcpcb.com/user-center/orders" in url:
            page.wait_for_load_state("networkidle")
            return
        time.sleep(1)
    raise TimeoutError("Login timed out after 5 minutes.")
