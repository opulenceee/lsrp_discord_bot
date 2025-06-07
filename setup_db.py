import time
import json
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import os
from dotenv import load_dotenv
from datetime import datetime
import asyncio
import threading
from selenium.common.exceptions import NoSuchWindowException, WebDriverException

load_dotenv() # Load environment variables from .env file

UCP_USERNAME = os.getenv('UCP_USERNAME')
UCP_PASSWORD = os.getenv('UCP_PASSWORD')
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
NOTIFICATION_CHANNEL_ID = 804688024704253986  # Your specified channel ID
SESSION_REFRESH_INTERVAL = 24 * 60 * 60  # 24 hours in seconds
MAX_LOGIN_RETRIES = 3  # Number of login attempts before a full restart
RESTART_DELAY = 10  # Time in seconds before retrying after max login retries
VERIFICATION_WAIT_TIME = 300  # 5 minutes to wait for email verification

# Create an event loop for Discord notifications
discord_loop = asyncio.new_event_loop()
asyncio.set_event_loop(discord_loop)

async def send_discord_notification(message):
    """Send a notification to the specified Discord channel."""
    try:
        from bot import bot  # Import the main bot instance
        channel = bot.get_channel(NOTIFICATION_CHANNEL_ID)
        if channel:
            await channel.send(f"<@804688024704253986> {message}")
            print(f"Discord notification sent: {message}")
        else:
            print(f"Could not find Discord channel {NOTIFICATION_CHANNEL_ID}")
    except Exception as e:
        print(f"Error sending Discord notification: {e}")

def check_for_verification(driver):
    """Check if email verification is required and handle it."""
    try:
        # Look for common verification prompts
        verification_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'verification') or contains(text(), 'verify') or contains(text(), 'confirm')]")
        if verification_elements:
            print("Email verification required. Waiting for manual verification...")
            # Send immediate notification
            asyncio.run_coroutine_threadsafe(
                send_discord_notification("⚠️ Email verification required! Please check your email and verify your account."),
                discord_loop
            )
            
            # Wait for verification to complete
            start_time = time.time()
            while time.time() - start_time < VERIFICATION_WAIT_TIME:
                try:
                    # Check if we're redirected to the main page or if verification is complete
                    if "ucp.ls-rp.com" in driver.current_url and "verification" not in driver.page_source.lower():
                        print("Verification appears to be complete.")
                        asyncio.run_coroutine_threadsafe(
                            send_discord_notification("✅ Email verification completed successfully!"),
                            discord_loop
                        )
                        return True
                except:
                    pass
                time.sleep(5)
            
            print("Verification timeout reached.")
            asyncio.run_coroutine_threadsafe(
                send_discord_notification("❌ Email verification timeout reached. Please verify manually."),
                discord_loop
            )
            return False
        return True
    except Exception as e:
        print(f"Error checking verification: {e}")
        return False

def login_ucp():
    retries = 0  # Track login attempts
    driver = None
    base_delay = 5  # Base delay in seconds
    
    while retries < MAX_LOGIN_RETRIES:
        try:
            print(f"Attempt {retries + 1} of {MAX_LOGIN_RETRIES} to log in.")

            # Setup Chrome options
            options = uc.ChromeOptions()
            options.add_argument("--auto-open-devtools-for-tabs")
            options.add_argument('--headless=new')  # Use new headless mode
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.binary_location = '/usr/bin/google-chrome'

            # Create Chrome driver
            driver = uc.Chrome(options=options)
            driver.get("https://ucp.ls-rp.com/")
            print("Opened Chrome, waiting for page to load.")
            time.sleep(5)  # Allow page to fully load

            # Find and enter username and password
            username_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//input[@formcontrolname="name"]'))
            )
            password_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//input[@formcontrolname="password"]'))
            )
            username_input.send_keys(UCP_USERNAME)
            password_input.send_keys(UCP_PASSWORD)
            password_input.send_keys(Keys.RETURN)
            print("Submitted login credentials.")

            time.sleep(5)  # Wait for the login process

            # Check for email verification
            if not check_for_verification(driver):
                raise ValueError("Email verification required but not completed.")

            # Check if login was successful
            if "Forbidden" in driver.page_source:
                raise ValueError("403 Forbidden: Login failed.")
            
            # Navigate to API page after login
            driver.get("https://ucp.ls-rp.com/api/sa/player-list")
            if "403 Forbidden" in driver.page_source:
                raise ValueError("403 Forbidden: Access to player list API denied.")

            print("Login successful.")
            return driver

        except Exception as e:
            print(f"Login attempt {retries + 1} failed: {e}")
            retries += 1
            
            # Calculate exponential backoff delay
            delay = base_delay * (2 ** (retries - 1))  # Exponential backoff
            print(f"Waiting {delay} seconds before next attempt...")
            
            if driver:
                try:
                    driver.quit()  # Close driver on failure
                except:
                    pass  # Ignore errors during cleanup
            
            time.sleep(delay)  # Wait with exponential backoff

    print(f"Max retries reached ({MAX_LOGIN_RETRIES}). Waiting {RESTART_DELAY} seconds before restarting...")
    time.sleep(RESTART_DELAY)
    return None  # Indicate failure after max retries


def fetch_and_save_json_data(driver):
    time.sleep(5)

    # Fetch body text containing JSON data
    body_text = driver.find_element(By.TAG_NAME, 'body').text
    print("Body text received:", body_text)  # DEBUG: Show the raw response

    try:
        # Parse the body text as JSON
        json_data = json.loads(body_text)

        # Ensure the 'data' directory exists
        os.makedirs('data', exist_ok=True)

        # Save the parsed JSON data to a file
        player_list_file = 'data/player_list.json'
        with open(player_list_file, 'w') as json_file:
            json.dump(json_data, json_file, indent=4)
        print(f"Player list data saved to {player_list_file}")

        # Load existing last_seen data if it exists
        last_seen_file = 'data/last_seen.json'
        if os.path.exists(last_seen_file):
            with open(last_seen_file, 'r') as f:
                last_seen_dict = json.load(f)
        else:
            last_seen_dict = {}  # Initialize an empty dictionary if the file doesn't exist

        # Get the syncTime from the fetched JSON data
        sync_time = json_data.get("syncTime")

        # Update or add character names in last_seen_dict
        for player in json_data.get("players", []):
            character_name = player.get("characterName")
            if character_name:
                last_seen_dict[character_name] = sync_time  # Update or add the entry

        # Save updated last_seen data back to the JSON file
        with open(last_seen_file, 'w') as f:
            json.dump(last_seen_dict, f, indent=4)
        print(f"Last seen data saved to {last_seen_file}")

    except json.JSONDecodeError as e:
        print(f"Failed to decode JSON: {e}")
        return False  # Indicate failure in fetching/parsing JSON data

    return True  # Indicate success

def refresh_page(driver):
    """Refresh both the API and forum pages with error handling."""
    print("Refreshing the pages...")
    try:
        # First check if we're still logged in
        driver.get("https://ucp.ls-rp.com/")
        if "Forbidden" in driver.page_source:
            print("Session expired, attempting to relogin...")
            driver.quit()
            new_driver = login_ucp()
            if new_driver:
                return new_driver
            return None
        
        # If still logged in, refresh the API page
        driver.get("https://ucp.ls-rp.com/api/sa/player-list")
        if "403 Forbidden" in driver.page_source:
            print("Lost access to API, attempting to relogin...")
            driver.quit()
            new_driver = login_ucp()
            if new_driver:
                return new_driver
            return None
            
        return driver
    except Exception as e:
        print(f"Error during page refresh: {e}")
        try:
            driver.quit()
        except:
            pass
        return None

def main():
    verification_failure_count = 0
    MAX_VERIFICATION_FAILURES = 3
    
    while True:
        try:
            driver = login_ucp()
            if driver:
                session_start_time = time.time()  # Track when the session started
                verification_failure_count = 0  # Reset verification failure count on successful login
                try:
                    # Refresh every 2 minutes - this is a good balance between:
                    # - Getting timely updates
                    # - Not overwhelming the server
                    # - Avoiding rate limits
                    refresh_interval = 120  # 2 minutes in seconds
                    while True:
                        current_time = time.time()

                        if current_time - session_start_time >= SESSION_REFRESH_INTERVAL:
                            print("Session expired, re-logging in.")
                            driver.quit()
                            driver = login_ucp()
                            if not driver:
                                print("Re-login failed after session expiry. Exiting.")
                                break
                            session_start_time = current_time

                        # Fetch data and update last_seen.json
                        success = fetch_and_save_json_data(driver)
                        if success:
                            print("Data fetched and saved successfully.")
                        else:
                            print("403 Forbidden detected, re-logging in.")
                            driver.quit()
                            driver = login_ucp()
                            if not driver:
                                print("Re-login failed after 403 Forbidden. Exiting.")
                                break
                            session_start_time = time.time()

                        time.sleep(refresh_interval)
                        refresh_page(driver)

                except (NoSuchWindowException, WebDriverException) as e:
                    print(f"Selenium browser error: {e}. Restarting browser session...")
                    try:
                        driver.quit()
                    except Exception:
                        pass
                    continue  # Restart the main while loop
                except ValueError as e:
                    if "Email verification required" in str(e):
                        verification_failure_count += 1
                        print(f"Verification failure {verification_failure_count} of {MAX_VERIFICATION_FAILURES}")
                        
                        if verification_failure_count >= MAX_VERIFICATION_FAILURES:
                            message = "⚠️ Maximum verification failures reached. Please check your email and verify manually."
                            print(message)
                            # Send Discord notification
                            asyncio.run_coroutine_threadsafe(
                                send_discord_notification(message),
                                discord_loop
                            )
                            time.sleep(300)  # Wait 5 minutes before trying again
                            verification_failure_count = 0
                        else:
                            time.sleep(60)  # Wait 1 minute before retrying
                    else:
                        print(f"Unexpected error: {e}")
                        break
                except KeyboardInterrupt:
                    print("Process interrupted by user.")
                    break
                finally:
                    print("Closing the browser.")
                    try:
                        driver.quit()
                    except Exception:
                        pass
            else:
                print("Initial login failed. Exiting script.")
                break
        except (NoSuchWindowException, WebDriverException) as e:
            print(f"Selenium browser error outside main loop: {e}. Restarting...")
            continue
        except KeyboardInterrupt:
            print("Process interrupted by user.")
            break
        except Exception as e:
            print(f"Unexpected error outside main loop: {e}")
            continue


if __name__ == "__main__":
    main()

