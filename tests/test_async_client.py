"""Tests for async_client.py"""

import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from async_client import AsyncGoProClient


def test_async_client_instantiation():
    with tempfile.TemporaryDirectory() as tmpdir:
        client = AsyncGoProClient("test_token", "test_user", Path(tmpdir))

        assert client.auth_token == "test_token"
        assert client.user_id == "test_user"
        assert client.HOST == "https://api.gopro.com"


def test_async_client_concurrency_settings():
    with tempfile.TemporaryDirectory() as tmpdir:
        client = AsyncGoProClient("test_token", "test_user", Path(tmpdir))

        assert client.MAX_CONCURRENT_METADATA == 50
        assert client.MAX_CONCURRENT_DOWNLOADS == 5
        assert client.DOWNLOAD_CHUNK_SIZE == 1024 * 1024


def test_async_client_cookies():
    with tempfile.TemporaryDirectory() as tmpdir:
        client = AsyncGoProClient("test_token", "test_user", Path(tmpdir))
        cookies = client._get_cookies()

        assert cookies["gp_access_token"] == "test_token"
        assert cookies["gp_user_id"] == "test_user"


def test_async_client_headers():
    with tempfile.TemporaryDirectory() as tmpdir:
        client = AsyncGoProClient("test_token", "test_user", Path(tmpdir))
        headers = client._get_headers()

        assert "Accept" in headers
        assert "gopro" in headers["Accept"]


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
