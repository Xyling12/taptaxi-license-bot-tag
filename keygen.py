"""
License key generator for TapTaxi patches.

Algorithm: HMAC-SHA256(SECRET_KEY, device_id) → first 16 hex chars, uppercased.
Deterministic: same device_id always produces same code.
"""

import hmac
import hashlib


def generate_license(device_id: str, secret_key: str) -> str:
    """
    Generate a deterministic 16-character license code for a given device_id.

    Args:
        device_id: Unique device identifier sent by the driver.
        secret_key: Server-side secret (must match the key baked into the APK).

    Returns:
        16-character uppercase hex string, e.g. "A3F2D1C09E4B7856"
    """
    device_id = device_id.strip()
    h = hmac.new(
        secret_key.encode("utf-8"),
        device_id.encode("utf-8"),
        hashlib.sha256,
    )
    return h.hexdigest()[:16].upper()


def verify_license(device_id: str, code: str, secret_key: str) -> bool:
    """Check whether a code is valid for a given device_id."""
    expected = generate_license(device_id, secret_key)
    return hmac.compare_digest(expected, code.strip().upper())


if __name__ == "__main__":
    import os
    import sys

    secret = os.getenv("SECRET_KEY", "changeme")
    if len(sys.argv) < 2:
        print("Usage: python keygen.py <device_id>")
        sys.exit(1)

    device_id = sys.argv[1]
    code = generate_license(device_id, secret)
    print(f"Device:  {device_id}")
    print(f"License: {code}")
