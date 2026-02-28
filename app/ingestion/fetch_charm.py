"""
CHARM Manual Fetcher
Operation CHARM is structured by make/year/model pages with PDF links.
Scrapes model page and extracts PDF links.
"""
import os
from typing import Optional

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://charm.li"


def fetch_charm_manuals(make: str, year: str, model: str) -> list[str]:
    """
    Fetch PDF links from CHARM for a specific make/year/model.
    
    Args:
        make: Vehicle make (e.g., "Honda")
        year: Vehicle year (e.g., "2016")
        model: Vehicle model (e.g., "Accord")
    
    Returns:
        List of PDF download URLs
    """
    url = f"{BASE_URL}/{make}/{year}/{model}/"
    
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return []
    
    soup = BeautifulSoup(r.text, "html.parser")
    
    pdf_links = []
    for a in soup.find_all("a"):
        href = a.get("href", "")
        if href.endswith(".pdf"):
            # Handle relative URLs
            if href.startswith("//"):
                pdf_links.append("https:" + href)
            elif href.startswith("/"):
                pdf_links.append(BASE_URL + href)
            elif href.startswith("http"):
                pdf_links.append(href)
            else:
                pdf_links.append(BASE_URL + "/" + href)
    
    return pdf_links


def download_pdf(url: str, save_dir: str) -> Optional[str]:
    """
    Download a PDF from URL to the specified directory.
    
    Args:
        url: PDF download URL
        save_dir: Directory to save the PDF
    
    Returns:
        Path to the downloaded PDF file, or None if download fails
    """
    os.makedirs(save_dir, exist_ok=True)
    filename = url.split("/")[-1]
    # Clean filename
    filename = filename.split("?")[0]
    path = os.path.join(save_dir, filename)
    
    if os.path.exists(path):
        print(f"Already exists: {path}")
        return path  # skip if already downloaded
    
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        
        with open(path, "wb") as f:
            f.write(r.content)
        
        print(f"Downloaded: {path}")
    except requests.RequestException as e:
        print(f"Error downloading {url}: {e}")
        return None
    
    return path


if __name__ == "__main__":
    # Test fetching
    links = fetch_charm_manuals("Honda", "2016", "Accord")
    print(f"Found {len(links)} PDF links:")
    for link in links:
        print(f"  - {link}")
