from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse, StreamingResponse
import json
import base64
import io
from PIL import Image
import qrcode
import pyotp

from src.database import Database, init_db
from src.models import KeyCreate, OTPResponse, KeyGenerate, KeyGenerateResponse, QRGenerate
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


@app.get("/keys/{name}/qr")
async def get_key_qr(name: str, request: Request):
    """Generate QR code for an existing key.

    Args:
        name: Key name.
        request: FastAPI Request object for accessing headers.

    Returns:
        QR code in requested format (base64 JSON or binary image).

    Raises:
        404: Key not found
    """
    try:
        # Get the key with secret (needed for otpauth URI generation)
        key = get_key_with_secret(db, name)
        if key is None:
            raise ValueError(f"Key '{name}' not found")

        # Generate otpauth URI
        otpauth_uri = generate_otpauth_uri(
            secret=key["secret"],
            name=name,
            type_=key["type"],
            algorithm=key["algorithm"],
            digits=key["digits"],
            issuer=key.get("issuer"),
            period=key.get("period"),
            counter=key.get("counter"),
        )

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(otpauth_uri)
        qr.make(fit=True)

        # Get Accept header
        accept_header = request.headers.get("accept", "application/json")

        # Determine format from Accept header
        if "image/png" in accept_header:
            img = qr.make_image(fill_color="black", back_color="white")
            img_bytes = io.BytesIO()
            img.save(img_bytes, format="PNG")
            img_bytes.seek(0)
            return StreamingResponse(
                img_bytes,
                media_type="image/png",
            )
        elif "image/jpeg" in accept_header:
            img = qr.make_image(fill_color="black", back_color="white")
            img_bytes = io.BytesIO()
            img.save(img_bytes, format="JPEG", quality=85)
            img_bytes.seek(0)
            return StreamingResponse(
                img_bytes,
                media_type="image/jpeg",
            )
        else:
            # Default to base64 JSON
            img = qr.make_image(fill_color="black", back_color="white")
            img_bytes = io.BytesIO()
            img.save(img_bytes, format="PNG")
            img_base64 = base64.b64encode(img_bytes.getvalue()).decode()
            return {
                "qr_code": img_base64,
                "format": "png",
            }

    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise


@app.post("/qr/generate")
async def generate_qr_endpoint(qr_gen: QRGenerate, request: Request):
    """Generate QR code from raw OTP parameters without storing.

    Args:
        qr_gen: QRGenerate model with secret and OTP parameters.
        request: FastAPI Request object for accessing headers.

    Returns:
        QR code in requested format (base64 JSON or binary image).

    Raises:
        400: Invalid parameters or invalid secret
    """
    try:
        # Validate secret is valid base32
        try:
            # Pyotp will validate the base32
            test_totp = pyotp.TOTP(qr_gen.secret)
        except Exception as e:
            raise ValueError(f"Invalid secret: {str(e)}")

        # Generate otpauth URI
        otpauth_uri = generate_otpauth_uri(
            secret=qr_gen.secret,
            name=qr_gen.name,
            type_=qr_gen.type,
            algorithm=qr_gen.algorithm,
            digits=qr_gen.digits,
            issuer=qr_gen.issuer,
            period=qr_gen.period if qr_gen.type == "totp" else None,
            counter=qr_gen.counter if qr_gen.type == "hotp" else None,
        )

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(otpauth_uri)
        qr.make(fit=True)

        # Get Accept header
        accept_header = request.headers.get("accept", "application/json")

        # Determine format from Accept header
        if "image/png" in accept_header:
            img = qr.make_image(fill_color="black", back_color="white")
            img_bytes = io.BytesIO()
            img.save(img_bytes, format="PNG")
            img_bytes.seek(0)
            return StreamingResponse(
                img_bytes,
                media_type="image/png",
            )
        elif "image/jpeg" in accept_header:
            img = qr.make_image(fill_color="black", back_color="white")
            img_bytes = io.BytesIO()
            img.save(img_bytes, format="JPEG", quality=85)
            img_bytes.seek(0)
            return StreamingResponse(
                img_bytes,
                media_type="image/jpeg",
            )
        else:
            # Default to base64 JSON
            img = qr.make_image(fill_color="black", back_color="white")
            img_bytes = io.BytesIO()
            img.save(img_bytes, format="PNG")
            img_base64 = base64.b64encode(img_bytes.getvalue()).decode()
            return {
                "qr_code": img_base64,
                "format": "png",
            }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
