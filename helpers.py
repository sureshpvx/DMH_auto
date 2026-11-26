import os
import re
import time
import uuid
from urllib.parse import urlsplit
from dotenv import load_dotenv
from playwright.sync_api import Page, expect

load_dotenv()

_RAW_BASE_URL = os.getenv("DMH_BASE_URL", "https://dmh.ssserver.in").rstrip("/")
_PARSED_BASE = urlsplit(_RAW_BASE_URL)
BASE_ORIGIN = (
    f"{_PARSED_BASE.scheme}://{_PARSED_BASE.netloc}"
    if _PARSED_BASE.scheme and _PARSED_BASE.netloc
    else "https://dmh.ssserver.in"
)

PATIENT_LOGIN_URL = os.getenv(
    "DMH_PATIENT_LOGIN_URL", f"{BASE_ORIGIN}/auth/patient-login"
)
DOCTOR_LOGIN_URL = os.getenv(
    "DMH_DOCTOR_LOGIN_URL", f"{BASE_ORIGIN}/auth/doctor-login"
)
DOCTOR_REGISTER_URL = f"{BASE_ORIGIN}/auth/doctor-register"
FORGOT_PASSWORD_URL = f"{BASE_ORIGIN}/auth/forget-password"
HOSPITAL_LOGIN_URL = os.getenv(
    "DMH_HOSPITAL_LOGIN_URL", f"{BASE_ORIGIN}/auth/hospital-login"
)
LAB_LOGIN_URL = os.getenv(
    "DMH_LAB_LOGIN_URL", f"{BASE_ORIGIN}/auth/lab-login"
)

SUBMENU_PARENTS = {
    "/setting": "Configuration",
    "/permission": "Configuration",
    "/logs": "System",
    "/queued-email": "System",
    "/message-template": "System",
}


def _require_env(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


def _submit_login_form(page: Page, url: str, email: str, password: str) -> None:
    """Navigate to a DMH login page and submit credentials."""
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")

    email_box = page.get_by_role("textbox", name="Email address")
    password_box = page.get_by_role("textbox", name="Password")
    remember_chk = page.get_by_role("checkbox", name="Remember me")

    expect(email_box).to_be_visible(timeout=10000)
    email_box.fill(email)
    password_box.fill(password)

    if remember_chk.count() > 0 and remember_chk.first.is_visible():
        remember_chk.first.check()

    # Patient login renders portal-switcher "Sign In" buttons outside the main <form>.
    form_submit = page.locator("form").get_by_role("button", name="Sign In")
    sign_in_btn = (
        form_submit.first
        if form_submit.count() > 0
        else page.get_by_role("button", name="Sign In").first
    )
    expect(sign_in_btn).to_be_enabled(timeout=10000)
    sign_in_btn.click()


def login_as_patient(
    page: Page,
    email: str | None = None,
    password: str | None = None,
) -> None:
    """Log into the DMH Patient portal and wait until the Patient dashboard loads."""
    target_email = email if email is not None else _require_env("DMH_USERNAME")
    target_password = (
        password if password is not None else _require_env("DMH_PASSWORD")
    )

    _submit_login_form(page, PATIENT_LOGIN_URL, target_email, target_password)
    expect(page).not_to_have_url(re.compile(r".*/auth/.*"), timeout=15000)
    page.wait_for_load_state("networkidle")


def login_as_doctor(
    page: Page,
    email: str | None = None,
    password: str | None = None,
) -> None:
    """
    Log into the DMH Doctor portal using .env credentials by default,
    select the first organization toggle, and wait until the Doctor Dashboard loads.
    """
    target_email = email if email is not None else _require_env("DMH_DOCTOR_USERNAME")
    target_password = (
        password if password is not None else _require_env("DMH_DOCTOR_PASSWORD")
    )

    _submit_login_form(page, DOCTOR_LOGIN_URL, target_email, target_password)

    expect(page.get_by_role("heading", name="Select Organization")).to_be_visible(
        timeout=10000
    )

    continue_btn = page.get_by_role("button", name="Continue")
    expect(continue_btn).to_be_disabled()

    page.locator(".p-toggleswitch").first.click(force=True)

    expect(continue_btn).to_be_enabled(timeout=5000)
    continue_btn.click()

    expect(page).not_to_have_url(DOCTOR_LOGIN_URL, timeout=10000)


def login_as_hospital(
    page: Page,
    email: str | None = None,
    password: str | None = None,
) -> None:
    """
    Log into the DMH Hospital portal using .env credentials by default,
    and wait until the Hospital Dashboard loads.
    """
    target_email = (
        email if email is not None else _require_env("DMH_HOSPITAL_USERNAME")
    )
    target_password = (
        password if password is not None else _require_env("DMH_HOSPITAL_PASSWORD")
    )

    _submit_login_form(page, HOSPITAL_LOGIN_URL, target_email, target_password)
    expect(page).not_to_have_url(HOSPITAL_LOGIN_URL, timeout=10000)


def login_as_lab(
    page: Page,
    email: str | None = None,
    password: str | None = None,
) -> None:
    """
    Log into the DMH Lab portal using .env credentials by default,
    and wait until the Lab Dashboard loads.
    """
    target_email = (
        email
        if email is not None
        else os.getenv("DMH_LAB_USERNAME", "lab@gmail.com")
    )
    target_password = (
        password
        if password is not None
        else os.getenv("DMH_LAB_PASSWORD", "Test!234")
    )

    try:
        _submit_login_form(page, LAB_LOGIN_URL, target_email, target_password)
        expect(page).not_to_have_url(LAB_LOGIN_URL, timeout=10000)
    except Exception as exc:
        raise AssertionError(
            f"[Lab Login Failed] URL='{page.url}' | User='{target_email}' | Cause: {exc}"
        ) from exc


def expand_sidebar_group(page: Page, group_label: str) -> None:
    """Expand a collapsed PrimeNG sidebar group (e.g. Configuration, System) if needed."""
    parent_li = page.locator(
        f".layout-sidebar li[app-menuitem]:has(> a .layout-menuitem-text:text-is('{group_label}'))"
    ).first
    if parent_li.count() == 0:
        return

    li_classes = parent_li.get_attribute("class") or ""
    if "active-menuitem" in li_classes:
        return

    toggle = parent_li.locator("> a").first
    if toggle.is_visible():
        toggle.scroll_into_view_if_needed()
        toggle.click()
        page.wait_for_timeout(300)


def click_sidebar_link(
    page: Page,
    label: str,
    *,
    href: str | None = None,
    exact: bool = False,
    timeout: int = 8000,
    portal_name: str = "Portal",
) -> None:
    """Expand any parent sidebar group if required, then scroll to and click a nav link."""
    if href and href in SUBMENU_PARENTS:
        expand_sidebar_group(page, SUBMENU_PARENTS[href])

    if href:
        link = page.locator(f"a[href='{href}']")
    elif exact:
        link = page.get_by_role("link", name=re.compile(rf"(?:^|\s){re.escape(label)}$"))
    else:
        link = page.get_by_role("link", name=re.compile(re.escape(label)))

    try:
        expect(link.first).to_be_visible(timeout=timeout)
        link.first.scroll_into_view_if_needed()
        link.first.click()
        expect(page.locator("body")).to_be_visible()
    except Exception as exc:
        raise AssertionError(
            f"[{portal_name} Nav Failed @ '{label}'] Current URL='{page.url}' | "
            f"Matching links={link.count()} | Cause: {exc}"
        ) from exc


def logout_current_user(
    page: Page,
    *,
    profile_button_pattern: str | None = None,
    timeout: int = 8000,
) -> None:
    """Open the topbar profile menu, click Logout, and wait for redirect to login."""
    try:
        if profile_button_pattern:
            profile_btn = page.get_by_role(
                "button", name=re.compile(profile_button_pattern, re.I)
            ).first
        else:
            profile_btn = page.locator(".layout-topbar button").last

        expect(profile_btn).to_be_visible(timeout=timeout)
        profile_btn.click()

        logout_item = page.get_by_text("Logout", exact=True).first
        expect(logout_item).to_be_visible(timeout=timeout)
        logout_item.click()
        expect(page).to_have_url(re.compile(r".*/auth/.*login"), timeout=10000)
    except Exception as exc:
        raise AssertionError(
            f"[Logout Failed] Current URL='{page.url}' | Cause: {exc}"
        ) from exc


def fill_valid_patient_form(
    page: Page,
    *,
    name_prefix: str = "QA Patient",
    mobile_prefix: str = "987458",
    email_prefix: str = "patient",
    title: str = "Dr.",
    blood_group: str = "AB+",
    remarks: str = "Automated QA test patient",
    image_path: str | None = None,
) -> dict[str, str]:
    """Populate all fields on /patient/add with unique valid values and return created metadata."""
    unique_suffix = str(int(time.time()))[-4:]
    short_uuid = uuid.uuid4().hex[:6]
    full_name = f"{name_prefix} {short_uuid}"
    mobile = f"{mobile_prefix}{unique_suffix}"
    email = f"{email_prefix}_{unique_suffix}_{short_uuid}@gmail.com"

    page.locator('input[formcontrolname="mobileNumber"]').fill(mobile)

    page.get_by_role("button", name="dropdown trigger").first.click()
    page.get_by_role("option", name=title, exact=True).click()

    page.locator('input[formcontrolname="name"]').fill(full_name)

    dob_input = page.get_by_role("combobox", name="dd/mm/yyyy").first
    dob_input.click()
    dob_input.type("10051995")
    dob_input.press("Tab")

    page.locator('input[formcontrolname="email"]').fill(email)

    age_input = page.locator('input[formcontrolname="age"]')
    if age_input.count() > 0 and age_input.first.is_editable():
        age_input.first.fill("31")

    page.get_by_role("combobox", name="Male").click()
    page.get_by_role("option", name="Male", exact=True).click()

    page.locator('input[formcontrolname="discountPercent"]').fill("10")
    page.locator('input[formcontrolname="address"]').fill("12 Ring Road, Surat, Gujarat")

    test_id_num = f"{int(time.time()) % 90000000 + 10000000}{unique_suffix}"
    page.locator('input[formcontrolname="aadhar"]').fill(test_id_num)

    page.get_by_role("combobox", name="A+").click()
    page.get_by_role("option", name=blood_group, exact=True).click()

    anniv_input = page.get_by_role("combobox", name="dd/mm/yyyy").nth(1)
    anniv_input.click()
    anniv_input.type("18112020")
    anniv_input.press("Tab")

    page.locator('input[formcontrolname="remarks"]').fill(remarks)

    if image_path:
        page.get_by_role("button", name="Choose").click()
        page.get_by_label("Browse Files").set_input_files(image_path)
        expect(page.get_by_role("img", name="Preview")).to_be_visible()

    return {"name": full_name, "mobile": mobile, "email": email}


def audit_portal_modules(
    page: Page,
    *,
    portal_name: str,
    screenshot_dir: str | None = None,
    report_path: str | None = None,
    ignore_paths: set[str] | None = None,
) -> list[str]:
    """
    Discover sidebar links, visit each module, and collect 404 routes, API errors,
    JS console errors, horizontal layout overflow culprits, and zero-dimension buttons.
    """
    if screenshot_dir:
        os.makedirs(screenshot_dir, exist_ok=True)

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1200)

    console_errors: list[str] = []
    server_errors: list[str] = []

    def handle_api_response(res) -> None:
        if res.status >= 400 and "/api/" in res.url:
            try:
                body = res.text()[:200]
            except Exception:
                body = "<no response body>"

            if res.status == 400 and "No data found" in body:
                return
            server_errors.append(f"[{res.status}] {res.url} -> {body}")

    page.on(
        "console",
        lambda msg: console_errors.append(f"[{page.url}] {msg.text}")
        if msg.type == "error" and "responded with a status of 400" not in msg.text
        else None,
    )
    page.on("response", handle_api_response)

    discovered = page.evaluate("""() => {
        const items = [];
        const seen = new Set();
        document.querySelectorAll('.layout-sidebar a[href], nav a[href], aside a[href]').forEach(el => {
            const href = el.getAttribute('href') || '';
            const label = el.innerText.trim().replace(/\\s+/g, ' ');
            if (!href || href === '#' || href === '/') return;
            if (/logout|signout|sign out/i.test(label + href)) return;
            if (!seen.has(href)) {
                seen.add(href);
                items.push({label: label || href, href});
            }
        });
        return items;
    }""")

    skipped = ignore_paths or set()
    menu_items = [item for item in discovered if item["href"] not in skipped]

    print(f"\n[{portal_name}] Active URL: {page.url} | Auditing {len(menu_items)} modules")

    layout_issues: list[str] = []
    broken_buttons: list[str] = []
    not_found_pages: list[str] = []

    targets = [{"label": f"{portal_name} Dashboard", "href": page.url}] + menu_items

    for idx, item in enumerate(targets, start=1):
        if idx > 1:
            click_sidebar_link(
                page,
                item["label"],
                href=item["href"],
                portal_name=portal_name,
            )
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(800)

        current_url = page.url
        if "notfound" in current_url.lower() or "404" in current_url.lower():
            not_found_pages.append(f"Menu '{item['label']}' routed to 404 ({current_url})")
            continue

        overflow_culprits = page.evaluate("""() => {
            const docWidth = document.documentElement.clientWidth;
            if (document.documentElement.scrollWidth <= docWidth + 1) {
                return [];
            }

            function isInsideScrollContainer(el) {
                let parent = el.parentElement;
                while (parent && parent !== document.body) {
                    const style = window.getComputedStyle(parent);
                    if (['auto', 'scroll', 'hidden', 'clip'].includes(style.overflowX)) {
                        return true;
                    }
                    parent = parent.parentElement;
                }
                return false;
            }

            const offenders = [];
            document.querySelectorAll('*').forEach(el => {
                const rect = el.getBoundingClientRect();
                if (rect.width > 0 && rect.right > docWidth + 1 && !isInsideScrollContainer(el)) {
                    offenders.push({
                        tag: el.tagName.toLowerCase(),
                        id: el.id ? '#' + el.id : '',
                        classes: typeof el.className === 'string' && el.className.trim()
                            ? '.' + el.className.trim().split(/\\s+/).join('.')
                            : '',
                        width: Math.round(rect.width),
                        rightEdge: Math.round(rect.right),
                        viewportWidth: docWidth
                    });
                }
            });
            offenders.sort((a, b) => b.rightEdge - a.rightEdge);
            return offenders.slice(0, 5);
        }""")

        if overflow_culprits:
            details = "\n".join(
                f"    -> <{c['tag']}{c['id']}{c['classes']}> "
                f"(width: {c['width']}px, right edge: {c['rightEdge']}px vs viewport: {c['viewportWidth']}px)"
                for c in overflow_culprits
            )
            layout_issues.append(f"Horizontal overflow on '{item['label']}' ({current_url}):\n{details}")

        zero_dim_buttons = page.evaluate("""() => {
            const broken = [];
            document.querySelectorAll('button').forEach(btn => {
                const style = window.getComputedStyle(btn);
                if (style.display === 'none' || style.visibility === 'hidden') return;
                if (!btn.offsetParent && style.position !== 'fixed') return;
                const rect = btn.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) {
                    broken.push((btn.innerText || '').trim() || '<icon-button>');
                }
            });
            return broken;
        }""")
        for btn_text in zero_dim_buttons:
            broken_buttons.append(f"Zero-dimension button '{btn_text}' on '{item['label']}'")

        if screenshot_dir:
            safe_name = "".join(c if c.isalnum() else "_" for c in item["label"]).strip("_").lower()
            page.screenshot(
                path=os.path.join(screenshot_dir, f"{idx:02d}_{safe_name}.png"),
                full_page=True,
            )

    all_bugs = (
        [f"[404 ROUTE] {e}" for e in not_found_pages]
        + [f"[API ERROR] {e}" for e in server_errors]
        + [f"[LAYOUT] {e}" for e in layout_issues]
        + [f"[BUTTON] {e}" for e in broken_buttons]
        + [f"[JS CONSOLE] {e}" for e in console_errors]
    )

    if report_path:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(all_bugs) if all_bugs else f"No {portal_name} bugs detected.")

    return all_bugs
