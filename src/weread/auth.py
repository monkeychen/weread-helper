import json
from pathlib import Path

from playwright.sync_api import Page, BrowserContext

from weread.errors import LoginExpiredError
from weread.utils import get_cookie_path

_LOGIN_INDICATOR = ".login_dialog_qrcode,.wr_login_dialog_qrcode,.navBar_link_Login"
_READER_CONTENT = ".readerChapterContent,.app_content"
_LOGIN_WAIT_INTERVAL = 2000


def load_cookies(context: BrowserContext) -> bool:
    cookie_path = get_cookie_path()
    if not cookie_path.exists():
        return False
    try:
        state = json.loads(cookie_path.read_text(encoding="utf-8"))
        context.add_cookies(state.get("cookies", []))
        return True
    except (json.JSONDecodeError, KeyError):
        return False


def save_cookies(context: BrowserContext) -> None:
    cookie_path = get_cookie_path()
    state = context.storage_state()
    cookie_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _is_login_required(page: Page) -> bool:
    try:
        page.wait_for_selector(_READER_CONTENT, timeout=8000)
        return False
    except Exception:
        login_el = page.query_selector(_LOGIN_INDICATOR)
        return login_el is not None


def ensure_login(page: Page) -> bool:
    if not _is_login_required(page):
        return True

    print("⚠️  检测到登录态已过期，请扫码登录")
    try:
        answer = input("   扫码完成后按 Enter 继续（Ctrl+C 取消）...")
    except (KeyboardInterrupt, EOFError):
        raise LoginExpiredError("用户取消了登录")

    page.reload()
    page.wait_for_selector(_READER_CONTENT, timeout=15000)

    save_cookies(page.context)
    return True
