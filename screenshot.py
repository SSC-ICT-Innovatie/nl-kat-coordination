import os
import time
from pathlib import Path

import django
from PIL import Image
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "openkat.settings")
django.setup()

from openkat.models import Organization, User

# Configuration
BASE_URL = "http://localhost:8000"
LOGIN_EMAIL = "test@test.com"
LOGIN_PASSWORD = "test"
TEST_ORG = "docs"
DOCS_BASE = Path(__file__).parent / "docs" / "source"

# Screenshot definitions: (url_path, filename, docs_subdir, wait_selector)
SCREENSHOTS = [
    # Getting started - onboarding flow (some may fail if not in onboarding state)
    (
        "/en/onboarding/step/introduction/registration/",
        "1-onboarding-welcome.jpg",
        "user-manual/getting-started/img",
        "main",
    ),
    (
        "/en/onboarding/organization/setup/",
        "2-onboarding-organization-setup.jpg",
        "user-manual/getting-started/img",
        "form",
    ),
    (
        "/en/onboarding/indemnification/setup/",
        "4-onboarding-indemnification-setup.jpg",
        "user-manual/getting-started/img",
        "form",
    ),
    # Navigation - Objects
    (f"/en/objects/hostname/?organization={TEST_ORG}", "objects.jpg", "user-manual/navigation/img", "main"),
    (f"/en/objects/hostname/?organization={TEST_ORG}", "add-object-01.jpg", "user-manual/getting-started/img", "main"),
    # object-details.jpg requires an actual object to exist - will need manual capture or object creation
    # Navigation - Findings
    (f"/en/objects/finding/?organization={TEST_ORG}", "findings.jpg", "user-manual/navigation/img", "main"),
    # Navigation - Tasks
    (f"/en/tasks/?organization={TEST_ORG}", "tasks.jpg", "user-manual/getting-started/img", "main"),
    (f"/en/tasks/?organization={TEST_ORG}", "tasks.jpg", "user-manual/navigation/img", "main"),
    # tasks-normalizer-yielded-objects.jpg requires specific task state
    # Navigation - Members
    (f"/en/{TEST_ORG}/members/", "members.jpg", "user-manual/navigation/img", "main"),
    # Navigation - Reports
    (f"/en/reports/?organization={TEST_ORG}", "report.jpg", "user-manual/navigation/img", "main"),
    (f"/en/reports/?organization={TEST_ORG}", "generate-report-01.jpg", "user-manual/getting-started/img", "main"),
    # generate-report-02.jpg and generate-report-05.jpg require interaction/generation
    # Navigation - Settings
    ("/en/account/settings/", "settings.jpg", "user-manual/navigation/img", "main"),
    # Navigation - User Settings
    ("/en/account/user-settings/", "user-settings.jpg", "user-manual/navigation/img", "main"),
    (f"/en/{TEST_ORG}/account/", "user-settings-profile.jpg", "user-manual/navigation/img", "main"),
    (
        f"/en/organizations/?organization={TEST_ORG}",
        "user-settings-my-organizations.jpg",
        "user-manual/navigation/img",
        "main",
    ),
]


def setup_driver():
    """Initialize and configure the Chrome WebDriver"""
    options = webdriver.ChromeOptions()
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--headless")  # Remove this line if you want to see the browser
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    return driver


def login(driver):
    """Log in to OpenKAT"""
    print(f"Logging in to {BASE_URL}...")
    driver.get(f"{BASE_URL}/en/login/")

    try:
        # Wait for login form to load
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "auth-username")))

        # Find and fill in the login form
        username_field = driver.find_element(By.NAME, "auth-username")
        password_field = driver.find_element(By.NAME, "auth-password")

        username_field.clear()
        username_field.send_keys(LOGIN_EMAIL)

        password_field.clear()
        password_field.send_keys(LOGIN_PASSWORD)

        # Submit by pressing Enter in the password field (most reliable method)
        password_field.send_keys(Keys.RETURN)

        # Wait for redirect after login (wait for URL to change)
        # The login might redirect to onboarding or to a dashboard
        WebDriverWait(driver, 10).until(lambda d: "/login" not in d.current_url)

        print(f"✓ Successfully logged in as {LOGIN_EMAIL}")
        print(f"  Current URL: {driver.current_url}")

        # Give the page a moment to fully load
        time.sleep(1)
        return True

    except (TimeoutException, NoSuchElementException) as e:
        print(f"✗ Login failed: {e}")
        print(f"  Current URL: {driver.current_url}")
        # Save a screenshot for debugging
        try:
            driver.save_screenshot("login_error.png")
            print("  Saved error screenshot to: login_error.png")
        except Exception as screenshot_error:
            print(f"  Could not save error screenshot: {screenshot_error}")
        return False


def take_screenshot(driver, url_path, filename, docs_subdir, wait_selector="main"):
    """Navigate to a URL and take a screenshot"""
    full_url = f"{BASE_URL}{url_path}"
    output_dir = DOCS_BASE / docs_subdir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    print(f"Capturing: {filename}")
    print(f"  URL: {full_url}")

    try:
        driver.get(full_url)

        # Wait for the page to load
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector)))

        # Additional wait for dynamic content
        time.sleep(1)

        # Take screenshot as PNG first (Selenium default)
        temp_png = output_dir / f"temp_{filename}.png"
        driver.save_screenshot(str(temp_png))

        # Convert PNG to JPEG for smaller file size
        with Image.open(temp_png) as img:
            # Convert RGBA to RGB if necessary (JPEG doesn't support transparency)
            if img.mode in ("RGBA", "LA", "P"):
                rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                img = rgb_img

            # Save as JPEG with quality 85 (good balance of quality and size)
            img.save(output_path, "JPEG", quality=85, optimize=True)

        # Remove temporary PNG file
        temp_png.unlink()

        # Show file size
        size_kb = output_path.stat().st_size / 1024
        print(f"  ✓ Saved to: {output_path.relative_to(Path.cwd())} ({size_kb:.1f} KB)")
        return True

    except Exception as e:
        print(f"  ✗ Failed: {e}")
        # Clean up temp file if it exists
        temp_png_path = output_dir / f"temp_{filename}.png"
        if temp_png_path.exists():
            temp_png_path.unlink()
        return False


def find_missing_screenshots():
    """Find all screenshots referenced in docs but not yet captured"""
    # All screenshots referenced in the documentation (now as JPEG)
    all_needed_screenshots = {
        # Getting started - onboarding
        "user-manual/getting-started/img": [
            "1-onboarding-welcome.jpg",
            "2-onboarding-organization-setup.jpg",
            "3-onboarding-organization-setup-meow.jpg",
            "4-onboarding-indemnification-setup.jpg",
            "5-onboarding-user-clearance-level.jpg",
            "6-onboarding-setup-scan-url.jpg",
            "7-onboarding-set-clearance-level.jpg",
            "8-onboarding-clearance-level-introduction.jpg",
            "8-onboarding-select-plugins.jpg",
            "9-onboarding-generate-report.jpg",
            "10-onboarding-boefjes-loading.jpg",
            "11-onboarding-dns-report.jpg",
            "00-onboarding-qr-code.jpg",
            "00-onboarding-qr-success.jpg",
            "add-object-01.jpg",
            "add-object-02.jpg",
            "add-object-03.jpg",
            "add-object-04.jpg",
            "add-object-05.jpg",
            "add-object-06.jpg",
            "add-object-07.jpg",
            "tasks.jpg",
            "generate-report-01.jpg",
            "generate-report-02.jpg",
            "generate-report-05.jpg",
            "openkat-simple-process.jpg",
        ],
        "user-manual/navigation/img": [
            "findings.jpg",
            "members.jpg",
            "objects.jpg",
            "object-details.jpg",
            "report.jpg",
            "settings.jpg",
            "tasks.jpg",
            "tasks-normalizer-yielded-objects.jpg",
            "user-settings.jpg",
            "user-settings-my-organizations.jpg",
            "user-settings-profile.jpg",
        ],
        "user-manual/basic-concepts/img": ["objects-clearance-types.jpg"],
        "installation-and-deployment/img": ["healthpage.jpg", "dockerps.jpg"],
    }

    missing = {}
    captured = {}

    for subdir, filenames in all_needed_screenshots.items():
        missing[subdir] = []
        captured[subdir] = []
        img_dir = DOCS_BASE / subdir
        for filename in filenames:
            img_path = img_dir / filename
            if img_path.exists():
                captured[subdir].append(filename)
            else:
                missing[subdir].append(filename)

    return missing, captured


def main():
    print("OpenKAT Documentation Screenshot Collection\n")

    driver = setup_driver()
    new_user = User.objects.create_superuser(email=LOGIN_EMAIL, password=LOGIN_PASSWORD, full_name=LOGIN_EMAIL)
    org, _ = Organization.objects.get_or_create(code=TEST_ORG, name=TEST_ORG)

    try:
        # Login first
        if not login(driver):
            print("\n✗ Login failed, cannot continue")
            return

        print("\nCapturing Screenshots\n")

        # Take all screenshots
        successful = 0
        failed = 0

        for screenshot_info in SCREENSHOTS:
            url_path, filename, docs_subdir, wait_selector = screenshot_info
            if take_screenshot(driver, url_path, filename, docs_subdir, wait_selector):
                successful += 1
            else:
                failed += 1
            print()

        print(f"Summary: {successful} successful, {failed} failed")

    finally:
        driver.quit()
        new_user.delete()
        org.delete()

    # Show missing screenshots
    print("Documentation Screenshot Status")

    missing, captured = find_missing_screenshots()

    total_captured = sum(len(files) for files in captured.values())
    total_missing = sum(len(files) for files in missing.values())
    total_needed = total_captured + total_missing

    print(
        f"Progress: {total_captured}/{total_needed} screenshots captured "
        f"({100 * total_captured // total_needed if total_needed > 0 else 0}%)\n"
    )

    if total_missing > 0:
        print("Still missing:")
        for subdir, filenames in missing.items():
            if filenames:
                print(f"\n  {subdir}:")
                for filename in sorted(filenames):
                    print(f"    - {filename}")
        print()
        print("Note: Some screenshots require manual capture or specific application state:")
        print("  - Onboarding screenshots (2-11): Require fresh user onboarding flow")
        print("  - QR code screenshots: Require 2FA setup flow")
        print("  - Object detail screenshots: Require objects to exist in the system")
        print("  - Task detail screenshots: Require tasks to be running")
        print("  - Report generation screenshots: Require interaction and waiting")
        print("  - Diagram screenshots: Need to be created/designed")
        print("  - dockerps.jpg: Terminal screenshot of docker ps output\n")
    else:
        print("✓ All documentation screenshots have been captured!\n")


if __name__ == "__main__":
    main()
