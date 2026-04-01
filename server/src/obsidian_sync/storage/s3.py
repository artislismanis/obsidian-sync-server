"""S3 storage backend using aioboto3."""

import hashlib
from datetime import datetime, timezone

import aioboto3

from obsidian_sync.storage.base import StorageBackend, StorageEntry, StorageStat


class S3Storage:
    """Stores vault files in an S3 bucket."""

    def __init__(
        self,
        bucket: str,
        prefix: str = "",
        region: str = "us-east-1",
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
    ) -> None:
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.region = region
        self._session = aioboto3.Session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region,
        )

    def _key(self, path: str) -> str:
        """Build the full S3 key from a vault-relative path."""
        if self.prefix:
            return f"{self.prefix}/{path}"
        return path

    async def read(self, path: str) -> bytes:
        """Read a file from S3. Raises FileNotFoundError if missing."""
        key = self._key(path)
        async with self._session.client("s3") as s3:
            try:
                response = await s3.get_object(Bucket=self.bucket, Key=key)
                return await response["Body"].read()
            except s3.exceptions.NoSuchKey:
                raise FileNotFoundError(f"File not found: {path}")
            except Exception as exc:
                # ClientError with 404 status
                error_code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
                if error_code in ("NoSuchKey", "404"):
                    raise FileNotFoundError(f"File not found: {path}")
                raise

    async def write(self, path: str, data: bytes, content_hash: str = "") -> None:
        """Write data to S3."""
        key = self._key(path)
        async with self._session.client("s3") as s3:
            await s3.put_object(Bucket=self.bucket, Key=key, Body=data)

    async def delete(self, path: str) -> None:
        """Delete a file from S3."""
        key = self._key(path)
        async with self._session.client("s3") as s3:
            await s3.delete_object(Bucket=self.bucket, Key=key)

    async def exists(self, path: str) -> bool:
        """Check if a file exists in S3."""
        key = self._key(path)
        async with self._session.client("s3") as s3:
            try:
                await s3.head_object(Bucket=self.bucket, Key=key)
                return True
            except Exception:
                return False

    async def list(self, prefix: str = "") -> list[StorageEntry]:
        """List objects under a prefix in S3."""
        s3_prefix = self._key(prefix) if prefix else (self.prefix + "/" if self.prefix else "")
        # Ensure trailing slash for prefix listing
        if s3_prefix and not s3_prefix.endswith("/"):
            s3_prefix += "/"

        entries: list[StorageEntry] = []
        async with self._session.client("s3") as s3:
            paginator = s3.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=self.bucket, Prefix=s3_prefix):
                for obj in page.get("Contents", []):
                    full_key: str = obj["Key"]
                    # Strip our prefix to get vault-relative path
                    if self.prefix:
                        rel_path = full_key[len(self.prefix) + 1 :]
                    else:
                        rel_path = full_key
                    if not rel_path:
                        continue
                    entries.append(
                        StorageEntry(
                            path=rel_path,
                            size=obj.get("Size", 0),
                            is_dir=False,
                            modified=obj.get("LastModified"),
                        )
                    )
        return sorted(entries, key=lambda e: e.path)

    async def stat(self, path: str) -> StorageStat:
        """Get metadata for a file in S3. Raises FileNotFoundError if missing."""
        key = self._key(path)
        async with self._session.client("s3") as s3:
            try:
                response = await s3.head_object(Bucket=self.bucket, Key=key)
            except Exception as exc:
                error_code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
                if error_code in ("NoSuchKey", "404"):
                    raise FileNotFoundError(f"File not found: {path}")
                raise

            # Read content to compute hash
            get_resp = await s3.get_object(Bucket=self.bucket, Key=key)
            data = await get_resp["Body"].read()
            content_hash = hashlib.sha256(data).hexdigest()

            return StorageStat(
                size=response.get("ContentLength", 0),
                modified=response.get("LastModified"),
                content_hash=content_hash,
            )
