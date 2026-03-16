"""Headless browser client for JLCPCB web API endpoints.

Used for endpoints not available in the official API (order listing,
parts order history) where Akamai Bot Manager blocks direct HTTP access.
"""

import json

_browser_instance = None


class BrowserClient:
    """Makes API calls through a headless Playwright browser."""

    def __init__(self):
        self._pw = None
        self._context = None
        self._page = None

    def _ensure_browser(self) -> None:
        if self._page is not None:
            return

        from playwright.sync_api import sync_playwright
        from jlcpcb_cli.core import auth

        self._pw = sync_playwright().start()
        self._context = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(auth.CHROME_PROFILE_DIR),
            headless=True,
            args=["--no-first-run", "--no-default-browser-check"],
        )
        self._page = (
            self._context.pages[0] if self._context.pages
            else self._context.new_page()
        )

        # Navigate to JLCPCB — saved cookies should authenticate us
        self._page.goto(
            "https://jlcpcb.com/user-center/orders/",
            wait_until="networkidle",
        )

    def api_post(self, path: str, data: dict) -> dict:
        """Make an authenticated POST to jlcpcb.com via browser fetch()."""
        self._ensure_browser()

        result = self._page.evaluate(
            """async ([path, data]) => {
                const cookies = document.cookie.split(';').map(c => c.trim());
                const xsrfCookie = cookies.find(c => c.startsWith('XSRF-TOKEN='));
                const xsrfToken = xsrfCookie
                    ? decodeURIComponent(xsrfCookie.split('=')[1]) : null;

                // Get secret key
                const uuid = crypto.randomUUID();
                const keyId = Array.from(new TextEncoder().encode(uuid))
                    .map(b => b.toString(16).padStart(2, '0')).join('');
                const secretResp = await fetch(
                    '/api/overseas-core-platform/secret/update',
                    {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'x-xsrf-token': xsrfToken
                        },
                        body: JSON.stringify({ keyId })
                    }
                );
                if (!secretResp.ok) {
                    return { success: false, code: secretResp.status,
                             message: 'secret/update failed: HTTP ' + secretResp.status };
                }
                const secretResult = await secretResp.json();
                if (!secretResult.success && secretResult.code !== 200) {
                    return secretResult;
                }
                const secretKey = secretResult.data.keyId;

                // Actual API call
                const resp = await fetch('/api' + path, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'x-xsrf-token': xsrfToken,
                        'secretkey': secretKey
                    },
                    body: JSON.stringify(data)
                });
                return await resp.json();
            }""",
            [path, data],
        )

        return result

    def close(self) -> None:
        if self._context:
            self._context.close()
            self._context = None
            self._page = None
        if self._pw:
            self._pw.stop()
            self._pw = None


def get_browser_client() -> BrowserClient:
    """Get or create the singleton browser client."""
    global _browser_instance
    if _browser_instance is None:
        _browser_instance = BrowserClient()
    return _browser_instance
