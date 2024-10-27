import os
import requests
import json
import time
from dotenv import load_dotenv
import discord
from discord.ext import commands
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime

load_dotenv()  # Load environment variables from .env file

# Environment variables
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
API_KEY = os.getenv('API_KEY')


intents = discord.Intents.default()
intents.messages = True  
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

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


def clean_html(raw_html):
    """Strip HTML tags and extract information about images or videos from the given HTML string."""
    print("Raw HTML:", raw_html)  # Debug: print the raw HTML
    soup = BeautifulSoup(raw_html, 'html.parser')

    # Extract the text
    text = soup.get_text(strip=True)
    print("Extracted Text:", text)  # Debug: print the extracted text

    # Initialize media presence flags
    contains_images = False
    contains_videos = False

    # Check for images
    for img in soup.find_all('img'):
        if img.get('src'):
            contains_images = True  # Set flag if any image is found

    # Check for videos
    for video in soup.find_all('iframe'):
        if video.get('src'):
            contains_videos = True  # Set flag if any video is found

    # Prepare the response content
    media_message = ""
    if contains_images and contains_videos:
        media_message = "**This reply contains images and videos.**"
    elif contains_images:
        media_message = "**This reply contains images.**"
    elif contains_videos:
        media_message = "**This reply contains videos.**"

    # Combine text and media message, if media message exists
    if media_message:
        return f"{text}\n{media_message}"
    return text  # Return just the text if no media message

def fetch_total_pages(topic_id, forums):
    """Fetch total pages from the forum API based on topic ID and forums."""
    url = API_URL.format(topic_id)
    params = {
        "forums": forums,
        "perPage": PER_PAGE,
        "page": 1  # Only need to request the first page to get the total pages
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json().get('totalPages', 0)  # Return total pages from response
    except requests.exceptions.RequestException as e:
        print(f"Error fetching total pages: {e}")
        return None

def fetch_forum_replies(topic_id, forums, page):
    """Fetch replies from the forum API based on topic ID, forums, and pagination."""
    url = API_URL.format(topic_id)  # Construct the URL with the topic ID
    params = {
        "forums": forums,
        "perPage": PER_PAGE,
        "page": page  # Specify the page number
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        # Debugging: Print the full response to understand its structure
        data = response.json()

        # Fetch replies from the 'results' key
        return data.get('results', [])  # Return results from the response
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from API: {e}")
        return None

def save_replies_to_file(replies, topic_id):
    # Ensure the data directory exists
    os.makedirs('data', exist_ok=True)  # This will create the directory if it doesn't exist
    json_file_path = f'data/forum_{topic_id}.json'
    
    with open(json_file_path, "w") as file:
        json.dump(replies, file)

async def main():
    # Fetch the total pages first
    total_pages = fetch_total_pages(TOPIC_ID, FORUMS)  # Get the total pages from the API
    print(f"Total pages available: {total_pages}")
    if total_pages is not None and total_pages > 0:
        # Fetch the replies from the last page
        last_page_replies = fetch_forum_replies(TOPIC_ID, FORUMS, total_pages)
        if last_page_replies:
            save_replies_to_file(last_page_replies, TOPIC_ID)  # Save using the topic ID in the filename

            
if __name__ == "__main__":
    asyncio.run(main())