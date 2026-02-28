"""Simple web search functionality."""
import requests
from bs4 import BeautifulSoup


def simple_search(query: str) -> list[str]:
    """Perform a simple web search.
    
    Args:
        query: Search query string
        
    Returns:
        List of search result titles (max 5)
        
    Note:
        This function appears to be unused and may be deprecated.
    """
    url = f"https://duckduckgo.com/html/?q={query}"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")
    results = soup.find_all("a", class_="result__a")
    return [a.get_text() for a in results[:5]]
