import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import os
import json
import re

class AndongEducationCrawler:
    def __init__(self, headless=True, checkpoint_file="andong_education_checkpoint.json"):
        try:
            # Configure Chrome options
            self.chrome_options = Options()
            if headless:
                self.chrome_options.add_argument('--headless=new')
            self.chrome_options.add_argument('--window-size=1920,1080')
            self.chrome_options.add_argument('--disable-gpu')
            self.chrome_options.add_argument('--no-sandbox')
            self.chrome_options.add_argument('--disable-dev-shm-usage')
            self.chrome_options.add_argument('--disable-extensions')
            self.chrome_options.add_argument('--disable-popup-blocking')
            self.chrome_options.add_argument('--ignore-certificate-errors')
            self.chrome_options.add_argument('--ignore-ssl-errors')
            self.chrome_options.add_argument('--disable-web-security')
            self.chrome_options.add_argument('--allow-running-insecure-content')
            self.chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            self.chrome_options.add_experimental_option('excludeSwitches', ['enable-automation', 'enable-logging'])
            self.chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Initialize the driver
            self.driver = webdriver.Chrome(options=self.chrome_options)
            self.driver.set_page_load_timeout(60)
            self.wait = WebDriverWait(self.driver, 30)
            
            # Structure for lecture data
            self.lecture_data = {
                "Id": 0,
                "Title": "",
                "Education_period": "",
                "Quota": "",
                "Fee": "",
                "Address": "",
                "Category": "안동시",  # Fixed value for Andong
                "Detail": ""
            }
            
            # Storage for collected lectures
            self.lectures = []
            self.current_id = 1
            
            # Checkpoint configuration
            self.checkpoint_file = checkpoint_file
            self.checkpoint = {
                "current_page": 1,
                "last_processed_item": 0,
                "last_id": 0,
                "last_url": "",
                "timestamp": ""
            }
            
            # Add user agent
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
            })
            
        except Exception as e:
            print(f"Error during initialization: {e}")
            raise e
    
    def navigate_to_url(self, url):
        """Navigate to URL"""
        print(f"Navigating to {url}")
        try:
            self.driver.get(url)
            time.sleep(5)
            self.checkpoint["last_url"] = url
            self.save_checkpoint()
        except Exception as e:
            print(f"Error during navigation: {e}")
            self.driver.get(url)
            time.sleep(10)
    
    def reset_lecture_data(self):
        """Reset the lecture_data dictionary"""
        self.lecture_data = {
            "Id": self.current_id,
            "Title": "Not found",
            "Education_period": "Not found",
            "Quota": "Not found",
            "Fee": "Not found",
            "Address": "Not found",
            "Category": "안동시",
            "Detail": "Not found"
        }
    
    def check_test_course(self, item_index):
        """Check if the course is a test course"""
        try:
            title_selector = f"#listForm > div.list-cont.open > ul > li:nth-child({item_index}) > a > p"
            title_element = self.driver.find_element(By.CSS_SELECTOR, title_selector)
            title_text = title_element.text.strip()
            
            # Check for test course keywords
            test_keywords = ['테스트강좌', '테스트 강좌']
            for keyword in test_keywords:
                if keyword in title_text:
                    print(f"Item {item_index} is a test course ('{title_text}'), skipping...")
                    return True
            
            return False
        except Exception as e:
            print(f"Error checking test course: {e}")
            return False
    
    def close_popup(self):
        """Close the popup window"""
        try:
            close_selector = "#layerpopup_mycode > div > div.pop-con > div.btn-box.taC > a.button.icon.del.close.pop-close"
            close_button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, close_selector))
            )
            close_button.click()
            time.sleep(1)
            print("Popup closed successfully")
            return True
        except Exception as e:
            print(f"Error closing popup: {e}")
            # Try alternative close methods
            try:
                # Try to find any element with class 'close' or 'pop-close'
                close_elements = self.driver.find_elements(By.CSS_SELECTOR, ".pop-close, .close")
                if close_elements:
                    close_elements[0].click()
                    time.sleep(1)
                    return True
            except:
                pass
            return False
    
    def extract_lecture_from_popup(self, item_index):
        """Extract lecture data from popup after clicking item"""
        try:
            print(f"\n>>> Extracting data from item {item_index}")
            
            # Check if it's a test course
            if self.check_test_course(item_index):
                return False
            
            # Reset lecture data
            self.reset_lecture_data()
            
            # Click on the item to open popup
            item_selector = f"#listForm > div.list-cont.open > ul > li:nth-child({item_index}) > a"
            try:
                item_element = self.wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, item_selector))
                )
                
                # Get the detail URL
                detail_url = item_element.get_attribute('href')
                
                # Check if it's a javascript URL
                if detail_url and 'javascript:' not in detail_url.lower():
                    self.lecture_data["Detail"] = detail_url
                    print(f"Detail URL: {detail_url}")
                else:
                    # Try to extract from onclick attribute
                    onclick = item_element.get_attribute('onclick')
                    if onclick:
                        # Extract any ID or parameters from onclick
                        # Look for patterns like idx=123 or similar
                        import re
                        idx_match = re.search(r'idx["\']?\s*[:=]\s*["\']?(\d+)', onclick)
                        if idx_match:
                            idx = idx_match.group(1)
                            # Construct a meaningful URL using the base URL and the ID
                            base_url = self.driver.current_url.split('?')[0]
                            self.lecture_data["Detail"] = f"{base_url}?idx={idx}"
                            print(f"Detail URL (constructed from idx): {self.lecture_data['Detail']}")
                        else:
                            # If no ID found, create a unique identifier
                            current_url = self.driver.current_url
                            self.lecture_data["Detail"] = f"{current_url}#item{item_index}_page{self.checkpoint['current_page']}"
                            print(f"Detail URL (generated): {self.lecture_data['Detail']}")
                    else:
                        # Generate a unique identifier based on page and item index
                        current_url = self.driver.current_url
                        self.lecture_data["Detail"] = f"{current_url}#item{item_index}_page{self.checkpoint['current_page']}"
                        print(f"Detail URL (generated): {self.lecture_data['Detail']}")
                
                # Scroll and click
                self.driver.execute_script("arguments[0].scrollIntoView(true);", item_element)
                time.sleep(1)
                self.driver.execute_script("arguments[0].click();", item_element)
                time.sleep(2)  # Wait for popup to load
                
            except Exception as e:
                print(f"Error clicking item: {e}")
                return False
            
            # Wait for popup to be visible
            try:
                # Wait for any element in the popup to be visible
                self.wait.until(
                    EC.presence_of_element_located((By.ID, "nameText"))
                )
            except:
                print("Popup did not load properly")
                return False
            
            # Extract Title
            try:
                title_element = self.driver.find_element(By.ID, "nameText")
                self.lecture_data["Title"] = title_element.text.strip()
                print(f"Title: {self.lecture_data['Title']}")
            except Exception as e:
                print(f"Error extracting title: {e}")
            
            # Extract Education Period
            try:
                education_element = self.driver.find_element(By.ID, "eduPeriodTd")
                self.lecture_data["Education_period"] = education_element.text.strip()
                print(f"Education period: {self.lecture_data['Education_period']}")
            except Exception as e:
                print(f"Error extracting education period: {e}")
            
            # Extract Quota
            try:
                quota_element = self.driver.find_element(By.ID, "numTd")
                self.lecture_data["Quota"] = quota_element.text.strip()
                print(f"Quota: {self.lecture_data['Quota']}")
            except Exception as e:
                print(f"Error extracting quota: {e}")
            
            # Extract Fee
            try:
                fee_element = self.driver.find_element(By.ID, "costTd")
                self.lecture_data["Fee"] = fee_element.text.strip()
                print(f"Fee: {self.lecture_data['Fee']}")
            except Exception as e:
                print(f"Error extracting fee: {e}")
            
            # Extract Address
            try:
                address_element = self.driver.find_element(By.ID, "placeTd")
                self.lecture_data["Address"] = address_element.text.strip()
                print(f"Address: {self.lecture_data['Address']}")
            except Exception as e:
                print(f"Error extracting address: {e}")
            
            # Close the popup
            self.close_popup()
            
            # Increment ID for next lecture
            self.current_id += 1
            
            return True
            
        except Exception as e:
            print(f"Error extracting lecture from popup: {e}")
            # Try to close popup if still open
            self.close_popup()
            return False
    
    def go_to_next_page(self, current_page):
        """Navigate to next page based on the pattern"""
        try:
            print(f"\nNavigating from page {current_page} to {current_page + 1}...")
            
            # Calculate the correct nth-child index
            # Page 1 -> 2: nth-child(2)
            # Page 2 -> 3: nth-child(3)
            # Page 3 -> 4: nth-child(4)
            # etc.
            next_index = current_page + 1
            next_selector = f"#listForm > div.list-cont.open > div.bod_page > div > a:nth-child({next_index})"
            
            print(f"Using selector: {next_selector}")
            
            # Save current URL to check if navigation was successful
            current_url = self.driver.current_url
            
            # Find and click next page link
            try:
                next_element = self.wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, next_selector))
                )
                
                # Scroll and click
                self.driver.execute_script("arguments[0].scrollIntoView(true);", next_element)
                time.sleep(1)
                self.driver.execute_script("arguments[0].click();", next_element)
                time.sleep(3)
                
                # Check if page changed
                new_url = self.driver.current_url
                if new_url != current_url:
                    print(f"Successfully navigated to page {current_page + 1}")
                    return True
                else:
                    # URL might not change, check page content instead
                    print("URL didn't change, checking page content...")
                    time.sleep(2)
                    return True
                    
            except Exception as e:
                print(f"Could not find next button with selector {next_selector}")
                # Try alternative pagination selectors
                try:
                    # Look for any "다음" (next) button
                    next_buttons = self.driver.find_elements(By.XPATH, "//a[contains(text(), '다음')]")
                    if next_buttons:
                        next_buttons[0].click()
                        time.sleep(3)
                        return True
                except:
                    pass
                
                return False
            
        except Exception as e:
            print(f"Error navigating to next page: {e}")
            return False
    
    def count_items_on_page(self):
        """Count the number of items on the current page"""
        try:
            items = self.driver.find_elements(By.CSS_SELECTOR, "#listForm > div.list-cont.open > ul > li")
            return len(items)
        except:
            return 0
    
    def save_to_csv(self, filename="andong_education.csv"):
        """Save collected data to CSV"""
        if not self.lectures:
            print("No lectures to save.")
            return
        
        df_new = pd.DataFrame(self.lectures)
        
        # Check if file exists
        file_exists = os.path.isfile(filename)
        
        if file_exists:
            try:
                # Read existing CSV
                df_existing = pd.read_csv(filename, encoding='utf-8-sig')
                
                # Append new data
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                
                # Remove duplicates based on Title
                df_combined = df_combined.drop_duplicates(subset=['Title'], keep='last')
                
                # Save combined dataframe
                df_combined.to_csv(filename, index=False, encoding='utf-8-sig', lineterminator='\n')
                print(f"Appended {len(df_new)} lectures. Total: {len(df_combined)} lectures")
                
            except Exception as e:
                print(f"Error appending to existing file: {e}")
                df_new.to_csv(filename, index=False, encoding='utf-8-sig', lineterminator='\n')
        else:
            # Create new file
            df_new.to_csv(filename, index=False, encoding='utf-8-sig', lineterminator='\n')
            print(f"Created new file with {len(df_new)} lectures")
        
        # Clear lectures list
        self.lectures = []
    
    def load_checkpoint(self):
        """Load checkpoint from file"""
        if not os.path.exists(self.checkpoint_file):
            print("No checkpoint file found")
            return False
        
        try:
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                self.checkpoint = json.load(f)
                self.current_id = self.checkpoint.get("last_id", 0) + 1
                print(f"Loaded checkpoint: Page {self.checkpoint['current_page']}, Item {self.checkpoint['last_processed_item']}")
                return True
        except Exception as e:
            print(f"Error loading checkpoint: {e}")
            return False
    
    def save_checkpoint(self):
        """Save checkpoint to file"""
        try:
            self.checkpoint["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
            self.checkpoint["last_id"] = self.current_id - 1
            
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(self.checkpoint, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving checkpoint: {e}")
    
    def close(self):
        """Close browser"""
        self.driver.quit()
    
    def run(self, start_url, max_pages=100):
        """Run the crawler"""
        # Load checkpoint
        checkpoint_exists = self.load_checkpoint()
        
        try:
            # Navigate to start URL
            self.navigate_to_url(start_url)
            
            # Determine starting page
            if checkpoint_exists:
                current_page = self.checkpoint["current_page"]
                last_processed_item = self.checkpoint["last_processed_item"]
                
                # Navigate to checkpoint page if needed
                if current_page > 1:
                    print(f"Navigating to checkpoint page {current_page}...")
                    for page in range(1, current_page):
                        if not self.go_to_next_page(page):
                            print(f"Failed to navigate to page {page + 1}")
                            break
                        time.sleep(2)
                    
                    # Important: If we're resuming on a page where we already processed some items,
                    # we keep the last_processed_item. Otherwise, reset it to 0
                    if self.checkpoint["current_page"] != current_page:
                        last_processed_item = 0
            else:
                current_page = 1
                last_processed_item = 0
            
            # Main crawling loop
            while current_page <= max_pages:
                print(f"\n=== Processing page {current_page} ===")
                
                # Update checkpoint
                self.checkpoint["current_page"] = current_page
                self.save_checkpoint()
                
                # Count items on current page
                total_items = self.count_items_on_page()
                print(f"Found {total_items} items on page {current_page}")
                
                if total_items == 0:
                    print("No items found on this page")
                    break
                
                # Process each item
                items_processed = 0
                # Reset last_processed_item at the beginning of each new page
                if last_processed_item == 0:
                    print("Starting fresh on this page")
                
                for item_index in range(1, total_items + 1):
                    # Skip if already processed
                    if current_page == self.checkpoint["current_page"] and item_index <= last_processed_item:
                        print(f"Skipping already processed item {item_index}")
                        continue
                    
                    print(f"Processing item {item_index}/{total_items} on page {current_page}")
                    
                    # Extract lecture details from popup
                    success = self.extract_lecture_from_popup(item_index)
                    
                    if success:
                        # Add to lectures collection
                        self.lectures.append(self.lecture_data.copy())
                        items_processed += 1
                        
                        # Save to CSV periodically
                        if len(self.lectures) >= 5:
                            self.save_to_csv()
                    
                    # Update checkpoint
                    self.checkpoint["last_processed_item"] = item_index
                    self.save_checkpoint()
                    
                    # Delay between items
                    time.sleep(2)
                
                print(f"Processed {items_processed} non-test items on page {current_page}")
                
                # Save any remaining lectures
                if self.lectures:
                    self.save_to_csv()
                
                # Check if we actually processed any items on this page
                if items_processed == 0 and last_processed_item == 0:
                    print(f"WARNING: No items were processed on page {current_page}")
                
                # Only go to next page if we've processed all items on current page
                if item_index >= total_items:
                    print(f"All {total_items} items processed on page {current_page}")
                    
                    # Go to next page
                    if not self.go_to_next_page(current_page):
                        print("No more pages available. Ending crawl.")
                        break
                    
                    current_page += 1
                    self.checkpoint["current_page"] = current_page
                    self.checkpoint["last_processed_item"] = 0
                    self.save_checkpoint()
                else:
                    print(f"ERROR: Not all items were processed on page {current_page}")
                    break
            
            print(f"\nCrawling completed! Total lectures processed: {self.current_id - 1}")
            
        except KeyboardInterrupt:
            print("\nCrawling interrupted by user.")
            if self.lectures:
                self.save_to_csv()
            self.save_checkpoint()
            
        except Exception as e:
            print(f"Error during crawling: {e}")
            import traceback
            traceback.print_exc()
            
            if self.lectures:
                self.save_to_csv()
            self.save_checkpoint()
            
        finally:
            print("Closing browser...")
            self.close()

# Run the crawler
if __name__ == "__main__":
    # URL for Andong education listings
    url = 'https://www.andong.go.kr/edu/forever/lecture/search.do?mId=0101000000&currentPageNo=1&detailSearchYn=true&_lifelongYn=on&_externalOrgYn=on&_typeList=on&_typeList=on&_typeList=on&_typeList=on&_typeList=on&_typeList=on&_typeList=on&_typeList=on&_typeList=on&_typeList=on&_typeList=on&_typeList=on&_lectureTimeList=on&_lectureTimeList=on&_lectureTimeList=on&_lectureTimeList=on&_lectureTimeList=on&_eduDayList=on&_eduDayList=on&_eduDayList=on&_eduDayList=on&_eduDayList=on&_eduDayList=on&_eduDayList=on&eduGroupList=1&_eduGroupList=on&_eduGroupList=on&_eduGroupList=on&_eduGroupList=on&_eduGroupList=on&eduGroupList=6&_eduGroupList=on&eduGroupList=7&_eduGroupList=on&_costTypeList=on&_costTypeList=on&_recruitmentTypeList=on&_recruitmentTypeList=on&stateList=1&_stateList=on&_stateList=on&_stateList=on&_stateList=on&keyword=&recordCountPerPage=12'
    try:
        # Create and run crawler
        crawler = AndongEducationCrawler(headless=False)  # Set to True for headless mode
        crawler.run(url, max_pages=100)
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()