"""medrack/tests/conftest.py — shared test infrastructure.

Auto-wires ``MEDRACK_HOME`` to ``tmp_path`` for any test that requests
the ``tmp_path`` fixture. This is the test-isolation contract used by
``medrack.answer.cache``, ``medrack.ingest.index``, ``medrack.module.storage``,
and friends: they all re-evaluate ``config.get_medrack_home()`` on every
call, so setting ``MEDRACK_HOME`` per-test gives each test its own
isolated answers/, modules/, index/ tree.

This conftest does NOT change the behaviour of tests that don't ask for
``tmp_path`` (the autouse fixture below is conditional on the test
requesting ``tmp_path``).
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _wire_medrack_home(request, tmp_path_factory, monkeypatch):
    """If a test requests ``tmp_path``, redirect ``MEDRACK_HOME`` to it.

    Tests that don't use ``tmp_path`` are unaffected — this fixture is
    only auto-activated when ``tmp_path`` appears in the test's
    requested fixtures (it pulls ``tmp_path`` from ``request`` only
    when the test asked for it).

    Note: we re-use pytest's built-in ``tmp_path`` factory so that the
    test's own ``tmp_path`` argument (if any) points at the same
    directory. For tests that don't take ``tmp_path`` as an argument
    but still need isolation, the brief's test files always take it.
    """
    if "tmp_path" not in request.fixturenames:
        return
    # The test will get its own tmp_path; we set MEDRACK_HOME to it.
    # pytest's tmp_path is per-test, function-scoped.
    test_tmp = request.getfixturevalue("tmp_path")
    # Ensure the standard subdirs exist so cache/manifest helpers don't
    # surprise the test with auto-created paths the test didn't expect.
    monkeypatch.setenv("MEDRACK_HOME", str(test_tmp))
    (test_tmp / "answers").mkdir(parents=True, exist_ok=True)
    (test_tmp / "index" / "chroma").mkdir(parents=True, exist_ok=True)
    (test_tmp / "modules").mkdir(parents=True, exist_ok=True)
    (test_tmp / "state").mkdir(parents=True, exist_ok=True)
