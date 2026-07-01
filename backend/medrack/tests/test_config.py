"""Tests for medrack.config — paths, subject enum, module format."""
import os
from pathlib import Path

import pytest

from medrack import config


def test_get_medrack_home_default():
    if not os.environ.get("MEDRACK_HOME"):
        assert config.get_medrack_home() == Path.home() / ".hermes" / "medrack"


def test_get_medrack_home_override(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDRACK_HOME", str(tmp_path))
    assert config.get_medrack_home() == tmp_path


def test_subject_enum_values():
    expected = ["psm", "fmt", "medicine", "surgery", "ortho",
                "obgyn", "anesthesia", "pediatrics", "ent", "ophthalmology"]
    assert config.Subject.values() == expected


def test_subject_from_str_valid():
    assert config.Subject.from_str("psm") == config.Subject.PSM
    assert config.Subject.from_str("MEDICINE") == config.Subject.MEDICINE
    assert config.Subject.from_str("fmt") == config.Subject.FMT


def test_subject_from_str_invalid():
    with pytest.raises(ValueError, match="Unknown subject"):
        config.Subject.from_str("biology")


def test_module_format_enum():
    assert config.ModuleFormat.AUTO.value == "auto"
    assert config.ModuleFormat.MCQ.value == "mcq"
    assert config.ModuleFormat.THEORY.value == "theory"


def test_data_dirs_all_paths():
    for name, path in config.DATA_DIRS.items():
        assert isinstance(path, Path)
        assert str(path).startswith(str(config.HOME))


def test_manifest_path_exists():
    assert config.MANIFEST_PATH.name == "manifest.json"
    assert config.MANIFEST_PATH.parent == config.DATA_DIRS["index"]


def test_llm_fallback_chain_nonempty():
    assert len(config.LLM_FALLBACK_CHAIN) >= 2
    assert config.LLM_DEFAULT_MODEL not in config.LLM_FALLBACK_CHAIN


def test_chunk_size_positive():
    assert config.CHUNK_SIZE_TOKENS > 0
    assert 0 < config.CHUNK_OVERLAP_TOKENS < config.CHUNK_SIZE_TOKENS


def test_retrieval_top_k_positive():
    assert config.RETRIEVAL_TOP_K > 0


def test_subject_filter_mandatory():
    """Critical safety invariant — never retrieve across subjects."""
    assert config.SUBJECT_FILTER_MANDATORY is True
