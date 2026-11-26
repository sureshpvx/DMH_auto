import re
from typing import Callable
import pytest
from playwright.sync_api import Page, expect
from helpers import (
    LAB_LOGIN_URL,
    audit_portal_modules,
    click_sidebar_link,
    fill_valid_patient_form,
    login_as_lab,
    logout_current_user,
)


def _open_lab_add_patient(page: Page) -> None:
    """Log into Lab portal and navigate to /patient/add."""
    login_as_lab(page)
    click_sidebar_link(page, "Patient", href="/patient", portal_name="Lab")

    add_btn = page.get_by_role("button", name=re.compile(r"add|new|create", re.I))
    expect(add_btn.first).to_be_visible(timeout=8000)
    add_btn.first.click()
    expect(page).to_have_url(re.compile(r".*/patient/add"), timeout=8000)


# =====================================================================
# 1. POSITIVE TESTS
# =====================================================================


class TestLabPositiveFlows:

    def test_lab_login_positive(self, page: Page):
        """Positive Test: Valid Lab credentials log into the Lab Dashboard."""
        login_as_lab(page)
        expect(page.locator("a[href='/']").filter(has_text="Dashboard")).to_be_visible(timeout=8000)
        expect(page.locator("a[href='/patient']")).to_be_visible(timeout=8000)
        expect(page.locator("a[href='/case']")).to_be_visible(timeout=8000)
        expect(page.locator("a[href='/report']")).to_be_visible(timeout=8000)

    @pytest.mark.parametrize(
        "menu_label, expected_path",
        [
            ("Patient", "/patient"),
            ("Case", "/case"),
            ("Report", "/report"),
            ("Test", "/test"),
            ("Audit Logs", "/audit-logs"),
        ],
    )
    def test_lab_sidebar_navigation_positive(
        self, page: Page, menu_label: str, expected_path: str
    ):
        """Positive Test: Core Lab sidebar modules load cleanly with expected URLs."""
        login_as_lab(page)
        click_sidebar_link(page, menu_label, href=expected_path, portal_name="Lab")
        expect(page).to_have_url(re.compile(rf".*{re.escape(expected_path)}"), timeout=8000)

    def test_lab_all_modules_audit(self, page: Page):
        """Audits all Lab portal modules for 404s, API errors, console errors, and layout overflow."""
        login_as_lab(page)
        all_bugs = audit_portal_modules(
            page,
            portal_name="Lab Dashboard",
            screenshot_dir="lab_audit_screenshots",
            report_path="lab_bug_report.txt",
        )
        assert not all_bugs, (
            f"\nFound {len(all_bugs)} Lab QA issues:\n" + "\n".join(all_bugs)
        )

    def test_lab_add_patient_positive(self, page: Page, valid_image_path: str):
        """Positive Test: Lab user can create a new patient with valid details."""
        _open_lab_add_patient(page)
        fill_valid_patient_form(
            page,
            name_prefix="Lab Patient",
            mobile_prefix="987459",
            email_prefix="lab_patient",
            title="Mr.",
            blood_group="B+",
            remarks="Automated Lab QA positive test",
            image_path=valid_image_path,
        )

        page.get_by_role("button", name=re.compile(r"Save")).click()
        expect(page).not_to_have_url(re.compile(r".*/patient/add"), timeout=10000)

    def test_lab_logout_positive(self, page: Page):
        """Positive Test: Lab user can log out cleanly and return to login."""
        login_as_lab(page)
        logout_current_user(page, profile_button_pattern=r"Profile Picture Lab")


# =====================================================================
# 2. NEGATIVE & EDGE CASE TESTS
# =====================================================================


class TestLabNegativeEdgeCases:

    @pytest.mark.parametrize(
        "email, password",
        [
            pytest.param("", "", id="both_fields_empty"),
            pytest.param("lab@gmail.com", "", id="empty_password"),
            pytest.param("", "Test!234", id="empty_email"),
            pytest.param("invalid-email-format", "Test!234", id="malformed_email"),
        ],
    )
    def test_lab_login_button_disabled_when_incomplete(
        self, page: Page, email: str, password: str
    ):
        """Negative Test (UI Validation): Sign In remains disabled on incomplete/malformed input."""
        page.goto(LAB_LOGIN_URL, wait_until="networkidle")
        page.get_by_role("textbox", name="Email address").fill(email)
        page.get_by_role("textbox", name="Password").fill(password)

        expect(page.get_by_role("button", name="Sign In")).to_be_disabled()
        expect(page).to_have_url(LAB_LOGIN_URL)

    @pytest.mark.parametrize(
        "email, password",
        [
            ("lab@gmail.com", "WrongPass!999"),
            ("unknown_lab@gmail.com", "Test!234"),
            ("invalid-email-format", "Test!234"),
            ("", ""),
        ],
    )
    def test_lab_login_negative_invalid_inputs(self, page: Page, email: str, password: str):
        """Negative Test: Invalid or blank credentials keep the user on /auth/lab-login."""
        page.goto(LAB_LOGIN_URL, wait_until="networkidle")
        page.get_by_role("textbox", name="Email address").fill(email)
        page.get_by_role("textbox", name="Password").fill(password)

        sign_in_btn = page.get_by_role("button", name="Sign In")
        if sign_in_btn.is_enabled():
            sign_in_btn.click()

        expect(page).to_have_url(LAB_LOGIN_URL)

    def test_address_preserved_on_validation_error(
        self, page: Page, js_error_collector: Callable[..., list[str]]
    ):
        """
        Regression / Negative Test on /patient/add:
        Submitting with required fields (Name, Email) blank must preserve entered Address.
        """
        _open_lab_add_patient(page)

        name_input = page.locator('input[formcontrolname="name"]')
        email_input = page.locator('input[formcontrolname="email"]')
        address_input = page.locator('input[formcontrolname="address"]')
        expect(address_input).to_be_visible(timeout=8000)

        entered_address = "104 Ring Road, Surat, Gujarat"
        address_input.fill(entered_address)

        suggestion = page.locator(
            "[role='option'], .pac-item, li[data-suggestion], ul[role='listbox'] li"
        ).first
        if suggestion.count() > 0 and suggestion.is_visible():
            suggestion.click()

        expected_address = address_input.input_value().strip() or entered_address
        assert expected_address != "", "Expected Address field to contain text before submit."

        name_input.fill("")
        email_input.fill("")

        save_btn = page.get_by_role("button", name=re.compile(r"save", re.I))
        expect(save_btn.first).to_be_visible(timeout=8000)
        if save_btn.first.is_enabled():
            save_btn.first.click()

        expect(page).to_have_url(re.compile(r".*/patient/add"))
        expect(name_input).to_have_class(re.compile(r"ng-invalid"))
        expect(email_input).to_have_class(re.compile(r"ng-invalid"))

        assert address_input.input_value() == expected_address, (
            f"Bug reproduced: Address changed from '{expected_address}' "
            f"to '{address_input.input_value()}' after validation failure."
        )

        captured_errors = js_error_collector(ignore_status_codes=("400",))
        assert not captured_errors, (
            "JS errors occurred during form validation:\n" + "\n".join(captured_errors)
        )

    def test_whitespace_only_name_and_email_rejected(self, page: Page):
        """Edge case: Whitespace-only strings in required fields should not create a patient."""
        _open_lab_add_patient(page)

        name_input = page.locator('input[formcontrolname="name"]')
        email_input = page.locator('input[formcontrolname="email"]')
        expect(email_input).to_be_visible(timeout=8000)
        name_input.fill("     ")
        email_input.fill("   @   ")

        save_btn = page.get_by_role("button", name=re.compile(r"save", re.I))
        if save_btn.first.is_enabled():
            save_btn.first.click()

        expect(page).to_have_url(re.compile(r".*/patient/add"))

    def test_lab_add_patient_negative_empty_form(self, page: Page):
        """Negative Test: Submitting an empty Lab patient form stays on /patient/add."""
        _open_lab_add_patient(page)
        save_btn = page.get_by_role("button", name=re.compile(r"Save"))
        if save_btn.is_enabled():
            save_btn.click()
        expect(page).to_have_url(re.compile(r".*/patient/add"))

    def test_lab_add_patient_negative_invalid_phone_and_email(self, page: Page):
        """Negative Test: Invalid mobile number and malformed email block Lab patient creation."""
        _open_lab_add_patient(page)
        page.locator('input[formcontrolname="mobileNumber"]').fill("123")
        page.locator('input[formcontrolname="name"]').fill("Invalid Lab Patient")
        page.locator('input[formcontrolname="email"]').fill("not-an-email")

        save_btn = page.get_by_role("button", name=re.compile(r"Save"))
        if save_btn.is_enabled():
            save_btn.click()
        expect(page).to_have_url(re.compile(r".*/patient/add"))

    def test_lab_add_patient_negative_unsupported_tif_upload(
        self, page: Page, invalid_file_path: str
    ):
        """Negative Test: Uploading an unsupported .tif file blocks Lab patient creation."""
        _open_lab_add_patient(page)
        page.get_by_role("button", name="Choose").click()
        page.get_by_label("Browse Files").set_input_files(invalid_file_path)

        save_btn = page.get_by_role("button", name=re.compile(r"Save"))
        if save_btn.is_enabled():
            save_btn.click()
        expect(page).to_have_url(re.compile(r".*/patient/add"))

    @pytest.mark.parametrize("discount", ["-15", "150"])
    def test_lab_add_patient_out_of_range_discount_blocked(
        self, page: Page, discount: str
    ):
        """Edge case: Out-of-range discount outside 0-100% stays on /patient/add."""
        _open_lab_add_patient(page)
        fill_valid_patient_form(
            page,
            name_prefix="Lab Discount Check",
            mobile_prefix="987459",
            email_prefix="lab_disc",
            title="Mr.",
            blood_group="B+",
        )
        page.locator('input[formcontrolname="discountPercent"]').fill(discount)

        save_btn = page.get_by_role("button", name=re.compile(r"Save"))
        if save_btn.is_enabled():
            save_btn.click()
        expect(page).to_have_url(re.compile(r".*/patient/add"))

    @pytest.mark.parametrize(
        "label, expected_path",
        [
            ("Setting", "/setting"),
            ("Access Control", "/permission"),
            ("Log", "/logs"),
            ("Message Queue", "/queued-email"),
            ("Message Template", "/message-template"),
        ],
    )
    def test_configuration_and_system_links_accessible(
        self, page: Page, label: str, expected_path: str
    ):
        """Verifies Configuration and System submenu links expand and load cleanly."""
        login_as_lab(page)
        click_sidebar_link(page, label, href=expected_path, portal_name="Lab")
        expect(page).to_have_url(re.compile(rf".*{re.escape(expected_path)}"), timeout=8000)

    @pytest.mark.xfail(
        reason="Known Bug: Angular throws uncaught PAGEERROR on HTTP 500 when loading /audit-logs",
        strict=False,
    )
    def test_module_handles_server_500_gracefully(
        self, page: Page, js_error_collector: Callable[..., list[str]]
    ):
        """Simulates a 500 error on GET /api/ calls and checks for uncaught JS crashes."""
        login_as_lab(page)

        def fail_api(route):
            if "/api/" in route.request.url and route.request.method == "GET":
                route.fulfill(
                    status=500,
                    content_type="application/json",
                    body='{"message":"Server Error"}',
                )
            else:
                route.continue_()

        page.route("**/*", fail_api)
        try:
            click_sidebar_link(page, "Audit Logs", href="/audit-logs", portal_name="Lab")
            expect(page.locator("body")).to_be_visible()
            captured_errors = js_error_collector(ignore_status_codes=("400", "500"))
            assert not captured_errors, (
                "Uncaught JS/console error on API 500:\n" + "\n".join(captured_errors)
            )
        finally:
            page.unroute("**/*", fail_api)

    def test_post_logout_browser_back_does_not_reenter_protected_session(self, page: Page):
        """After logging out, pressing browser Back should not restore an authenticated session."""
        login_as_lab(page)
        click_sidebar_link(page, "Audit Logs", href="/audit-logs", portal_name="Lab")
        protected_url = page.url

        logout_current_user(page, profile_button_pattern=r"Profile Picture Lab")
        page.go_back(wait_until="domcontentloaded")

        assert (
            page.url != protected_url
            or page.get_by_role("button", name=re.compile(r"login|sign in", re.I)).count() > 0
        ), f"Post-logout browser Back stayed on protected URL '{page.url}'."
