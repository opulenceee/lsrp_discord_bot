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

load_dotenv() # Load environment variables from .env file

UCP_USERNAME = os.getenv('UCP_USERNAME')
UCP_PASSWORD = os.getenv('UCP_PASSWORD')
SESSION_REFRESH_INTERVAL = 24 * 60 * 60  # 48 hours in seconds
MAX_LOGIN_RETRIES = 3  # Number of login attempts before a full restart
RESTART_DELAY = 10  # Time in seconds before retrying after max login retries


def login_ucp():
    retries = 0  # Track login attempts
    while retries < MAX_LOGIN_RETRIES:
        try:
            print(f"Attempt {retries + 1} of {MAX_LOGIN_RETRIES} to log in.")

            # Setup Chrome options
            options = uc.ChromeOptions()
            options.add_argument("--auto-open-devtools-for-tabs")
            options.add_argument('--headless')  # Run Chrome in headless mode
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')

            driver = uc.Chrome(headless=True, use_subprocess=True, options=options)
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

            # Check if login was successful
            if "Forbidden" in driver.page_source:
                raise ValueError("403 Forbidden: Login failed.")
            
            # Navigate to API page after login
            driver.get("https://ucp.ls-rp.com/api/sa/player-list")
            if "403 Forbidden" in driver.page_source:
                raise ValueError("403 Forbidden: Access to player list API denied.")

            print("Login successful.")
            return driver  # Return driver if login is successful

        except Exception as e:
            print(f"Login attempt {retries + 1} failed: {e}")
            retries += 1
            driver.quit()  # Close driver on failure

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
        with open('data/player_list.json', 'w') as json_file:
            json.dump(json_data, json_file, indent=4)
        print("Player list data saved to data/player_list.json")
    except json.JSONDecodeError as e:
        print(f"Failed to decode JSON: {e}")
        return False  # Indicate failure in fetching/parsing JSON data

    return True  # Indicate success


def refresh_page(driver):
    """Refresh both the API and forum pages."""
    print("Refreshing the pages...")
    driver.refresh()  # Refresh API page


def main():
    while True:
        driver = login_ucp()
        if driver:
            session_start_time = time.time()  # Track when the session started
            try:
                refresh_interval = 15  # Refresh interval in seconds
                while True:
                    current_time = time.time()

                    # Check if session needs to be refreshed based on SESSION_REFRESH_INTERVAL
                    if current_time - session_start_time >= SESSION_REFRESH_INTERVAL:
                        print("Session expired, re-logging in.")
                        driver.quit()
                        driver = login_ucp()  # Force re-login
                        if not driver:
                            print("Re-login failed after session expiry. Exiting.")
                            break  # Exit loop if re-login fails
                        session_start_time = current_time  # Reset session timer

                    # Fetch data
                    success = fetch_and_save_json_data(driver)
                    if success:
                        print("Data fetched and saved successfully.")
                    else:
                        # Force re-login on 403 Forbidden
                        print("403 Forbidden detected, re-logging in.")
                        driver.quit()
                        driver = login_ucp()
                        if not driver:
                            print("Re-login failed after 403 Forbidden. Exiting.")
                            break
                        session_start_time = time.time()  # Reset session start time on re-login

                    time.sleep(refresh_interval)  # Wait before the next fetch
                    refresh_page(driver)

            except KeyboardInterrupt:
                print("Process interrupted by user.")
            finally:
                print("Closing the browser.")
                driver.quit()
        else:
            print("Initial login failed. Exiting script.")
            break


if __name__ == "__main__":
    main()