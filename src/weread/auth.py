from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page, BrowserContext

from weread.errors import LoginExpiredError
from weread.utils import get_cookie_path

_READING_VIEW = ".readerTopBar"
_READ_BUTTON = "button:has-text('阅读'), a:has-text('阅读')"


def get_storage_state_path() -> Path | None:
    path = get_cookie_path()
    return path if path.exists() else None


def save_state(context: BrowserContext) -> None:
    path = get_cookie_path()
    context.storage_state(path=str(path))


def _is_login_required(page: Page) -> bool:
    login_link = page.locator("a:has-text('登录'), .navBar_link_Login")
    return login_link.count() > 0


def _enter_reading_view(page: Page) -> None:
    read_btn = page.locator(_READ_BUTTON)
    if read_btn.count() > 0 and read_btn.first.is_visible():
        read_btn.first.click()
        page.wait_for_selector(_READING_VIEW, timeout=15000)


def ensure_login(page: Page) -> bool:
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    if _is_login_required(page):
        print("⚠️  检测到登录态已过期，请扫码登录")
        try:
            input("   扫码完成后按 Enter 继续（Ctrl+C 取消）...")
        except (KeyboardInterrupt, EOFError):
            raise LoginExpiredError("用户取消了登录")

        page.reload()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        if _is_login_required(page):
            raise LoginExpiredError("登录后仍未检测到有效登录态")

    _enter_reading_view(page)
    save_state(page.context)
    return True
