# Auth-Helper API

A local REST API that functions as a programmatic authenticator, generating TOTP and HOTP codes from stored keys or QR code images.

## Prerequisites

- Python 3.9+
- libzbar0 (required for QR code scanning)

### Installing libzbar0

On Ubuntu/Debian:
```bash
sudo apt-get install libzbar0
```

On macOS:
```bash
brew install zbar
```

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
- **GET /keys/{name}/otp** - Get the current OTP code for a registered key
  ```bash
  curl http://localhost:8000/keys/github/otp
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
- **DELETE /keys/{name}** - Delete a registered key
  ```bash
  curl -X DELETE http://localhost:8000/keys/github
  ```
  Response: 204 No Content

## Architecture

- `src/main.py` - FastAPI application and endpoints
- `src/database.py` - SQLite database initialization and connection
- `src/models.py` - Pydantic models for validation
- `src/crud.py` - CRUD operations for keys
- `src/otp.py` - OTP generation logic
- `src/qr.py` - QR code parsing logic

## Development

Run the test suite:
```bash
pytest
```

Type checking:
```bash
python -m mypy src/
```

Linting:
```bash
python -m pylint src/
```
