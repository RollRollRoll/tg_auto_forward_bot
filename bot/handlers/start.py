from telegram import Update
from telegram.ext import ContextTypes

from bot.config import SUPER_ADMIN_ID
from bot.database.connection import get_db
from bot.database.crud import is_admin
from bot.handlers.filters import private_chat_only

HELP_TEXT = """<b>Video Forward Bot</b>

Send me a video link and I'll publish it to a Telegram channel.
Supports YouTube, X/Twitter, TikTok, Instagram, and 1000+ sites.

<b>How to use:</b>
1. Send a video link
2. I'll ask you for a caption
3. Choose resolution and target channel
4. I'll download and publish!

<b>Caption format (HTML):</b>
Supported tags: <code>&lt;b&gt;</code> <code>&lt;i&gt;</code> <code>&lt;u&gt;</code> <code>&lt;s&gt;</code> <code>&lt;a href="..."&gt;</code> <code>&lt;code&gt;</code> <code>&lt;pre&gt;</code>
Max length: 1024 characters (text only, tags don't count)

<b>Admin commands:</b>
/add_channel &lt;chat_id&gt; — Add channel
/remove_channel &lt;chat_id&gt; — Remove channel
/list_channels — List channels
/set &lt;key&gt; &lt;value&gt; — Update setting
/settings — View all settings
/tasks — View active downloads &amp; recent tasks

<b>Super admin commands:</b>
/add_admin &lt;user_id&gt; — Add admin
/remove_admin &lt;user_id&gt; — Remove admin
/list_admins — List admins"""


@private_chat_only
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db = await get_db()
    if user_id == SUPER_ADMIN_ID or await is_admin(db, user_id=user_id):
        from bot.handlers.menu import MENU_GREETING, build_main_keyboard
        await update.message.reply_text(
            MENU_GREETING,
            reply_markup=build_main_keyboard(user_id),
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(HELP_TEXT, parse_mode="HTML")


@private_chat_only
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="HTML")
