"""
session.py
==========
Handles bypass of Naukri's bot-protection (reCAPTCHA / WAF) by using Playwright
to initialize a real browser session, capturing the `nkparam` token and cookies,
and returning a standard `requests.Session` for fast subsequent scraping.
"""

from playwright.sync_api import sync_playwright
import requests
import time
from utils import log

def setup_naukri_session() -> tuple[requests.Session, dict]:
    """
    Spins up a headless Firefox browser, visits Naukri to solve anti-bot checks,
    captures the necessary API headers (nkparam), and returns a configured requests.Session.
    """
    log("[INFO] Starting headless Firefox to initialize session & bypass WAF...")
    
    captured_headers = {}
    pw_cookies = []

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        # Use a very standard Windows Firefox User-Agent
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
        ctx = browser.new_context(
            user_agent=user_agent,
            viewport={'width': 1920, 'height': 1080}
        )
        page = ctx.new_page()

        def handle_request(req):
            if "jobapi/v3/search" in req.url:
                if "nkparam" in req.headers:
                    # Capture the dynamic session token
                    captured_headers["nkparam"] = req.headers["nkparam"]

        page.on("request", handle_request)
        
        try:
            # Visit a search page to trigger the API calls and token generation
            page.goto("https://www.naukri.com/software-developer-jobs-in-india", wait_until="domcontentloaded", timeout=60000)
            
            # Actively poll for the token up to 15 seconds
            for _ in range(15):
                if "nkparam" in captured_headers:
                    break
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1000)
            
            # If still not found, try navigating to a different page just in case
            if "nkparam" not in captured_headers:
                page.goto("https://www.naukri.com/data-scientist-jobs-in-bangalore", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)
                
            pw_cookies = ctx.cookies()
        except Exception as e:
            log(f"[WARN] Error during Playwright initialization: {e}")
        finally:
            browser.close()

    if "nkparam" not in captured_headers:
        log("[WARN] Failed to capture 'nkparam' token. API calls might be blocked.")
    else:
        # Avoid printing the whole token for security, just show we got it
        token_preview = captured_headers["nkparam"][:10] + "..."
        log(f"[INFO] Successfully captured session token (nkparam: {token_preview})")

    # Transfer cookies to a standard requests session
    session = requests.Session()
    for c in pw_cookies:
        session.cookies.set(c['name'], c['value'], domain=c['domain'])

    return session, captured_headers
