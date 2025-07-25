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

class BusanEducationCrawler:
    def __init__(self, headless=True, checkpoint_file="busan_education_checkpoint.json"):
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
                "Recruitment_period": "",
                "Education_period": "",
                "Date": "",
                "Quota": "",
                "Institution": "",
                "Address": "",
                "Tel": "",
                "Category": "",
                "Fee": "",
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
            "Recruitment_period": "Not found",
            "Education_period": "Not found",
            "Date": "Not found",
            "Quota": "Not found",
            "Institution": "Not found",
            "Address": "Not found",
            "Tel": "Not found",
            "Category": "Not found",
            "Fee": "Not found",
            "Detail": ""
        }
    
    def extract_category_from_address(self, address):
        """Extract district (구) from address"""
        try:
            # Find pattern like "XX구" in the address
            match = re.search(r'(\w+구)', address)
            if match:
                return match.group(1)
            else:
                # If no district found, return second word
                parts = address.split()
                if len(parts) >= 2:
                    return parts[1]
                return "Not found"
        except:
            return "Not found"
    
    def extract_lecture_detail(self, item_index):
        """Extract lecture details from a specific list item"""
        try:
            print(f"\n>>> Extracting data for item {item_index}")
            
            # Reset lecture data
            self.reset_lecture_data()
            
            # Save list page URL
            list_page_url = self.driver.current_url
            
            # Find and click the lecture link
            link_selector = f"#contents > div.reserveListType > div.reserveListWrap > ul > li:nth-child({item_index}) > a"
            try:
                link_element = self.wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, link_selector))
                )
                
                # Scroll to element and click
                self.driver.execute_script("arguments[0].scrollIntoView(true);", link_element)
                time.sleep(1)
                self.driver.execute_script("arguments[0].click();", link_element)
                time.sleep(3)
                
                # Save detail page URL
                detail_url = self.driver.current_url
                self.lecture_data["Detail"] = detail_url
                print(f"Detail page URL: {detail_url}")
                
            except Exception as e:
                print(f"Error clicking lecture link: {e}")
                return False
            
            # Extract Title
            try:
                title_element = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#viewForm > div.contHeader.titStateHeader > h3"))
                )
                self.lecture_data["Title"] = title_element.text.strip()
                print(f"Title: {self.lecture_data['Title']}")
            except Exception as e:
                print(f"Error extracting title: {e}")
            
            # Extract Recruitment Period
            try:
                recruitment_element = self.driver.find_element(
                    By.CSS_SELECTOR, 
                    "#viewForm > div.reserveStateWrap > div > div.reserveStateInfo > dl:nth-child(2) > dd > span"
                )
                self.lecture_data["Recruitment_period"] = recruitment_element.text.strip()
                print(f"Recruitment period: {self.lecture_data['Recruitment_period']}")
            except Exception as e:
                print(f"Error extracting recruitment period: {e}")
            
            # Extract Education Period
            try:
                education_element = self.driver.find_element(
                    By.CSS_SELECTOR, 
                    "#viewForm > div.reserveStateWrap > div > div.reserveStateInfo > dl:nth-child(1) > dd > span"
                )
                self.lecture_data["Education_period"] = education_element.text.strip()
                print(f"Education period: {self.lecture_data['Education_period']}")
            except Exception as e:
                print(f"Error extracting education period: {e}")
            
            # Extract Date
            try:
                date_element = self.driver.find_element(
                    By.CSS_SELECTOR, 
                    "#viewForm > div.reserveStateWrap > div > div.reserveStateInfo > dl:nth-child(6) > dd > span"
                )
                self.lecture_data["Date"] = date_element.text.strip()
                print(f"Date: {self.lecture_data['Date']}")
            except Exception as e:
                print(f"Error extracting date: {e}")
            
            # Extract Quota
            try:
                quota_element = self.driver.find_element(
                    By.CSS_SELECTOR, 
                    "#viewForm > div.reserveStateWrap > div > div.reserveStateInfo > div.tableStateWrap > table > tbody > tr > td:nth-child(2) > span"
                )
                self.lecture_data["Quota"] = quota_element.text.strip()
                print(f"Quota: {self.lecture_data['Quota']}")
            except Exception as e:
                print(f"Error extracting quota: {e}")
            
            # Extract Institution
            try:
                institution_element = self.driver.find_element(
                    By.CSS_SELECTOR, 
                    "#viewForm > div.reserveStateWrap > div > div.reserveStateInfo > dl:nth-child(8) > dd > span"
                )
                self.lecture_data["Institution"] = institution_element.text.strip()
                print(f"Institution: {self.lecture_data['Institution']}")
            except Exception as e:
                print(f"Error extracting institution: {e}")
            
            # Extract Tel
            try:
                tel_element = self.driver.find_element(
                    By.CSS_SELECTOR, 
                    "#viewForm > div.reserveStateWrap > div > div.reserveStateInfo > dl:nth-child(7) > dd"
                )
                self.lecture_data["Tel"] = tel_element.text.strip()
                print(f"Tel: {self.lecture_data['Tel']}")
            except Exception as e:
                print(f"Error extracting tel: {e}")
            
            # Extract Fee
            try:
                fee_element = self.driver.find_element(
                    By.CSS_SELECTOR, 
                    "#viewForm > div.reserveStateWrap > div > div.reserveStateInfo > dl:nth-child(5) > dd"
                )
                self.lecture_data["Fee"] = fee_element.text.strip()
                print(f"Fee: {self.lecture_data['Fee']}")
            except Exception as e:
                print(f"Error extracting fee: {e}")
            
            # Extract Address from second tab
            try:
                # Click on the second tab
                tab_selector = "#viewForm > div.reserveDetail > div.reserveTabWrap > ul > li:nth-child(2) > a"
                tab_element = self.wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, tab_selector))
                )
                self.driver.execute_script("arguments[0].click();", tab_element)
                time.sleep(2)
                
                # Extract address text
                address_selector = "#reserveTabCont2 > div > div.h4Section > div:nth-child(2) > ul > li"
                address_element = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, address_selector))
                )
                address_text = address_element.text.strip()
                self.lecture_data["Address"] = address_text
                print(f"Address: {address_text}")
                
                # Extract category from address
                self.lecture_data["Category"] = self.extract_category_from_address(address_text)
                print(f"Category: {self.lecture_data['Category']}")
                
            except Exception as e:
                print(f"Error extracting address: {e}")
            
            # Go back to list page
            print("Going back to list page...")
            self.driver.get(list_page_url)
            time.sleep(3)
            
            # Increment ID for next lecture
            self.current_id += 1
            
            return True
            
        except Exception as e:
            print(f"Error extracting lecture detail: {e}")
            # Try to go back to list page
            try:
                self.driver.get(list_page_url)
                time.sleep(3)
            except:
                pass
            return False
    
    def go_to_next_page(self, current_page):
        """Navigate to next page"""
        try:
            print(f"\nNavigating from page {current_page} to {current_page + 1}...")
            
            # Different selectors based on page number
            if current_page < 10:
                # Pages 1-9: Use numbered links
                next_selector = f"#contents > div.reserveListType > div.paginate > div > a:nth-child({current_page + 1})"
            elif current_page == 10:
                # Page 10: Use pgNext button
                next_selector = "#contents > div.reserveListType > div.paginate > a.pgNext"
            else:
                # Pages 11+: Determine the correct selector
                page_in_group = ((current_page - 1) % 10) + 1
                if page_in_group == 10:
                    next_selector = "#contents > div.reserveListType > div.paginate > a.pgNext"
                else:
                    next_selector = f"#contents > div.reserveListType > div.paginate > div > a:nth-child({page_in_group + 1})"
            
            print(f"Using selector: {next_selector}")
            
            # Find and click next page link
            next_element = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, next_selector))
            )
            
            # Scroll and click
            self.driver.execute_script("arguments[0].scrollIntoView(true);", next_element)
            time.sleep(1)
            self.driver.execute_script("arguments[0].click();", next_element)
            time.sleep(3)
            
            print(f"Successfully navigated to page {current_page + 1}")
            return True
            
        except Exception as e:
            print(f"Error navigating to next page: {e}")
            return False
    
    def save_to_csv(self, filename="busan_education.csv"):
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
                
                # Remove duplicates based on Detail URL
                df_combined = df_combined.drop_duplicates(subset=['Detail'], keep='last')
                
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
            else:
                current_page = 1
                last_processed_item = 0
            
            # Main crawling loop
            while current_page <= max_pages:
                print(f"\n=== Processing page {current_page} ===")
                
                # Update checkpoint
                self.checkpoint["current_page"] = current_page
                self.save_checkpoint()
                
                # Find all lecture items on current page
                try:
                    items = self.driver.find_elements(
                        By.CSS_SELECTOR, 
                        "#contents > div.reserveListType > div.reserveListWrap > ul > li"
                    )
                    total_items = len(items)
                    print(f"Found {total_items} items on page {current_page}")
                    
                    if total_items == 0:
                        print("No items found on this page")
                        break
                    
                except Exception as e:
                    print(f"Error finding items: {e}")
                    break
                
                # Process each item
                items_processed = 0
                for item_index in range(1, min(total_items + 1, 11)):  # Max 10 items per page
                    # Skip if already processed
                    if current_page == self.checkpoint["current_page"] and item_index <= last_processed_item:
                        print(f"Skipping already processed item {item_index}")
                        continue
                    
                    # Extract lecture details
                    success = self.extract_lecture_detail(item_index)
                    
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
                
                print(f"Processed {items_processed} items on page {current_page}")
                
                # Save any remaining lectures
                if self.lectures:
                    self.save_to_csv()
                
                # Go to next page
                if not self.go_to_next_page(current_page):
                    print("No more pages available. Ending crawl.")
                    break
                
                current_page += 1
                self.checkpoint["current_page"] = current_page
                self.checkpoint["last_processed_item"] = 0
                self.save_checkpoint()
            
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
    # URL for Busan education listings
    url = 'https://reserve.busan.go.kr/lctre?curPage=1&resveGroupSn=&progrmSn=&srchGugun=&srchCtgry=&srchBeginDe=&srchEndDe=&srchIngStat=RI&srchResveMth=&srchVal='
    
    try:
        # Create and run crawler
        crawler = BusanEducationCrawler(headless=False)  # Set to True for headless mode
        crawler.run(url, max_pages=100)
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()