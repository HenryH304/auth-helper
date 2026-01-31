import pytest
from PIL import Image
from io import BytesIO
import qrcode

from src.qr import parse_qr_image


def create_qr_image(data: str) -> bytes:
    """Create a QR code image with the given data.

    Args:
        data: Data to encode in QR code.

    Returns:
        Image bytes.
    """
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to bytes
    img_bytes = BytesIO()
    img.save(img_bytes, format='PNG')
    return img_bytes.getvalue()


def test_parse_totp_qr():
    """Test parsing TOTP QR code."""
    qr_data = "otpauth://totp/GitHub:user@example.com?secret=JBSWY3DPEBLW64TMMQ======&issuer=GitHub&algorithm=SHA1&digits=6&period=30"
    image_bytes = create_qr_image(qr_data)

    result = parse_qr_image(image_bytes)

    assert result['secret'] == "JBSWY3DPEBLW64TMMQ======"
    assert result['type'] == 'totp'
    assert result['algorithm'] == 'sha1'
    assert result['digits'] == 6
    assert result['period'] == 30
    assert result['issuer'] == 'GitHub'
    assert result['name'] == 'user@example.com'


def test_parse_hotp_qr():
    """Test parsing HOTP QR code."""
    qr_data = "otpauth://hotp/AWS:user@example.com?secret=JBSWY3DPEBLW64TMMQ======&issuer=AWS&counter=0"
    image_bytes = create_qr_image(qr_data)

    result = parse_qr_image(image_bytes)

    assert result['secret'] == "JBSWY3DPEBLW64TMMQ======"
    assert result['type'] == 'hotp'
    assert result['counter'] == 0
    assert result['issuer'] == 'AWS'
    assert result['name'] == 'user@example.com'


def test_parse_qr_invalid_image():
    """Test parsing invalid image."""
    invalid_bytes = b"not an image"

    with pytest.raises(ValueError, match="Invalid image format"):
        parse_qr_image(invalid_bytes)


def test_parse_qr_no_qr_code():
    """Test parsing image without QR code."""
    # Create a blank image
    img = Image.new('RGB', (100, 100), color='white')
    img_bytes = BytesIO()
    img.save(img_bytes, format='PNG')

    with pytest.raises(ValueError, match="No QR code found"):
        parse_qr_image(img_bytes.getvalue())


def test_parse_qr_invalid_uri():
    """Test parsing QR code with invalid URI."""
    # QR code with non-otpauth URI
    qr_data = "https://example.com"
    image_bytes = create_qr_image(qr_data)

    with pytest.raises(ValueError, match="does not contain valid otpauth"):
        parse_qr_image(image_bytes)


def test_parse_qr_sha256():
    """Test parsing QR code with SHA256."""
    qr_data = "otpauth://totp/Test:test?secret=JBSWY3DPEBLW64TMMQ======&algorithm=SHA256"
    image_bytes = create_qr_image(qr_data)

    result = parse_qr_image(image_bytes)

    assert result['algorithm'] == 'sha256'
