"""Tests for api.py"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api import GoProAPI


def test_api_instantiation():
    api = GoProAPI("test_token", "test_user")
    assert api.auth_token == "test_token"
    assert api.user_id == "test_user"
    assert api.HOST == "https://api.gopro.com"


def test_api_default_headers():
    api = GoProAPI("test_token", "test_user")
    headers = api.default_headers()

    assert "Accept" in headers
    assert "Accept-Language" in headers
    assert "User-Agent" in headers
    assert "gopro" in headers["Accept"]


def test_api_default_cookies():
    api = GoProAPI("test_token", "test_user")
    cookies = api.default_cookies()

    assert cookies["gp_access_token"] == "test_token"
    assert cookies["gp_user_id"] == "test_user"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
