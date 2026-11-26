import time
from playwright.sync_api import Page, expect
from helpers import DOCTOR_REGISTER_URL


def test_doctor_registration(page: Page):
    """Positive Test: Valid doctor registration redirects away from /auth/doctor-register."""
    page.goto(DOCTOR_REGISTER_URL, wait_until="networkidle")

    unique_id = int(time.time())
    unique_mobile = f"9{str(unique_id)[-9:]}"

    page.get_by_role("textbox").first.fill("Play Doctor")
    page.get_by_role("spinbutton").fill(unique_mobile)
    page.get_by_role("textbox").nth(2).fill(f"doctor{unique_id}@test.com")
    page.get_by_role("textbox").nth(3).fill("Test!234")
    page.get_by_role("textbox").nth(4).fill("Test!234")

    page.get_by_role("button", name="Sign Up").click()

    expect(page).not_to_have_url(DOCTOR_REGISTER_URL, timeout=10000)


def test_doctor_registration_empty_form_blocked(page: Page):
    """Negative Test: Submitting an empty doctor registration form keeps user on register page."""
    page.goto(DOCTOR_REGISTER_URL, wait_until="networkidle")
    sign_up_btn = page.get_by_role("button", name="Sign Up")
    if sign_up_btn.is_enabled():
        sign_up_btn.click()

    expect(page).to_have_url(DOCTOR_REGISTER_URL)


def test_doctor_registration_invalid_mobile_and_email_blocked(page: Page):
    """Negative Test: Short mobile number and invalid email block doctor registration."""
    page.goto(DOCTOR_REGISTER_URL, wait_until="networkidle")

    page.get_by_role("textbox").first.fill("Invalid Format Doctor")
    page.get_by_role("spinbutton").fill("123")
    page.get_by_role("textbox").nth(2).fill("not-an-email")
    page.get_by_role("textbox").nth(3).fill("Test!234")
    page.get_by_role("textbox").nth(4).fill("Test!234")

    sign_up_btn = page.get_by_role("button", name="Sign Up")
    if sign_up_btn.is_enabled():
        sign_up_btn.click()

    expect(page).to_have_url(DOCTOR_REGISTER_URL)
