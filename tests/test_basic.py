"""Basic tests for kb-studio core components."""

import json
import tempfile
from pathlib import Path

import pytest


# ── Chunker tests ──

def test_sliding_window_no_infinite_loop():
    """overlap >= chunk_size must not cause infinite loop."""
    from kb_studio.core.doc_processor.chunker import SlidingWindowChunker

    chunker = SlidingWindowChunker(chunk_size=10, overlap=10)
    chunks = chunker.chunk("a" * 50)
    assert len(chunks) > 0
    assert len(chunks) < 100  # Sanity: should not explode

    chunker2 = SlidingWindowChunker(chunk_size=10, overlap=20)
    chunks2 = chunker2.chunk("a" * 50)
    assert len(chunks2) > 0


def test_sliding_window_normal():
    from kb_studio.core.doc_processor.chunker import SlidingWindowChunker

    text = "abcdefghij" * 10  # 100 chars
    chunker = SlidingWindowChunker(chunk_size=20, overlap=5)
    chunks = chunker.chunk(text)
    assert len(chunks) > 1
    assert all(c.source for c in chunks)
    assert all(c.chunk_id for c in chunks)


def test_semantic_chunker():
    from kb_studio.core.doc_processor.chunker import SemanticChunker

    text = "# Title\n\nSome content here.\n\n## Subtitle\n\nMore content."
    chunker = SemanticChunker(max_chunk_size=200, min_chunk_size=10)
    chunks = chunker.chunk(text, metadata={"filename": "test.md"})
    assert len(chunks) >= 1
    assert chunks[0].source == "test.md"


def test_heading_chunker():
    from kb_studio.core.doc_processor.chunker import HeadingChunker

    text = "# A\n\nContent A\n\n# B\n\nContent B"
    chunker = HeadingChunker(max_chunk_size=200)
    chunks = chunker.chunk(text, metadata={"filename": "test.md"})
    assert len(chunks) >= 2


# ── Vector Store tests ──

def test_memory_store_insert_and_search():
    from kb_studio.core.vector_store.memory_store import MemoryVectorStore
    import numpy as np

    store = MemoryVectorStore(dimension=4)
    chunks = [
        {"chunk_id": "c1", "content": "hello", "source": "a.txt", "heading_path": [], "metadata": {}},
        {"chunk_id": "c2", "content": "world", "source": "b.txt", "heading_path": [], "metadata": {}},
    ]
    embeddings = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=np.float32)
    store.insert_chunks(chunks, embeddings)

    results = store.search([1, 0, 0, 0], top_k=2)
    assert len(results) == 2
    assert results[0].chunk_id == "c1"
    assert results[0].score > results[1].score


def test_memory_store_dict_chunks():
    """insert_chunks should work with plain dicts (not Chunk objects)."""
    from kb_studio.core.vector_store.memory_store import MemoryVectorStore

    store = MemoryVectorStore(dimension=3)
    chunks = [{"chunk_id": "x", "content": "test", "source": "f.txt", "heading_path": [], "metadata": {}}]
    store.insert_chunks(chunks, [[1.0, 0.0, 0.0]])
    assert store.get_collection_stats()["row_count"] == 1


# ── Converter tests ──

def test_converter_supported_extensions():
    from kb_studio.core.doc_processor.converter import DocumentConverter

    exts = DocumentConverter.get_supported_extensions()
    assert exts["count"] > 40
    assert ".pdf" in exts["all"]
    assert ".ipynb" in exts["all"]
    assert ".md" in exts["all"]
    assert "documents" in exts["categories"]
    assert "text_code" in exts["categories"]


def test_converter_txt():
    from kb_studio.core.doc_processor.converter import DocumentConverter

    converter = DocumentConverter()
    tmp = tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False)
    try:
        tmp.write("Hello world")
        tmp.close()
        doc = converter.convert_file(tmp.name)
        assert "Hello world" in doc.markdown
        assert doc.file_type == ".txt"
    finally:
        Path(tmp.name).unlink(missing_ok=True)


def test_converter_unsupported():
    from kb_studio.core.doc_processor.converter import DocumentConverter

    converter = DocumentConverter()
    tmp = tempfile.NamedTemporaryFile(suffix=".xyz", mode="w", delete=False)
    try:
        tmp.write("data")
        tmp.close()
        with pytest.raises(ValueError, match="Unsupported"):
            converter.convert_file(tmp.name)
    finally:
        Path(tmp.name).unlink(missing_ok=True)


# ── KBManager tests ──

def test_kb_manager_create_and_list():
    from kb_studio.kb_manager import KBManager

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = KBManager(data_dir=tmpdir)
        mgr.create("test-kb", description="A test KB")
        kbs = mgr.list()
        assert len(kbs) == 1
        assert kbs[0].name == "test-kb"
        assert kbs[0].description == "A test KB"


def test_kb_manager_create_duplicate():
    from kb_studio.kb_manager import KBManager

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = KBManager(data_dir=tmpdir)
        mgr.create("dup")
        with pytest.raises(ValueError, match="already exists"):
            mgr.create("dup")


def test_kb_manager_delete():
    from kb_studio.kb_manager import KBManager

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = KBManager(data_dir=tmpdir)
        mgr.create("to-delete")
        mgr.delete("to-delete")
        assert len(mgr.list()) == 0


def test_kb_manager_memory():
    from kb_studio.kb_manager import KBManager

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = KBManager(data_dir=tmpdir)
        mgr.create("mem-test")

        # Empty memory
        mem = mgr.get_memory("mem-test")
        assert mem["entries"] == []

        # Add entry
        entry = mgr.add_memory_entry("mem-test", "User likes Chinese", "user_preference", importance=0.8)
        assert entry["content"] == "User likes Chinese"

        # Get memory context
        ctx = mgr.get_memory_context("mem-test")
        assert "User likes Chinese" in ctx
        assert "user_preference" in ctx

        # Delete entry
        mgr.delete_memory_entry("mem-test", entry["id"])
        assert len(mgr.get_memory("mem-test")["entries"]) == 0


def test_kb_manager_conversations():
    from kb_studio.kb_manager import KBManager

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = KBManager(data_dir=tmpdir)
        mgr.create("conv-test")

        # List triggers migration (creates default)
        convs = mgr.list_conversations("conv-test")
        assert len(convs) == 1
        assert convs[0]["name"] == "Default"

        # Create new conversation
        conv = mgr.create_conversation("conv-test", "My Chat")
        assert conv["name"] == "My Chat"

        # Save message
        mgr.save_conversation_message("conv-test", conv["id"], {"role": "user", "content": "hello"})
        msgs = mgr.get_conversation_history("conv-test", conv["id"])
        assert len(msgs) == 1
        assert msgs[0]["content"] == "hello"


# ── Agent Pipeline tests ──

def test_pipeline_step_creation():
    from kb_studio.agent_pipeline import PipelineStep

    step = PipelineStep(name="retriever", role_prompt="test", kb_names=["kb1"])
    assert step.name == "retriever"
    assert step.enabled is True
