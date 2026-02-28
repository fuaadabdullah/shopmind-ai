"""VIN decoder using NHTSA API."""
from typing import Any

import requests


def decode_vin(vin: str) -> dict[str, Any]:
    """Decode a Vehicle Identification Number using NHTSA API.
    
    Args:
        vin: 17-character Vehicle Identification Number
        
    Returns:
        Dictionary containing decoded vehicle information
    """
    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVin/{vin}?format=json"
    r = requests.get(url)
    return r.json()
