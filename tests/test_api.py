import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile
import qrcode
from io import BytesIO

from src.main import app
from src.database import Database, init_db
from src.crud import create_key
from src.models import KeyCreate

# Override database for testing
test_db = None


@pytest.fixture
def client():
    """Create test client with temporary database."""
    global test_db
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        test_db = Database(str(db_path))
        init_db(test_db)

        # Monkey patch the app's db
        import src.main
        original_db = src.main.db
        src.main.db = test_db

        client = TestClient(app)
        yield client

        # Restore original db
        src.main.db = original_db
        test_db.close()


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_key_post(client):
    """Test creating a key via POST."""
    response = client.post(
        "/keys",
        json={
            "name": "github",
            "secret": "JBSWY3DPEBLW64TMMQ======",
            "type": "totp",
            "algorithm": "sha1",
            "digits": 6,
            "period": 30,
            "issuer": "GitHub",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "github"
    assert data["type"] == "totp"
    assert "secret" not in data  # Secret should not be in response


def test_create_key_duplicate(client):
    """Test creating a key with duplicate name."""
    client.post(
        "/keys",
        json={
            "name": "github",
            "secret": "JBSWY3DPEBLW64TMMQ======",
            "type": "totp",
        },
    )

    # Try to create another with same name
    response = client.post(
        "/keys",
        json={
            "name": "github",
            "secret": "DIFFERENT_SECRET",
            "type": "totp",
        },
    )
    assert response.status_code == 409


def test_list_keys_empty(client):
    """Test listing keys when empty."""
    response = client.get("/keys")
    assert response.status_code == 200
    assert response.json() == []


def test_list_keys(client):
    """Test listing multiple keys."""
    # Create two keys
    client.post(
        "/keys",
        json={
            "name": "github",
            "secret": "JBSWY3DPEBLW64TMMQ======",
            "type": "totp",
        },
    )
    client.post(
        "/keys",
        json={
            "name": "aws",
            "secret": "JBSWY3DPEBLW64TMMQ======",
            "type": "hotp",
            "counter": 0,
        },
    )

    response = client.get("/keys")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    names = {key["name"] for key in data}
    assert names == {"github", "aws"}


def test_get_otp_totp(client):
    """Test getting TOTP code."""
    client.post(
        "/keys",
        json={
            "name": "test",
            "secret": "JBSWY3DPEBLW64TMMQ======",
            "type": "totp",
        },
    )

    response = client.get("/keys/test/otp")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "totp"
    assert "code" in data
    assert len(data["code"]) == 6
    assert "time_remaining" in data


def test_get_otp_hotp(client):
    """Test getting HOTP code."""
    client.post(
        "/keys",
        json={
            "name": "test",
            "secret": "JBSWY3DPEBLW64TMMQ======",
            "type": "hotp",
        },
    )

    response = client.get("/keys/test/otp")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "hotp"
    assert "code" in data
    assert data["counter"] == 0


def test_get_otp_not_found(client):
    """Test getting OTP for non-existent key."""
    response = client.get("/keys/nonexistent/otp")
    assert response.status_code == 404


def test_delete_key(client):
    """Test deleting a key."""
    client.post(
        "/keys",
        json={
            "name": "github",
            "secret": "JBSWY3DPEBLW64TMMQ======",
            "type": "totp",
        },
    )

    response = client.delete("/keys/github")
    assert response.status_code == 204

    # Verify key is deleted
    response = client.get("/keys/github/otp")
    assert response.status_code == 404


def test_delete_key_not_found(client):
    """Test deleting non-existent key."""
    response = client.delete("/keys/nonexistent")
    assert response.status_code == 404


def create_qr_image(data: str) -> bytes:
    """Create a QR code image."""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    img_bytes = BytesIO()
    img.save(img_bytes, format='PNG')
    return img_bytes.getvalue()


def test_create_key_from_qr(client):
    """Test creating a key from QR code."""
    qr_data = "otpauth://totp/GitHub:user?secret=JBSWY3DPEBLW64TMMQ======&issuer=GitHub"
    image_bytes = create_qr_image(qr_data)

    response = client.post(
        "/keys/qr",
        files={"file": ("qr.png", image_bytes, "image/png")},
        data={"name": "github"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "github"
    assert data["issuer"] == "GitHub"


def test_create_key_from_qr_without_name_override(client):
    """Test creating a key from QR code using QR-encoded name."""
    qr_data = "otpauth://totp/GitHub:user?secret=JBSWY3DPEBLW64TMMQ======&issuer=GitHub"
    image_bytes = create_qr_image(qr_data)

    response = client.post(
        "/keys/qr",
        files={"file": ("qr.png", image_bytes, "image/png")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "user"


def test_create_key_from_qr_invalid_image(client):
    """Test creating key from invalid image."""
    response = client.post(
        "/keys/qr",
        files={"file": ("invalid.png", b"not an image", "image/png")},
    )
    assert response.status_code == 400


def test_create_key_from_qr_no_qr(client):
    """Test creating key from image without QR code."""
    from PIL import Image
    img = Image.new('RGB', (100, 100), color='white')
    img_bytes = BytesIO()
    img.save(img_bytes, format='PNG')

    response = client.post(
        "/keys/qr",
        files={"file": ("blank.png", img_bytes.getvalue(), "image/png")},
    )
    assert response.status_code == 400


def test_hotp_counter_increments_on_get_otp(client):
    """Test that HOTP counter increments after each GET /otp."""
    client.post(
        "/keys",
        json={
            "name": "test",
            "secret": "JBSWY3DPEBLW64TMMQ======",
            "type": "hotp",
        },
    )

    # First OTP
    response1 = client.get("/keys/test/otp")
    assert response1.json()["counter"] == 0

    # Second OTP
    response2 = client.get("/keys/test/otp")
    assert response2.json()["counter"] == 1

    # Verify counter in list
    list_response = client.get("/keys")
    keys = list_response.json()
    test_key = [k for k in keys if k["name"] == "test"][0]
    assert test_key["counter"] == 2
