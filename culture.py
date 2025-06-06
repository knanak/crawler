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

class CulturalLecturesCrawler:
    def __init__(self, headless=True, checkpoint_file="cultural_lectures_checkpoint.json"):
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
        
        # Structure for lecture data - Added Tel field
        self.lecture_data = {
            "Institution": "",
            "Title": "",
            "Recruitment_period": "",
            "Education_period": "",
            "Fees": "",
            "Quota": "",
            "Detail": "",
            "Tel": ""
        }
        
        # Storage for collected lectures
        self.lectures = []
        
        # Checkpoint configuration
        self.checkpoint_file = checkpoint_file
        self.checkpoint = {
            "current_page": 1,
            "last_processed_row": 0,
            "current_page_index": 3,  # Starting index for pagination (a:nth-child(3))
            "timestamp": ""
        }
        
        # Add user agent to appear more like a regular browser
        self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36'
        })
        
    def navigate_to_url(self, url):
        """Navigate to the main lecture listing URL"""
        print(f"Navigating to {url}")
        self.driver.get(url)
        time.sleep(3)  # Allow the page to load
        self.save_checkpoint()
        
    def reset_lecture_data(self):
        """Reset the lecture_data dictionary to initial state"""
        self.lecture_data = {
            "Institution": "Not found",
            "Title": "Not found",
            "Recruitment_period": "Not found",
            "Education_period": "Not found",
            "Fees": "Not found",
            "Quota": "Not found",
            "Detail": "Not found",
            "Tel": "Not found"
        }
    
    def extract_detail_and_tel(self, row_number):
        """Extract detail URL and telephone number from the detail page"""
        try:
            # Find the detail button for this row
            detail_button_selector = f"body > div:nth-child(6) > div.campus-course-list-table > table > tbody > tr:nth-child({row_number}) > td.td-normal-btn > a"
            
            
            try:
                detail_button = self.driver.find_element(By.CSS_SELECTOR, detail_button_selector)
                
                # Get the detail URL
                detail_url = detail_button.get_attribute('href')
                self.lecture_data["Detail"] = detail_url if detail_url else "Not found"
                print(f"Found detail URL: {detail_url}")
                
                # Click the detail button to go to detail page
                # Store current window handle
                main_window = self.driver.current_window_handle
                
                # Click the link
                detail_button.click()
                time.sleep(2)  # Wait for page load
                
                # Check if a new window/tab opened
                if len(self.driver.window_handles) > 1:
                    # Switch to the new window
                    for window_handle in self.driver.window_handles:
                        if window_handle != main_window:
                            self.driver.switch_to.window(window_handle)
                            break
                
                # Extract telephone number from detail page
                try:
                    tel_selector = "body > div.container > div.course-content.clearfix > div.course-right > div.course-contact > p > a"
                    tel_element = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, tel_selector)))
                    tel_number = tel_element.text.strip()
                    self.lecture_data["Tel"] = tel_number if tel_number else "Not found"
                    print(f"Found telephone: {tel_number}")
                except Exception as e:
                    print(f"Could not find telephone number: {e}")
                    self.lecture_data["Tel"] = "Not found"
                
                # Close the detail window if it's a new window/tab
                if len(self.driver.window_handles) > 1:
                    self.driver.close()
                    self.driver.switch_to.window(main_window)
                else:
                    # If same window, go back
                    self.driver.back()
                    time.sleep(2)  # Wait for page to load
                
            except NoSuchElementException:
                print(f"Detail button not found for row {row_number}")
                self.lecture_data["Detail"] = "Not found"
                self.lecture_data["Tel"] = "Not found"
                
        except Exception as e:
            print(f"Error extracting detail and tel for row {row_number}: {e}")
            self.lecture_data["Detail"] = "Not found"
            self.lecture_data["Tel"] = "Not found"
    
    def extract_lecture_data(self, row_number):
        """Extract lecture data from the table row"""
        print(f"Extracting data from row {row_number}")
        try:
            # Reset lecture data for this row
            self.reset_lecture_data()
            
            # CSS selectors for the row
            institution_selector = f"body > div:nth-child(6) > div.campus-course-list-table > table > tbody > tr:nth-child({row_number}) > td.td-normal.td-normal--first"
            title_selector = f"body > div:nth-child(6) > div.campus-course-list-table > table > tbody > tr:nth-child({row_number}) > td:nth-child(4)"
            recruitment_selector = f"body > div:nth-child(6) > div.campus-course-list-table > table > tbody > tr:nth-child({row_number}) > td:nth-child(5)"
            education_selector = f"body > div:nth-child(6) > div.campus-course-list-table > table > tbody > tr:nth-child({row_number}) > td:nth-child(6)"
            fees_selector = f"body > div:nth-child(6) > div.campus-course-list-table > table > tbody > tr:nth-child({row_number}) > td:nth-child(8)"
            quota_selector = f"body > div:nth-child(6) > div.campus-course-list-table > table > tbody > tr:nth-child({row_number}) > td:nth-child(9)"
            
            # Extract data from each field
            try:
                institution = self.driver.find_element(By.CSS_SELECTOR, institution_selector).text.strip()
                self.lecture_data["Institution"] = institution if institution else "Not found"
            except NoSuchElementException:
                print(f"Institution not found for row {row_number}")
            
            try:
                title = self.driver.find_element(By.CSS_SELECTOR, title_selector).text.strip()
                self.lecture_data["Title"] = title if title else "Not found"
            except NoSuchElementException:
                print(f"Title not found for row {row_number}")
            
            try:
                recruitment = self.driver.find_element(By.CSS_SELECTOR, recruitment_selector).text.strip()
                self.lecture_data["Recruitment_period"] = recruitment if recruitment else "Not found"
            except NoSuchElementException:
                print(f"Recruitment period not found for row {row_number}")
            
            try:
                education = self.driver.find_element(By.CSS_SELECTOR, education_selector).text.strip()
                self.lecture_data["Education_period"] = education if education else "Not found"
            except NoSuchElementException:
                print(f"Education period not found for row {row_number}")
            
            try:
                fees = self.driver.find_element(By.CSS_SELECTOR, fees_selector).text.strip()
                self.lecture_data["Fees"] = fees if fees else "Not found"
            except NoSuchElementException:
                print(f"Fees not found for row {row_number}")
            
            try:
                quota = self.driver.find_element(By.CSS_SELECTOR, quota_selector).text.strip()
                self.lecture_data["Quota"] = quota if quota else "Not found"
            except NoSuchElementException:
                print(f"Quota not found for row {row_number}")
            
            # Extract detail URL and telephone number
            self.extract_detail_and_tel(row_number)
            
            print(f"Successfully extracted data for row {row_number}")
            return True
                
        except Exception as e:
            print(f"Error extracting data from row {row_number}: {e}")
            return False
    
    def count_rows_on_page(self):
        """Count the number of table rows on the current page"""
        try:
            rows = self.driver.find_elements(By.CSS_SELECTOR, "body > div:nth-child(6) > div.campus-course-list-table > table > tbody > tr")
            return len(rows)
        except Exception as e:
            print(f"Error counting rows: {e}")
            return 0
    
    def go_to_next_page(self):
        """Navigate to the next page of results
        
        This function attempts to navigate through pagination links (a:nth-child(3) through a:nth-child(10))
        until there is no more data to crawl.
        """
        try:
            # First check if we're at the end of available pages
            # We'll try to find the next pagination element
            pagination_wrapper = self.driver.find_element(By.CSS_SELECTOR, "body > div:nth-child(6) > div.pagination-wrapper > div")
            pagination_links = pagination_wrapper.find_elements(By.TAG_NAME, "a")
            
            # Get the current page index from checkpoint
            current_page_index = self.checkpoint["current_page_index"]
            
            # Check if we need to reset page index and move to next set of pages
            # This happens when we've gone through links 3-10 and need to click "next page set" button
            if current_page_index > 10:
                # Try to click the "next page set" button (typically the last link in pagination)
                next_set_button = None
                for link in pagination_links:
                    if "다음" in link.text or "next" in link.text.lower() or ">" in link.text:
                        next_set_button = link
                        break
                
                if next_set_button:
                    print("Moving to next set of pages...")
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", next_set_button)
                    time.sleep(0.5)
                    next_set_button.click()
                    print("Clicked next page set button")
                    time.sleep(3)  # Wait for the page to load
                    
                    # Reset page index to 3 for the new set of pages
                    self.checkpoint["current_page_index"] = 3
                    return True
                else:
                    print("No more page sets available. End of pagination.")
                    return False
            
            # Try to find and click the next page number
            next_page_selector = f"body > div:nth-child(6) > div.pagination-wrapper > div > a:nth-child({current_page_index})"
            
            try:
                next_button = self.driver.find_element(By.CSS_SELECTOR, next_page_selector)
                
                # Check if this is an active link (not the current page)
                current_class = next_button.get_attribute("class")
                if "active" in current_class or "current" in current_class:
                    # This is the current page, move to the next index
                    self.checkpoint["current_page_index"] += 1
                    return self.go_to_next_page()  # Recursively try the next index
                
                # Click the next page link
                self.driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                time.sleep(0.5)
                next_button.click()
                print(f"Clicked page link: index {current_page_index}")
                time.sleep(3)  # Wait for the page to load
                
                # Increment the page index for next time
                self.checkpoint["current_page_index"] += 1
                return True
            
            except NoSuchElementException:
                # If we can't find the specific link, check if there's any next page available
                has_next_page = False
                for i in range(3, 11):
                    try:
                        test_selector = f"body > div:nth-child(6) > div.pagination-wrapper > div > a:nth-child({i})"
                        self.driver.find_element(By.CSS_SELECTOR, test_selector)
                        has_next_page = True
                        break
                    except NoSuchElementException:
                        continue
                
                if not has_next_page:
                    print("No more page links available. End of pagination.")
                    return False
                
                # If we found other page links but not the one we were looking for,
                # reset the page index and try again
                self.checkpoint["current_page_index"] = 3
                return self.go_to_next_page()
                
        except Exception as e:
            print(f"Error navigating to next page: {e}")
            return False
    
    def save_to_csv(self, filename="cultural_lectures.csv"):
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
                
                # Check if Tel column exists in existing data
                if 'Tel' not in df_existing.columns:
                    df_existing['Tel'] = 'Not found'
                
                # Append new data to existing data
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                
                # Remove duplicates
                df_combined = df_combined.drop_duplicates(subset=['Institution', 'Title', 'Education_period'], keep='last')
                
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
                print(f"Loaded checkpoint: Page {self.checkpoint['current_page']}, Row {self.checkpoint['last_processed_row']}, Page Index {self.checkpoint.get('current_page_index', 3)}")
                
                # Ensure the current_page_index field exists
                if 'current_page_index' not in self.checkpoint:
                    self.checkpoint['current_page_index'] = 3
                    
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
                
            print(f"Checkpoint saved for page {self.checkpoint['current_page']}, row {self.checkpoint['last_processed_row']}, page index {self.checkpoint['current_page_index']}")
        except Exception as e:
            print(f"Error saving checkpoint: {e}")
    
    def navigate_to_checkpoint(self, base_url):
        """Navigate to the page specified in the checkpoint"""
        target_page = self.checkpoint["current_page"]
        if target_page > 1:
            url = base_url.replace("page=1", f"page={target_page}")
            self.navigate_to_url(url)
        else:
            self.navigate_to_url(base_url)
    
    def run(self, start_url, max_pages=50):
        """Run the scraping process for the cultural lectures"""
        # Load checkpoint if it exists
        checkpoint_exists = self.load_checkpoint()
        
        try:
            # Navigate to the appropriate starting point
            if checkpoint_exists:
                self.navigate_to_checkpoint(start_url)
                start_page = self.checkpoint["current_page"]
                start_row = self.checkpoint["last_processed_row"] + 1  # Start from the next row
            else:
                self.navigate_to_url(start_url)
                start_page = 1
                start_row = 1
            
            current_page = start_page
            
            while current_page <= max_pages:
                print(f"\n--- Scraping page {current_page} ---")
                
                # Update checkpoint with current page
                self.checkpoint["current_page"] = current_page
                self.save_checkpoint()
                
                # Count rows on this page
                row_count = self.count_rows_on_page()
                if row_count == 0:
                    print("No rows found on this page. Ending crawl.")
                    break
                
                print(f"Found {row_count} rows on page {current_page}")
                
                # Process each row on the page
                for row_num in range(start_row, row_count + 1):
                    print(f"Processing row {row_num}/{row_count} on page {current_page}")
                    
                    # Extract data from this row
                    success = self.extract_lecture_data(row_num)
                    
                    if success:
                        # Add the lecture data to our collection
                        self.lectures.append(self.lecture_data.copy())
                        
                        # Update checkpoint
                        self.checkpoint["last_processed_row"] = row_num
                        self.save_checkpoint()
                    
                    # Small delay between rows
                    time.sleep(0.5)
                
                # Save data after each page
                self.save_to_csv("cultural_lectures.csv")
                
                # Reset the start row for the next page
                start_row = 1
                
                # Go to the next page
                success = self.go_to_next_page()
                if not success:
                    print("Could not navigate to next page. Ending crawl.")
                    break
                
                current_page += 1
                self.checkpoint["current_page"] = current_page
                self.checkpoint["last_processed_row"] = 0  # Reset row counter for new page
                self.save_checkpoint()
            
            # Save any remaining data
            if self.lectures:
                self.save_to_csv("cultural_lectures.csv")
            
            print("Crawling completed successfully.")
            
        except KeyboardInterrupt:
            print("\nCrawling interrupted by user. Saving progress...")
            # Save current data and checkpoint
            self.save_to_csv("cultural_lectures.csv")
            self.save_checkpoint()
            print("Progress saved. You can resume later from this point.")
            
        except Exception as e:
            print(f"Error during scraping process: {e}")
            # Save whatever data we've collected so far
            if self.lectures:
                self.save_to_csv("cultural_lectures.csv")
            # Make sure the checkpoint is saved
            self.save_checkpoint()
            print("Saved checkpoint. You can resume from this point later.")
            
        finally:
            self.close()

# Run the crawler
if __name__ == "__main__":
    # URL for cultural lecture listings
    url = 'https://50plus.or.kr/education.do?page=1&cost=ALL&state=JOIN&type=ALL&'
    
    # Create and run the crawler - set headless=False to see the browser in action
    crawler = CulturalLecturesCrawler(headless=False)
    crawler.run(url, max_pages=30)  # Crawl up to 30 pages