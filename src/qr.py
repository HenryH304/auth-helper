import hashlib
import pyotp
from pyzbar.pyzbar import decode
from PIL import Image
from io import BytesIO
from typing import Dict, Any


def parse_qr_image(image_bytes: bytes) -> Dict[str, Any]:
    """Parse QR code image and extract otpauth:// URI.

    Args:
        image_bytes: Image file bytes.

    Returns:
        Dictionary with parsed key details from URI.

    Raises:
        ValueError: If no QR code found or invalid otpauth:// URI.
    """
    try:
        image = Image.open(BytesIO(image_bytes))
    except Exception as e:
        raise ValueError(f"Invalid image format: {str(e)}")

    # Decode QR codes
    qr_codes = decode(image)

    if not qr_codes:
        raise ValueError("No QR code found in image")

    # Get first QR code data
    qr_data = qr_codes[0].data.decode('utf-8')

    # Parse otpauth:// URI
    if not qr_data.startswith('otpauth://'):
        raise ValueError("QR code does not contain valid otpauth:// URI")

    try:
        parsed = pyotp.parse_uri(qr_data)
    except Exception as e:
        raise ValueError(f"Failed to parse otpauth:// URI: {str(e)}")

    # Extract algorithm from digest
    if parsed.digest == hashlib.sha1:
        algorithm = 'sha1'
    elif parsed.digest == hashlib.sha256:
        algorithm = 'sha256'
    elif parsed.digest == hashlib.sha512:
        algorithm = 'sha512'
    else:
        algorithm = 'sha1'  # default

    # Extract counter for HOTP
    counter = None
    if isinstance(parsed, pyotp.HOTP):
        counter = parsed.initial_count

    # Extract details from parsed URI
    return {
        'secret': parsed.secret,
        'type': 'totp' if isinstance(parsed, pyotp.TOTP) else 'hotp',
        'algorithm': algorithm,
        'digits': parsed.digits,
        'period': parsed.interval if isinstance(parsed, pyotp.TOTP) else None,
        'counter': counter,
        'issuer': parsed.issuer,
        'name': parsed.name,
    }
