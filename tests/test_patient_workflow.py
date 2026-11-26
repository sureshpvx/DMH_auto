import re
import pytest
from playwright.sync_api import Page, expect
from helpers import (
    DOCTOR_LOGIN_URL,
    click_sidebar_link,
    fill_valid_patient_form,
    login_as_doctor,
)


@pytest.fixture
def add_patient_page(page: Page) -> Page:
    """Logs in via login_as_doctor and opens the Add Patient page."""
    login_as_doctor(page)
    click_sidebar_link(page, "Patient", href="/patient", portal_name="Doctor")
    page.get_by_role("button", name=re.compile(r"Add New")).click()
    expect(page).to_have_url(re.compile(r".*/patient/add"), timeout=10000)
    return page


# =====================================================================
# 1. DOCTOR LOGIN TESTS (Positive & Negative)
# =====================================================================


class TestDoctorLogin:

    def test_doctor_login_positive(self, page: Page):
        """Verify valid doctor login + organization toggle navigates to dashboard."""
        login_as_doctor(page)
        expect(page.locator('a[href="/patient"]')).to_be_visible()

    @pytest.mark.parametrize(
        "email, password",
        [
            ("doc@gmail.com", "WrongPass!99"),
            ("unknown_doc@gmail.com", "Test!234"),
            ("bad-email-format", "Test!234"),
        ],
    )
    def test_doctor_login_negative_bad_credentials(self, page: Page, email: str, password: str):
        """Verify bad credentials never reach the Select Organization gate."""
        page.goto(DOCTOR_LOGIN_URL, wait_until="networkidle")
        page.get_by_role("textbox", name="Email address").fill(email)
        page.get_by_role("textbox", name="Password").fill(password)

        sign_in_btn = page.get_by_role("button", name="Sign In")
        if sign_in_btn.is_enabled():
            sign_in_btn.click()

        expect(page.get_by_role("heading", name="Select Organization")).not_to_be_visible()
        expect(page).to_have_url(DOCTOR_LOGIN_URL)

    def test_doctor_login_negative_empty_credentials_disables_submit(self, page: Page):
        """Verify Sign In button stays disabled when email and password are empty."""
        page.goto(DOCTOR_LOGIN_URL, wait_until="networkidle")
        expect(page.get_by_role("button", name="Sign In")).to_be_disabled()

    def test_doctor_login_negative_continue_disabled_without_org_toggle(self, page: Page):
        """Verify Continue button remains disabled if no organization toggle is enabled."""
        page.goto(DOCTOR_LOGIN_URL, wait_until="networkidle")
        page.get_by_role("textbox", name="Email address").fill("doc@gmail.com")
        page.get_by_role("textbox", name="Password").fill("Test!234")
        page.get_by_role("button", name="Sign In").click()

        expect(page.get_by_role("heading", name="Select Organization")).to_be_visible(timeout=10000)
        expect(page.get_by_role("button", name="Continue")).to_be_disabled()


# =====================================================================
# 2. ADD PATIENT TESTS (Positive & Negative)
# =====================================================================


class TestAddPatient:

    def test_add_patient_positive(self, add_patient_page: Page, valid_image_path: str):
        """Verify creating a patient with valid details and PNG avatar succeeds."""
        page = add_patient_page
        fill_valid_patient_form(
            page,
            name_prefix="Rahul Sharma",
            mobile_prefix="987458",
            email_prefix="patient",
            title="Dr.",
            blood_group="AB+",
            remarks="Automated QA test patient",
            image_path=valid_image_path,
        )

        page.get_by_role("button", name=re.compile(r"Save")).click()
        expect(page).not_to_have_url(re.compile(r".*/patient/add"), timeout=10000)

    def test_add_patient_negative_empty_form(self, add_patient_page: Page):
        """Verify submitting an empty patient form is blocked by validation."""
        page = add_patient_page
        save_btn = page.get_by_role("button", name=re.compile(r"Save"))
        if save_btn.is_enabled():
            save_btn.click()

        expect(page).to_have_url(re.compile(r".*/patient/add"))

    def test_add_patient_negative_invalid_phone_and_email(self, add_patient_page: Page):
        """Verify invalid mobile number length and malformed email prevent submission."""
        page = add_patient_page

        page.locator('input[formcontrolname="mobileNumber"]').fill("123")
        page.locator('input[formcontrolname="name"]').fill("Invalid Patient")
        page.locator('input[formcontrolname="email"]').fill("not-an-email")

        save_btn = page.get_by_role("button", name=re.compile(r"Save"))
        if save_btn.is_enabled():
            save_btn.click()

        expect(page).to_have_url(re.compile(r".*/patient/add"))

    def test_add_patient_negative_unsupported_tif_upload(
        self, add_patient_page: Page, invalid_file_path: str
    ):
        """Verify uploading a .tif file does not allow successful patient creation."""
        page = add_patient_page

        page.get_by_role("button", name="Choose").click()
        page.get_by_label("Browse Files").set_input_files(invalid_file_path)

        save_btn = page.get_by_role("button", name=re.compile(r"Save"))
        if save_btn.is_enabled():
            save_btn.click()

        expect(page).to_have_url(re.compile(r".*/patient/add"))


# =====================================================================
# 3. DOCTOR PORTAL MODULES
# =====================================================================


class TestDoctorPortalModules:

    @pytest.mark.parametrize(
        "menu_label, expected_path",
        [
            ("Patient", "/patient"),
            ("Visited Patient", "/visited-patient"),
            ("Case", "/case"),
            ("Report", "/report"),
            ("Medicine", "/medicine"),
            ("Lab Report Request", "/lab-report-request"),
            ("Setting", "/setting"),
        ],
    )
    def test_doctor_sidebar_navigation_positive(
        self, page: Page, menu_label: str, expected_path: str
    ):
        """Positive Test: Doctor sidebar modules (including Configuration -> Setting) load cleanly."""
        login_as_doctor(page)
        click_sidebar_link(page, menu_label, href=expected_path, portal_name="Doctor")
        expect(page).to_have_url(re.compile(rf".*{re.escape(expected_path)}"), timeout=8000)

    def test_doctor_patient_list_loads_and_reloads(self, page: Page):
        """Verify Doctor /patient listing loads cleanly and survives page reload."""
        login_as_doctor(page)
        click_sidebar_link(page, "Patient", href="/patient", portal_name="Doctor")
        expect(page.get_by_role("button", name=re.compile(r"Add New"))).to_be_visible(timeout=8000)
        page.reload(wait_until="networkidle")
        expect(page).to_have_url(re.compile(r".*/patient"))
        expect(page.get_by_role("button", name=re.compile(r"Add New"))).to_be_visible(timeout=8000)
