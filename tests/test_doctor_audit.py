from playwright.sync_api import Page
from helpers import audit_portal_modules, login_as_doctor

SCREENSHOT_DIR = "doctor_audit_screenshots"


def test_audit_all_doctor_dashboard_pages(page: Page):
    """
    Log into Doctor Dashboard, click through all discovered sidebar modules,
    and verify zero 404s, API errors, JS console errors, overflow, or broken buttons.
    """
    page.set_viewport_size({"width": 1440, "height": 900})
    login_as_doctor(page)

    all_bugs = audit_portal_modules(
        page,
        portal_name="Doctor Dashboard",
        screenshot_dir=SCREENSHOT_DIR,
        report_path="doctor_bug_report.txt",
    )

    assert not all_bugs, (
        f"\nFound {len(all_bugs)} QA issues (saved to doctor_bug_report.txt):\n"
        + "\n".join(all_bugs)
    )
