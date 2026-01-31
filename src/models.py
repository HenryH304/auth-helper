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


class KeyGenerate(BaseModel):
    """Model for generating a new key."""

    name: str = Field(..., description="Unique name for the key")
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


class KeyGenerateResponse(BaseModel):
    """Model for key generation response (includes secret for initial setup)."""

    name: str
    type: Literal["totp", "hotp"]
    secret: str
    otpauth_uri: str
    algorithm: Literal["sha1", "sha256", "sha512"]
    digits: Literal[6, 8]
    issuer: Optional[str] = None
    created_at: str
    period: Optional[int] = None
    counter: Optional[int] = None
