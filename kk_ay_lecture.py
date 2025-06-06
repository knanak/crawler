import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import os
import json

class AnyangLecturesCrawler:
    def __init__(self, headless=True, checkpoint_file="anyang_lectures_checkpoint.json"):
        # Configure Chrome options with enhanced stability settings
        self.chrome_options = Options()
        if headless:
            self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--window-size=1920,1080')
        self.chrome_options.add_argument('--disable-gpu')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        # Additional stability options
        self.chrome_options.add_argument('--disable-extensions')
        self.chrome_options.add_argument('--disable-popup-blocking')
        self.chrome_options.add_argument('--ignore-certificate-errors')
        self.chrome_options.add_argument('--disable-web-security')
        self.chrome_options.add_argument('--allow-running-insecure-content')
        # Prevent detection
        self.chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        self.chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        self.chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Initialize the driver with longer page load timeout
        self.driver = webdriver.Chrome(options=self.chrome_options)
        self.driver.set_page_load_timeout(30)  # Increase page load timeout
        self.wait = WebDriverWait(self.driver, 15)  # Increase default wait time
        
        # Structure for lecture data
        self.lecture_data = {
            "City": "경기도 안양시", 
            "Lecture_Category": "",
            "Title": "",
            "Recruitment_period": "",
            "Education_period": "",
            "Institution": "",
            "Address": "",
            "Quota": "",
            "State": "",
            "Register": "",
            "Detail": "",
        }
        
        # Storage for collected lectures
        self.lectures = []
        
        # Checkpoint configuration
        self.checkpoint_file = checkpoint_file
        self.checkpoint = {
            "current_page": 1,
            "last_processed_row": 0,
            "timestamp": ""
        }
        
        # Add user agent to appear more like a regular browser
        self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36'
        })
        
    def navigate_to_url(self, url):
        """Navigate to the main lecture listing URL"""
        print(f"Navigating to {url}")
        try:
            self.driver.get(url)
            time.sleep(3)  # Allow the page to load
            self.save_checkpoint()
            return True
        except Exception as e:
            print(f"Error navigating to URL: {e}")
            return False
        
    def reset_lecture_data(self):
        """Reset the lecture_data dictionary to initial state"""
        self.lecture_data = {
            "City": "경기도 안양시", 
            "Lecture_Category": "",
            "Title": "",
            "Recruitment_period": "",
            "Education_period": "",
            "Institution": "",
            "Address": "",
            "Quota": "",
            "State": "",
            "Register": "",
            "Detail": "",
        }
    
    def navigate_to_section(self, section_num):
        """Navigate to the specified section using side menu buttons"""
        if section_num == 1:
            # Already on the main page, no need to click
            return True
        
        try:
            # Select the appropriate menu button
            menu_selector = f"#container > div.wrap.clearfix > div > div.side_menu > nav > div > ul > li:nth-child({section_num}) > a"
            menu_button = self.driver.find_element(By.CSS_SELECTOR, menu_selector)
            
            # Click the menu button
            self.driver.execute_script("arguments[0].scrollIntoView(true);", menu_button)
            time.sleep(0.5)
            menu_button.click()
            print(f"Clicked on section {section_num} menu button")
            time.sleep(3)  # Wait for the page to load
            
            return True
        except Exception as e:
            print(f"Error navigating to section {section_num}: {e}")
            return False
    
    def extract_lecture_data(self, row_number, section_num=None):
        """Extract lecture data from the table row"""
        print(f"Extracting data from row {row_number}")
        try:
            # Reset lecture data for this row
            self.reset_lecture_data()
            
            # Check if this row has recruiting status
            state_selector = f"#contents > div > table > tbody > tr:nth-child({row_number}) > td:nth-child(7)"
            try:
                state_element = self.driver.find_element(By.CSS_SELECTOR, state_selector)
                state_text = state_element.text.strip()
                
                # If the state is not "모집중", skip this row
                if state_text != "모집중":
                    print(f"Skipping row {row_number} - state is '{state_text}' (not '모집중')")
                    return False
                
                # Set the state since it's "모집중"
                self.lecture_data["State"] = "모집중"
            except NoSuchElementException:
                print(f"State element not found for row {row_number}")
                return False
            
            # CSS selectors for the row
            category_selector = f"#contents > div > table > tbody > tr:nth-child({row_number}) > td:nth-child(2)"
            title_selector = f"#contents > div > table > tbody > tr:nth-child({row_number}) > td.p-subject > a"
            period_selector = f"#contents > div > table > tbody > tr:nth-child({row_number}) > td:nth-child(4)"
            place_selector = f"#contents > div > table > tbody > tr:nth-child({row_number}) > td:nth-child(5)"
            quota_selector = f"#contents > div > table > tbody > tr:nth-child({row_number}) > td:nth-child(6)"
            register_selector = f"#contents > div > table > tbody > tr:nth-child({row_number}) > td:nth-child(8)"
            detail_selector = f"#contents > div > table > tbody > tr:nth-child({row_number}) > td:nth-child(9) > a"
            
            # Extract data from each field
            try:
                category = self.driver.find_element(By.CSS_SELECTOR, category_selector).text.strip()
                self.lecture_data["Lecture_Category"] = category if category else "Not found"
            except NoSuchElementException:
                print(f"Category not found for row {row_number}")
            
            try:
                title_element = self.driver.find_element(By.CSS_SELECTOR, title_selector)
                title = title_element.text.strip()
                self.lecture_data["Title"] = title if title else "Not found"
            except NoSuchElementException:
                print(f"Title not found for row {row_number}")
            
            try:
                # Handle period which has recruitment and education periods separated by <br>
                period_element = self.driver.find_element(By.CSS_SELECTOR, period_selector)
                period_html = period_element.get_attribute('innerHTML')
                
                if "<br>" in period_html:
                    periods = period_html.split("<br>")
                    recruitment = periods[0].strip()
                    education = periods[1].strip()
                    
                    self.lecture_data["Recruitment_period"] = recruitment if recruitment else "Not found"
                    self.lecture_data["Education_period"] = education if education else "Not found"
                else:
                    # If there's no <br>, put the entire text in Recruitment_period
                    period_text = period_element.text.strip()
                    self.lecture_data["Recruitment_period"] = period_text if period_text else "Not found"
                    self.lecture_data["Education_period"] = "Not found"
            except NoSuchElementException:
                print(f"Period information not found for row {row_number}")
            
            try:
                # Handle place which has institution and address separated by <br>
                place_element = self.driver.find_element(By.CSS_SELECTOR, place_selector)
                place_html = place_element.get_attribute('innerHTML')
                
                if "<br>" in place_html:
                    places = place_html.split("<br>")
                    institution = places[0].strip()
                    address = places[1].strip()
                    
                    self.lecture_data["Institution"] = institution if institution else "Not found"
                    self.lecture_data["Address"] = address if address else "Not found"
                else:
                    # If there's no <br>, put the entire text in Institution
                    place_text = place_element.text.strip()
                    self.lecture_data["Institution"] = place_text if place_text else "Not found"
                    self.lecture_data["Address"] = "Not found"
            except NoSuchElementException:
                print(f"Place information not found for row {row_number}")
            
            try:
                quota = self.driver.find_element(By.CSS_SELECTOR, quota_selector).text.strip()
                self.lecture_data["Quota"] = quota if quota else "Not found"
            except NoSuchElementException:
                print(f"Quota not found for row {row_number}")
            
            try:
                register = self.driver.find_element(By.CSS_SELECTOR, register_selector).text.strip()
                self.lecture_data["Register"] = register if register else "Not found"
            except NoSuchElementException:
                print(f"Register information not found for row {row_number}")
            
            try:
                detail_element = self.driver.find_element(By.CSS_SELECTOR, detail_selector)
                detail_url = detail_element.get_attribute('href')
                self.lecture_data["Detail"] = detail_url if detail_url else "Not found"
            except NoSuchElementException:
                print(f"Detail link not found for row {row_number}")
            
            print(f"Successfully extracted data for row {row_number}")
            return True
                
        except Exception as e:
            print(f"Error extracting data from row {row_number}: {e}")
            return False
    
    def count_rows_on_page(self):
        """Count the number of table rows on the current page"""
        try:
            rows = self.driver.find_elements(By.CSS_SELECTOR, "#contents > div > table > tbody > tr")
            return len(rows)
        except Exception as e:
            print(f"Error counting rows: {e}")
            return 0
    
    def navigate_to_specific_page(self, page_number):
        """Navigate to a specific page number using direct URL manipulation"""
        try:
            # Get the current URL
            current_url = self.driver.current_url
            print(f"Current URL: {current_url}")
            
            # Check if there's already a pageIndex parameter
            if "pageIndex=" in current_url:
                # Replace the existing pageIndex parameter
                new_url = current_url.replace(
                    f"pageIndex={self.checkpoint['current_page']}", 
                    f"pageIndex={page_number}"
                )
            else:
                # Add the pageIndex parameter
                new_url = f"{current_url}&pageIndex={page_number}"
            
            print(f"Navigating to page {page_number} using URL: {new_url}")
            self.driver.get(new_url)
            time.sleep(3)  # Wait for the page to load
            
            # Check if there are any rows on this page
            row_count = self.count_rows_on_page()
            if row_count > 0:
                print(f"Successfully navigated to page {page_number}")
                return True
            else:
                print(f"No content found on page {page_number}. This may be the last page.")
                return False
            
        except Exception as e:
            print(f"Error navigating to page {page_number}: {e}")
            return False
    
    def save_to_csv(self, filename="anyang_lectures.csv"):
        """Save the collected lecture data to a CSV file"""
        if not self.lectures:
            print("No lectures to save.")
            return
            
        # Create DataFrame from current lecture data
        df_new = pd.DataFrame(self.lectures)
        
        # Check if file already exists
        file_exists = os.path.isfile(filename)
        
        if file_exists:
            try:
                # Read existing CSV
                df_existing = pd.read_csv(filename, encoding='utf-8-sig')
                
                # Append new data to existing data
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                
                # Remove duplicates
                df_combined = df_combined.drop_duplicates(subset=['City', 'Title', 'Institution', 'Education_period'], keep='last')
                
                # Save combined dataframe
                df_combined.to_csv(filename, index=False, encoding='utf-8-sig', lineterminator='\n')
                print(f"Appended {len(df_new)} lectures to existing file {filename}. Total: {len(df_combined)} lectures")
                
            except Exception as e:
                print(f"Error appending to existing file: {e}")
                # Fallback to creating a new file with current data only
                df_new.to_csv(filename, index=False, encoding='utf-8-sig', lineterminator='\n')
                print(f"Created new file {filename} with {len(df_new)} lectures")
        else:
            # File doesn't exist, create new
            df_new.to_csv(filename, index=False, encoding='utf-8-sig', lineterminator='\n')
            print(f"Created new file {filename} with {len(df_new)} lectures")
        
        # Reset the lectures list to free memory after saving to CSV
        self.lectures = []
        print("Lecture data saved successfully")
    
    def close(self):
        """Close the browser and clean up"""
        self.driver.quit()
    
    def load_checkpoint(self):
        """Load the crawling checkpoint from a file if it exists"""
        if not os.path.exists(self.checkpoint_file):
            print("No checkpoint file found, starting from beginning")
            return False
        
        try:
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                self.checkpoint = json.load(f)
                print(f"Loaded checkpoint: Page {self.checkpoint['current_page']}, Row {self.checkpoint['last_processed_row']}")
                return True
        except Exception as e:
            print(f"Error loading checkpoint: {e}")
            return False
            
    def save_checkpoint(self):
        """Save the current crawling state to a checkpoint file"""
        try:
            self.checkpoint["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
            
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(self.checkpoint, f, ensure_ascii=False, indent=2)
                
            print(f"Checkpoint saved for page {self.checkpoint['current_page']}, row {self.checkpoint['last_processed_row']}")
        except Exception as e:
            print(f"Error saving checkpoint: {e}")
    
    def run(self, start_url, max_pages=10):
        """Run the scraping process for Anyang city lectures"""
        # Load checkpoint if it exists
        checkpoint_exists = self.load_checkpoint()
        
        try:
            # Navigate to the starting point
            self.navigate_to_url(start_url)
            
            if checkpoint_exists:
                start_page = self.checkpoint["current_page"]
                start_row = self.checkpoint["last_processed_row"] + 1  # Start from the next row
            else:
                start_page = 1
                start_row = 1
            
            # Start from page 1
            current_page = start_page
            
            while current_page <= max_pages:
                print(f"\n--- Scraping page {current_page} ---")
                
                # Update checkpoint with current page
                self.checkpoint["current_page"] = current_page
                self.save_checkpoint()
                
                # For pages after the first, navigate directly using URL
                if current_page > 1:
                    success = self.navigate_to_specific_page(current_page)
                    if not success:
                        print(f"Could not navigate to page {current_page}. Ending crawl.")
                        break
                
                # Count rows on this page
                row_count = self.count_rows_on_page()
                if row_count == 0:
                    print("No rows found on this page. Ending crawl.")
                    break
                
                print(f"Found {row_count} rows on page {current_page}")
                
                # Process each row on the page
                for row_num in range(start_row, row_count + 1):
                    print(f"Processing row {row_num}/{row_count} on page {current_page}")
                    
                    # Extract data from this row if it's "모집중"
                    success = self.extract_lecture_data(row_num, 1)  # Always use section 1 since we're only on one page
                    
                    if success:
                        # Add the lecture data to our collection
                        self.lectures.append(self.lecture_data.copy())
                    
                    # Update checkpoint
                    self.checkpoint["last_processed_row"] = row_num
                    self.save_checkpoint()
                    
                    # Small delay between rows
                    time.sleep(0.5)
                
                # Save data after each page
                self.save_to_csv("anyang_lectures.csv")
                
                # Reset the start row for the next page
                start_row = 1
                
                # Move to the next page
                current_page += 1
                self.checkpoint["current_page"] = current_page
                self.checkpoint["last_processed_row"] = 0  # Reset row counter for new page
                self.save_checkpoint()
            
            # Save any remaining data
            if self.lectures:
                self.save_to_csv("anyang_lectures.csv")
            
            print("Crawling completed successfully.")
            
        except KeyboardInterrupt:
            print("\nCrawling interrupted by user. Saving progress...")
            # Save current data and checkpoint
            self.save_to_csv("anyang_lectures.csv")
            self.save_checkpoint()
            print("Progress saved. You can resume later from this point.")
            
        except Exception as e:
            print(f"Error during scraping process: {e}")
            # Save whatever data we've collected so far
            if self.lectures:
                self.save_to_csv("anyang_lectures.csv")
            # Make sure the checkpoint is saved
            self.save_checkpoint()
            print("Saved checkpoint. You can resume from this point later.")
            
        finally:
            self.close()

# Run the crawler
if __name__ == "__main__":
    # URL for Anyang city lecture listings - modified URL as requested
    url = 'https://www.anyang.go.kr/reserve/selectEduLctreWebList.do?key=1376&searchDiv=0&searchInsttNo=&searchRcritSttus=&searchKrwd='
    
    # Create and run the crawler - set headless=False to see the browser in action
    crawler = AnyangLecturesCrawler(headless=False)
    crawler.run(url, max_pages=10)  # Crawl up to 10 pages