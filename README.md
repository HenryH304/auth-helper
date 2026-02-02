# Auth-Helper API

A local REST API for TOTP/HOTP authentication that can act as **both parties** in the two-factor authentication flow:
- **Party A (Service Provider)**: Generate secrets and verify OTP codes from users
- **Party B (Authenticator)**: Store secrets and generate OTP codes when challenged

## How It Works

### The Two Parties

| Party | Role | This API Can Act As |
|-------|------|---------------------|
| **Party A** | Service provider - creates secrets and verifies codes | Yes (`/keys/generate`, `/keys/verify`) |
| **Party B** | User/Authenticator - stores secrets and generates codes | Yes (`/keys`, `/keys/qr`, `/keys/otp`) |

### Flow 1: Using Auth-Helper as Party B (Authenticator)

Use this when logging into external services (GitHub, AWS, etc.) that provide you with a secret/QR code.

```
┌─────────────────────────────────────────────────────────────────────────┐
│ SETUP PHASE (one-time)                                                  │
└─────────────────────────────────────────────────────────────────────────┘

    Party A                                        Party B
    (GitHub)                                    (Auth-Helper)
       │                                              │
       │  1. Generates shared secret                  │
       │     (e.g., "JBSWY3DPEHPK3PXP")              │
       │                                              │
       │  2. Displays QR code or manual key           │
       │─────────────────────────────────────────────>│
       │                                              │
       │                              3. POST /keys/qr (upload QR image)
       │                                 OR
       │                                 POST /keys (manual entry)
       │                                              │
       │                              4. Secret stored in database
       │                                              │

┌─────────────────────────────────────────────────────────────────────────┐
│ AUTHENTICATION PHASE (every login)                                      │
└─────────────────────────────────────────────────────────────────────────┘

    Party A                                        Party B
    (GitHub)                                    (Auth-Helper)
       │                                              │
       │  5. "Enter your 6-digit code"               │
       │<─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─│
       │                                              │
       │                              6. GET /keys/otp?name=github
       │                                 Returns: {"code": "482957", ...}
       │                                              │
       │  7. User enters "482957"                     │
       │<─────────────────────────────────────────────│
       │                                              │
       │  8. Party A verifies code                    │
       │     "482957" == "482957" ✓                   │
       │                                              │
       │  9. Access granted                           │
       │                                              │
```

### Flow 2: Using Auth-Helper as Party A (Service Provider)

Use this when building your own service that requires 2FA from users.

```
┌─────────────────────────────────────────────────────────────────────────┐
│ SETUP PHASE (one-time)                                                  │
└─────────────────────────────────────────────────────────────────────────┘

    Party A                                        Party B
    (Auth-Helper)                               (User's Authenticator)
       │                                              │
       │  1. POST /keys/generate {"name": "bob"}      │
       │     Returns: {secret, uri}                   │
       │                                              │
       │  2. Display QR code (from uri) to user       │
       │─────────────────────────────────────────────>│
       │                                              │
       │                              3. User scans QR with their app
       │                                 (Google Authenticator, etc.)
       │                                              │

┌─────────────────────────────────────────────────────────────────────────┐
│ AUTHENTICATION PHASE (every login)                                      │
└─────────────────────────────────────────────────────────────────────────┘

    Party A                                        Party B
    (Auth-Helper)                               (User's Authenticator)
       │                                              │
       │  4. Prompt user: "Enter your 6-digit code"  │
       │<─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─│
       │                                              │
       │                              5. User opens authenticator app
       │                                 Gets code: "482957"
       │                                              │
       │  6. User submits "482957"                    │
       │<─────────────────────────────────────────────│
       │                                              │
       │  7. POST /keys/verify                        │
       │     {"name": "bob", "code": "482957"}        │
       │     Returns: {"valid": true}                 │
       │                                              │
       │  8. Access granted                           │
       │                                              │
```

### Why It Works

Both parties share the **same secret** and use the **same algorithm** (TOTP). Given:
- The shared secret
- The current time (rounded to 30-second intervals)
- The agreed algorithm (SHA1, 6 digits, etc.)

Both parties independently compute the **same OTP** without any network communication.

### Endpoint Summary by Role

| Role | Phase | Endpoint | Purpose |
|------|-------|----------|---------|
| Party A | Setup | `POST /keys/generate` | Create secret for a user |
| Party A | Auth | `POST /keys/verify` | Verify code submitted by user |
| Party B | Setup | `POST /keys/qr` | Import secret from QR code |
| Party B | Setup | `POST /keys` | Manually enter a secret |
| Party B | Auth | `GET /keys/otp?name=x` | Generate code when challenged |
| Both | Manage | `GET /keys` | List all stored keys |
| Both | Manage | `DELETE /keys?name=x` | Remove a key |

## Prerequisites

- Python 3.9+
- System libraries (see below)

### System Dependencies

| Library | Purpose | Installation |
|---------|---------|--------------|
| **zbar** | QR code decoding | Required for parsing QR code images |

**Ubuntu/Debian:**
```bash
sudo apt-get install libzbar0
```

**macOS:**
```bash
brew install zbar
```

### Python Dependencies

| Package | Purpose |
|---------|---------|
| **fastapi** | Web framework for the REST API |
| **uvicorn** | ASGI server to run the application |
| **pyotp** | TOTP/HOTP code generation (RFC 6238/RFC 4226) |
| **pyzbar** | Python bindings for zbar QR code reader |
| **Pillow** | Image processing for QR code uploads |
| **python-multipart** | File upload handling in FastAPI |
| **qrcode** | QR code generation (used in tests) |

## Setup

1. Clone the repository and navigate to the project directory

2. Create a virtual environment:
```bash
python3 -m venv venv
```

3. Activate the virtual environment:

On Linux/macOS:
```bash
source venv/bin/activate
```

On Windows:
```bash
venv\Scripts\activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Service

```bash
./run.sh
```

Or manually:
```bash
source venv/bin/activate
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Documentation

Interactive API documentation is available at `http://localhost:8000/docs`

## Endpoints

### Health Check
- **GET /health** - Check if the service is running
  ```bash
  curl http://localhost:8000/health
  ```
  Response:
  ```json
  {"status": "ok"}
  ```

### Register a Key Manually
- **POST /keys** - Register a new authentication key manually
  ```bash
  curl -X POST http://localhost:8000/keys \
    -H "Content-Type: application/json" \
    -d '{
      "name": "github",
      "secret": "JBSWY3DPEBLW64TMMQ======",
      "type": "totp",
      "algorithm": "sha1",
      "digits": 6,
      "period": 30,
      "issuer": "GitHub"
    }'
  ```
  Response:
  ```json
  {
    "name": "github",
    "type": "totp",
    "algorithm": "sha1",
    "digits": 6,
    "period": 30,
    "issuer": "GitHub",
    "created_at": "2024-01-31T12:00:00"
  }
  ```

### Register a Key from QR Code
- **POST /keys/qr** - Register a key by uploading a QR code image
  ```bash
  curl -X POST http://localhost:8000/keys/qr \
    -F "file=@qrcode.png" \
    -F "name=github"
  ```
  Response:
  ```json
  {
    "name": "github",
    "type": "totp",
    "algorithm": "sha1",
    "digits": 6,
    "period": 30,
    "issuer": "GitHub",
    "created_at": "2024-01-31T12:00:00"
  }
  ```

### Get Current OTP
- **GET /keys/otp?name={name}** - Get the current OTP code for a registered key
  ```bash
  curl "http://localhost:8000/keys/otp?name=github"
  ```
  Response for TOTP:
  ```json
  {
    "code": "123456",
    "type": "totp",
    "time_remaining": 15
  }
  ```
  Response for HOTP:
  ```json
  {
    "code": "123456",
    "type": "hotp",
    "counter": 42
  }
  ```

### List All Keys
- **GET /keys** - List all registered keys
  ```bash
  curl http://localhost:8000/keys
  ```
  Response:
  ```json
  [
    {
      "name": "github",
      "type": "totp",
      "algorithm": "sha1",
      "digits": 6,
      "period": 30,
      "issuer": "GitHub",
      "created_at": "2024-01-31T12:00:00"
    },
    {
      "name": "aws",
      "type": "hotp",
      "algorithm": "sha1",
      "digits": 6,
      "counter": 42,
      "issuer": "Amazon AWS",
      "created_at": "2024-01-31T12:01:00"
    }
  ]
  ```

### Delete a Key
- **DELETE /keys?name={name}** - Delete a registered key
  ```bash
  curl -X DELETE "http://localhost:8000/keys?name=github"
  ```
  Response: 204 No Content

### Generate a Key (Party A)
- **POST /keys/generate** - Generate a new key with a random secret
  ```bash
  curl -X POST http://localhost:8000/keys/generate \
    -H "Content-Type: application/json" \
    -d '{
      "name": "bob",
      "type": "totp",
      "issuer": "MyApp"
    }'
  ```
  Response:
  ```json
  {
    "name": "bob",
    "type": "totp",
    "algorithm": "sha1",
    "digits": 6,
    "period": 30,
    "issuer": "MyApp",
    "secret": "JBSWY3DPEHPK3PXP",
    "uri": "otpauth://totp/MyApp:bob?secret=JBSWY3DPEHPK3PXP&issuer=MyApp"
  }
  ```
  Use the `uri` to generate a QR code for the user to scan with their authenticator app.

### Verify an OTP (Party A)
- **POST /keys/verify** - Verify an OTP code against a stored key
  ```bash
  curl -X POST http://localhost:8000/keys/verify \
    -H "Content-Type: application/json" \
    -d '{
      "name": "bob",
      "code": "482957"
    }'
  ```
  Response (valid code):
  ```json
  {"valid": true}
  ```
  Response (invalid code):
  ```json
  {"valid": false}
  ```
  Notes:
  - TOTP verification allows a 1-period window for clock drift
  - HOTP verification uses a look-ahead window of 10 and auto-increments the counter on success

## Architecture

- `src/main.py` - FastAPI application and endpoints
- `src/database.py` - SQLite database initialization and connection
- `src/models.py` - Pydantic models for validation
- `src/crud.py` - CRUD operations for keys
- `src/otp.py` - OTP generation logic
- `src/qr.py` - QR code parsing logic

## Development

### Setup
```bash
make venv
```

### Run tests locally
```bash
make test-local
```

### Run tests in Docker
```bash
make test
```

### Type checking
```bash
python -m mypy src/
```

### Linting
```bash
python -m pylint src/
```
