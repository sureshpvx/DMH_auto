import re
from typing import Callable
import pytest
from playwright.sync_api import Page, expect
from helpers import click_sidebar_link, login_as_hospital


@pytest.fixture
def visited_patient_page(page: Page) -> Page:
    """Log into Hospital portal and open the /visited-patient queue without mutating rows."""
    login_as_hospital(page)
    click_sidebar_link(page, "Visited Patient", href="/visited-patient", portal_name="Hospital")
    expect(page).to_have_url(re.compile(r".*/visited-patient"), timeout=10000)
    page.wait_for_load_state("networkidle")
    return page


class TestTakePatientEdgeCases:

    def test_take_patient_page_loads(self, visited_patient_page: Page):
        """Verify Visited Patient page renders queue table and core action buttons."""
        page = visited_patient_page
        expect(page.locator("body")).to_be_visible()
        expect(page.get_by_role("button", name="View Screen")).to_be_visible()
        expect(page.get_by_role("button", name="Add New")).to_be_visible()
        expect(page.get_by_role("button", name="Search")).to_be_visible()
        expect(page.get_by_role("button", name="Clear")).to_be_visible()
        expect(page.get_by_role("button", name=re.compile(r"Take Patient")).first).to_be_visible()

    def test_take_patient_updates_visit_status_positive(self, visited_patient_page: Page):
        """Verify clicking Take Patient calls DoctorNextPatient (200 OK) and updates visit status."""
        page = visited_patient_page
        take_btn = page.get_by_role("button", name=re.compile(r"Take Patient")).first
        expect(take_btn).to_be_visible(timeout=10000)

        with page.expect_response(
            lambda res: "PatientVisit/DoctorNextPatient" in res.url
            and res.request.method == "PUT",
            timeout=10000,
        ) as resp_info:
            take_btn.click()

        assert resp_info.value.status == 200, (
            f"Expected 200 OK from DoctorNextPatient, got {resp_info.value.status}"
        )
        expect(page.get_by_text(re.compile(r"PatientVisit updated successfully", re.I)).first).to_be_visible(
            timeout=8000
        )
        expect(page.locator("table tbody tr").filter(has_text="InProgress").first).to_be_visible(
            timeout=8000
        )

    def test_take_patient_search_and_clear(
        self, visited_patient_page: Page, js_error_collector: Callable[..., list[str]]
    ):
        """Verify Search and Clear controls on Visited Patient run without JS errors."""
        page = visited_patient_page
        page.get_by_role("button", name="Search").click()
        page.wait_for_load_state("networkidle")
        page.get_by_role("button", name="Clear").click()
        page.wait_for_load_state("networkidle")

        expect(page.locator("table")).to_be_visible()
        assert not js_error_collector(), "Unexpected JS errors on Visited Patient Search/Clear."

    def test_take_patient_reload_does_not_crash(
        self, visited_patient_page: Page, js_error_collector: Callable[..., list[str]]
    ):
        """Edge case: Reloading the Visited Patient view keeps controls visible without errors."""
        page = visited_patient_page
        page.reload(wait_until="networkidle")
        expect(page.locator("body")).to_be_visible()
        expect(page.get_by_role("button", name="Search")).to_be_visible()
        assert not js_error_collector(), "Unexpected JS errors after reloading /visited-patient."
