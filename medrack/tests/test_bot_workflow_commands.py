"""Tests for workflow bot commands."""
import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def make_update(text="/preview x", chat_id=12345):
    update = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.message.reply_document = AsyncMock()
    update.effective_chat.id = chat_id
    return update


def test_cmd_preview_with_no_args_asks_for_usage():
    from medrack.bot.app import cmd_preview
    update = make_update()
    context = MagicMock()
    context.args = []
    asyncio.run(cmd_preview(update, context))
    sent = update.message.reply_text.await_args.args[0]
    assert "Usage" in sent


def test_cmd_preview_calls_cli_cmd_preview():
    from medrack.bot.app import cmd_preview
    update = make_update()
    context = MagicMock()
    context.args = ["psm-module-1", "chapter 1"]
    captured = {}
    def mock_preview(args):
        captured["module"] = args.module
        captured["chapter"] = args.chapter
        return 5  # error
    with patch("medrack.bot.app.cli.cmd_preview", mock_preview):
        asyncio.run(cmd_preview(update, context))
    assert captured["module"] == "psm-module-1"
    assert captured["chapter"] == "chapter 1"
    # With rc=5, no PDF sent
    update.message.reply_document.assert_not_awaited()


def test_cmd_preview_with_successful_state_sends_pdf(tmp_path):
    from medrack.bot.app import cmd_preview
    # Create a fake PDF
    pdf = tmp_path / "preview.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    state = {"module": "psm-module-1", "pdf_path": str(pdf)}
    update = make_update()
    context = MagicMock()
    context.args = ["psm-module-1"]
    with patch("medrack.bot.app.cli.cmd_preview", return_value=0):
        with patch("medrack.bot.app.cli._load_preview_state", return_value=state):
            asyncio.run(cmd_preview(update, context))
    # The PDF should be sent
    update.message.reply_document.assert_awaited_once()


def test_cmd_approve_runs_full_batch():
    from medrack.bot.app import cmd_approve
    update = make_update()
    context = MagicMock()
    with patch("medrack.bot.app.cli.cmd_approve", return_value=0):
        with patch("medrack.bot.app.config.get_medrack_home", return_value=Path("/nonexistent")):
            asyncio.run(cmd_approve(update, context))
    update.message.reply_text.assert_awaited_once()


def test_cmd_revise_validates_args():
    from medrack.bot.app import cmd_revise
    update = make_update()
    context = MagicMock()
    context.args = []
    asyncio.run(cmd_revise(update, context))
    sent = update.message.reply_text.await_args.args[0]
    assert "Usage" in sent


def test_cmd_revise_calls_cli_cmd_revise():
    from medrack.bot.app import cmd_revise
    update = make_update()
    context = MagicMock()
    context.args = ["wordcount", "1500", "more", "notes"]
    captured = {}
    def mock_revise(args):
        captured["axis"] = args.axis
        captured["notes"] = args.notes
        return 0
    with patch("medrack.bot.app.cli.cmd_revise", mock_revise):
        asyncio.run(cmd_revise(update, context))
    assert captured["axis"] == "wordcount"
    assert captured["notes"] == "1500 more notes"


def test_cmd_cancel_calls_cli_cmd_cancel():
    from medrack.bot.app import cmd_cancel
    update = make_update()
    context = MagicMock()
    with patch("medrack.bot.app.cli.cmd_cancel", return_value=0):
        asyncio.run(cmd_cancel(update, context))
    update.message.reply_text.assert_awaited_once()
    sent = update.message.reply_text.await_args.args[0]
    assert "cancelled" in sent.lower()
