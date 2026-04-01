"""Tests for the local storage backend."""

import os
import tempfile

import pytest

from obsidian_sync.storage.local import LocalStorage


@pytest.fixture
def storage(tmp_path) -> LocalStorage:
    return LocalStorage(str(tmp_path))


@pytest.mark.asyncio
async def test_write_and_read(storage: LocalStorage) -> None:
    await storage.write("test.md", b"# Hello\n")
    data = await storage.read("test.md")
    assert data == b"# Hello\n"


@pytest.mark.asyncio
async def test_write_creates_directories(storage: LocalStorage) -> None:
    await storage.write("folder/sub/deep.md", b"content")
    data = await storage.read("folder/sub/deep.md")
    assert data == b"content"


@pytest.mark.asyncio
async def test_exists(storage: LocalStorage) -> None:
    assert not await storage.exists("nope.md")
    await storage.write("exists.md", b"yes")
    assert await storage.exists("exists.md")


@pytest.mark.asyncio
async def test_delete(storage: LocalStorage) -> None:
    await storage.write("deleteme.md", b"bye")
    assert await storage.exists("deleteme.md")
    await storage.delete("deleteme.md")
    assert not await storage.exists("deleteme.md")


@pytest.mark.asyncio
async def test_delete_nonexistent_is_noop(storage: LocalStorage) -> None:
    await storage.delete("nope.md")  # Should not raise


@pytest.mark.asyncio
async def test_list_files(storage: LocalStorage) -> None:
    await storage.write("a.md", b"a")
    await storage.write("b.md", b"bb")
    await storage.write("sub/c.md", b"ccc")

    entries = await storage.list()
    paths = [e.path for e in entries]
    assert "a.md" in paths
    assert "b.md" in paths
    assert "sub" in paths  # directory

    sub_entries = await storage.list("sub")
    assert len(sub_entries) == 1
    assert sub_entries[0].path == "sub/c.md"


@pytest.mark.asyncio
async def test_stat(storage: LocalStorage) -> None:
    content = b"hello world"
    await storage.write("stat.md", content)
    s = await storage.stat("stat.md")
    assert s.size == len(content)
    assert s.content_hash is not None
    assert s.modified is not None


@pytest.mark.asyncio
async def test_stat_nonexistent_raises(storage: LocalStorage) -> None:
    with pytest.raises(FileNotFoundError):
        await storage.stat("nope.md")


@pytest.mark.asyncio
async def test_path_traversal_blocked(storage: LocalStorage) -> None:
    with pytest.raises(ValueError, match="traversal"):
        await storage.read("../../etc/passwd")


@pytest.mark.asyncio
async def test_binary_files(storage: LocalStorage) -> None:
    binary_data = bytes(range(256))
    await storage.write("binary.bin", binary_data)
    data = await storage.read("binary.bin")
    assert data == binary_data
