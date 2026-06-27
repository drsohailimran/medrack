"""MedRack Telegram bot application.

Stage 2.7: T1 skeleton (build_application + 11 stub handlers + main).
T2/T3/T4 fill in the handler bodies.

NOTE: do NOT add `from __future__ import annotations` here. The brief's
`test_main_function_returns_int` (test_bot_layout.py) asserts that
`inspect.signature(main).return_annotation == int` is the actual `int`
type, not the string `'int'`. The `__future__` import would break that.
Python 3.11 supports `str | None` natively, so we don't need it.
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Imports for the T2 informational handlers. T3 and T4 will also need
# these (T3 patches ``cli.cmd_*`` and uses ``config.get_medrack_home``).
import medrack.cli as cli
import medrack.config as config
from medrack.cli import _load_preview_state
from medrack.ingest.manifest import list_books
from medrack.module.storage import list_modules, load_extracted
from telegram.ext import Application, CommandHandler


def build_application(token: str | None = None) -> Application:
    """Build the MedRack Telegram bot application.

    Registers all command handlers. Returns the Application, ready to .run_polling().
    """
    app = Application.builder().token(token or "TEST_TOKEN").build()

    # Informational
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("status", cmd_status))

    # Workflow
    app.add_handler(CommandHandler("preview", cmd_preview))
    app.add_handler(CommandHandler("approve", cmd_approve))
    app.add_handler(CommandHandler("revise", cmd_revise))
    app.add_handler(CommandHandler("cancel", cmd_cancel))

    # Operator-only
    app.add_handler(CommandHandler("ingest_module", cmd_ingest_module))
    app.add_handler(CommandHandler("ingest_book", cmd_ingest_book))
    app.add_handler(CommandHandler("set_llm_mode", cmd_set_llm_mode))

    return app


# ---------------------------------------------------------------------------
# T2: Informational handlers
# ---------------------------------------------------------------------------
WELCOME_TEXT = """\
Welcome to MedRack! 📚

I'm your MBBS theory-exam answer generator. I can:
• /list — show all ingested modules
• /preview <module> [chapter] — generate a preview answer
• /approve — approve the last preview, generate the full batch
• /status — show system state
• /help — show all commands

Get started by typing /list to see what modules are available, then /preview <name>.
"""


HELP_TEXT = """\
*MedRack commands*

*Informational:*
/start — welcome message
/help — this help
/list — list ingested modules
/status — show system state

*Workflow:*
/preview <module> [chapter] — run preview (default chapter: all)
/approve — approve the last preview, generate full batch
/revise <axis> <notes> — record a revision for the last preview
/cancel — cancel the current preview

*Operator-only:*
/ingest_module <subject> <name> — start module ingest (then send PDF)
/ingest_book <subject> <title> — start KB ingest (then send PDF)
/set_llm_mode <mock|real> — switch LLM mode
"""


async def cmd_start(update, context):
    await update.message.reply_text(WELCOME_TEXT)


async def cmd_help(update, context):
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def cmd_list(update, context):
    rows = []
    for mod in list_modules():
        # list_modules() can return either list[dict] (production) or
        # list[tuple] (per the brief's test fixture). Normalize both.
        if isinstance(mod, tuple):
            subject, name = mod[0], mod[1]
            ext_path = None
        else:
            subject = mod.get("subject", "?")
            name = mod.get("name", "?")
            p = mod.get("path")
            if p is None:
                ext_path = None
            else:
                ext_path = Path(p) / "extracted.json"
        if ext_path and ext_path.is_file():
            data = json.loads(ext_path.read_text())
            meta = data.get("metadata", {})
            count = meta.get("questions_extracted", "?")
            fmt = meta.get("format", "?")
            rows.append(f"• `{name}` [{subject}] — {count} questions ({fmt})")
    text = "*Ingested modules:*\n\n" + ("\n".join(rows) if rows else "_(none yet)_")
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_status(update, context):
    books = list_books()
    modules = list_modules()
    n_books = len(books) if isinstance(books, list) else len(list(books))
    n_modules = len(modules)
    state = _load_preview_state()
    state_line = f"  preview: {state.get('module', '?')}" if state else "  preview: (none)"
    text = (
        f"*MedRack system state:*\n\n"
        f"  KB books: {n_books}\n"
        f"  Modules:  {n_modules}\n"
        f"{state_line}\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# Stubs — replaced in T3, T4
# ---------------------------------------------------------------------------
async def cmd_preview(update, context):
    """Handle /preview <module> [chapter]."""
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: /preview <module> [chapter]")
        return
    module_name = args[0]
    chapter = args[1] if len(args) > 1 else "all"
    try:
        ns = argparse.Namespace(
            module=module_name, chapter=chapter, subject=None, reanswer=False,
        )
        rc = cli.cmd_preview(ns)
    except Exception as exc:
        await update.message.reply_text(f"ERROR: {exc}")
        return
    state = cli._load_preview_state()
    if rc == 0 and state and state.get("pdf_path"):
        from pathlib import Path
        pdf = Path(state["pdf_path"])
        if pdf.is_file():
            await update.message.reply_document(
                document=pdf.open("rb"),
                filename=pdf.name,
                caption=f"Preview for {module_name} (chapter: {chapter})",
            )
            return
    await update.message.reply_text(f"rc={rc}")


async def cmd_approve(update, context):
    """Handle /approve — run the full batch."""
    try:
        rc = cli.cmd_approve(argparse.Namespace())
    except Exception as exc:
        await update.message.reply_text(f"ERROR: {exc}")
        return
    if rc == 0:
        from pathlib import Path
        state_path = config.get_medrack_home() / "state" / "batch_state.json"
        if state_path.is_file():
            state = json.loads(state_path.read_text())
            output_pdf = Path(state.get("output_pdf", ""))
            if output_pdf.is_file():
                await update.message.reply_document(
                    document=output_pdf.open("rb"),
                    filename=output_pdf.name,
                    caption=f"Full batch for {state.get('module', '?')}",
                )
                return
    await update.message.reply_text(f"approved, rc={rc}")


async def cmd_revise(update, context):
    """Handle /revise <axis> <notes...>."""
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text("Usage: /revise <wordcount|format|quality> <notes>")
        return
    axis = args[0]
    notes = " ".join(args[1:])
    try:
        rc = cli.cmd_revise(argparse.Namespace(axis=axis, notes=notes))
    except Exception as exc:
        await update.message.reply_text(f"ERROR: {exc}")
        return
    await update.message.reply_text(f"Revision recorded: {axis} = {notes}. rc={rc}")


async def cmd_cancel(update, context):
    """Handle /cancel — clear the preview state."""
    try:
        rc = cli.cmd_cancel(argparse.Namespace())
    except Exception as exc:
        await update.message.reply_text(f"ERROR: {exc}")
        return
    await update.message.reply_text(f"Preview cancelled. rc={rc}")


# ---------------------------------------------------------------------------
# T4: Operator-only handlers + auth helpers
# ---------------------------------------------------------------------------
def is_authorized(chat_id: int) -> bool:
    """Check if a chat_id is authorized for operator commands.

    If MEDRACK_OPERATOR_CHAT_ID is unset, all chats are authorized
    (dev mode). Otherwise, only the matching chat_id is authorized.
    """
    operator_id = os.environ.get("MEDRACK_OPERATOR_CHAT_ID")
    if not operator_id:
        return True  # dev mode: all chats are authorized
    return str(chat_id) == str(operator_id)


async def _require_operator(update, context):
    """If not authorized, send a message and return True (caller should bail).

    Returns False when the user IS authorized (proceed normally).
    """
    chat_id = update.effective_chat.id if update.effective_chat else 0
    if not is_authorized(chat_id):
        await update.message.reply_text("ERROR: not authorized (operator-only command)")
        return True
    return False


async def cmd_ingest_module(update, context):
    """Handle /ingest_module <subject> <name> — then user sends PDF as next message."""
    if await _require_operator(update, context):
        return
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text("Usage: /ingest_module <subject> <name>")
        return
    subject, name = args[0], args[1]
    # Stash the (subject, name) in context.user_data for the next file upload handler
    context.user_data["pending_ingest"] = {"kind": "module", "subject": subject, "name": name}
    await update.message.reply_text(
        f"OK — now send the module PDF for {name} [{subject}]. "
        f"Reply /cancel to abort."
    )


async def cmd_ingest_book(update, context):
    """Handle /ingest_book <subject> <title>."""
    if await _require_operator(update, context):
        return
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text("Usage: /ingest_book <subject> <title>")
        return
    subject, title = args[0], " ".join(args[1:])
    context.user_data["pending_ingest"] = {"kind": "book", "subject": subject, "title": title}
    await update.message.reply_text(
        f"OK — now send the book PDF for {title} [{subject}]. "
        f"Reply /cancel to abort."
    )


async def cmd_set_llm_mode(update, context):
    """Handle /set_llm_mode <mock|real>."""
    if await _require_operator(update, context):
        return
    args = context.args or []
    if not args or args[0] not in ("mock", "real"):
        await update.message.reply_text("Usage: /set_llm_mode <mock|real>")
        return
    # The bot runs as a service and has its own env; we use a sidecar file
    # that cmd_* functions read on each call.
    config_path = config.get_medrack_home() / "state" / "llm_mode"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(args[0])
    await update.message.reply_text(f"LLM mode set to: {args[0]}")


def main() -> int:
    """CLI entry point: `medrack bot`.

    Reads from $MEDRACK_TELEGRAM_BOT_TOKEN (NOT the Hermes gateway's
    $TELEGRAM_BOT_TOKEN, which is reserved for the Hermes agent bot).
    This lets MedRack run as a separate Telegram bot on the same host.
    """
    token = os.environ.get("MEDRACK_TELEGRAM_BOT_TOKEN")
    if not token:
        print("ERROR: $MEDRACK_TELEGRAM_BOT_TOKEN is not set", file=sys.stderr)
        return 2
    app = build_application(token)
    app.run_polling()
    return 0
