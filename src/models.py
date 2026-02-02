from typing import Literal, Optional

from pydantic import BaseModel, Field


class KeyCreate(BaseModel):
    """Model for creating a new key."""

    name: str = Field(..., description="Unique name for the key")
    secret: str = Field(..., description="Base32-encoded secret")
    type: Literal["totp", "hotp"] = Field(..., description="Type of OTP")
    algorithm: Literal["sha1", "sha256", "sha512"] = Field(
        default="sha1", description="HMAC algorithm"
    )
    digits: Literal[6, 8] = Field(default=6, description="Number of digits in OTP")
    period: Optional[int] = Field(
        default=30, description="Period in seconds for TOTP (ignored for HOTP)"
    )
    counter: Optional[int] = Field(default=None, description="Counter for HOTP")
    issuer: Optional[str] = Field(default=None, description="Issuer name")

    def __init__(self, **data):
        """Custom initialization to set defaults based on type."""
        super().__init__(**data)
        # For HOTP, default counter to 0 if not provided
        if self.type == "hotp" and self.counter is None:
            self.counter = 0


class KeyResponse(BaseModel):
    """Model for key response (excludes secret)."""

    name: str
    type: Literal["totp", "hotp"]
    algorithm: Literal["sha1", "sha256", "sha512"]
    digits: Literal[6, 8]
    issuer: Optional[str] = None
    created_at: str

    model_config = {"from_attributes": True}


class KeyOutput(BaseModel):
    """Model for key output with type-specific fields."""

    name: str
    type: Literal["totp", "hotp"]
    algorithm: Literal["sha1", "sha256", "sha512"]
    digits: Literal[6, 8]
    issuer: Optional[str] = None
    created_at: str
    period: Optional[int] = None
    counter: Optional[int] = None

    model_config = {"from_attributes": True}


class OTPResponse(BaseModel):
    """Model for OTP generation response."""

    code: str
    type: Literal["totp", "hotp"]
    time_remaining: Optional[int] = None
    counter: Optional[int] = None


class KeyGenerateRequest(BaseModel):
    """Model for generating a new key (Party A)."""

    name: str = Field(..., description="Unique name for the key")
    type: Literal["totp", "hotp"] = Field(..., description="Type of OTP")
    algorithm: Literal["sha1", "sha256", "sha512"] = Field(
        default="sha1", description="HMAC algorithm"
    )
    digits: Literal[6, 8] = Field(default=6, description="Number of digits in OTP")
    period: Optional[int] = Field(
        default=30, description="Period in seconds for TOTP (ignored for HOTP)"
    )
    issuer: Optional[str] = Field(default=None, description="Issuer name")


class KeyGenerateResponse(BaseModel):
    """Model for key generation response (includes secret for Party A)."""

    name: str
    type: Literal["totp", "hotp"]
    algorithm: Literal["sha1", "sha256", "sha512"]
    digits: Literal[6, 8]
    period: Optional[int] = None
    counter: Optional[int] = None
    issuer: Optional[str] = None
    secret: str  # Included for Party A to share with Party B
    uri: str  # otpauth:// URI for QR code generation


class OTPVerifyRequest(BaseModel):
    """Model for verifying an OTP (Party A)."""

    name: str = Field(..., description="Key name to verify against")
    code: str = Field(..., description="OTP code to verify")


class OTPVerifyResponse(BaseModel):
    """Model for OTP verification response."""

    valid: bool
