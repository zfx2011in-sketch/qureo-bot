import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from solver import QureoSolver

BOT_TOKEN = os.environ["BOT_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

active_users = set()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً بك في بوت حل منصة QUREO (JavaScript) 🚀\n\n"
        "أرسل بيانات حسابك في سطرين بهذا الشكل:\n"
        "Login_ID\n"
        "Password\n\n"
        "ملاحظة: سيتم حذف رسالتك فور استلام البيانات لحماية حسابك."
    )

async def handle_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    try:
        await update.message.delete()
    except Exception:
        pass

    if user_id in active_users:
        await context.bot.send_message(chat_id=user_id, text="⏳ لديك جلسة قيد التشغيل حالياً، انتظر حتى تنتهي.")
        return

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        await context.bot.send_message(
            chat_id=user_id,
            text="⚠️ صيغة غير صحيحة. أرسل Login ID في السطر الأول وكلمة المرور في السطر الثاني."
        )
        return

    login_id, password = lines[0], lines[1]
    active_users.add(user_id)

    status_msg = await context.bot.send_message(chat_id=user_id, text="🚀 تم استلام البيانات وحذف الرسالة. جاري بدء التشغيل...")

    async def update_status(msg: str):
        try:
            await status_msg.edit_text(msg)
        except Exception:
            await context.bot.send_message(chat_id=user_id, text=msg)

    async def background_task():
        try:
            solver = QureoSolver(GEMINI_API_KEY)
            await solver.run(login_id, password, update_status)
        finally:
            active_users.discard(user_id)

    asyncio.create_task(background_task())

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_credentials))
    app.run_polling()

if __name__ == "__main__":
    main()
  
