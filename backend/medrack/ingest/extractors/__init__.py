"""medrack.ingest.extractors — pluggable metadata extractors.

The :class:`medrack.ingest.metadata.MetadataExtractor` interface lives in
``medrack.ingest.metadata``; concrete implementations live here. v1
ships :class:`RegexMetadataExtractor`. Future extractors (LLM-based,
hybrid) can be added as new modules here without changing the
ingestion pipeline.
"""
from medrack.ingest.extractors.regex_extractor import RegexMetadataExtractor

__all__ = ["RegexMetadataExtractor"]
