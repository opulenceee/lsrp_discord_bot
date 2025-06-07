import os
import requests
import json
import time
from dotenv import load_dotenv
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime

load_dotenv()  # Load environment variables from .env file

# Environment variables
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
API_KEY = os.getenv('API_KEY')

# Constants
API_URL = "https://community.ls-rp.com/api/forums/topics/{}/posts"  # Base URL with a placeholder for topic ID
TOPIC_ID = 15621  # Topic ID (modifiable)
FORUMS = 749      # Forums parameter (fixed)
PER_PAGE = 15     # Number of replies per page (fixed)

def format_date(date_str):
    """Convert ISO 8601 date string to a more readable format."""
    # Parse the ISO date
    dt = datetime.fromisoformat(date_str[:-1])  # Remove the 'Z' and convert
    return dt.strftime("%B %d, %Y at %I:%M %p")  # Format date

def fetch_total_pages(topic_id, forums):
    """Fetch the total number of pages for a topic."""
    url = API_URL.format(topic_id)
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }
    params = {
        'forums': forums,
        'perPage': PER_PAGE,
        'page': 1
    }
    
    try:
        print(f"Making request to URL: {url}")
        print(f"With params: {params}")
        print(f"Headers (partially redacted): {{'Authorization': 'Bearer ***', 'Content-Type': headers['Content-Type']}}")
        
        response = requests.get(url, headers=headers, params=params)
        print(f"Response status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            total_pages = data.get('totalPages', 0)
            return total_pages
        else:
            print(f"Error fetching total pages: {response.status_code}")
            return None
    except Exception as e:
        print(f"Exception while fetching total pages: {e}")
        return None

def fetch_forum_replies(topic_id, forums, page):
    """Fetch replies from a specific page of a topic."""
    url = API_URL.format(topic_id)
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }
    params = {
        'forums': forums,
        'perPage': PER_PAGE,
        'page': page
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            return data.get('results', [])
        else:
            print(f"Error fetching replies: {response.status_code}")
            return None
    except Exception as e:
        print(f"Exception while fetching replies: {e}")
        return None

def save_replies_to_file(replies, topic_id):
    # Ensure the data directory exists
    os.makedirs('data', exist_ok=True)  # This will create the directory if it doesn't exist
    json_file_path = f'data/forum_{topic_id}.json'
    
    with open(json_file_path, "w") as file:
        json.dump(replies, file)

async def monitor_forum():
    """Monitor forum for new replies."""
    while True:
        try:
            # Fetch the total pages first
            total_pages = fetch_total_pages(TOPIC_ID, FORUMS)
            if total_pages is not None and total_pages > 0:
                # Fetch the replies from the last page
                last_page_replies = fetch_forum_replies(TOPIC_ID, FORUMS, total_pages)
                if last_page_replies:
                    save_replies_to_file(last_page_replies, TOPIC_ID)
            
            await asyncio.sleep(240)  # Check every 4 minutes
            
        except Exception as e:
            print(f"Error in forum monitoring: {e}")
            await asyncio.sleep(60)  # Wait a minute before retrying

if __name__ == "__main__":
    asyncio.run(monitor_forum())