# PRD: Auth-Helper API Enhancements

**Project:** Auth-Helper  
**Feature:** Extended API Endpoints for Key Management and Validation  
**Date:** January 31, 2026  
**Version:** 2.0

---

## Overview

Extend the existing Auth-Helper API with new endpoints for key generation, QR code creation, and token validation. This will enable the service to be used by both test sites (generating keys/QR codes) and scraping systems (consuming keys and producing OTP tokens).

## Problem Statement

The current Auth-Helper API is designed for end-user consumption (store keys, generate tokens). We need to extend it to support **programmatic use cases** where:

1. **Test sites** need to generate TOTP secrets and QR codes dynamically
2. **Scraping systems** need to validate tokens against known secrets
3. **Both systems** can use the same service for different purposes

## Goals

1. **Add key generation endpoints** that create secrets and return otpauth:// URIs
2. **Add QR code generation endpoints** that create QR images from keys or secrets
3. **Add token validation endpoints** that verify OTP codes
4. **Support multiple response formats** (base64, binary) for QR codes
5. **Maintain backward compatibility** with existing API

## Target Users

- **Test site developers** who need to generate TOTP secrets for testing
- **Automation/scraping developers** who need to validate OTP tokens
- **Existing API users** (no breaking changes)

## Success Criteria

- New endpoints work independently and integrate with existing database
- QR codes are properly formatted and scannable by authenticator apps
- Token validation is accurate for TOTP/HOTP algorithms
- Performance is acceptable (< 500ms per request)
- API is well-documented and consistent with existing patterns

---

## User Stories

### US-001: Generate New TOTP Secret
**As a** test site developer  
**I want** to generate new TOTP secrets programmatically  
**So that** I can create fresh test accounts with 2FA

**Acceptance Criteria:**
- POST /keys/generate endpoint accepts parameters (name, issuer, algorithm, digits, period)
- Returns generated secret, otpauth:// URI, and key details
- Automatically stores key in database for later use
- Supports TOTP with configurable parameters
- Returns 201 on success, 400 on validation errors
- Typecheck passes

### US-002: Generate New HOTP Secret  
**As a** test site developer  
**I want** to generate new HOTP secrets programmatically  
**So that** I can create counter-based 2FA test accounts

**Acceptance Criteria:**
- POST /keys/generate endpoint supports HOTP type
- Accepts counter parameter for HOTP
- Returns generated secret, otpauth:// URI, and key details
- Automatically stores key in database
- Counter starts at provided value (default 0)
- Typecheck passes

### US-003: Generate QR Code from Existing Key
**As a** test site developer  
**I want** to generate QR codes from stored keys  
**So that** I can display them for manual testing

**Acceptance Criteria:**
- GET /keys/{name}/qr endpoint returns QR code image
- Supports both base64 (Accept: application/json) and binary (Accept: image/png)
- QR code contains valid otpauth:// URI
- Returns 404 if key doesn't exist
- QR code is scannable by Google Authenticator
- Typecheck passes

### US-004: Generate QR Code from Raw Secret
**As a** test site developer  
**I want** to generate QR codes from raw secrets/parameters  
**So that** I can create QR codes without storing keys

**Acceptance Criteria:**
- POST /qr/generate endpoint accepts secret, type, name, issuer, etc.
- Supports both TOTP and HOTP parameters
- Returns QR code in requested format (base64/binary)
- Does NOT store the secret in database
- Validates otpauth:// URI format before generating QR
- Returns 400 for invalid parameters
- Typecheck passes

### US-005: Validate TOTP Token
**As a** scraping system developer  
**I want** to validate TOTP codes against stored keys  
**So that** I can verify if scraped tokens are correct

**Acceptance Criteria:**
- POST /keys/{name}/validate endpoint accepts token parameter
- Returns JSON with {valid: true/false, type: "totp", time_remaining: N}
- Validates token against stored key's secret and parameters
- Handles time window tolerance (±1 period)
- Returns 404 if key doesn't exist
- Returns 400 for malformed requests
- Typecheck passes

### US-006: Validate HOTP Token
**As a** scraping system developer  
**I want** to validate HOTP codes and increment counters  
**So that** I can verify counter-based tokens

**Acceptance Criteria:**
- POST /keys/{name}/validate works for HOTP keys
- Validates token against current counter value
- Increments counter on successful validation
- Returns JSON with {valid: true/false, type: "hotp", counter: N}
- Counter persistence works across requests
- Look-ahead window for counter synchronization (check next 10 values)
- Typecheck passes

### US-007: Content Negotiation for QR Codes
**As an** API consumer  
**I want** to request QR codes in different formats  
**So that** I can use them in web (base64) or native apps (binary)

**Acceptance Criteria:**
- Accept: application/json returns {qr_code: "base64string", format: "png"}
- Accept: image/png returns binary PNG data with Content-Type: image/png
- Accept: image/jpeg returns binary JPEG data with Content-Type: image/jpeg
- Default format is application/json if no Accept header
- Proper HTTP headers for binary responses
- Image quality is configurable (default: 85% for JPEG)
- Typecheck passes

### US-008: Enhanced Error Handling
**As an** API consumer  
**I want** clear error messages for invalid requests  
**So that** I can debug integration issues

**Acceptance Criteria:**
- 400 errors include detailed validation messages
- 404 errors specify what resource was not found
- 422 errors explain which fields failed validation
- Consistent error format: {error: "type", message: "details", field: "name"}
- Rate limiting returns 429 with Retry-After header
- Proper HTTP status codes for all scenarios
- Typecheck passes

### US-009: API Documentation Updates
**As a** developer integrating with the API  
**I want** updated documentation for new endpoints  
**So that** I can understand how to use them

**Acceptance Criteria:**
- OpenAPI/Swagger schema includes all new endpoints
- /docs endpoint shows examples for each new endpoint
- Request/response models are properly documented
- Content-Type examples for QR code endpoints
- Error response examples
- Integration examples in README.md
- Typecheck passes

### US-010: Database Schema Updates
**As a** system  
**I want** to support new use cases without breaking existing data  
**So that** current keys continue to work

**Acceptance Criteria:**
- Database migration preserves existing keys
- New fields are optional and backward compatible
- Counter updates work for HOTP keys
- Key generation creates proper database entries
- Foreign key constraints maintained
- Database indexes for performance
- Typecheck passes

### US-011: Performance Optimization
**As an** API consumer  
**I want** fast response times for all operations  
**So that** my applications remain responsive

**Acceptance Criteria:**
- QR code generation < 200ms
- Token validation < 50ms
- Key generation < 100ms
- Database queries optimized with indexes
- QR code caching for identical requests
- Efficient secret generation using crypto-secure random
- Typecheck passes

### US-012: Integration Tests
**As a** developer  
**I want** comprehensive tests for new endpoints  
**So that** the API works reliably in production

**Acceptance Criteria:**
- Unit tests for all new endpoint functions
- Integration tests for complete request/response cycles
- Test QR code generation and scanning
- Test token validation edge cases (expired, wrong counter, etc.)
- Test content negotiation for different Accept headers
- Test error conditions and edge cases
- All tests pass with 100% coverage for new code
- Typecheck passes

---

## Technical Requirements

### Dependencies
- Add `qrcode` library for QR generation
- Add `cryptography` for secure random generation
- Ensure `pyzbar` and `Pillow` support QR creation

### API Design
- RESTful endpoints following existing patterns
- Consistent JSON response formats
- Proper HTTP status codes
- Content negotiation support

### Security
- Secure random secret generation
- Input validation and sanitization
- Rate limiting to prevent abuse
- No secret exposure in logs

### Performance
- QR code caching for repeated requests
- Efficient database queries
- Async endpoint support where beneficial

---

## Out of Scope

- Web UI for key management
- Bulk operations (generate 100 keys at once)
- Advanced authentication (API keys, OAuth)
- Secret encryption at rest (future enhancement)
- Multi-tenant support

---

## Success Metrics

- All existing tests continue to pass
- New endpoints respond within performance targets
- QR codes are scannable by major authenticator apps
- Integration tests validate end-to-end workflows

---

## Dependencies

- Existing Auth-Helper API infrastructure
- SQLite database with existing schema
- FastAPI framework
- Current test suite

---

## Timeline

Implementation via Ralph autonomous agent system. Estimated completion: 30-50 iterations based on complexity.