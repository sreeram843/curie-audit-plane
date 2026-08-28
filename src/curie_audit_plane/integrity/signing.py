from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)


def generate_keypair() -> tuple[bytes, bytes]:
    key = Ed25519PrivateKey.generate()
    private_key = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    public_key = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return private_key, public_key


def sign_hex(message_hex: str, private_key: bytes) -> str:
    key = Ed25519PrivateKey.from_private_bytes(private_key)
    return key.sign(message_hex.encode("ascii")).hex()


def verify_signature(message_hex: str, signature_hex: str, public_key: bytes) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            bytes.fromhex(signature_hex),
            message_hex.encode("ascii"),
        )
    except (InvalidSignature, ValueError):
        return False
    return True
