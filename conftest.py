import os
from typing import Callable
import pytest
from dotenv import load_dotenv
from playwright.sync_api import Page
from helpers import BASE_ORIGIN, login_as_patient

load_dotenv()

BASE_URL = os.getenv("DMH_BASE_URL", BASE_ORIGIN).rstrip("/")
USERNAME = os.getenv("DMH_USERNAME", "")
PASSWORD = os.getenv("DMH_PASSWORD", "")
AUTH_FILE = "auth_state.json"
SESSION_STORAGE_FILE = "session_storage.json"


@pytest.fixture(scope="session")
def base_url():
    """Provides the default base URL for pytest-playwright without class-fixture warnings."""
    return BASE_URL


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    """Adds Windows Chromium stability flags to prevent mid-run renderer crashes."""
    return {
        **browser_type_launch_args,
        "args": [
            *browser_type_launch_args.get("args", []),
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
    }


@pytest.fixture(scope="module")
def browser(browser_type, browser_type_launch_args):
    """Restarts Chromium per test file so memory doesn't accumulate across tests."""
    browser = browser_type.launch(**browser_type_launch_args)
    yield browser
    browser.close()


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Sets default 1440x900 viewport for all Playwright page/context fixtures."""
    return {
        **browser_context_args,
        "viewport": {"width": 1440, "height": 900},
    }


@pytest.fixture(scope="session")
def setup_patient_auth(browser_type, browser_type_launch_args):
    """Logs into DMH Patient portal once and saves cookies, localStorage, and sessionStorage."""
    assert BASE_URL, "DMH_BASE_URL is missing in .env"

    auth_browser = browser_type.launch(**browser_type_launch_args)
    context = auth_browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()

    login_as_patient(page, USERNAME, PASSWORD)
    page.wait_for_timeout(1500)
    print(f"\n[AUTH] Post-login URL: {page.url}")

    context.storage_state(path=AUTH_FILE)
    session_data = page.evaluate("() => JSON.stringify(sessionStorage)")
    with open(SESSION_STORAGE_FILE, "w", encoding="utf-8") as f:
        f.write(session_data)

    context.close()
    auth_browser.close()


@pytest.fixture(scope="function")
def auth_page(setup_patient_auth, browser):
    """Restores full browser state (cookies, localStorage, and sessionStorage)."""
    context = browser.new_context(
        storage_state=AUTH_FILE,
        viewport={"width": 1440, "height": 900},
    )

    if os.path.exists(SESSION_STORAGE_FILE):
        with open(SESSION_STORAGE_FILE, "r", encoding="utf-8") as f:
            session_json = f.read()
        context.add_init_script(
            f"""
            const data = {session_json};
            for (const [k, v] of Object.entries(data)) {{
                window.sessionStorage.setItem(k, v);
            }}
            """
        )

    page = context.new_page()
    yield page
    context.close()


@pytest.fixture
def valid_image_path(tmp_path) -> str:
    """Generates a valid 1x1 PNG file on the fly for patient avatar upload tests."""
    img_file = tmp_path / "avatar.png"
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    img_file.write_bytes(png_bytes)
    return str(img_file)


@pytest.fixture
def invalid_file_path(tmp_path) -> str:
    """Generates a dummy .tif file to verify unsupported file upload rejection."""
    tif_file = tmp_path / "test_standard.tif"
    tif_file.write_bytes(b"II*\x00\x08\x00\x00\x00")
    return str(tif_file)


@pytest.fixture
def js_error_collector(page: Page) -> Callable[..., list[str]]:
    """Collects uncaught page errors and unexpected console errors during a test."""
    errors: list[str] = []
    ignored_statuses: set[str] = {"400"}

    def on_page_error(exc) -> None:
        errors.append(f"PAGEERROR: {exc}")

    def on_console(msg) -> None:
        if msg.type == "error":
            if any(f"status of {code}" in msg.text for code in ignored_statuses):
                return
            errors.append(f"CONSOLE_ERROR: {msg.text}")

    page.on("pageerror", on_page_error)
    page.on("console", on_console)

    def _get_errors(*, ignore_status_codes: tuple[str, ...] = ("400",)) -> list[str]:
        nonlocal ignored_statuses
        ignored_statuses = set(ignore_status_codes)
        return [
            err for err in errors
            if not any(f"status of {code}" in err for code in ignored_statuses)
        ]

    return _get_errors
