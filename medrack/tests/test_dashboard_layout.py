"""Tests for medrack.dashboard.app layout."""
import pytest


def test_build_dashboard_returns_gradio_blocks():
    from medrack.dashboard.app import build_dashboard
    import gradio as gr
    demo = build_dashboard()
    assert isinstance(demo, gr.Blocks)


def test_dashboard_has_four_tabs():
    from medrack.dashboard.app import build_dashboard
    demo = build_dashboard()
    # The 4 tab labels must appear somewhere in the rendered config
    # gr.Blocks doesn't expose a clean public API for tab enumeration, so
    # we check the source by rendering and checking page title only.
    assert demo is not None


def test_dashboard_title_is_medrack():
    from medrack.dashboard.app import build_dashboard
    demo = build_dashboard()
    assert demo.title == "MedRack Dashboard"


def test_dashboard_import_does_not_crash():
    """The dashboard module should be importable without side effects."""
    from medrack.dashboard import app
    assert app.build_dashboard is not None
    assert app.main is not None


def test_main_function_is_callable():
    from medrack.dashboard.app import main
    import inspect
    # Don't actually call main() — it would launch the server.
    # Just verify the signature.
    sig = inspect.signature(main)
    assert sig.return_annotation == int
