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
FORUMS = 749      # Forums parameter (fixed)
PER_PAGE = 15     # Number of replies per page (fixed)

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, 'bot_config.json')

def load_config():
    """Load bot configuration and extract topic IDs."""
    if not os.path.exists(CONFIG_FILE):
        print(f"Warning: {CONFIG_FILE} not found")
        return {}
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            content = f.read()
            if not content:
                return {}
            return json.loads(content)
    except json.JSONDecodeError:
        print("Failed to decode JSON from bot config")
        return {}

def get_configured_topic_ids():
    """Get all unique topic IDs from bot configuration."""
    config = load_config()
    topic_ids = set()
    
    for guild_id, guild_config in config.items():
        topic_id = guild_config.get('topic_id')
        if topic_id:
            topic_ids.add(str(topic_id))
    
    topic_list = list(topic_ids)
    print(f"Found {len(topic_list)} unique topic IDs to monitor: {topic_list}")
    return topic_list

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
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            total_pages = data.get('totalPages', 0)
            return total_pages
        elif response.status_code == 429:
            print("Rate limited! API returned 429")
            return None
        else:
            print(f"Error fetching total pages for topic {topic_id}: {response.status_code}")
            return None
    except requests.exceptions.Timeout:
        print(f"Request timed out for topic {topic_id}")
        return None
    except requests.exceptions.ConnectionError:
        print(f"Connection error for topic {topic_id}")
        return None
    except Exception as e:
        print(f"Exception while fetching total pages for topic {topic_id}: {e}")
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
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            replies = data.get('results', [])
            return replies
        elif response.status_code == 429:
            print("Rate limited! API returned 429")
            return None
        else:
            print(f"Error fetching replies for topic {topic_id}: {response.status_code}")
            return None
    except requests.exceptions.Timeout:
        print(f"Request timed out for topic {topic_id}")
        return None
    except requests.exceptions.ConnectionError:
        print(f"Connection error for topic {topic_id}")
        return None
    except Exception as e:
        print(f"Exception while fetching replies for topic {topic_id}: {e}")
        return None

def save_replies_to_file(replies, topic_id):
    # Ensure the data directory exists
    os.makedirs('data', exist_ok=True)  # This will create the directory if it doesn't exist
    json_file_path = f'data/forum_{topic_id}.json'
    
    with open(json_file_path, "w") as file:
        json.dump(replies, file)

async def monitor_single_topic(topic_id):
    """Monitor a single topic for new replies."""
    try:
        # Add delay before API calls to prevent rate limiting
        await asyncio.sleep(1)
        
        # Fetch the total pages first
        total_pages = fetch_total_pages(topic_id, FORUMS)
        
        if total_pages is None:
            print(f"Failed to fetch total pages for topic {topic_id}")
            return False
        
        if total_pages <= 0:
            print(f"Invalid total pages for topic {topic_id}: {total_pages}")
            return False
        
        # Add delay before second API call
        await asyncio.sleep(1)
        
        # Fetch the replies from the last page
        last_page_replies = fetch_forum_replies(topic_id, FORUMS, total_pages)
        
        if last_page_replies is None:
            print(f"Failed to fetch replies for topic {topic_id}")
            return False
        
        if last_page_replies:
            save_replies_to_file(last_page_replies, topic_id)
            return True
        else:
            return True
            
    except Exception as e:
        print(f"❌ Error monitoring topic {topic_id}: {e}")
        return False

async def monitor_forum():
    """Monitor forum for new replies across all configured topics."""
    consecutive_errors = 0
    max_consecutive_errors = 10  # Increased since we're monitoring multiple topics
    
    while True:
        try:
            print(f"\n[{datetime.now()}] Starting forum check for all topics...")
            
            # Get all configured topic IDs
            topic_ids = get_configured_topic_ids()
            
            if not topic_ids:
                print("No topic IDs configured, waiting 4 minutes...")
                await asyncio.sleep(240)
                continue
            
            successful_topics = 0
            failed_topics = 0
            
            # Monitor each topic
            for topic_id in topic_ids:
                success = await monitor_single_topic(topic_id)
                if success:
                    successful_topics += 1
                else:
                    failed_topics += 1
                
                # Add delay between topics to prevent rate limiting
                await asyncio.sleep(2)
            
            print(f"\n--- Forum check complete ---")
            print(f"✅ Successful: {successful_topics} topics")
            print(f"❌ Failed: {failed_topics} topics")
            
            # Reset error counter if at least some topics succeeded
            if successful_topics > 0:
                consecutive_errors = 0
            elif failed_topics > 0:
                consecutive_errors += 1
            
            if consecutive_errors >= max_consecutive_errors:
                print(f"Too many consecutive failures ({consecutive_errors}). Waiting 10 minutes...")
                await asyncio.sleep(600)  # Wait 10 minutes
                consecutive_errors = 0
            else:
                print(f"Waiting 4 minutes before next check...")
                await asyncio.sleep(240)  # Check every 4 minutes
            
        except Exception as e:
            consecutive_errors += 1
            print(f"❌ Error in forum monitoring: {e}")
            print(f"Consecutive errors: {consecutive_errors}")
            
            if consecutive_errors >= max_consecutive_errors:
                print(f"Too many consecutive errors ({consecutive_errors}). Waiting 10 minutes...")
                await asyncio.sleep(600)  # Wait 10 minutes
                consecutive_errors = 0
            else:
                await asyncio.sleep(60)  # Wait a minute before retrying

if __name__ == "__main__":
    asyncio.run(monitor_forum())