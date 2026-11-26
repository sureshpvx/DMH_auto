import re
import pytest
from playwright.sync_api import Page, expect
from helpers import (
    BASE_ORIGIN,
    FORGOT_PASSWORD_URL,
    PATIENT_LOGIN_URL,
    audit_portal_modules,
    click_sidebar_link,
    login_as_patient,
    logout_current_user,
)

SCREENSHOT_DIR = "audit_screenshots"


def test_login_page_console_health(browser):
    """Verify the unauthenticated Patient login page loads with zero console or page errors."""
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    errors: list[str] = []

    page.on("pageerror", lambda err: errors.append(f"PAGEERROR: {err}"))
    page.on(
        "console",
        lambda msg: errors.append(f"CONSOLE: {msg.text}") if msg.type == "error" else None,
    )
    page.goto(PATIENT_LOGIN_URL, wait_until="networkidle")
    page.wait_for_timeout(1200)
    context.close()

    assert not errors, "Login page errors:\n" + "\n".join(errors)


def test_authenticated_dmh_modules(auth_page: Page):
    """Audit all authenticated Patient portal modules after login settles."""
    auth_page.goto(BASE_ORIGIN, wait_until="networkidle")
    auth_page.wait_for_timeout(1500)
    assert "/auth/" not in auth_page.url, (
        f"Expected authenticated Patient session at '{BASE_ORIGIN}', landed on '{auth_page.url}'."
    )

    all_bugs = audit_portal_modules(
        auth_page,
        portal_name="Patient Dashboard",
        screenshot_dir=SCREENSHOT_DIR,
        report_path="dmh_bug_report.txt",
    )
    assert not all_bugs, f"\nFound {len(all_bugs)} QA issues:\n" + "\n".join(all_bugs)


class TestPatientPortalFlows:

    def test_patient_login_positive(self, page: Page):
        """Positive Test: Valid Patient credentials log into the Patient Dashboard."""
        login_as_patient(page)
        expect(page.locator("a[href='/']").filter(has_text="Dashboard")).to_be_visible(timeout=8000)
        expect(page.locator("a[href='/report']")).to_be_visible(timeout=8000)

    @pytest.mark.parametrize(
        "email, password",
        [
            pytest.param("", "", id="both_fields_empty"),
            pytest.param("pat@gmail.com", "", id="empty_password"),
            pytest.param("", "Test!234", id="empty_email"),
        ],
    )
    def test_patient_login_button_disabled_when_incomplete(
        self, page: Page, email: str, password: str
    ):
        """Negative Test (UI Validation): Sign In button stays disabled when fields are empty."""
        page.goto(PATIENT_LOGIN_URL, wait_until="networkidle")
        page.get_by_role("textbox", name="Email address").fill(email)
        page.get_by_role("textbox", name="Password").fill(password)

        sign_in_btn = page.locator("form").get_by_role("button", name="Sign In")
        expect(sign_in_btn).to_be_disabled()
        expect(page).to_have_url(PATIENT_LOGIN_URL)

    @pytest.mark.parametrize(
        "email, password",
        [
            ("pat@gmail.com", "WrongPass!99"),
            ("unknown_patient@gmail.com", "Test!234"),
            ("bad-email-format", "Test!234"),
        ],
    )
    def test_patient_login_negative_invalid_credentials(
        self, page: Page, email: str, password: str
    ):
        """Negative Test: Invalid Patient credentials keep user on /auth/patient-login."""
        page.goto(PATIENT_LOGIN_URL, wait_until="networkidle")
        page.get_by_role("textbox", name="Email address").fill(email)
        page.get_by_role("textbox", name="Password").fill(password)

        sign_in_btn = page.locator("form").get_by_role("button", name="Sign In")
        expect(sign_in_btn).to_be_enabled()
        sign_in_btn.click()

        expect(page).to_have_url(PATIENT_LOGIN_URL)

    @pytest.mark.parametrize(
        "menu_label, expected_path",
        [
            ("Report", "/report"),
            ("Setting", "/setting"),
        ],
    )
    def test_patient_sidebar_navigation_positive(
        self, page: Page, menu_label: str, expected_path: str
    ):
        """Positive Test: Patient sidebar links (including Configuration -> Setting) load cleanly."""
        login_as_patient(page)
        click_sidebar_link(page, menu_label, href=expected_path, portal_name="Patient")
        expect(page).to_have_url(re.compile(rf".*{re.escape(expected_path)}"), timeout=8000)

    def test_patient_forgot_password_page_and_validation(self, page: Page):
        """Verify Forgot Password route loads and rejects empty/malformed email submission."""
        page.goto(PATIENT_LOGIN_URL, wait_until="networkidle")
        page.get_by_text(re.compile(r"Forgot Password", re.I)).first.click()
        expect(page).to_have_url(FORGOT_PASSWORD_URL, timeout=8000)

        email_input = page.locator("input").first
        send_otp_btn = page.get_by_role("button", name="Send OTP")
        expect(email_input).to_be_visible()
        expect(send_otp_btn).to_be_visible()

        email_input.fill("not-an-email")
        if send_otp_btn.is_enabled():
            send_otp_btn.click()
        expect(page).to_have_url(FORGOT_PASSWORD_URL)

    def test_patient_logout_and_back_navigation_blocked(self, page: Page):
        """Security Test: Logging out from Patient portal blocks browser Back re-entry."""
        login_as_patient(page)
        click_sidebar_link(page, "Report", href="/report", portal_name="Patient")
        protected_url = page.url

        logout_current_user(page)
        page.go_back(wait_until="domcontentloaded")

        assert (
            page.url != protected_url
            or page.locator("form").get_by_role("button", name=re.compile(r"login|sign in", re.I)).count() > 0
        ), f"Post-logout browser Back stayed on protected URL '{page.url}'."
