import re
import pytest
from playwright.sync_api import Page, expect
from helpers import (
    HOSPITAL_LOGIN_URL,
    audit_portal_modules,
    click_sidebar_link,
    fill_valid_patient_form,
    login_as_hospital,
    logout_current_user,
)


def _get_login_locators(page: Page):
    email_input = page.locator(
        'input[type="email"], input[name*="email" i], input[placeholder*="email" i]'
    ).first
    password_input = page.locator('input[type="password"]').first
    submit_btn = page.locator('button[type="submit"]').first
    return email_input, password_input, submit_btn


def _open_hospital_add_patient(page: Page) -> None:
    """Log into Hospital portal and open /patient/add."""
    login_as_hospital(page)
    click_sidebar_link(page, "Patient", href="/patient", portal_name="Hospital")
    add_btn = page.get_by_role("button", name=re.compile(r"Add New|add|new", re.I))
    expect(add_btn.first).to_be_visible(timeout=8000)
    add_btn.first.click()
    expect(page).to_have_url(re.compile(r".*/patient/add"), timeout=8000)


def test_hospital_login(page: Page):
    """Positive Test: Valid credentials log into the Hospital dashboard."""
    login_as_hospital(page)
    expect(page.get_by_role("link", name="Dashboard")).to_be_visible()


@pytest.mark.parametrize(
    "email, password",
    [
        pytest.param("", "", id="both_fields_empty"),
        pytest.param("hospitaladmin@example.com", "", id="empty_password"),
        pytest.param("", "ValidPassword123!", id="empty_email"),
        pytest.param("not-an-email-format", "ValidPassword123!", id="malformed_email"),
    ],
)
def test_hospital_login_button_disabled_when_incomplete(
    page: Page, email: str, password: str
):
    """Negative Test (UI Validation): Sign In button stays disabled until valid inputs are entered."""
    page.goto(HOSPITAL_LOGIN_URL)
    email_input, password_input, submit_btn = _get_login_locators(page)

    email_input.fill(email)
    password_input.fill(password)

    expect(submit_btn).to_be_disabled()
    expect(page).to_have_url(HOSPITAL_LOGIN_URL)


@pytest.mark.parametrize(
    "email, password",
    [
        pytest.param(
            "hospitaladmin@example.com",
            "WrongPassword123!",
            id="invalid_password",
        ),
        pytest.param(
            "nonexistent_user@example.com",
            "ValidPassword123!",
            id="unregistered_email",
        ),
    ],
)
def test_hospital_login_invalid_credentials(page: Page, email: str, password: str):
    """Negative Test (Auth Rejection): Button enables when filled, but invalid credentials fail login."""
    page.goto(HOSPITAL_LOGIN_URL)
    email_input, password_input, submit_btn = _get_login_locators(page)

    email_input.fill(email)
    password_input.fill(password)

    expect(submit_btn).to_be_enabled()
    submit_btn.click()

    expect(page).to_have_url(HOSPITAL_LOGIN_URL)
    expect(page.get_by_role("link", name="Dashboard")).not_to_be_visible()


@pytest.mark.parametrize(
    "label, expected_path",
    [
        ("Patient", "/patient"),
        ("Visited Patient", "/visited-patient"),
        ("Case", "/case"),
        ("Report", "/report"),
        ("Doctor", "/doctor"),
        ("Audit Logs", "/audit-logs"),
        ("Setting", "/setting"),
        ("Access Control", "/permission"),
        ("Log", "/logs"),
        ("Message Queue", "/queued-email"),
        ("Message Template", "/message-template"),
    ],
)
def test_hospital_sidebar_navigation_positive(
    page: Page, label: str, expected_path: str
):
    """Positive Test: Hospital modules (including Configuration and System submenus) load cleanly."""
    login_as_hospital(page)
    click_sidebar_link(page, label, href=expected_path, portal_name="Hospital")
    expect(page).to_have_url(re.compile(rf".*{re.escape(expected_path)}"), timeout=8000)


def test_hospital_all_modules_audit(page: Page):
    """Audit Hospital portal modules (excluding /tenant RBAC issue) for 404s, API, console, and layout bugs."""
    login_as_hospital(page)
    all_bugs = audit_portal_modules(
        page,
        portal_name="Hospital Dashboard",
        screenshot_dir="hospital_audit_screenshots",
        report_path="hospital_bug_report.txt",
        ignore_paths={"/tenant"},
    )
    assert not all_bugs, (
        f"\nFound {len(all_bugs)} Hospital QA issues:\n" + "\n".join(all_bugs)
    )


@pytest.mark.xfail(
    reason="Known Bug: Hospital sidebar exposes /tenant which returns HTTP 403 Forbidden from /api/Tenants/GetAll",
    strict=False,
)
def test_hospital_tenant_returns_403_known_bug(page: Page):
    """Reproduces the 403 Forbidden API failure when Hospital opens its visible Tenant sidebar link."""
    login_as_hospital(page)
    forbidden_calls: list[str] = []

    def on_response(res) -> None:
        if "/api/" in res.url and res.status == 403:
            forbidden_calls.append(f"[{res.status}] {res.url}")

    page.on("response", on_response)
    click_sidebar_link(page, "Tenant", href="/tenant", portal_name="Hospital")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(800)

    assert not forbidden_calls, (
        "Hospital Tenant page triggered 403 Forbidden API responses:\n"
        + "\n".join(forbidden_calls)
    )


def test_hospital_add_patient_positive(page: Page, valid_image_path: str):
    """Positive Test: Hospital user can create a new patient with valid details."""
    _open_hospital_add_patient(page)
    fill_valid_patient_form(
        page,
        name_prefix="Hospital Patient",
        mobile_prefix="987460",
        email_prefix="hosp_patient",
        title="Mrs.",
        blood_group="O+",
        remarks="Automated Hospital QA positive test",
        image_path=valid_image_path,
    )
    page.get_by_role("button", name=re.compile(r"Save")).click()
    expect(page).not_to_have_url(re.compile(r".*/patient/add"), timeout=10000)


def test_hospital_add_patient_negative_empty_form(page: Page):
    """Negative Test: Submitting an empty Hospital patient form stays on /patient/add."""
    _open_hospital_add_patient(page)
    save_btn = page.get_by_role("button", name=re.compile(r"Save"))
    if save_btn.is_enabled():
        save_btn.click()
    expect(page).to_have_url(re.compile(r".*/patient/add"))


def test_hospital_logout_and_back_navigation_blocked(page: Page):
    """Security Test: Logging out from Hospital portal blocks browser Back re-entry."""
    login_as_hospital(page)
    click_sidebar_link(page, "Visited Patient", href="/visited-patient", portal_name="Hospital")
    protected_url = page.url

    logout_current_user(page, profile_button_pattern=r"Hospital")
    page.go_back(wait_until="domcontentloaded")

    assert (
        page.url != protected_url
        or page.locator("form").get_by_role("button", name=re.compile(r"login|sign in", re.I)).count() > 0
    ), f"Post-logout browser Back stayed on protected URL '{page.url}'."
