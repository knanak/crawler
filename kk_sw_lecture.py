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

class SuwonEducationCrawler:
    def __init__(self, headless=True, checkpoint_file="suwon_education_checkpoint.json"):
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
            "City": "경기도 수원시", 
            "Title": "",
            "Recruitment_period": "",
            "Education_period": "",
            "Date": "",
            "Quota": "",
            "Institution" : "",
            "Address": "",
            "State": "",
            "Detail": "",
        }
        
        # Storage for collected lectures
        self.lectures = []
        
        # Checkpoint configuration
        self.checkpoint_file = checkpoint_file
        self.checkpoint = {
            "current_page": 1,
            "last_processed_row": 0,
            "page_type": "normal",  # normal for pages 1-10, next for pages 11-20, etc.
            "last_url": "",
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
        self.checkpoint["last_url"] = url
        self.save_checkpoint()
        
    def reset_lecture_data(self):
        """Reset the lecture_data dictionary to initial state"""
        self.lecture_data = {
            "City": "경기도 수원시",
            "Title": "Not found",
            "Recruitment_period": "Not found",
            "Education_period": "Not found",
            "Date": "Not found",
            "Quota": "Not found",
            "Institution" : "",
            "Address": "Not found",
            "State": "Not found",
            "Detail": "Not found"
        }
    
    def extract_lecture_data(self, row_number):
        """Extract lecture data from the table row"""
        print(f"Extracting data from row {row_number}")
        try:
            # Reset lecture data for this row
            self.reset_lecture_data()
            
            # CSS selectors for the row
            title_selector = f"#contents_box > table > tbody > tr:nth-child({row_number}) > td.p-subject"
            period_selector = f"#contents_box > table > tbody > tr:nth-child({row_number}) > td:nth-child(3)"
            date_selector = f"#contents_box > table > tbody > tr:nth-child({row_number}) > td:nth-child(4)"
            quota_selector = f"#contents_box > table > tbody > tr:nth-child({row_number}) > td:nth-child(6)"
            address_selector = f"#contents_box > table > tbody > tr:nth-child({row_number}) > td:nth-child(7)"
            state_selector = f"#contents_box > table > tbody > tr:nth-child({row_number}) > td.edu"
            
            # Extract title and detail URL
            try:
                title_element = self.driver.find_element(By.CSS_SELECTOR, title_selector)
                title = title_element.text.strip()
                self.lecture_data["Title"] = title if title else "Not found"
                
                # Get detail URL
                try:
                    # Look for anchor tag within the title cell
                    a_tag = title_element.find_element(By.TAG_NAME, "a")
                    href = a_tag.get_attribute("href")
                    self.lecture_data["Detail"] = href if href else "Not found"
                except:
                    self.lecture_data["Detail"] = "Not found"
            except NoSuchElementException:
                print(f"Title not found for row {row_number}")
            
            # Extract period (recruitment and education periods)
            try:
                period_element = self.driver.find_element(By.CSS_SELECTOR, period_selector)
                period_text = period_element.get_attribute('innerHTML')
                
                # Split by <br> tag to separate recruitment and education periods
                if "<br>" in period_text:
                    periods = period_text.split("<br>")
                    recruitment = periods[0].strip()
                    education = periods[1].strip()
                    self.lecture_data["Recruitment_period"] = recruitment if recruitment else "Not found"
                    self.lecture_data["Education_period"] = education if education else "Not found"
                else:
                    # If there's no <br>, put all text in Recruitment_period
                    period_text = period_element.text.strip()
                    self.lecture_data["Recruitment_period"] = period_text if period_text else "Not found"
            except NoSuchElementException:
                print(f"Period not found for row {row_number}")
            
            # Extract date
            try:
                date = self.driver.find_element(By.CSS_SELECTOR, date_selector).text.strip()
                self.lecture_data["Date"] = date if date else "Not found"
            except NoSuchElementException:
                print(f"Date not found for row {row_number}")
            
            # Extract quota
            try:
                quota = self.driver.find_element(By.CSS_SELECTOR, quota_selector).text.strip()
                self.lecture_data["Quota"] = quota if quota else "Not found"
            except NoSuchElementException:
                print(f"Quota not found for row {row_number}")
            
            # Extract address
            try:
                address = self.driver.find_element(By.CSS_SELECTOR, address_selector).text.strip()
                self.lecture_data["Address"] = address if address else "Not found"
            except NoSuchElementException:
                print(f"Address not found for row {row_number}")
            
            # Extract state
            try:
                state = self.driver.find_element(By.CSS_SELECTOR, state_selector).text.strip()
                self.lecture_data["State"] = state if state else "Not found"
            except NoSuchElementException:
                print(f"State not found for row {row_number}")
            
            print(f"Successfully extracted data for row {row_number}")
            return True
                
        except Exception as e:
            print(f"Error extracting data from row {row_number}: {e}")
            return False
    
    def count_rows_on_page(self):
        """Count the number of table rows on the current page"""
        try:
            rows = self.driver.find_elements(By.CSS_SELECTOR, "#contents_box > table > tbody > tr")
            return len(rows)
        except Exception as e:
            print(f"Error counting rows: {e}")
            return 0
    
    def go_to_next_page(self, current_page):
        """Navigate to the next page of results"""
        try:
            # Calculate which pagination set we're in (1-10, 11-20, 21-30, etc.)
            page_set = (current_page - 1) // 10
            next_page = current_page + 1
            next_page_in_set = (next_page - 1) % 10 + 1
            
            print(f"Current page: {current_page}, Next page: {next_page}, Page set: {page_set}, Next page in set: {next_page_in_set}")
            
            # Check if we need to move to the next set of pages (e.g., from page 10 to 11)
            if next_page_in_set == 1:
                # We need to click the "next" button to go to the next set
                next_set_selector = "#contents_box > div.p-pagination > div > span:nth-child(3) > a.p-page__link.next"
                try:
                    next_button = self.driver.find_element(By.CSS_SELECTOR, next_set_selector)
                    print("Found 'next set' button, clicking...")
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                    time.sleep(0.5)
                    next_button.click()
                    print("Clicked next set button")
                    self.checkpoint["page_type"] = "next"
                    time.sleep(3)  # Wait for the page to load
                    return True
                except NoSuchElementException:
                    print("No 'next set' button found. This might be the last page set.")
                    return False
            else:
                # We're still in the same set of pages, just click the next number
                if next_page_in_set == 1:
                    page_index = 1  # First page in a set has index 1
                else:
                    page_index = next_page_in_set
                
                next_page_selector = f"#contents_box > div.p-pagination > div > span.p-page__link-group > a:nth-child({page_index})"
                
                try:
                    next_button = self.driver.find_element(By.CSS_SELECTOR, next_page_selector)
                    print(f"Found page number {next_page} button, clicking...")
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                    time.sleep(0.5)
                    next_button.click()
                    print(f"Clicked page number {next_page} button")
                    time.sleep(3)  # Wait for the page to load
                    return True
                except NoSuchElementException:
                    print(f"Could not find page number {next_page}. This might be the last page.")
                    return False
                
        except Exception as e:
            print(f"Error navigating to next page: {e}")
            return False
    
    def save_to_csv(self, filename="suwon_education.csv"):
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
                df_combined = df_combined.drop_duplicates(subset=['Title', 'Education_period', 'Address'], keep='last')
                
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
                print(f"Loaded checkpoint: Page {self.checkpoint['current_page']}, Row {self.checkpoint['last_processed_row']}, Page type: {self.checkpoint.get('page_type', 'normal')}")
                
                # Ensure the page_type field exists
                if 'page_type' not in self.checkpoint:
                    self.checkpoint['page_type'] = 'normal'
                    
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
                
            print(f"Checkpoint saved for page {self.checkpoint['current_page']}, row {self.checkpoint['last_processed_row']}, page type: {self.checkpoint['page_type']}")
        except Exception as e:
            print(f"Error saving checkpoint: {e}")
    
    def navigate_to_checkpoint(self, base_url):
        """Navigate to the page specified in the checkpoint"""
        target_page = self.checkpoint["current_page"]
        
        if self.checkpoint["last_url"]:
            # If we have a last URL, use that directly
            self.navigate_to_url(self.checkpoint["last_url"])
            return
        
        # Otherwise, calculate the URL based on page number
        if target_page > 1:
            # Modify the URL to go to the specific page
            url = base_url.replace("q_currPage=1", f"q_currPage={target_page}")
            self.navigate_to_url(url)
        else:
            self.navigate_to_url(base_url)
    
    def run(self, start_url, max_pages=100):
        """Run the scraping process for the Suwon education programs"""
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
                self.save_to_csv("suwon_education.csv")
                
                # Reset the start row for the next page
                start_row = 1
                
                # Go to the next page
                success = self.go_to_next_page(current_page)
                if not success:
                    print("Could not navigate to next page. Ending crawl.")
                    break
                
                current_page += 1
                self.checkpoint["current_page"] = current_page
                self.checkpoint["last_processed_row"] = 0  # Reset row counter for new page
                self.save_checkpoint()
            
            # Save any remaining data
            if self.lectures:
                self.save_to_csv("suwon_education.csv")
            
            print("Crawling completed successfully.")
            
        except KeyboardInterrupt:
            print("\nCrawling interrupted by user. Saving progress...")
            # Save current data and checkpoint
            self.save_to_csv("suwon_education.csv")
            self.save_checkpoint()
            print("Progress saved. You can resume later from this point.")
            
        except Exception as e:
            print(f"Error during scraping process: {e}")
            # Save whatever data we've collected so far
            if self.lectures:
                self.save_to_csv("suwon_education.csv")
            # Make sure the checkpoint is saved
            self.save_checkpoint()
            print("Saved checkpoint. You can resume from this point later.")
            
        finally:
            self.close()
            

# Run the crawler
if __name__ == "__main__":
    # URL for Suwon education listings
    url = 'https://www.suwon.go.kr/web/reserv/edu/list.do?q_rowPerPage=10&q_currPage=1&q_sortName=&q_sortOrder=&q_orgSeqNo=&q_serviceSeqNo=&q_searchKey=ALL&q_progressStatusCd=72&q_searchVal='
    
    # Create and run the crawler - set headless=False to see the browser in action
    crawler = SuwonEducationCrawler(headless=False)
    crawler.run(url, max_pages=100)  # Crawl up to 100 pages