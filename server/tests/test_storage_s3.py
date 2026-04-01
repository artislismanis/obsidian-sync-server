"""Tests for S3Storage backend using mocked aioboto3."""

import hashlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from obsidian_sync.storage.s3 import S3Storage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_body(data: bytes) -> MagicMock:
    """Create a mock S3 response Body with an async read() method."""
    body = MagicMock()
    body.read = AsyncMock(return_value=data)
    return body


def _make_s3_client() -> AsyncMock:
    """Create a mock S3 client with common methods."""
    client = AsyncMock()
    # Create a mock exceptions namespace
    client.exceptions = MagicMock()
    client.exceptions.NoSuchKey = type("NoSuchKey", (Exception,), {})
    return client


class _AsyncContextManager:
    """Helper to make an async context manager from a mock."""

    def __init__(self, mock: AsyncMock) -> None:
        self._mock = mock

    async def __aenter__(self) -> AsyncMock:
        return self._mock

    async def __aexit__(self, *args: object) -> None:
        pass


class _AsyncPaginator:
    """Async iterator over pages returned by a mocked paginator."""

    def __init__(self, pages: list[dict]) -> None:
        self._pages = pages

    def __aiter__(self) -> "_AsyncPaginator":
        self._idx = 0
        return self

    async def __anext__(self) -> dict:
        if self._idx >= len(self._pages):
            raise StopAsyncIteration
        page = self._pages[self._idx]
        self._idx += 1
        return page


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def s3_storage() -> S3Storage:
    return S3Storage(
        bucket="test-bucket",
        prefix="vaults/abc123",
        region="us-east-1",
        aws_access_key_id="AKID",
        aws_secret_access_key="SECRET",
    )


@pytest.fixture
def s3_no_prefix() -> S3Storage:
    return S3Storage(
        bucket="test-bucket",
        prefix="",
        region="us-east-1",
    )


class TestS3StorageKeyBuilding:
    def test_key_with_prefix(self, s3_storage: S3Storage) -> None:
        assert s3_storage._key("notes/hello.md") == "vaults/abc123/notes/hello.md"

    def test_key_without_prefix(self, s3_no_prefix: S3Storage) -> None:
        assert s3_no_prefix._key("notes/hello.md") == "notes/hello.md"


class TestRead:
    async def test_read_success(self, s3_storage: S3Storage) -> None:
        mock_client = _make_s3_client()
        content = b"# Hello World"
        mock_client.get_object = AsyncMock(
            return_value={"Body": _make_body(content)}
        )

        with patch.object(
            s3_storage._session, "client", return_value=_AsyncContextManager(mock_client)
        ):
            result = await s3_storage.read("notes/hello.md")

        assert result == content
        mock_client.get_object.assert_called_once_with(
            Bucket="test-bucket", Key="vaults/abc123/notes/hello.md"
        )

    async def test_read_not_found(self, s3_storage: S3Storage) -> None:
        mock_client = _make_s3_client()
        mock_client.get_object = AsyncMock(
            side_effect=mock_client.exceptions.NoSuchKey("not found")
        )

        with patch.object(
            s3_storage._session, "client", return_value=_AsyncContextManager(mock_client)
        ):
            with pytest.raises(FileNotFoundError):
                await s3_storage.read("missing.md")


class TestWrite:
    async def test_write_success(self, s3_storage: S3Storage) -> None:
        mock_client = _make_s3_client()
        mock_client.put_object = AsyncMock()

        with patch.object(
            s3_storage._session, "client", return_value=_AsyncContextManager(mock_client)
        ):
            await s3_storage.write("notes/hello.md", b"content")

        mock_client.put_object.assert_called_once_with(
            Bucket="test-bucket", Key="vaults/abc123/notes/hello.md", Body=b"content"
        )


class TestDelete:
    async def test_delete_success(self, s3_storage: S3Storage) -> None:
        mock_client = _make_s3_client()
        mock_client.delete_object = AsyncMock()

        with patch.object(
            s3_storage._session, "client", return_value=_AsyncContextManager(mock_client)
        ):
            await s3_storage.delete("notes/hello.md")

        mock_client.delete_object.assert_called_once_with(
            Bucket="test-bucket", Key="vaults/abc123/notes/hello.md"
        )


class TestExists:
    async def test_exists_true(self, s3_storage: S3Storage) -> None:
        mock_client = _make_s3_client()
        mock_client.head_object = AsyncMock(return_value={"ContentLength": 42})

        with patch.object(
            s3_storage._session, "client", return_value=_AsyncContextManager(mock_client)
        ):
            result = await s3_storage.exists("notes/hello.md")

        assert result is True

    async def test_exists_false(self, s3_storage: S3Storage) -> None:
        mock_client = _make_s3_client()
        mock_client.head_object = AsyncMock(side_effect=Exception("not found"))

        with patch.object(
            s3_storage._session, "client", return_value=_AsyncContextManager(mock_client)
        ):
            result = await s3_storage.exists("missing.md")

        assert result is False


class TestList:
    async def test_list_objects(self, s3_storage: S3Storage) -> None:
        mock_client = _make_s3_client()
        now = datetime.now(tz=timezone.utc)
        page = {
            "Contents": [
                {"Key": "vaults/abc123/notes/a.md", "Size": 100, "LastModified": now},
                {"Key": "vaults/abc123/notes/b.md", "Size": 200, "LastModified": now},
            ]
        }
        paginator = MagicMock()
        paginator.paginate = MagicMock(return_value=_AsyncPaginator([page]))
        mock_client.get_paginator = MagicMock(return_value=paginator)

        with patch.object(
            s3_storage._session, "client", return_value=_AsyncContextManager(mock_client)
        ):
            entries = await s3_storage.list("notes")

        assert len(entries) == 2
        assert entries[0].path == "notes/a.md"
        assert entries[0].size == 100
        assert entries[1].path == "notes/b.md"
        assert entries[1].size == 200

    async def test_list_empty(self, s3_storage: S3Storage) -> None:
        mock_client = _make_s3_client()
        paginator = MagicMock()
        paginator.paginate = MagicMock(return_value=_AsyncPaginator([{"Contents": []}]))
        mock_client.get_paginator = MagicMock(return_value=paginator)

        with patch.object(
            s3_storage._session, "client", return_value=_AsyncContextManager(mock_client)
        ):
            entries = await s3_storage.list("")

        assert entries == []


class TestStat:
    async def test_stat_success(self, s3_storage: S3Storage) -> None:
        mock_client = _make_s3_client()
        now = datetime.now(tz=timezone.utc)
        content = b"hello world"
        expected_hash = hashlib.sha256(content).hexdigest()

        mock_client.head_object = AsyncMock(
            return_value={"ContentLength": len(content), "LastModified": now}
        )
        mock_client.get_object = AsyncMock(
            return_value={"Body": _make_body(content)}
        )

        with patch.object(
            s3_storage._session, "client", return_value=_AsyncContextManager(mock_client)
        ):
            result = await s3_storage.stat("notes/hello.md")

        assert result.size == len(content)
        assert result.modified == now
        assert result.content_hash == expected_hash

    async def test_stat_not_found(self, s3_storage: S3Storage) -> None:
        mock_client = _make_s3_client()
        error_response = {"Error": {"Code": "404"}}
        exc = Exception("not found")
        exc.response = error_response  # type: ignore[attr-defined]
        mock_client.head_object = AsyncMock(side_effect=exc)

        with patch.object(
            s3_storage._session, "client", return_value=_AsyncContextManager(mock_client)
        ):
            with pytest.raises(FileNotFoundError):
                await s3_storage.stat("missing.md")
