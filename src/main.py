from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
import json
import os

from src.database import Database, init_db
from src.models import (
    KeyCreate,
    OTPResponse,
    KeyGenerateRequest,
    KeyGenerateResponse,
    OTPVerifyRequest,
    OTPVerifyResponse,
)
from src.crud import (
    create_key,
    get_key_by_name,
    list_keys,
    delete_key,
    get_key_with_secret,
)
from src.otp import generate_otp, verify_otp
import pyotp
from src.qr import parse_qr_image

# Initialize FastAPI app
app = FastAPI(
    title="Auth-Helper API",
    description="Local REST API for generating TOTP and HOTP codes",
    version="1.0.0",
)

# Initialize database (use DATA_DIR env var for Docker volume persistence)
db_path = os.path.join(os.environ.get("DATA_DIR", "."), "auth_helper.db")
db = Database(db_path)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db(db)


@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    """Handle ValueError exceptions."""
    if "already exists" in str(exc):
        return JSONResponse(
            status_code=409,
            content={"detail": str(exc)},
        )
    elif "not found" in str(exc):
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc)},
        )
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/keys", status_code=201)
async def create_key_endpoint(key: KeyCreate):
    """Create a new key manually.

    Args:
        key: KeyCreate model with key details.

    Returns:
        Created key details (excluding secret).

    Raises:
        400: Validation error
        409: Name already exists
    """
    try:
        result = create_key(db, key)
        return result
    except ValueError as e:
        if "already exists" in str(e):
            raise HTTPException(status_code=409, detail=str(e))
        raise


@app.post("/keys/qr", status_code=201)
async def create_key_from_qr(
    file: UploadFile = File(...), name: str = Form(None)
):
    """Register a key by uploading a QR code image.

    Args:
        file: QR code image file.
        name: Optional name override for the key.

    Returns:
        Created key details (excluding secret).

    Raises:
        400: Invalid image or QR code
        409: Name already exists
    """
    try:
        # Read image bytes
        image_bytes = await file.read()

        # Parse QR code
        qr_data = parse_qr_image(image_bytes)

        # Use provided name or fall back to QR code name
        key_name = name or qr_data.get("name")
        if not key_name:
            raise ValueError("Name must be provided or encoded in QR code")

        # Create KeyCreate model from QR data
        key_data = KeyCreate(
            name=key_name,
            secret=qr_data["secret"],
            type=qr_data["type"],
            algorithm=qr_data["algorithm"],
            digits=qr_data["digits"],
            period=qr_data["period"],
            counter=qr_data["counter"],
            issuer=qr_data["issuer"],
        )

        # Create the key
        result = create_key(db, key_data)
        return result
    except ValueError as e:
        error_msg = str(e)
        if "already exists" in error_msg:
            raise HTTPException(status_code=409, detail=error_msg)
        elif "No QR code" in error_msg or "does not contain" in error_msg or "Invalid image" in error_msg:
            raise HTTPException(status_code=400, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)


@app.get("/keys/otp")
async def get_otp(name: str):
    """Get the current OTP code for a key.

    Args:
        name: Key name (query parameter).

    Returns:
        OTP code and metadata.

    Raises:
        404: Key not found
    """
    try:
        result = generate_otp(db, name)
        return result
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise


@app.get("/keys")
async def list_all_keys():
    """List all registered keys.

    Returns:
        List of keys (excluding secrets).
    """
    return list_keys(db)


@app.delete("/keys", status_code=204)
async def delete_key_endpoint(name: str):
    """Delete a registered key.

    Args:
        name: Key name (query parameter).

    Raises:
        404: Key not found
    """
    try:
        delete_key(db, name)
        return None
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise


# =============================================================================
# Party A Endpoints: Generate and Verify
# =============================================================================


@app.post("/keys/generate", status_code=201, response_model=KeyGenerateResponse)
async def generate_key_endpoint(request: KeyGenerateRequest):
    """Generate a new key with a random secret (Party A).

    Creates a new key with a randomly generated secret and returns
    both the secret and an otpauth:// URI for sharing with Party B.

    Args:
        request: KeyGenerateRequest with key configuration.

    Returns:
        Key details including secret and URI.

    Raises:
        409: Name already exists
    """
    # Generate a random secret
    secret = pyotp.random_base32()

    # Build the otpauth:// URI
    if request.type == "totp":
        otp = pyotp.TOTP(secret, digits=request.digits, interval=request.period)
        uri = otp.provisioning_uri(name=request.name, issuer_name=request.issuer)
        counter = None
    else:  # hotp
        otp = pyotp.HOTP(secret, digits=request.digits)
        uri = otp.provisioning_uri(name=request.name, issuer_name=request.issuer, initial_count=0)
        counter = 0

    # Create the key in the database
    key_data = KeyCreate(
        name=request.name,
        secret=secret,
        type=request.type,
        algorithm=request.algorithm,
        digits=request.digits,
        period=request.period if request.type == "totp" else None,
        counter=counter,
        issuer=request.issuer,
    )

    try:
        create_key(db, key_data)
    except ValueError as e:
        if "already exists" in str(e):
            raise HTTPException(status_code=409, detail=str(e))
        raise

    return KeyGenerateResponse(
        name=request.name,
        type=request.type,
        algorithm=request.algorithm,
        digits=request.digits,
        period=request.period if request.type == "totp" else None,
        counter=counter,
        issuer=request.issuer,
        secret=secret,
        uri=uri,
    )


@app.post("/keys/verify", response_model=OTPVerifyResponse)
async def verify_otp_endpoint(request: OTPVerifyRequest):
    """Verify an OTP code against a stored key (Party A).

    Args:
        request: OTPVerifyRequest with key name and code.

    Returns:
        Verification result (valid: true/false).

    Raises:
        404: Key not found
    """
    try:
        result = verify_otp(db, request.name, request.code)
        return result
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise
