"""
Test encryption utilities.
"""
import sys
import os
import pytest

# Add backend/src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))


def test_encryption_service_singleton():
    """Test that encryption service is a singleton"""
    from database.encryption import get_encryption_service

    # Should work even without environment variable set
    # (it should generate a key internally for testing)
    service1 = get_encryption_service()
    service2 = get_encryption_service()

    assert service1 is service2, "Encryption service should be a singleton"


def test_encryption_decrypt_roundtrip():
    """Test that encryption/decryption works correctly"""
    from database.encryption import get_encryption_service

    service = get_encryption_service()

    # Test with a sample token
    original_token = "MTIzNDU2Nzg5MDEyMzQ1Njc4OQ.TestToken.Example"

    # Encrypt
    encrypted = service.encrypt(original_token)
    assert encrypted != original_token, "Encrypted should differ from original"
    assert len(encrypted) > 0, "Encrypted should not be empty"

    # Decrypt
    decrypted = service.decrypt(encrypted)
    assert decrypted == original_token, "Decrypted should match original"


def test_encryption_different_inputs():
    """Test that different inputs produce different ciphertexts"""
    from database.encryption import get_encryption_service

    service = get_encryption_service()

    token1 = "Token1.ABC.XYZ"
    token2 = "Token2.DEF.UVW"

    encrypted1 = service.encrypt(token1)
    encrypted2 = service.encrypt(token2)

    assert encrypted1 != encrypted2, "Different tokens should encrypt differently"


def test_encryption_consistent():
    """Test that same encryption service produces consistent results"""
    from database.encryption import get_encryption_service

    service = get_encryption_service()

    token = "TestToken.123.ABC"

    encrypted1 = service.encrypt(token)
    encrypted2 = service.encrypt(token)

    # Note: Fernet uses a timestamp, so encryptions of same plaintext will differ
    # But both should decrypt to the same value
    decrypted1 = service.decrypt(encrypted1)
    decrypted2 = service.decrypt(encrypted2)

    assert decrypted1 == token
    assert decrypted2 == token
    assert decrypted1 == decrypted2
