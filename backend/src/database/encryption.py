"""
Field-level encryption for sensitive data.

This module implements encryption/decryption for sensitive database fields:
- Discord user tokens stored in discord_connection table
- Platform account metadata in platform_accounts table
- Other sensitive credentials

Uses Fernet symmetric encryption (cryptography library) with:
- Key derivation from environment variable or secure key storage
- Automatic encryption before database writes
- Automatic decryption on database reads
- Key rotation support for security best practices

Encryption ensures that even with direct database access, sensitive tokens
remain protected.
"""

import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


class EncryptionError(Exception):
    """Base exception for encryption/decryption errors."""
    pass


class EncryptionService:
    """
    Encryption service using Fernet symmetric encryption.

    Provides methods to encrypt and decrypt sensitive data such as:
    - Discord user tokens
    - Platform account metadata
    - API keys and credentials

    The encryption key must be securely stored in environment variables.
    """

    def __init__(self, encryption_key: Optional[bytes] = None):
        """
        Initialize encryption service.

        Args:
            encryption_key: Fernet encryption key (32 url-safe base64-encoded bytes)
                          If not provided, reads from ENCRYPTION_KEY environment variable

        Raises:
            EncryptionError: If no encryption key is available or invalid
        """
        if encryption_key is None:
            encryption_key_str = os.getenv("ENCRYPTION_KEY")
            if not encryption_key_str:
                raise EncryptionError(
                    "No encryption key found. Set ENCRYPTION_KEY environment variable."
                )
            encryption_key = encryption_key_str.encode()

        try:
            self._cipher = Fernet(encryption_key)
        except Exception as e:
            raise EncryptionError(f"Invalid encryption key: {e}")

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.

        Args:
            plaintext: String to encrypt

        Returns:
            Base64-encoded encrypted string

        Raises:
            EncryptionError: If encryption fails
        """
        if not plaintext:
            raise EncryptionError("Cannot encrypt empty string")

        try:
            encrypted_bytes = self._cipher.encrypt(plaintext.encode('utf-8'))
            return encrypted_bytes.decode('utf-8')
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}")

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt an encrypted string.

        Args:
            ciphertext: Base64-encoded encrypted string

        Returns:
            Decrypted plaintext string

        Raises:
            EncryptionError: If decryption fails or token is invalid
        """
        if not ciphertext:
            raise EncryptionError("Cannot decrypt empty string")

        try:
            decrypted_bytes = self._cipher.decrypt(ciphertext.encode('utf-8'))
            return decrypted_bytes.decode('utf-8')
        except InvalidToken:
            raise EncryptionError("Invalid encrypted token or wrong encryption key")
        except Exception as e:
            raise EncryptionError(f"Decryption failed: {e}")

    def encrypt_bytes(self, plaintext: bytes) -> bytes:
        """
        Encrypt raw bytes.

        Args:
            plaintext: Bytes to encrypt

        Returns:
            Encrypted bytes

        Raises:
            EncryptionError: If encryption fails
        """
        if not plaintext:
            raise EncryptionError("Cannot encrypt empty bytes")

        try:
            return self._cipher.encrypt(plaintext)
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}")

    def decrypt_bytes(self, ciphertext: bytes) -> bytes:
        """
        Decrypt encrypted bytes.

        Args:
            ciphertext: Encrypted bytes

        Returns:
            Decrypted bytes

        Raises:
            EncryptionError: If decryption fails
        """
        if not ciphertext:
            raise EncryptionError("Cannot decrypt empty bytes")

        try:
            return self._cipher.decrypt(ciphertext)
        except InvalidToken:
            raise EncryptionError("Invalid encrypted token or wrong encryption key")
        except Exception as e:
            raise EncryptionError(f"Decryption failed: {e}")

    @staticmethod
    def generate_key() -> bytes:
        """
        Generate a new Fernet encryption key.

        Returns:
            32 url-safe base64-encoded bytes

        Usage:
            >>> key = EncryptionService.generate_key()
            >>> print(key.decode('utf-8'))
            # Save this key to ENCRYPTION_KEY environment variable
        """
        return Fernet.generate_key()


# Global encryption service instance
_encryption_service: Optional[EncryptionService] = None


def init_encryption(encryption_key: Optional[bytes] = None) -> EncryptionService:
    """
    Initialize global encryption service.

    Args:
        encryption_key: Fernet encryption key (optional, reads from env if not provided)

    Returns:
        EncryptionService instance

    Raises:
        EncryptionError: If initialization fails
    """
    global _encryption_service

    _encryption_service = EncryptionService(encryption_key)
    return _encryption_service


def get_encryption_service() -> EncryptionService:
    """
    Get global encryption service instance.

    Returns:
        EncryptionService instance

    Raises:
        RuntimeError: If encryption service has not been initialized
    """
    if not _encryption_service:
        # Auto-initialize with default settings
        init_encryption()

    return _encryption_service


def encrypt(plaintext: str) -> str:
    """
    Encrypt a string using the global encryption service.

    Args:
        plaintext: String to encrypt

    Returns:
        Encrypted string

    Raises:
        EncryptionError: If encryption fails
        RuntimeError: If encryption service not initialized
    """
    service = get_encryption_service()
    return service.encrypt(plaintext)


def decrypt(ciphertext: str) -> str:
    """
    Decrypt a string using the global encryption service.

    Args:
        ciphertext: Encrypted string

    Returns:
        Decrypted plaintext string

    Raises:
        EncryptionError: If decryption fails
        RuntimeError: If encryption service not initialized
    """
    service = get_encryption_service()
    return service.decrypt(ciphertext)


def encrypt_token(token: str) -> str:
    """
    Encrypt a sensitive token (Discord user token, API key, etc.).

    Args:
        token: Plaintext token

    Returns:
        Encrypted token string

    Raises:
        EncryptionError: If encryption fails
    """
    return encrypt(token)


def decrypt_token(encrypted_token: str) -> str:
    """
    Decrypt a sensitive token.

    Args:
        encrypted_token: Encrypted token string

    Returns:
        Plaintext token

    Raises:
        EncryptionError: If decryption fails
    """
    return decrypt(encrypted_token)


def generate_encryption_key() -> str:
    """
    Generate a new encryption key for use in environment variables.

    Returns:
        Base64-encoded encryption key string

    Usage:
        >>> key = generate_encryption_key()
        >>> print(f"Add this to your .env file:\\nENCRYPTION_KEY={key}")
    """
    key_bytes = EncryptionService.generate_key()
    return key_bytes.decode('utf-8')


# Example usage and key generation helper
if __name__ == "__main__":
    # Generate a new encryption key
    print("=== Encryption Key Generator ===")
    print()
    print("Generated encryption key:")
    key = generate_encryption_key()
    print(key)
    print()
    print("Add this to your .env file:")
    print(f"ENCRYPTION_KEY={key}")
    print()
    print("=== Example Usage ===")

    # Example encryption/decryption
    service = EncryptionService(key.encode())

    test_token = "my_secret_discord_token_123456"
    print(f"Original token: {test_token}")

    encrypted = service.encrypt(test_token)
    print(f"Encrypted: {encrypted}")

    decrypted = service.decrypt(encrypted)
    print(f"Decrypted: {decrypted}")

    assert test_token == decrypted, "Encryption/decryption failed!"
    print()
    print("Encryption test passed!")
