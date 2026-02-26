"""
Telegram bot for sending trading signals.
Supports both push notifications (from scanner) and interactive commands.
"""
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


async def send_message(text, parse_mode=None):
    """Send a message to the configured Telegram chat."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[TELEGRAM] Bot token or chat ID not configured. Printing to console:")
        print(text)
        return False

    try:
        from telegram import Bot
        bot = Bot(token=TELEGRAM_BOT_TOKEN)

        # Telegram has a 4096 char limit per message
        if len(text) > 4000:
            chunks = _split_message(text, 4000)
            for chunk in chunks:
                await bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=chunk,
                    parse_mode=parse_mode,
                )
        else:
            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=text,
                parse_mode=parse_mode,
            )
        print("[TELEGRAM] Message sent successfully")
        return True
    except Exception as e:
        print(f"[TELEGRAM] Failed to send: {e}")
        print("[TELEGRAM] Message content:")
        print(text)
        return False


def send_message_sync(text, parse_mode=None):
    """Synchronous wrapper for send_message."""
    return asyncio.run(send_message(text, parse_mode))


def send_signal_alert(signal):
    """Send a formatted signal alert."""
    from bot.formatter import format_signal
    text = format_signal(signal)
    return send_message_sync(text)


def send_daily_digest(digest_text):
    """Send the daily market digest."""
    return send_message_sync(digest_text)


def send_multiple_signals(signals):
    """Send multiple signal alerts."""
    from bot.formatter import format_multiple_signals
    text = format_multiple_signals(signals)
    return send_message_sync(text)


def _split_message(text, max_length):
    """Split a long message into chunks."""
    lines = text.split("\n")
    chunks = []
    current = []
    current_len = 0

    for line in lines:
        if current_len + len(line) + 1 > max_length and current:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += len(line) + 1

    if current:
        chunks.append("\n".join(current))

    return chunks


if __name__ == "__main__":
    print("Testing Telegram bot...")
    test_msg = (
        "TEST MESSAGE\n"
        "=================\n"
        "Trading Signal Bot is working!\n"
        "=================\n"
        "This is a test from MetaTrader5 Strategy system."
    )
    send_message_sync(test_msg)
