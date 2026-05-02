from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page, BrowserContext

from weread.errors import LoginExpiredError
from weread.utils import get_cookie_path

_CHAPTER_CONTENT = ".readerChapterContent"
_LOGIN_LINK = "a:has-text('登录'), .navBar_link_Login"


def get_storage_state_path() -> Path | None:
    path = get_cookie_path()
    return path if path.exists() else None


def save_state(context: BrowserContext) -> None:
    path = get_cookie_path()
    context.storage_state(path=str(path))


def _is_login_required(page: Page) -> bool:
    return page.locator(_LOGIN_LINK).count() > 0


def ensure_login(page: Page) -> bool:
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    if _is_login_required(page):
        print("⚠️  检测到未登录，请在浏览器中扫码登录")
        print("   登录后请手动点击「阅读」按钮进入阅读页")
        try:
            input("   确认已在阅读页后按 Enter 继续（Ctrl+C 取消）...")
        except (KeyboardInterrupt, EOFError):
            raise LoginExpiredError("用户取消了登录")
    else:
        print("   ✓ 登录态有效，请确认已进入阅读页")
        try:
            input("   确认已在阅读页后按 Enter 继续（Ctrl+C 取消）...")
        except (KeyboardInterrupt, EOFError):
            raise LoginExpiredError("用户取消了操作")

    save_state(page.context)
    return True
