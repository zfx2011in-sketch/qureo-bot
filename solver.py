import asyncio
import re
from google import genai
from playwright.async_api import async_playwright

class QureoSolver:
    def __init__(self, gemini_api_key: str):
        self.ai = genai.Client(api_key=gemini_api_key)

    def ask_ai(self, prompt: str) -> str:
        response = self.ai.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text.strip()

    async def solve_mcq(self, question_text: str, options: list[str]) -> int:
        prompt = (
            "أجب برقم الخيار الصحيح فقط (1 أو 2 أو 3 أو 4) بدون أي نص إضافي:\n"
            f"السؤال:\n{question_text}\n"
            f"الخيارات:\n" + "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(options))
        )
        ans = self.ask_ai(prompt)
        match = re.search(r"[1-4]", ans)
        return int(match.group(0)) if match else 1

    async def solve_code(self, question_text: str, current_code: str) -> str:
        prompt = (
            "اكتب كود JavaScript النهائي الصحيح فقط لحل المهمة التالية بدون علامات markdown أو شرح:\n"
            f"المطلوب:\n{question_text}\n"
            f"الكود الموجود حالياً في المحرر:\n{current_code}"
        )
        code = self.ask_ai(prompt)
        code = re.sub(r"^```(?:javascript|js)?\s*|\s*```$", "", code, flags=re.IGNORECASE).strip()
        return code

    async def run(self, login_id: str, password: str, status_callback):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = await browser.new_context(viewport={"width": 1280, "height": 800})
            page = await context.new_page()

            try:
                await status_callback("⏳ جاري فتح بوابة SPRIX وتسجيل الدخول...")
                await page.goto("https://sprixportal.jp/", wait_until="networkidle")

                login_btns = page.locator("text=تسجيل الدخول")
                await login_btns.first.click()
                await page.wait_for_load_state("networkidle")

                learning_login_btn = page.locator("text=Go to Learning Login")
                if await learning_login_btn.count() > 0:
                    await learning_login_btn.first.click()
                    await page.wait_for_load_state("networkidle")

                inputs = page.locator("input")
                await inputs.nth(0).fill(login_id)
                await inputs.nth(1).fill(password)
                await page.locator("button:has-text('Login'), input[type='submit']").first.click()
                await page.wait_for_load_state("networkidle")

                if "Login" in await page.title() and await page.locator("input[type='password']").count() > 0:
                    await status_callback("❌ فشل تسجيل الدخول. تأكد من صحة Login ID وكلمة المرور.")
                    return

                await status_callback("✅ تم تسجيل الدخول بنجاح! جاري الدخول إلى QUREO...")

                start_btn = page.locator("text=ابدأ")
                if await start_btn.count() > 0:
                    await start_btn.first.click()
                    await page.wait_for_load_state("networkidle")

                for step_round in range(1, 350):
                    await asyncio.sleep(1.5)

                    body_text = await page.inner_text("body")
                    if "42 / 42" in body_text or "42/42" in body_text:
                        await status_callback("🎉 اكتمل جميع الفصول (42/42) بنجاح!")
                        break

                    next_btn = page.locator("button:has-text('التالي'), a:has-text('التالي')")
                    if await next_btn.count() > 0 and await next_btn.first.is_visible():
                        await next_btn.first.click()
                        continue

                    choice_btns = page.locator("button, label, li").filter(
                        has_text=re.compile(r"^(1|2|3|4|أريد أن ألعب|لنلعب|لا أريد)")
                    )
                    if await choice_btns.count() >= 2 and await page.locator("text=تشغيل الكود").count() == 0:
                        opts = [await choice_btns.nth(i).inner_text() for i in range(min(4, await choice_btns.count()))]
                        idx = await self.solve_mcq(body_text[:1000], opts)
                        target = choice_btns.nth(min(idx - 1, len(opts) - 1))
                        await target.click()
                        await asyncio.sleep(0.8)
                        continue

                    run_code_btn = page.locator("button:has-text('تشغيل الكود')")
                    if await run_code_btn.count() > 0 and await run_code_btn.first.is_visible():
                        editor_area = page.locator(".monaco-editor, .CodeMirror, textarea").first
                        current_code = await editor_area.inner_text() if await editor_area.count() > 0 else ""
                        solution_code = await self.solve_code(body_text[:1500], current_code)

                        await editor_area.click()
                        await page.keyboard.press("Control+A")
                        await page.keyboard.press("Backspace")
                        await page.keyboard.insert_text(solution_code)
                        await asyncio.sleep(0.5)
                        await run_code_btn.first.click()
                        await asyncio.sleep(2)

                        after_btn = page.locator("button:has-text('التالي'), button:has-text('العودة إلى النتائج'), a:has-text('الانتقال إلى الدرس التالي')")
                        if await after_btn.count() > 0:
                            await after_btn.first.click()
                        continue

                    for label in ["فهمت", "تم", "الانتقال إلى الدرس التالي", "العودة إلى أعلى المراجعة"]:
                        btn = page.locator(f"button:has-text('{label}'), a:has-text('{label}')")
                        if await btn.count() > 0 and await btn.first.is_visible():
                            await btn.first.click()
                            await asyncio.sleep(1)
                            break

                    if step_round % 25 == 0:
                        await status_callback(f"🔄 مستمر في الحل... (الخطوة {step_round})")

            except Exception as e:
                await status_callback(f"⚠️ حدث خطأ أثناء التنفيذ: {str(e)[:200]}")
            finally:
                await browser.close()
          
