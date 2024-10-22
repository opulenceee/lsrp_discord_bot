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



def login_ucp():
    options = uc.ChromeOptions()
    options.add_argument("--auto-open-devtools-for-tabs")
    options.add_argument('--headless')  # This runs Chrome in headless mode
    options.add_argument('--no-sandbox')  # Allows running as root
    options.add_argument('--disable-dev-shm-usage')

    driver = uc.Chrome(headless = True,use_subprocess=True)
    driver.execute_script('''window.open("https://ucp.ls-rp.com/","_blank");''') # open page in new ta
    print('Opened Chrome, initiating now.')
    time.sleep(5) # wait until page has loaded
    driver.switch_to.window(window_name=driver.window_handles[0])   # switch to first tab
    driver.close() # close first tab
    driver.switch_to.window(window_name=driver.window_handles[0] )  # switch back to new tab
   

    
    try:
     
        print(f"Current url: {driver.current_url}")
        username_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//input[@formcontrolname="name"]'))
        )

        print('Username input has been typed.')
        password_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//input[@formcontrolname="password"]'))
        )
        print('Password input has been typed.')

        print('Both inputs have been typed, script continues.')


        # Send username and password
        username_input.send_keys(UCP_USERNAME)
        password_input.send_keys(UCP_PASSWORD)

        # Submit login
        password_input.send_keys(Keys.RETURN)
        print('Sent both credintials.')

        time.sleep(5)

        # Check if login is successful
        if driver.current_url == 'https://ucp.ls-rp.com/':
            print("Login successful.")
            # Navigate to API page after login
            driver.get('https://ucp.ls-rp.com/api/sa/player-list')
            return driver  # Return the driver instance
        else:
            print("Login failed. Check your credentials.")
            driver.quit()  # Quit the driver on failure

    except Exception as e:
        print(f"An error occurred while logging in: {e}")
        driver.quit()  # Quit the driver if an error occurs

    return None


def fetch_and_save_json_data(driver):
    time.sleep(5)
    
    # Fetch the body text which contains the JSON data
    body_text = driver.find_element(By.TAG_NAME, 'body').text
    
    print("Body text received:")
    print(body_text)  # DEBUG: Show the raw response for inspection

    try:
        # Parse the body text as JSON
        json_data = json.loads(body_text)

        # Save the parsed JSON data to a file
        with open('player_list.json', 'w') as json_file:
            json.dump(json_data, json_file, indent=4)
        print("Player list data saved to player_list.json")
    except json.JSONDecodeError as e:
        print(f"Failed to decode JSON: {e}")
        return False  # Indicate a failure in fetching/parsing JSON data

    return True  # Indicate success


def refresh_page(driver):
    print("Refreshing the page...")
    driver.refresh()  # just refreshing api page


def main():
    driver = login_ucp()

    if driver:
        try:
            refresh_interval = 30  
            
            while True:  
                success = fetch_and_save_json_data(driver)  
                
                if success:
                    print("Data fetched and saved successfully.")
                else:
                    print("Data fetching failed. Retrying after refresh.")
                time.sleep(refresh_interval)
                refresh_page(driver)
        
        except KeyboardInterrupt:
            print("Process interrupted by user.")
        finally:
            print("Closing the browser.")
            driver.quit()  

if __name__ == "__main__":
    main()