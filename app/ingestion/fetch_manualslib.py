"""
ManualsLib Fetcher
ManualsLib requires search + parsing result links.
Scrapes manual search results and extracts manual page links.
"""
from typing import Optional

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.manualslib.com"


def search_manualslib(query: str, max_results: int = 5) -> list[str]:
    """
    Search ManualsLib for manuals matching the query.
    
    Args:
        query: Search query (e.g., "Honda Accord 2016 service manual")
        max_results: Maximum number of results to return
    
    Returns:
        List of manual page URLs
    """
    url = f"{BASE_URL}/search.html?q={query.replace(' ', '+')}"
    
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"Error searching {url}: {e}")
        return []
    
    soup = BeautifulSoup(r.text, "html.parser")
    
    results = []
    for a in soup.select("a[href*='/manual/']"):
        href = a.get("href", "")
        if href:
            # Handle relative URLs
            if href.startswith("//"):
                results.append("https:" + href)
            elif href.startswith("/"):
                results.append(BASE_URL + href)
            elif href.startswith("http"):
                results.append(href)
            else:
                results.append(BASE_URL + "/" + href)
    
    # Remove duplicates and limit results
    results = list(set(results))[:max_results]
    
    return results


def get_manual_pdf_links(manual_url: str) -> list[str]:
    """
    Extract PDF download links from a ManualsLib manual page.
    
    Args:
        manual_url: URL of the manual page
    
    Returns:
        List of PDF download URLs
    """
    try:
        r = requests.get(manual_url, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching manual page {manual_url}: {e}")
        return []
    
    soup = BeautifulSoup(r.text, "html.parser")
    
    pdf_links = []
    
    # Look for PDF download links - ManualsLib often has download buttons
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        # Check for PDF links or download links
        if ".pdf" in href.lower() or "download" in href.lower():
            if href.startswith("//"):
                pdf_links.append("https:" + href)
            elif href.startswith("/"):
                pdf_links.append(BASE_URL + href)
            elif href.startswith("http"):
                pdf_links.append(href)
    
    return pdf_links


def download_manual_pdf(url: str, save_dir: str) -> Optional[str]:
    """
    Download a PDF from ManualsLib.
    
    Args:
        url: PDF download URL
        save_dir: Directory to save the PDF
    
    Returns:
        Path to the downloaded PDF file, or None if download fails
    """
    import os
    
    os.makedirs(save_dir, exist_ok=True)
    filename = url.split("/")[-1]
    # Clean filename
    filename = filename.split("?")[0]
    path = os.path.join(save_dir, filename)
    
    if os.path.exists(path):
        print(f"Already exists: {path}")
        return path
    
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
    # Test searching
    results = search_manualslib("Honda Accord 2016 service manual")
    print(f"Found {len(results)} manual results:")
    for result in results:
        print(f"  - {result}")
