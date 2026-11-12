"""Generate installation-local VAPID keys. Run privately, never commit the output."""

import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def generate():
    private = ec.generate_private_key(ec.SECP256R1())
    encode = lambda value: base64.urlsafe_b64encode(value).decode().rstrip("=")
    return {
        "PUSH_VAPID_PUBLIC_KEY": encode(
            private.public_key().public_bytes(
                serialization.Encoding.X962,
                serialization.PublicFormat.UncompressedPoint,
            )
        ),
        "PUSH_VAPID_PRIVATE_KEY": encode(
            private.private_numbers().private_value.to_bytes(32, "big")
        ),
        "PUSH_ENCRYPTION_KEY": Fernet.generate_key().decode(),
    }


if __name__ == "__main__":
    for key, value in generate().items():
        print(f"{key}={value}")
    print("# Set PUSH_VAPID_SUBJECT to a monitored mailto: contact address.")
