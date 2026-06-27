"""Tests for operator-only bot commands."""
import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def make_update(text="/ingest_module psm test", chat_id=12345):
    update = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.effective_chat.id = chat_id
    return update


def test_is_authorized_no_env_var_allows_all():
    from medrack.bot.app import is_authorized
    with patch.dict(os.environ, {}, clear=True):
        assert is_authorized(12345) is True


def test_is_authorized_with_matching_chat_id():
    from medrack.bot.app import is_authorized
    with patch.dict(os.environ, {"MEDRACK_OPERATOR_CHAT_ID": "12345"}):
        assert is_authorized(12345) is True


def test_is_authorized_with_different_chat_id():
    from medrack.bot.app import is_authorized
    with patch.dict(os.environ, {"MEDRACK_OPERATOR_CHAT_ID": "12345"}):
        assert is_authorized(99999) is False


def test_cmd_ingest_module_unauthorized():
    from medrack.bot.app import cmd_ingest_module
    update = make_update(chat_id=99999)
    context = MagicMock()
    context.args = ["psm", "test-mod"]
    with patch.dict(os.environ, {"MEDRACK_OPERATOR_CHAT_ID": "12345"}):
        asyncio.run(cmd_ingest_module(update, context))
    sent = update.message.reply_text.await_args.args[0]
    assert "not authorized" in sent


def test_cmd_ingest_module_stashes_pending_ingest():
    from medrack.bot.app import cmd_ingest_module
    update = make_update(chat_id=12345)
    context = MagicMock()
    context.args = ["psm", "test-mod"]
    context.user_data = {}
    with patch.dict(os.environ, {}, clear=True):  # dev mode
        asyncio.run(cmd_ingest_module(update, context))
    assert context.user_data.get("pending_ingest") == {
        "kind": "module", "subject": "psm", "name": "test-mod",
    }


def test_cmd_ingest_book_stashes_pending_ingest():
    from medrack.bot.app import cmd_ingest_book
    update = make_update(chat_id=12345)
    context = MagicMock()
    context.args = ["psm", "Park's", "PSM", "Book"]
    context.user_data = {}
    with patch.dict(os.environ, {}, clear=True):
        asyncio.run(cmd_ingest_book(update, context))
    assert context.user_data.get("pending_ingest") == {
        "kind": "book", "subject": "psm", "title": "Park's PSM Book",
    }


def test_cmd_ingest_module_validates_args():
    from medrack.bot.app import cmd_ingest_module
    update = make_update()
    context = MagicMock()
    context.args = ["only_one_arg"]
    with patch.dict(os.environ, {}, clear=True):
        asyncio.run(cmd_ingest_module(update, context))
    sent = update.message.reply_text.await_args.args[0]
    assert "Usage" in sent


def test_cmd_set_llm_mode_writes_to_state():
    from medrack.bot.app import cmd_set_llm_mode
    update = make_update(chat_id=12345)
    context = MagicMock()
    context.args = ["mock"]
    with patch.dict(os.environ, {}, clear=True):
        with tempfile.TemporaryDirectory(prefix="hermes-verify-") as tmp:
            with patch("medrack.bot.app.config.get_medrack_home", return_value=Path(tmp)):
                asyncio.run(cmd_set_llm_mode(update, context))
            # The llm_mode file should exist with content "mock"
            mode_file = Path(tmp) / "state" / "llm_mode"
            assert mode_file.read_text() == "mock"
