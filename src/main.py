from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
import json

from src.database import Database, init_db
from src.models import KeyCreate, OTPResponse, KeyGenerate, KeyGenerateResponse
from src.crud import (
    create_key,
    get_key_by_name,
    list_keys,
    delete_key,
    get_key_with_secret,
)
from src.otp import generate_otp, generate_secret, generate_otpauth_uri
from src.qr import parse_qr_image

# Initialize FastAPI app
app = FastAPI(
    title="Auth-Helper API",
    description="Local REST API for generating TOTP and HOTP codes",
    version="1.0.0",
)

# Initialize database
db = Database()


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


@app.post("/keys/generate", status_code=201)
async def generate_key_endpoint(key_gen: KeyGenerate):
    """Generate a new TOTP or HOTP secret and store it.

    Args:
        key_gen: KeyGenerate model with key configuration.

    Returns:
        Generated key details (including secret for initial setup).

    Raises:
        400: Validation error
        409: Name already exists
    """
    try:
        # Generate a random secret
        secret = generate_secret()

        # Create KeyCreate with the generated secret
        key_create = KeyCreate(
            name=key_gen.name,
            secret=secret,
            type=key_gen.type,
            algorithm=key_gen.algorithm,
            digits=key_gen.digits,
            period=key_gen.period if key_gen.type == "totp" else None,
            counter=key_gen.counter if key_gen.type == "hotp" else None,
            issuer=key_gen.issuer,
        )

        # Store the key
        created_key = create_key(db, key_create)

        # Generate otpauth URI
        otpauth_uri = generate_otpauth_uri(
            secret=secret,
            name=key_gen.name,
            type_=key_gen.type,
            algorithm=key_gen.algorithm,
            digits=key_gen.digits,
            issuer=key_gen.issuer,
            period=key_gen.period if key_gen.type == "totp" else None,
            counter=key_gen.counter if key_gen.type == "hotp" else None,
        )

        # Return the response with secret and URI (for initial setup)
        return KeyGenerateResponse(
            name=created_key["name"],
            type=created_key["type"],
            secret=secret,
            otpauth_uri=otpauth_uri,
            algorithm=created_key["algorithm"],
            digits=created_key["digits"],
            issuer=created_key.get("issuer"),
            created_at=created_key["created_at"],
            period=created_key.get("period"),
            counter=created_key.get("counter"),
        )
    except ValueError as e:
        if "already exists" in str(e):
            raise HTTPException(status_code=409, detail=str(e))
        raise


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


@app.get("/keys/{name}/otp")
async def get_otp(name: str):
    """Get the current OTP code for a key.

    Args:
        name: Key name.

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


@app.delete("/keys/{name}", status_code=204)
async def delete_key_endpoint(name: str):
    """Delete a registered key.

    Args:
        name: Key name.

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
