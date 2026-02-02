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

    response = client.get("/keys/otp", params={"name": "test"})
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

    response = client.get("/keys/otp", params={"name": "test"})
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "hotp"
    assert "code" in data
    assert data["counter"] == 0


def test_get_otp_not_found(client):
    """Test getting OTP for non-existent key."""
    response = client.get("/keys/otp", params={"name": "nonexistent"})
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

    response = client.delete("/keys", params={"name": "github"})
    assert response.status_code == 204

    # Verify key is deleted
    response = client.get("/keys/otp", params={"name": "github"})
    assert response.status_code == 404


def test_delete_key_not_found(client):
    """Test deleting non-existent key."""
    response = client.delete("/keys", params={"name": "nonexistent"})
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
    response1 = client.get("/keys/otp", params={"name": "test"})
    assert response1.json()["counter"] == 0

    # Second OTP
    response2 = client.get("/keys/otp", params={"name": "test"})
    assert response2.json()["counter"] == 1

    # Verify counter in list
    list_response = client.get("/keys")
    keys = list_response.json()
    test_key = [k for k in keys if k["name"] == "test"][0]
    assert test_key["counter"] == 2


# =============================================================================
# Party A Endpoints: Generate and Verify
# =============================================================================


def test_generate_key_totp(client):
    """Test generating a new TOTP key."""
    response = client.post(
        "/keys/generate",
        json={
            "name": "bob",
            "type": "totp",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "bob"
    assert data["type"] == "totp"
    assert "secret" in data  # Secret SHOULD be in response for Party A
    assert "uri" in data  # otpauth:// URI for QR code generation
    assert data["uri"].startswith("otpauth://totp/")
    assert len(data["secret"]) >= 16  # Base32 secret should be at least 16 chars


def test_generate_key_hotp(client):
    """Test generating a new HOTP key."""
    response = client.post(
        "/keys/generate",
        json={
            "name": "alice",
            "type": "hotp",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "alice"
    assert data["type"] == "hotp"
    assert "secret" in data
    assert "uri" in data
    assert data["uri"].startswith("otpauth://hotp/")


def test_generate_key_with_issuer(client):
    """Test generating a key with custom issuer."""
    response = client.post(
        "/keys/generate",
        json={
            "name": "charlie",
            "type": "totp",
            "issuer": "MyApp",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["issuer"] == "MyApp"
    assert "MyApp" in data["uri"]


def test_generate_key_duplicate(client):
    """Test generating a key with duplicate name fails."""
    client.post(
        "/keys/generate",
        json={"name": "bob", "type": "totp"},
    )

    response = client.post(
        "/keys/generate",
        json={"name": "bob", "type": "totp"},
    )
    assert response.status_code == 409


def test_verify_otp_valid_totp(client):
    """Test verifying a valid TOTP code."""
    import pyotp

    # Generate a key
    gen_response = client.post(
        "/keys/generate",
        json={"name": "bob", "type": "totp"},
    )
    secret = gen_response.json()["secret"]

    # Generate a valid OTP using the same secret
    totp = pyotp.TOTP(secret)
    valid_code = totp.now()

    # Verify
    response = client.post(
        "/keys/verify",
        json={"name": "bob", "code": valid_code},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True


def test_verify_otp_invalid_code(client):
    """Test verifying an invalid OTP code."""
    client.post(
        "/keys/generate",
        json={"name": "bob", "type": "totp"},
    )

    response = client.post(
        "/keys/verify",
        json={"name": "bob", "code": "000000"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False


def test_verify_otp_not_found(client):
    """Test verifying OTP for non-existent key."""
    response = client.post(
        "/keys/verify",
        json={"name": "nonexistent", "code": "123456"},
    )
    assert response.status_code == 404


def test_verify_otp_valid_hotp(client):
    """Test verifying a valid HOTP code."""
    import pyotp

    # Generate a key
    gen_response = client.post(
        "/keys/generate",
        json={"name": "alice", "type": "hotp"},
    )
    secret = gen_response.json()["secret"]

    # Generate a valid OTP using the same secret at counter 0
    hotp = pyotp.HOTP(secret)
    valid_code = hotp.at(0)

    # Verify
    response = client.post(
        "/keys/verify",
        json={"name": "alice", "code": valid_code},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True


def test_verify_hotp_increments_counter(client):
    """Test that verifying HOTP increments the counter."""
    import pyotp

    # Generate a key
    gen_response = client.post(
        "/keys/generate",
        json={"name": "alice", "type": "hotp"},
    )
    secret = gen_response.json()["secret"]

    hotp = pyotp.HOTP(secret)

    # Verify code at counter 0
    response = client.post(
        "/keys/verify",
        json={"name": "alice", "code": hotp.at(0)},
    )
    assert response.json()["valid"] is True

    # Counter 0 should no longer work
    response = client.post(
        "/keys/verify",
        json={"name": "alice", "code": hotp.at(0)},
    )
    assert response.json()["valid"] is False

    # Counter 1 should now work
    response = client.post(
        "/keys/verify",
        json={"name": "alice", "code": hotp.at(1)},
    )
    assert response.json()["valid"] is True


def test_verify_hotp_look_ahead_window(client):
    """Test that HOTP verification allows a look-ahead window."""
    import pyotp

    # Generate a key
    gen_response = client.post(
        "/keys/generate",
        json={"name": "alice", "type": "hotp"},
    )
    secret = gen_response.json()["secret"]

    hotp = pyotp.HOTP(secret)

    # Verify code at counter 2 (skipping 0 and 1) - should work within window
    response = client.post(
        "/keys/verify",
        json={"name": "alice", "code": hotp.at(2)},
    )
    assert response.json()["valid"] is True

    # Counter should now be at 3
    response = client.post(
        "/keys/verify",
        json={"name": "alice", "code": hotp.at(3)},
    )
    assert response.json()["valid"] is True
