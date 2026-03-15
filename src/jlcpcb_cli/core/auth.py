"""Authentication via Playwright browser + cookie persistence."""

import http.cookiejar
import os
import socket
import stat
import subprocess
import time
from pathlib import Path

COOKIE_DIR = Path.home() / ".jlcpcb-cli"
COOKIE_FILE = COOKIE_DIR / "cookies.txt"

# JLCPCB cookie domains to persist
COOKIE_DOMAINS = {
    ".jlcpcb.com",
    "jlcpcb.com",
    "passport.jlcpcb.com",
    ".passport.jlcpcb.com",
    "im.jlcpcb.com",
}

# Chrome user data directory for persistent browser profile
CHROME_PROFILE_DIR = COOKIE_DIR / "chrome-profile"


def _ensure_cookie_dir() -> None:
    COOKIE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)


def load_cookies() -> http.cookiejar.MozillaCookieJar:
    """Load persisted cookies from disk."""
    jar = http.cookiejar.MozillaCookieJar(str(COOKIE_FILE))
    if COOKIE_FILE.exists():
        try:
            jar.load(ignore_discard=True, ignore_expires=True)
        except (OSError, http.cookiejar.LoadError):
            pass
    return jar


def save_cookies(jar: http.cookiejar.MozillaCookieJar) -> None:
    """Persist cookies to disk with restricted permissions."""
    _ensure_cookie_dir()
    jar.save(ignore_discard=True, ignore_expires=True)
    os.chmod(COOKIE_FILE, stat.S_IRUSR | stat.S_IWUSR)


def get_xsrf_token(jar: http.cookiejar.MozillaCookieJar) -> str | None:
    """Extract the XSRF-TOKEN cookie value."""
    for cookie in jar:
        if cookie.name == "XSRF-TOKEN" and "jlcpcb" in cookie.domain:
            return cookie.value
    return None


def has_valid_session(jar: http.cookiejar.MozillaCookieJar) -> bool:
    """Check if the cookie jar has the long-lived session cookie.

    Only checks for JLCPCB_SESSION_ID. The XSRF token is short-lived
    and refreshed automatically by the client.
    """
    return any(cookie.name == "JLCPCB_SESSION_ID" for cookie in jar)


def _find_chrome() -> str:
    """Find Chrome/Chromium executable on the system."""
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "google-chrome",
        "chromium",
        "chromium-browser",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.is_absolute() and path.exists():
            return str(path)
        try:
            result = subprocess.run(
                ["which", candidate], capture_output=True, text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except FileNotFoundError:
            continue
    raise RuntimeError(
        "Chrome not found. Install Google Chrome or set CHROME_PATH env var."
    )


def _find_free_port() -> int:
    """Find a free TCP port for Chrome debugging."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _launch_chrome_with_debugging(port: int | None = None) -> tuple[subprocess.Popen, int]:
    """Launch Chrome with remote debugging enabled and a persistent profile."""
    if port is None:
        port = _find_free_port()

    _ensure_cookie_dir()
    chrome_path = os.environ.get("CHROME_PATH", _find_chrome())

    args = [
        chrome_path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={CHROME_PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "about:blank",
    ]

    process = subprocess.Popen(
        args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    return process, port


def login() -> http.cookiejar.MozillaCookieJar:
    """Launch real Chrome for interactive login, extract and persist cookies."""
    from playwright.sync_api import sync_playwright

    jar = http.cookiejar.MozillaCookieJar(str(COOKIE_FILE))

    chrome_process, port = _launch_chrome_with_debugging()

    try:
        time.sleep(2)

        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{port}")
            context = browser.contexts[0]

            if context.pages:
                page = context.pages[0]
            else:
                page = context.new_page()

            page.goto("https://jlcpcb.com/user-center/orders/")

            print("Please log in via the Chrome window.")
            print("Waiting for order page to load (up to 5 minutes)...")

            _wait_for_login(page)

            # Extract cookies from browser context
            browser_cookies = context.cookies()
            for bc in browser_cookies:
                domain = bc["domain"]
                if not any(domain.endswith(d.lstrip(".")) for d in COOKIE_DOMAINS):
                    continue

                # Session cookies (expires <= 0) get a far-future expiry so
                # MozillaCookieJar doesn't treat them as expired on reload.
                FAR_FUTURE = 2147483647  # 2038-01-19
                raw_expires = bc.get("expires", -1)
                expires = int(raw_expires) if raw_expires > 0 else FAR_FUTURE

                cookie = http.cookiejar.Cookie(
                    version=0,
                    name=bc["name"],
                    value=bc["value"],
                    port=None,
                    port_specified=False,
                    domain=bc["domain"],
                    domain_specified=True,
                    domain_initial_dot=bc["domain"].startswith("."),
                    path=bc.get("path", "/"),
                    path_specified=True,
                    secure=bc.get("secure", False),
                    expires=expires,
                    discard=False,
                    comment=None,
                    comment_url=None,
                    rest={"HttpOnly": str(bc.get("httpOnly", False))},
                )
                jar.set_cookie(cookie)

            browser.close()
    finally:
        chrome_process.terminate()
        try:
            chrome_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            chrome_process.kill()

    if not has_valid_session(jar):
        raise RuntimeError(
            "Login succeeded but required cookies not found. "
            "Session may not have been established correctly."
        )

    save_cookies(jar)
    print(f"Login successful. {len(jar)} cookies persisted.")
    return jar


def _wait_for_login(page) -> None:
    """Wait for the user to complete login and reach the orders page."""
    timeout = 300  # 5 minutes max
    start = time.time()
    while time.time() - start < timeout:
        url = page.url
        if "jlcpcb.com/user-center/orders" in url:
            page.wait_for_load_state("networkidle")
            return
        time.sleep(1)
    raise TimeoutError("Login timed out after 5 minutes.")
