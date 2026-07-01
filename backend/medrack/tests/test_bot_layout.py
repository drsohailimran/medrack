"""Tests for medrack.bot.app layout."""
import pytest


def test_build_application_returns_application():
    from medrack.bot.app import build_application
    from telegram.ext import Application
    app = build_application(token="TEST_TOKEN_FOR_TESTING")
    assert isinstance(app, Application)


def test_build_application_registers_start_handler():
    from medrack.bot.app import build_application
    app = build_application(token="TEST_TOKEN_FOR_TESTING")
    # ptb 22.6 uses `.commands` (frozenset), not `.command` (list).
    # Use the correct attribute name based on the installed version.
    handler_names = set()
    for h in app.handlers[0]:
        if hasattr(h, "commands"):  # ptb >= 20
            handler_names |= h.commands
        elif hasattr(h, "command"):  # ptb < 20
            handler_names |= set(h.command)
    assert "start" in handler_names


def test_build_application_registers_all_expected_commands():
    from medrack.bot.app import build_application
    app = build_application(token="TEST_TOKEN_FOR_TESTING")
    handler_names = set()
    for h in app.handlers[0]:
        if hasattr(h, "commands"):
            handler_names |= h.commands
        elif hasattr(h, "command"):
            handler_names |= set(h.command)
    expected = {"start", "help", "list", "status", "preview", "approve",
                "revise", "cancel", "ingest_module", "ingest_book", "set_llm_mode"}
    assert expected.issubset(handler_names)


def test_bot_app_imports_without_crash():
    from medrack.bot import app
    assert app.build_application is not None
    assert app.main is not None


def test_main_function_returns_int():
    from medrack.bot.app import main
    import inspect
    sig = inspect.signature(main)
    assert sig.return_annotation == int
