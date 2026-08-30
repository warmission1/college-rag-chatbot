import pytest
from backend.app.auth.security import get_password_hash, verify_password, create_access_token, decode_access_token


def test_password_hashing():
    raw_password = "CollegeSecurePassword2026!"
    hashed = get_password_hash(raw_password)
    assert hashed != raw_password
    assert verify_password(raw_password, hashed) is True
    assert verify_password("WrongPassword123", hashed) is False


def test_jwt_token_creation_and_decoding():
    user_id = "test-user-uuid-12345"
    token = create_access_token(user_id)
    assert isinstance(token, str)
    assert len(token) > 20
    
    decoded_id = decode_access_token(token)
    assert decoded_id == user_id


def test_jwt_invalid_token():
    assert decode_access_token("invalid.jwt.token") is None
