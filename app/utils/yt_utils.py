import re
import requests
from bs4 import BeautifulSoup

def validate_url(url: str):
    # Basic validation, HttpUrl does more
    return url.startswith("https://www.youtube.com/watch?v=")

def get_title(url: str):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status() # Raise error for bad responses
        soup = BeautifulSoup(r.text, 'html.parser')
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.text.split(' - YouTube')[0].strip()
    except requests.RequestException as e:
        print(f"Error fetching title for {url}: {e}")
    except Exception as e:
        print(f"Error parsing title for {url}: {e}")
    return "Unknown Title" # Fallback

def get_description(url: str) -> str:
    # This regex method is brittle; YouTube's structure changes.
    # Consider library alternatives or more robust scraping if needed.
    try:
        full_html = requests.get(url, timeout=10).text
        match = re.search(r'shortDescription":"(.*?)(?<!\\)"', full_html, re.DOTALL)
        if match:
            # Handle escaped sequences like \n, \" etc.
            return match.group(1).encode('utf-8').decode('unicode_escape')
        else:
             print(f"Could not find shortDescription for {url}")
             return ""
    except requests.RequestException as e:
        print(f"Error fetching description for {url}: {e}")
        return ""
    except Exception as e:
         print(f"Error processing description for {url}: {e}")
         return ""

def get_video_id(url: str) -> str | None:
    # Use regex for more robust extraction
    match = re.search(r"youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})", url)
    return match.group(1) if match else None