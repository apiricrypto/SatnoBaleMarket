"""Run browser acceptance against an ephemeral database and loopback server only.
Requires playwright and Chromium. Never connects to production or starts Sync.
"""

import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def check_layout(base, password, changed_password, out, chromium):
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=chromium, headless=True, args=["--no-sandbox"]
        )
        seed = browser.new_context()
        assert seed.request.post(
            base + "/api/auth/login",
            data={"username": "demo-admin", "password": password},
        ).ok
        assert seed.request.post(
            base + "/api/sources",
            data={
                "peer_type": 2,
                "peer_id": 990003,
                "title": "منبع نمایشی غیرفعال",
                "enabled": False,
                "score": 50,
            },
        ).ok
        seed.close()
        for width in (375, 768, 1440):
            context = browser.new_context(viewport={"width": width, "height": 1000})
            page = context.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on(
                "console",
                lambda message: (
                    errors.append(message.text) if message.type == "error" else None
                ),
            )
            page.on("requestfailed", lambda request: errors.append(request.url))
            page.goto(base + "/login")
            page.wait_for_load_state("networkidle")
            for logo in page.locator('img[src="/assets/satno-logo.jpg"]').all():
                assert logo.evaluate(
                    "img => img.complete && img.naturalWidth === 1280 && img.naturalHeight === 1218"
                )
                size = logo.bounding_box()
                assert abs(size["width"] / size["height"] - 1280 / 1218) < 0.02
            assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
            page.screenshot(path=str(out / f"login-{width}.png"), full_page=True)
            page.get_by_label("نام کاربری", exact=True).fill("demo-admin")
            page.get_by_label("رمز عبور", exact=True).fill(password)
            page.get_by_role("button", name="ورود", exact=True).click()
            page.wait_for_url(base + "/")
            for path, name in [
                ("/", "dashboard"),
                ("/sources/manage", "sources"),
                ("/profile/password", "password"),
                ("/review", "review"),
                ("/status", "status"),
                ("/admin/users", "users"),
                ("/crm/outbox", "outbox"),
            ]:
                page.goto(base + path)
                page.wait_for_load_state("networkidle")
                assert page.locator('nav a[href="/profile/password"]').count() == 1
                assert page.locator('nav img[src="/assets/satno-logo.jpg"]').evaluate(
                    "img => img.complete && img.naturalWidth === 1280"
                )
                assert page.evaluate(
                    "document.documentElement.scrollWidth<=innerWidth"
                ), f"overflow {name} {width}"
                page.screenshot(path=str(out / f"{name}-{width}.png"), full_page=True)
            context.close()
        browser.close()
    assert not errors, errors
    print(
        json.dumps(
            {
                "viewports": [375, 768, 1440],
                "pages": 8,
                "page_errors": errors,
                "overflow": "none",
            },
            ensure_ascii=False,
        )
    )


def check_auth(base, password, changed_password, out, chromium):
    with sync_playwright() as p:
        b = p.chromium.launch(
            executable_path=chromium, headless=True, args=["--no-sandbox"]
        )
        page = b.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        def login(user, password, success=True):
            page.goto(base + "/login")
            page.get_by_label("نام کاربری", exact=True).fill(user)
            page.get_by_label("رمز عبور", exact=True).fill(password)
            page.get_by_role("button", name="ورود", exact=True).click()
            if success:
                page.wait_for_url(base + "/")
            else:
                expect(page.locator("#err")).to_contain_text("نادرست")

        login("demo-sales", "wrong", False)
        login("demo-sales", password)
        page.get_by_role("link", name="تغییر رمز", exact=True).click()
        page.get_by_label("رمز فعلی", exact=True).fill("wrong")
        page.get_by_label("رمز جدید (حداقل ۱۲ کاراکتر)", exact=True).fill(
            changed_password
        )
        page.get_by_label("تکرار رمز جدید", exact=True).fill("DifferentDemoOnly123!")
        page.get_by_role("button", name="تغییر رمز عبور", exact=True).click()
        expect(page.locator("#status")).to_contain_text("یکسان نیست")
        page.get_by_label("تکرار رمز جدید", exact=True).fill(changed_password)
        page.get_by_role("button", name="تغییر رمز عبور", exact=True).click()
        expect(page.locator("#status")).to_contain_text("صحیح نیست")
        page.get_by_label("رمز فعلی", exact=True).fill(password)
        page.get_by_role("button", name="تغییر رمز عبور", exact=True).click()
        page.wait_for_url(base + "/login")
        login("demo-sales", password, False)
        login("demo-sales", changed_password)
        page.get_by_role("button", name="خروج از حساب", exact=True).click()
        page.wait_for_url(base + "/login")
        login("demo-admin", password)
        # Admin reset uses the existing management endpoint, exercised through browser request context.
        users = page.request.get(base + "/api/admin/users").json()
        member = next(u for u in users if u["username"] == "demo-sales")
        assert page.request.patch(
            base + "/api/admin/users/" + str(member["id"]), data={"password": password}
        ).ok
        page.get_by_role("button", name="خروج از حساب", exact=True).click()
        page.wait_for_url(base + "/login")
        login("demo-sales", changed_password, False)
        login("demo-sales", password)
        assert page.locator('nav a[href="/admin/users"]').count() == 0
        page.get_by_role("button", name="خروج از حساب", exact=True).click()
        page.wait_for_url(base + "/login")
        login("demo-viewer", password)
        assert page.locator('nav a[href="/review"]').count() == 0
        assert page.request.get(base + "/admin/users").status == 403
        assert page.request.get(base + "/review").status == 403
        assert not errors, errors
        b.close()
    print(
        "PASS: login errors, mismatch, current password, password change, old/new login, logout, admin reset, viewer/sales RBAC; no page errors"
    )


def check_sources(base, password, changed_password, out, chromium):
    with sync_playwright() as p:
        b = p.chromium.launch(
            executable_path=chromium, headless=True, args=["--no-sandbox"]
        )
        page = b.new_page()
        assert page.request.post(
            base + "/api/auth/login",
            data={"username": "demo-admin", "password": password},
        ).ok
        for peer_id in (990001, 990002):
            assert page.request.post(
                base + "/api/sources",
                data={
                    "peer_type": 2,
                    "peer_id": peer_id,
                    "title": "منبع نمایشی " + str(peer_id),
                    "enabled": False,
                    "score": 50,
                },
            ).ok
        page.goto(base + "/sources/manage")
        page.wait_for_load_state("networkidle")
        expect(page.locator(".source")).to_have_count(2)
        page.get_by_label("انتخاب همه موارد نمایش‌داده‌شده", exact=True).check()
        expect(page.locator("#bulkDeleteBtn")).to_be_enabled()
        dismiss_dialog = lambda dialog: dialog.dismiss()
        page.on("dialog", dismiss_dialog)
        page.locator("#bulkDeleteBtn").click()
        expect(page.locator(".source")).to_have_count(2)
        # Replace the dismissal listener with acceptance only after cancellation was checked.
        page.remove_listener("dialog", dismiss_dialog)
        page.on(
            "dialog",
            lambda dialog: (
                dialog.accept("2") if dialog.type == "prompt" else dialog.accept()
            ),
        )
        page.locator("#bulkDeleteBtn").click()
        expect(page.locator(".source")).to_have_count(0)
        expect(page.locator("#sourceMsg")).to_contain_text("2 منبع حذف شد.")
        assert len(page.request.get(base + "/api/messages").json()) == 4
        b.close()
    print(
        "PASS: bulk selection, cancellation, confirmed deletion; historical messages preserved"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", default="/tmp/satno-ui-evidence")
    parser.add_argument("--port", type=int, default=8006)
    parser.add_argument("--chromium", default="/usr/bin/chromium")
    args = parser.parse_args()
    out = Path(args.artifacts).resolve()
    out.mkdir(parents=True, exist_ok=True)
    password = secrets.token_urlsafe(24)
    changed_password = secrets.token_urlsafe(24)
    base = f"http://127.0.0.1:{args.port}"
    with tempfile.TemporaryDirectory(prefix="satno-ui-") as temporary:
        os.environ["DATABASE_PATH"] = str(Path(temporary) / "demo.db")
        os.environ["SATNO_CRM_LEAD_URL"] = ""
        os.environ["SESSION_COOKIE_SECURE"] = "0"
        from auth import create_user
        from main import save_message, MessageIn

        for role in ("admin", "sales", "viewer"):
            create_user("demo-" + role, password, role, "کاربر آزمایشی " + role)
        for i, text in enumerate(
            [
                "فروش پنل خورشیدی ۵۵۰ وات در تهران",
                "خریدار اینورتر ۱۰ کیلووات در شیراز",
                "موجودی پنل JA Solar 580 وات",
                "استعلام پروژه نیروگاه خورشیدی ۲۰ کیلووات",
            ]
        ):
            save_message(
                MessageIn(
                    external_id="demo-" + str(i),
                    chat_name="منبع نمایشی جداگانه",
                    sender_name="تست محلی",
                    text=text,
                )
            )
        with (out / "server.log").open("w") as log:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(args.port),
                ],
                cwd=ROOT,
                stdout=log,
                stderr=log,
            )
            try:
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError("Test server exited; see server.log")
                    try:
                        with urlopen(base + "/health", timeout=1) as response:
                            assert json.load(response)["version"] == "0.5.2"
                        break
                    except OSError:
                        time.sleep(0.1)
                else:
                    raise RuntimeError("Test server readiness timed out")
                check_sources(base, password, changed_password, out, args.chromium)
                check_layout(base, password, changed_password, out, args.chromium)
                check_auth(base, password, changed_password, out, args.chromium)
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    main()
