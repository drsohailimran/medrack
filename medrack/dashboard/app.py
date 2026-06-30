"""medrack.dashboard.app — Gradio dashboard for MedRack (Stage 2.6)."""

import argparse
import json
import re

import gradio as gr

import medrack.config as config
import medrack.orchestrate as orchestrate
from medrack.state import load_preview_state
from medrack.config import DATA_DIRS, Subject, get_medrack_home
from medrack.ingest.manifest import get_manifest_path
from medrack.module.storage import list_modules, module_dir


# kebab-case slug regex: lowercase letters/digits separated by single
# hyphens, no leading/trailing hyphen, no consecutive hyphens. Matches
# medrack.cli._KEBAB_CASE_RE.
_KEBAB_CASE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def build_dashboard() -> gr.Blocks:
    """Build the MedRack dashboard as a 4-tab Gradio Blocks app.

    Tabs: Ingest | Modules | Preview | State.
    """
    with gr.Blocks(title="MedRack Dashboard", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# MedRack Dashboard")
        with gr.Tabs():
            with gr.Tab("Ingest"):
                _build_ingest_tab()
            with gr.Tab("Modules"):
                _build_modules_tab()
            with gr.Tab("Preview"):
                _build_preview_tab()
            with gr.Tab("State"):
                _build_state_tab()
    return demo


def _build_ingest_tab():
    """Build the Ingest tab: KB book ingest + module ingest, with status output.

    Wires real Gradio components to the ``_ingest_kb_handler`` and
    ``_ingest_module_handler`` functions. Each sub-section has its own
    file upload, subject dropdown, contextual inputs, primary action
    button, and a read-only textbox for the CLI return value.
    """
    gr.Markdown("## Ingest KB / Module")
    subject_choices = Subject.values()

    # --- KB book ingest ---
    with gr.Group():
        gr.Markdown("### Ingest KB book")
        with gr.Row():
            kb_pdf = gr.File(
                label="PDF file",
                file_types=[".pdf"],
                type="filepath",
            )
            kb_subject = gr.Dropdown(
                label="Subject",
                choices=subject_choices,
                value="psm",
            )
        with gr.Row():
            kb_title = gr.Textbox(
                label="Book title",
                placeholder="e.g. Park's PSM 26th ed.",
            )
            kb_replace = gr.Checkbox(
                label="Replace if already indexed",
                value=False,
            )
        kb_button = gr.Button("Ingest KB", variant="primary")
        kb_output = gr.Textbox(label="KB ingest status", lines=3, interactive=False)
        kb_button.click(
            fn=_ingest_kb_handler,
            inputs=[kb_pdf, kb_subject, kb_title, kb_replace],
            outputs=kb_output,
        )

    # --- Module ingest ---
    with gr.Group():
        gr.Markdown("### Ingest module")
        with gr.Row():
            mod_pdf = gr.File(
                label="PDF file",
                file_types=[".pdf"],
                type="filepath",
            )
            mod_subject = gr.Dropdown(
                label="Subject",
                choices=subject_choices,
                value="psm",
            )
        with gr.Row():
            mod_name = gr.Textbox(
                label="Module name (kebab-case)",
                placeholder="e.g. psm-module-1",
            )
            mod_format = gr.Radio(
                label="Format",
                choices=["auto", "mcq", "theory"],
                value="auto",
            )
        mod_button = gr.Button("Ingest Module", variant="primary")
        mod_output = gr.Textbox(label="Module ingest status", lines=3, interactive=False)
        mod_button.click(
            fn=_ingest_module_handler,
            inputs=[mod_pdf, mod_subject, mod_name, mod_format],
            outputs=mod_output,
        )


def _build_modules_tab():
    """Build the Modules tab with list + Preview/Approve/Revise/Cancel actions.

    Lays out a Dataframe of ingested modules, a Dropdown for the selected
    module, and four action buttons that all dispatch to
    ``_action_button_handler`` with a different ``action`` value. The
    action result is shown in a read-only Textbox.
    """
    gr.Markdown("## Modules")
    df = gr.Dataframe(
        headers=["name", "subject", "format", "question_count", "chapters"],
        datatype=["str", "str", "str", "str", "str"],
        value=_list_modules_handler(),
        interactive=False,
        label="Ingested modules",
    )
    dropdown = gr.Dropdown(choices=_module_choices(), label="Module")
    result = gr.Textbox(label="Action result", interactive=False)

    refresh = gr.Button("Refresh")
    refresh.click(_refresh_modules_tab, inputs=[], outputs=[df, dropdown])

    with gr.Row():
        btn_preview = gr.Button("Preview")
        btn_approve = gr.Button("Approve")
        btn_revise = gr.Button("Revise")
        btn_cancel = gr.Button("Cancel")

    # Each button dispatches to the same handler with a different action constant.
    for button, action in (
        (btn_preview, "preview"),
        (btn_approve, "approve"),
        (btn_revise, "revise"),
        (btn_cancel, "cancel"),
    ):
        button.click(
            _action_button_handler,
            inputs=[dropdown, gr.State(action)],
            outputs=[result],
        )


def _refresh_modules_tab() -> tuple[list[list[str]], gr.update]:
    """Refresh both the Dataframe and the Dropdown choices."""
    return _list_modules_handler(), gr.update(choices=_module_choices())


def _module_choices() -> list[str]:
    """Return the list of module names for the Dropdown (no placeholder rows)."""
    return [
        row[0] for row in _list_modules_handler()
        if row[0] and not row[0].startswith("<")
    ]


def _build_preview_tab():
    """Build the Preview tab: pick a module, optionally a chapter, run preview.

    The [Run Preview] button calls :func:`_run_preview_handler`, which
    dispatches to :func:`medrack.cli.cmd_preview` and returns a 2-tuple of
    ``(status_text, pdf_path_or_None)``. The status is shown in a Textbox;
    the PDF is offered as a download via a ``gr.File`` output (only shown
    when the preview succeeded).
    """
    gr.Markdown("## Preview / Approve")
    gr.Markdown(
        "Pick a module (from the Modules tab) and optionally a chapter, "
        "then click **Run Preview** to generate a PDF for review."
    )

    with gr.Row():
        preview_module = gr.Dropdown(
            label="Module",
            choices=_module_choices(),
            value=_module_choices()[0] if _module_choices() else None,
        )
        preview_chapter = gr.Textbox(
            label="Chapter",
            value="all",
            placeholder="e.g. chapter 1, or 'all'",
        )

    run_button = gr.Button("Run Preview", variant="primary")

    pdf_output = gr.File(
        label="Preview PDF",
        interactive=False,
        visible=False,
    )
    status_output = gr.Textbox(
        label="Status",
        lines=2,
        interactive=False,
    )

    def _show_pdf(pdf_path):
        """Return a gr.update(...) that surfaces the PDF when present."""
        return gr.File(value=pdf_path, visible=pdf_path is not None)

    run_button.click(
        fn=_run_preview_handler,
        inputs=[preview_module, preview_chapter],
        outputs=[status_output, pdf_output],
    )
    # Wire the status output's side effect to show/hide the File widget.
    run_button.click(
        fn=_show_pdf,
        inputs=[pdf_output],
        outputs=[pdf_output],
    )


def _build_state_tab():
    """Build the State tab: manifest, batch state, and cached-answers table.

    The [Refresh] button re-invokes :func:`_load_manifest`,
    :func:`_load_batch_state`, and :func:`_list_cached_answers` so the
    operator can see up-to-date state after running other tabs. All three
    handlers are read-only and safe to call repeatedly.
    """
    gr.Markdown("## State Inspection")
    gr.Markdown(
        "Read-only view of the on-disk MedRack state. Click **Refresh** "
        "after running previews / generates on the other tabs."
    )

    refresh = gr.Button("Refresh", variant="primary")

    with gr.Row():
        manifest_box = gr.Textbox(
            label="manifest.json",
            value=_load_manifest(),
            lines=12,
            interactive=False,
        )
        batch_box = gr.Textbox(
            label="batch_state.json",
            value=_load_batch_state(),
            lines=12,
            interactive=False,
        )

    answers_df = gr.Dataframe(
        headers=["module", "chapter", "qid", "model", "tokens"],
        datatype=["str", "str", "str", "str", "str"],
        value=_list_cached_answers(),
        interactive=False,
        label="Cached answers",
    )

    def _refresh_state():
        return _load_manifest(), _load_batch_state(), _list_cached_answers()

    refresh.click(
        fn=_refresh_state,
        inputs=[],
        outputs=[manifest_box, batch_box, answers_df],
    )


# ----- Handlers (D2/D3) -----

def _ingest_kb_handler(pdf_file, subject, book_title, replace, progress=gr.Progress()):
    """Handler for the [Ingest KB] button. Returns status string."""
    if pdf_file is None:
        return "ERROR: no file selected"
    try:
        subject_enum = Subject.from_str(subject)
    except ValueError as exc:
        return f"ERROR: invalid subject: {exc}"
    args = argparse.Namespace(
        pdf=pdf_file,
        subject=subject_enum.value,
        book=book_title,
        replace=replace,
    )
    return orchestrate.cmd_ingest_book(args) or "done"


def _ingest_module_handler(pdf_file, subject, module_name, format_choice, progress=gr.Progress()):
    """Handler for the [Ingest Module] button. Returns status string."""
    if pdf_file is None:
        return "ERROR: no file selected"
    if not module_name or not _KEBAB_CASE_RE.match(module_name):
        return (
            "ERROR: module name must be kebab-case "
            "(lowercase letters, digits, and single hyphens; e.g. 'psm-module-1')"
        )
    try:
        subject_enum = Subject.from_str(subject)
    except ValueError as exc:
        return f"ERROR: invalid subject: {exc}"
    args = argparse.Namespace(
        pdf=pdf_file,
        subject=subject_enum.value,
        name=module_name,
        format=format_choice,
    )
    return orchestrate.cmd_ingest_module(args) or "done"


def _list_modules_handler() -> list[list[str]]:
    """Return a 2D list of [name, subject, format, question_count, chapters] rows.

    Reads from ``medrack.module.storage.list_modules()`` and each
    module's ``extracted.json``. Falls back to a single placeholder row
    when no modules are ingested.
    """
    rows: list[list[str]] = []
    for mod in list_modules():
        # list_modules() can return either list[dict] (production) or
        # list[tuple] (per the brief's test fixture). Normalize both.
        if isinstance(mod, tuple):
            subject, name = mod[0], mod[1]
        else:
            subject = mod.get("subject") or mod.get("subject_code") or "?"
            name = mod.get("name") or mod.get("module_name") or "?"
        ext_path = module_dir(subject, name) / "extracted.json"
        if ext_path.is_file():
            data = json.loads(ext_path.read_text())
            meta = data.get("metadata", {})
            rows.append([
                name,
                subject,
                meta.get("format", "?"),
                str(meta.get("questions_extracted", 0)),
                ", ".join(meta.get("chapters", [])) or "(all)",
            ])
    return rows or [["<no modules ingested yet>", "", "", "", ""]]


def _action_button_handler(module_name: str, action: str) -> str:
    """Handle Preview/Approve/Revise/Cancel button clicks.

    Validates ``module_name``, builds the right ``argparse.Namespace``
    for the requested action, calls the matching ``cli.cmd_*`` function,
    and returns a short status string like ``action=preview rc=0`` or
    ``ERROR: ...``.
    """
    if not module_name or module_name.startswith("<"):
        return "ERROR: select a module first"
    if action == "preview":
        args = argparse.Namespace(
            module=module_name, chapter="all", subject=None, reanswer=False,
        )
        rc = orchestrate.cmd_preview(args)
    elif action == "approve":
        rc = orchestrate.cmd_approve(argparse.Namespace())
    elif action == "revise":
        args = argparse.Namespace(axis="wordcount", notes="1500")
        rc = orchestrate.cmd_revise(args)
    elif action == "cancel":
        rc = orchestrate.cmd_cancel(argparse.Namespace())
    else:
        return f"ERROR: unknown action: {action}"
    return f"action={action} rc={rc}"


# ----- Handlers (D4) -----


def _run_preview_handler(module_name: str, chapter: str) -> tuple[str, str | None]:
    """Run preview, return (status_text, pdf_path_or_None).

    Thin wrapper around :func:`medrack.cli.cmd_preview` that the Preview
    tab wires to its [Run Preview] button. Validates ``module_name`` and
    then re-reads the preview state to extract the generated PDF path so
    the UI can offer it as a download.
    """
    if not module_name or module_name.startswith("<"):
        return ("ERROR: select a module first", None)
    args = argparse.Namespace(
        module=module_name, chapter=chapter or "all",
        subject=None, reanswer=False,
    )
    rc = orchestrate.cmd_preview(args)
    state = load_preview_state()
    if rc == 0 and state:
        return (f"Preview PDF: {state.get('pdf_path')}", state.get("pdf_path"))
    return (f"rc={rc}", None)


def _load_manifest() -> str:
    """Return the manifest.json as a JSON string.

    Falls back to ``"(no manifest yet)"`` when the file does not exist so
    the Gradio Textbox always has something meaningful to display.
    """
    p = get_manifest_path()
    if not p.is_file():
        return "(no manifest yet)"
    return p.read_text()


def _load_batch_state() -> str:
    """Return ``state/batch_state.json`` as a JSON string.

    Falls back to ``"(no batch state yet)"`` when the file does not exist.
    """
    p = get_medrack_home() / "state" / "batch_state.json"
    if not p.is_file():
        return "(no batch state yet)"
    return p.read_text()


def _list_cached_answers() -> list[list[str]]:
    """List all cached answers as rows of [module, chapter, qid, model, tokens].

    Walks the answers directory (``DATA_DIRS["answers"]``) two levels deep
    (module / chapter) and reads every ``*.json`` file. Returns a single
    placeholder row when the directory is missing or empty so the
    Dataframe always renders something.
    """
    rows: list[list[str]] = []
    answers_root = DATA_DIRS["answers"]
    if not answers_root.is_dir():
        return [["<no cached answers>", "", "", "", ""]]
    for module_dir in answers_root.iterdir():
        if not module_dir.is_dir():
            continue
        for chapter_dir in module_dir.iterdir():
            if not chapter_dir.is_dir():
                continue
            for ans_file in chapter_dir.glob("*.json"):
                data = json.loads(ans_file.read_text())
                rows.append([
                    module_dir.name,
                    chapter_dir.name,
                    ans_file.stem,
                    data.get("model", "?"),
                    str(data.get("total_tokens", 0)),
                ])
    return rows or [["<no cached answers>", "", "", "", ""]]


def main() -> int:
    """Launch the dashboard. CLI entry point for `medrack dashboard`."""
    demo = build_dashboard()
    # Bind to 0.0.0.0 so the dashboard is reachable from the local network
    # (and via Tailscale at 100.74.196.11). Originally was 127.0.0.1 which
    # only worked when accessing from the same host. Per operator request
    # so the dashboard can be opened from the Windows 11 PC.
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
    )
    return 0
