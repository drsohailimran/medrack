"""Tests for informational bot commands."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


def make_update(text="/start"):
    """Build a fake Update with a Message that has a .reply_text async method."""
    update = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    return update


def test_cmd_start_replies_with_welcome():
    from medrack.bot.app import cmd_start, WELCOME_TEXT
    update = make_update()
    context = MagicMock()
    asyncio.run(cmd_start(update, context))
    update.message.reply_text.assert_awaited_once()
    sent = update.message.reply_text.await_args.args[0]
    assert "MedRack" in sent
    assert WELCOME_TEXT == sent


def test_cmd_help_replies_with_help():
    from medrack.bot.app import cmd_help
    update = make_update()
    context = MagicMock()
    asyncio.run(cmd_help(update, context))
    update.message.reply_text.assert_awaited_once()
    sent = update.message.reply_text.await_args.args[0]
    assert "/list" in sent and "/preview" in sent


def test_cmd_list_replies_with_module_list():
    from medrack.bot.app import cmd_list
    with patch("medrack.bot.app.list_modules", return_value=[
        {"subject": "psm", "name": "psm-module-1",
         "path": __import__("pathlib").Path("/nonexistent/but/it/wont/be/read")}
    ]):
        update = make_update()
        context = MagicMock()
        asyncio.run(cmd_list(update, context))
    update.message.reply_text.assert_awaited_once()
    sent = update.message.reply_text.await_args.args[0]
    # Will be the "no extracted.json" placeholder (since /nonexistent doesn't exist)
    assert "none" in sent.lower() or "psm-module-1" in sent


def test_cmd_status_shows_book_and_module_counts():
    from medrack.bot.app import cmd_status
    with patch("medrack.bot.app.list_books", return_value=[{"book_id": "1"}, {"book_id": "2"}]):
        with patch("medrack.bot.app.list_modules", return_value=[{"name": "m1"}]):
            update = make_update()
            context = MagicMock()
            asyncio.run(cmd_status(update, context))
    sent = update.message.reply_text.await_args.args[0]
    assert "2" in sent  # 2 books
    assert "1" in sent  # 1 module
