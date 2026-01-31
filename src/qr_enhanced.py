import hashlib
import pyotp
from pyzbar.pyzbar import decode
from PIL import Image
from io import BytesIO
from typing import Dict, Any, List, Tuple, Optional


def find_qr_regions(image: Image.Image) -> List[Tuple[int, int, int, int]]:
    """Find potential QR code regions in an image.
    
    Args:
        image: PIL Image object
        
    Returns:
        List of (x, y, width, height) tuples for potential QR regions
    """
    width, height = image.size
    regions = []
    
    # Try different grid sizes to scan the image
    for grid_size in [3, 4, 5, 6]:
        step_x = width // grid_size
        step_y = height // grid_size
        
        for x in range(0, width - step_x, step_x // 2):
            for y in range(0, height - step_y, step_y // 2):
                regions.append((x, y, x + step_x, y + step_y))
    
    # Add some common QR code sizes as fixed regions
    min_size = min(width, height)
    qr_sizes = [200, 300, 400, 500]
    
    for size in qr_sizes:
        if size <= min_size:
            # Center region
            x = (width - size) // 2
            y = (height - size) // 2
            regions.append((x, y, x + size, y + size))
            
            # Corner regions
            regions.extend([
                (0, 0, size, size),  # Top-left
                (width - size, 0, width, size),  # Top-right
                (0, height - size, size, height),  # Bottom-left
                (width - size, height - size, width, height),  # Bottom-right
            ])
    
    return regions


def find_and_decode_qr(image: Image.Image) -> Optional[str]:
    """Find and decode QR codes from an image, trying cropping if needed.
    
    Args:
        image: PIL Image object
        
    Returns:
        Decoded QR code data string, or None if no QR found
    """
    # First try the full image
    qr_codes = decode(image)
    if qr_codes:
        return qr_codes[0].data.decode('utf-8')
    
    # If no QR found, try cropping different regions
    print("No QR found in full image, trying region scanning...")
    regions = find_qr_regions(image)
    
    for i, (x1, y1, x2, y2) in enumerate(regions):
        try:
            # Crop the region
            cropped = image.crop((x1, y1, x2, y2))
            
            # Skip very small regions
            if cropped.width < 50 or cropped.height < 50:
                continue
                
            # Try to decode this region
            qr_codes = decode(cropped)
            if qr_codes:
                print(f"QR found in region {i+1}/{len(regions)}: ({x1},{y1},{x2},{y2})")
                return qr_codes[0].data.decode('utf-8')
                
        except Exception as e:
            # Skip problematic crops
            continue
    
    return None


def parse_otpauth_uri(uri: str) -> Dict[str, Any]:
    """Parse otpauth:// URI and extract TOTP/HOTP parameters.
    
    Args:
        uri: otpauth:// URI string
        
    Returns:
        Dictionary with parsed parameters
        
    Raises:
        ValueError: If URI is invalid or not otpauth://
    """
    if not uri.startswith('otpauth://'):
        raise ValueError(f"Invalid otpauth:// URI: {uri}")
    
    # Parse URI components
    from urllib.parse import urlparse, parse_qs
    
    parsed = urlparse(uri)
    
    if parsed.scheme != 'otpauth':
        raise ValueError(f"Invalid scheme: {parsed.scheme}")
    
    otp_type = parsed.hostname.lower()
    if otp_type not in ['totp', 'hotp']:
        raise ValueError(f"Invalid OTP type: {otp_type}")
    
    # Extract account name from path
    account = parsed.path.lstrip('/')
    
    # Parse query parameters
    params = parse_qs(parsed.query)
    
    # Extract required secret
    if 'secret' not in params:
        raise ValueError("Missing required 'secret' parameter")
    
    secret = params['secret'][0]
    
    # Extract optional parameters with defaults
    algorithm = params.get('algorithm', ['SHA1'])[0].lower().replace('sha', 'sha')
    digits = int(params.get('digits', ['6'])[0])
    issuer = params.get('issuer', [None])[0]
    
    result = {
        'secret': secret,
        'type': otp_type,
        'algorithm': algorithm,
        'digits': digits,
        'period': None,
        'counter': None,
        'issuer': issuer,
        'name': account
    }
    
    if otp_type == 'totp':
        result['period'] = int(params.get('period', ['30'])[0])
    elif otp_type == 'hotp':
        result['counter'] = int(params.get('counter', ['0'])[0])
    
    return result


def parse_qr_image(image_bytes: bytes) -> Dict[str, Any]:
    """Parse QR code image and extract otpauth:// URI with auto-cropping.

    Args:
        image_bytes: Image file bytes.

    Returns:
        Dictionary with parsed key details from URI.

    Raises:
        ValueError: If no QR code found or invalid otpauth:// URI.
    """
    try:
        image = Image.open(BytesIO(image_bytes))
    except Exception as e:
        raise ValueError(f"Invalid image format: {str(e)}")

    # Find and decode QR code (with auto-cropping)
    qr_data = find_and_decode_qr(image)
    
    if not qr_data:
        raise ValueError("No QR code found in image")

    # Parse the otpauth:// URI
    return parse_otpauth_uri(qr_data)