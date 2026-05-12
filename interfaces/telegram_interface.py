"""Telegram interface for the agent.

To use:
1. Create a Telegram bot via @BotFather on Telegram
2. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env
3. Call telegram_producer() and telegram_consumer() from main()

The producer listens for incoming Telegram messages.
The consumer sends responses back to Telegram.
"""

from event_bus import EventBus
from events import Event, ResponseEvent
from config import settings


async def telegram_producer(event_bus: EventBus) -> None:
    """Listen for incoming Telegram messages and put on event bus.

    TODO: Implement using python-telegram-bot with polling or webhook.
    """
    # from telegram import Bot
    # from telegram.ext import Application, CommandHandler, MessageHandler, filters
    # app = Application.builder().token(settings.telegram_bot_token).build()
    # ...
    pass


async def telegram_consumer(event_bus: EventBus) -> None:
    """Send responses to Telegram users.

    TODO: Implement using python-telegram-bot.
    """
    # from telegram import Bot
    # bot = Bot(token=settings.telegram_bot_token)
    # while True:
    #     event = await event_bus.get_output()
    #     if event.dest.startswith("telegram:"):
    #         user_id = event.dest.split(":")[1]
    #         await bot.send_message(chat_id=user_id, text=event.content)
    pass
