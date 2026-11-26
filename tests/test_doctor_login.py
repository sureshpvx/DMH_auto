import re
import time
import pytest
from playwright.sync_api import Page, expect
from helpers import (
    DOCTOR_LOGIN_URL,
    DOCTOR_REGISTER_URL,
    click_sidebar_link,
    fill_valid_patient_form,
    login_as_doctor,
    logout_current_user,
)


@pytest.fixture
def add_patient_page(page: Page) -> Page:
    """Log into Doctor portal and navigate to /patient/add."""
    login_as_doctor(page)
    click_sidebar_link(page, "Patient", href="/patient", portal_name="Doctor")
    page.get_by_role("button", name=re.compile(r"Add New")).click()
    expect(page).to_have_url(re.compile(r".*/patient/add"), timeout=10000)
    return page


class TestDoctorAuthEdgeCases:

    @pytest.mark.parametrize(
        "email, password",
        [
            ("doc@gmail.com", "WrongPass!99"),
            ("unknown_doc@gmail.com", "Test!234"),
            ("bad-email-format", "Test!234"),
            ("   ", "Test!234"),
            ("doc@gmail.com", "   "),
            ("' OR '1'='1", "' OR '1'='1"),
        ],
    )
    def test_doctor_login_negative_edge_inputs(self, page: Page, email: str, password: str):
        """Negative Test: Invalid or malformed inputs keep Doctor user on /auth/doctor-login."""
        page.goto(DOCTOR_LOGIN_URL, wait_until="networkidle")
        page.get_by_role("textbox", name="Email address").fill(email)
        page.get_by_role("textbox", name="Password").fill(password)

        sign_in_btn = page.get_by_role("button", name="Sign In")
        if sign_in_btn.is_enabled():
            sign_in_btn.click()

        expect(page.get_by_role("heading", name="Select Organization")).not_to_be_visible()
        expect(page).to_have_url(DOCTOR_LOGIN_URL)

    def test_doctor_registration_mismatched_passwords_blocked(self, page: Page):
        """Negative Test: Registration with mismatched password and confirmation stays on register page."""
        page.goto(DOCTOR_REGISTER_URL, wait_until="networkidle")
        unique_id = int(time.time())

        page.get_by_role("textbox").nth(0).fill("Mismatch Doctor")
        page.get_by_role("spinbutton").fill(f"9{str(unique_id)[-9:]}")
        page.get_by_role("textbox").nth(2).fill(f"mismatch_{unique_id}@test.com")
        page.get_by_role("textbox").nth(3).fill("Test!234")
        page.get_by_role("textbox").nth(4).fill("DifferentPass!999")

        sign_up_btn = page.get_by_role("button", name="Sign Up")
        if sign_up_btn.is_enabled():
            sign_up_btn.click()

        expect(page).to_have_url(DOCTOR_REGISTER_URL)

    def test_doctor_change_hospital_modal_switches_organization(self, page: Page):
        """Positive Test: Doctor can open Change Hospital modal, switch organization, and continue."""
        login_as_doctor(page)
        change_btn = page.get_by_role("button", name=re.compile(r"Change Hospital", re.I))
        expect(change_btn).to_be_visible(timeout=8000)
        change_btn.click()

        dlg = page.locator(".p-dialog:visible, [role='dialog']:visible").first
        expect(dlg).to_be_visible(timeout=8000)
        expect(dlg.get_by_text("Change Hospital")).to_be_visible()

        toggles = dlg.locator(".p-toggleswitch")
        assert toggles.count() >= 1, "Expected at least one organization toggle in Change Hospital modal."
        if toggles.count() >= 2:
            toggles.nth(1).click(force=True)
        else:
            toggles.first.click(force=True)

        continue_btn = dlg.get_by_role("button", name="Continue")
        expect(continue_btn).to_be_enabled(timeout=5000)
        continue_btn.click()

        expect(dlg).not_to_be_visible(timeout=8000)
        expect(page.locator('a[href="/patient"]')).to_be_visible()

    def test_doctor_logout_and_back_navigation_blocked(self, page: Page):
        """Security Test: Logging out redirects to login and browser Back cannot re-enter session."""
        login_as_doctor(page)
        click_sidebar_link(page, "Patient", href="/patient", portal_name="Doctor")
        protected_url = page.url

        logout_current_user(page)
        page.go_back(wait_until="domcontentloaded")

        assert (
            page.url != protected_url
            or page.locator("form").get_by_role("button", name=re.compile(r"login|sign in", re.I)).count() > 0
        ), f"Post-logout browser Back stayed on protected URL '{page.url}'."


class TestAddPatientEdgeCases:

    def test_add_patient_positive(self, add_patient_page: Page, valid_image_path: str):
        """Positive Test: Doctor creates a new patient with valid details and PNG avatar."""
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

    @pytest.mark.parametrize("discount", ["-15", "150"])
    def test_add_patient_out_of_range_discount_blocked(
        self, add_patient_page: Page, discount: str
    ):
        """Edge case: Discount outside 0-100% should not allow saving."""
        page = add_patient_page
        fill_valid_patient_form(
            page,
            name_prefix="Discount Boundary Test",
            mobile_prefix="987458",
            email_prefix="disc",
            title="Dr.",
            blood_group="AB+",
        )
        page.locator('input[formcontrolname="discountPercent"]').fill(discount)

        save_btn = page.get_by_role("button", name=re.compile(r"Save"))
        if save_btn.is_enabled():
            save_btn.click()

        expect(page).to_have_url(re.compile(r".*/patient/add"))

    def test_add_patient_whitespace_only_rejected(self, add_patient_page: Page):
        """Edge case: Whitespace-only name and email do not create a patient."""
        page = add_patient_page
        page.locator('input[formcontrolname="name"]').fill("     ")
        page.locator('input[formcontrolname="email"]').fill("   @   ")

        save_btn = page.get_by_role("button", name=re.compile(r"Save"))
        if save_btn.is_enabled():
            save_btn.click()

        expect(page).to_have_url(re.compile(r".*/patient/add"))

    def test_add_patient_negative_unsupported_tif_upload(
        self, add_patient_page: Page, invalid_file_path: str
    ):
        """Negative Test: Unsupported .tif upload blocks patient creation."""
        page = add_patient_page
        page.get_by_role("button", name="Choose").click()
        page.get_by_label("Browse Files").set_input_files(invalid_file_path)

        save_btn = page.get_by_role("button", name=re.compile(r"Save"))
        if save_btn.is_enabled():
            save_btn.click()

        expect(page).to_have_url(re.compile(r".*/patient/add"))
