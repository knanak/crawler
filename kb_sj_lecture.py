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

class SangjuEducationCrawler:
    def __init__(self, headless=True, checkpoint_file="sangju_education_checkpoint.json"):
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
                "Quota": "",
                "Institution": "",
                "Address": "",
                "Category": "",
                "Detail": ""
            }
            
            # Storage for collected lectures
            self.lectures = []
            self.current_id = 1
            
            # Checkpoint configuration
            self.checkpoint_file = checkpoint_file
            self.checkpoint = {
                "current_page": 1,
                "last_processed_section": 0,
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
            "Quota": "Not found",
            "Institution": "Not found",
            "Address": "Not found",
            "Category": "Not found",
            "Detail": "Not found"
        }
    
    def extract_category_from_address(self, address):
        """Extract district (구) or city/county from address"""
        try:
            # Remove span tags if present
            clean_address = self.remove_span_tags(address)
            
            # Split address and get second part
            parts = clean_address.split()
            if len(parts) >= 2:
                return parts[1]
            
            # If no second part, try to find pattern like "XX시" or "XX구"
            match = re.search(r'(\w+[시구군])', clean_address)
            if match:
                return match.group(1)
            
            return "Not found"
        except:
            return "Not found"
    
    def remove_span_tags(self, text):
        """Remove span tags and their content from text"""
        try:
            # Get the inner HTML if it's an element
            if hasattr(text, 'get_attribute'):
                inner_html = text.get_attribute('innerHTML')
                if inner_html:
                    text = inner_html
            
            # Remove span tags and their content using multiple patterns
            clean_text = re.sub(r'<span[^>]*>.*?</span>', '', str(text))
            # Remove any remaining HTML tags
            clean_text = re.sub(r'<[^>]+>', '', clean_text)
            # Clean up extra whitespace
            clean_text = ' '.join(clean_text.split())
            
            return clean_text.strip()
        except Exception as e:
            print(f"Error in remove_span_tags: {e}")
            return str(text).strip()
    
    def check_reservation_button(self, section_index):
        """Check if the section has a '예약' button"""
        try:
            button_selector = f"#reserveList > section:nth-child({section_index}) > ul > li > a"
            button_element = self.driver.find_element(By.CSS_SELECTOR, button_selector)
            button_text = button_element.text.strip()
            
            print(f"Section {section_index} button text: '{button_text}'")
            return button_text == "예약"
        except Exception as e:
            print(f"Error checking reservation button for section {section_index}: {e}")
            return False
    
    def extract_lecture_from_section(self, section_index):
        """Extract lecture data from a specific section"""
        try:
            print(f"\n>>> Extracting data from section {section_index}")
            
            # Check if this section has '예약' button
            if not self.check_reservation_button(section_index):
                print(f"Section {section_index} does not have '예약' button, skipping...")
                return False
            
            # Reset lecture data
            self.reset_lecture_data()
            
            # Extract Title
            try:
                title_selector = f"#reserveList > section:nth-child({section_index}) > div > div.right > h1 > a"
                title_element = self.driver.find_element(By.CSS_SELECTOR, title_selector)
                self.lecture_data["Title"] = title_element.text.strip()
                print(f"Title: {self.lecture_data['Title']}")
            except Exception as e:
                print(f"Error extracting title: {e}")
            
            # Extract Detail (href)
            try:
                detail_selector = f"#reserveList > section:nth-child({section_index}) > div > div.right > a"
                detail_element = self.driver.find_element(By.CSS_SELECTOR, detail_selector)
                href = detail_element.get_attribute('href')
                
                # Check if href is javascript:; or similar
                if href and 'javascript:' not in href:
                    self.lecture_data["Detail"] = href
                    print(f"Detail URL: {href}")
                else:
                    # If it's a javascript link, try to click and get the actual URL
                    print("Found javascript link, attempting to get actual URL...")
                    
                    # Save current URL
                    current_url = self.driver.current_url
                    
                    try:
                        # Click the detail link
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", detail_element)
                        time.sleep(1)
                        self.driver.execute_script("arguments[0].click();", detail_element)
                        time.sleep(2)
                        
                        # Get the new URL
                        new_url = self.driver.current_url
                        
                        if new_url != current_url:
                            self.lecture_data["Detail"] = new_url
                            print(f"Detail URL (from navigation): {new_url}")
                            
                            # Go back to list page
                            self.driver.back()
                            time.sleep(2)
                        else:
                            # If URL didn't change, try to extract from onclick or other attributes
                            onclick = detail_element.get_attribute('onclick')
                            if onclick:
                                # Try to extract any URL or ID from onclick
                                import re
                                url_match = re.search(r'(https?://[^\s\'\"]+)', onclick)
                                if url_match:
                                    self.lecture_data["Detail"] = url_match.group(1)
                                else:
                                    # If no URL found, use the current page URL with section info
                                    self.lecture_data["Detail"] = f"{current_url}#section{section_index}"
                            else:
                                self.lecture_data["Detail"] = f"{current_url}#section{section_index}"
                            print(f"Detail URL (constructed): {self.lecture_data['Detail']}")
                    except Exception as e:
                        print(f"Error navigating to detail page: {e}")
                        self.lecture_data["Detail"] = f"{current_url}#section{section_index}"
                        
            except Exception as e:
                print(f"Error extracting detail URL: {e}")
            
            # Extract Recruitment Period
            try:
                recruitment_selector = f"#reserveList > section:nth-child({section_index}) > ul > li > ul > li:nth-child(1)"
                recruitment_element = self.driver.find_element(By.CSS_SELECTOR, recruitment_selector)
                # Get the full HTML content
                recruitment_html = recruitment_element.get_attribute('innerHTML')
                # Remove span tags and their content
                recruitment_text = self.remove_span_tags(recruitment_html)
                self.lecture_data["Recruitment_period"] = recruitment_text
                print(f"Recruitment period: {recruitment_text}")
            except Exception as e:
                print(f"Error extracting recruitment period: {e}")
            
            # Extract Education Period
            try:
                education_selector = f"#reserveList > section:nth-child({section_index}) > div > div.right > ul > li:nth-child(3)"
                education_element = self.driver.find_element(By.CSS_SELECTOR, education_selector)
                # Get the full HTML content
                education_html = education_element.get_attribute('innerHTML')
                # Remove span tags and their content
                education_text = self.remove_span_tags(education_html)
                self.lecture_data["Education_period"] = education_text
                print(f"Education period: {education_text}")
            except Exception as e:
                print(f"Error extracting education period: {e}")
            
            # Extract Quota
            try:
                quota_selector = f"#reserveList > section:nth-child({section_index}) > ul > li > ul > li:nth-child(2) > p"
                quota_element = self.driver.find_element(By.CSS_SELECTOR, quota_selector)
                # Get the full HTML content
                quota_html = quota_element.get_attribute('innerHTML')
                # Remove span tags and their content
                quota_text = self.remove_span_tags(quota_html)
                self.lecture_data["Quota"] = quota_text
                print(f"Quota: {quota_text}")
            except Exception as e:
                print(f"Error extracting quota: {e}")
            
            # Extract Institution
            try:
                institution_selector = f"#reserveList > section:nth-child({section_index}) > div > div.right > ul > li:nth-child(2)"
                institution_element = self.driver.find_element(By.CSS_SELECTOR, institution_selector)
                # Get the full HTML content
                institution_html = institution_element.get_attribute('innerHTML')
                # Remove span tags and their content
                institution_text = self.remove_span_tags(institution_html)
                self.lecture_data["Institution"] = institution_text
                print(f"Institution: {institution_text}")
            except Exception as e:
                print(f"Error extracting institution: {e}")
            
            # Extract Address
            try:
                address_selector = f"#reserveList > section:nth-child({section_index}) > div > div.right > ul > li:nth-child(4)"
                address_element = self.driver.find_element(By.CSS_SELECTOR, address_selector)
                # Get the full HTML content
                address_html = address_element.get_attribute('innerHTML')
                # Remove span tags and their content
                address_text = self.remove_span_tags(address_html)
                self.lecture_data["Address"] = address_text
                print(f"Address: {address_text}")
                
                # Extract category from address
                self.lecture_data["Category"] = self.extract_category_from_address(address_text)
                print(f"Category: {self.lecture_data['Category']}")
                
            except Exception as e:
                print(f"Error extracting address: {e}")
            
            # Increment ID for next lecture
            self.current_id += 1
            
            return True
            
        except Exception as e:
            print(f"Error extracting lecture from section {section_index}: {e}")
            return False
    
    def go_to_next_page(self, current_page):
        """Navigate to next page based on the pattern"""
        try:
            print(f"\nNavigating from page {current_page} to {current_page + 1}...")
            
            # Determine the correct selector based on page pattern
            # Pattern: pages 1-5 use nth-child(4), page 6 uses nth-child(6), then back to nth-child(4)
            page_in_group = ((current_page - 1) % 5) + 1
            
            if page_in_group == 5 and current_page == 5:
                # Special case: going from page 5 to 6
                next_selector = "#reserveListForm > ul.pager > li:nth-child(6) > a"
            else:
                # Normal case: use nth-child(4)
                next_selector = "#reserveListForm > ul.pager > li:nth-child(4) > a"
            
            print(f"Using selector: {next_selector}")
            
            # Save current URL to check if navigation was successful
            current_url = self.driver.current_url
            
            # Find and click next page link
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
                print("Page URL didn't change, navigation might have failed")
                return False
            
        except Exception as e:
            print(f"Error navigating to next page: {e}")
            return False
    
    def count_sections_on_page(self):
        """Count the number of sections on the current page"""
        try:
            sections = self.driver.find_elements(By.CSS_SELECTOR, "#reserveList > section")
            return len(sections)
        except:
            return 0
    
    def save_to_csv(self, filename="sangju_education.csv"):
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
                
                # Remove duplicates based on Title and Institution
                df_combined = df_combined.drop_duplicates(subset=['Title', 'Institution'], keep='last')
                
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
                print(f"Loaded checkpoint: Page {self.checkpoint['current_page']}, Section {self.checkpoint['last_processed_section']}")
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
                last_processed_section = self.checkpoint["last_processed_section"]
                
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
                last_processed_section = 0
            
            # Main crawling loop
            while current_page <= max_pages:
                print(f"\n=== Processing page {current_page} ===")
                
                # Update checkpoint
                self.checkpoint["current_page"] = current_page
                self.save_checkpoint()
                
                # Count sections on current page
                total_sections = self.count_sections_on_page()
                print(f"Found {total_sections} sections on page {current_page}")
                
                if total_sections == 0:
                    print("No sections found on this page")
                    break
                
                # Process each section
                sections_processed = 0
                for section_index in range(1, total_sections + 1):
                    # Skip if already processed
                    if current_page == self.checkpoint["current_page"] and section_index <= last_processed_section:
                        print(f"Skipping already processed section {section_index}")
                        continue
                    
                    # Extract lecture details
                    success = self.extract_lecture_from_section(section_index)
                    
                    if success:
                        # Add to lectures collection
                        self.lectures.append(self.lecture_data.copy())
                        sections_processed += 1
                        
                        # Save to CSV periodically
                        if len(self.lectures) >= 5:
                            self.save_to_csv()
                    
                    # Update checkpoint
                    self.checkpoint["last_processed_section"] = section_index
                    self.save_checkpoint()
                    
                    # Delay between sections
                    time.sleep(1)
                
                print(f"Processed {sections_processed} sections with '예약' button on page {current_page}")
                
                # Save any remaining lectures
                if self.lectures:
                    self.save_to_csv()
                
                # Go to next page
                if not self.go_to_next_page(current_page):
                    print("No more pages available. Ending crawl.")
                    break
                
                current_page += 1
                self.checkpoint["current_page"] = current_page
                self.checkpoint["last_processed_section"] = 0
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
    # URL for Sangju education listings
    url = 'https://www.sangju.go.kr/reserve/reservation/list.tc?pageNo=11881&mn=15375&pageIndex=1&searchTrgtClsfCd=RMS004001&searchFcltNo=&cyclNo=&rcptNo=&searchUpClsfCd=&searchRgnClsfCd=&searchKeyword=&orderBy='
    
    try:
        # Create and run crawler
        crawler = SangjuEducationCrawler(headless=False)  # Set to True for headless mode
        crawler.run(url, max_pages=100)
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()