import asyncio

from langchain_core.tools import tool

from config import settings
from guardrails.tool_guards import check_rate_limit, GuardrailError
from guardrails.confirmation_gate import request_confirmation, ConfirmationDeniedError


@tool
def send_telegram_tool(message: str) -> str:
    """Send a message to the configured Telegram chat.
    Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in environment."""
    try:
        check_rate_limit("send_telegram_tool")
        request_confirmation("Send Telegram message", f"To chat {settings.telegram_chat_id}: {message[:80]}")
        return asyncio.run(_send_async(message))
    except GuardrailError as e:
        return f"[Blocked] {e}"
    except ConfirmationDeniedError as e:
        return f"[Cancelled] {e}"


async def _send_async(message: str) -> str:
    try:
        from telegram import Bot
        bot = Bot(token=settings.telegram_bot_token)
        async with bot:
            await bot.send_message(chat_id=settings.telegram_chat_id, text=message)
        return "Telegram message sent"
    except Exception as e:
        return f"Failed to send Telegram message: {e}"
