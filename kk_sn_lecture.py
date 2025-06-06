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

class SeongnamEducationCrawler:
    def __init__(self, headless=True, checkpoint_file="seongnam_education_checkpoint.json"):
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
        self.driver.set_page_load_timeout(60)  # Increase page load timeout to 60 seconds
        self.wait = WebDriverWait(self.driver, 30)  # Increase default wait time to 30 seconds
        
        # Structure for lecture data
        self.lecture_data = {
            "City": "경기도 성남시",
            "Title": "",
            "Recruitment_period": "",
            "Education_period": "",
            "Date": "",
            "Quota": "",
            "Institution": "",
            "Address": "",
            "Tel": "",
            "State": "",
            "Detail": "",
            "Fee": "",
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
            "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36'
        })
        
    def navigate_to_url(self, url):
        """Navigate to the main lecture listing URL"""
        print(f"Navigating to {url}")
        self.driver.get(url)
        time.sleep(5)  # Increased wait time for initial page load
        self.checkpoint["last_url"] = url
        self.save_checkpoint()
        
    def apply_filters(self):
        """Apply the required filters for searching lectures"""
        try:
            # 2. Click the search filter button
            print("Waiting for filter button to be clickable...")
            filter_button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#content > div.wrap_srch_lecture > div > a"))
            )
            filter_button.click()
            print("Clicked on filter button")
            time.sleep(2)
            
            # 3. Check #learning_target05 (성인반) and #learning_target06 (전문가반)
            print("Waiting for adult checkbox...")
            adult_checkbox = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#learning_target05"))
            )
            self.driver.execute_script("arguments[0].click();", adult_checkbox)
            print("Checked '성인반' checkbox")
            time.sleep(1)
            
            print("Waiting for expert checkbox...")
            expert_checkbox = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#learning_target06"))
            )
            self.driver.execute_script("arguments[0].click();", expert_checkbox)
            print("Checked '전문가반' checkbox")
            time.sleep(1)
            
            # 4. Check #e2 (인터넷)
            print("Waiting for internet checkbox...")
            internet_checkbox = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#e2"))
            )
            self.driver.execute_script("arguments[0].click();", internet_checkbox)
            print("Checked '인터넷' checkbox")
            time.sleep(1)
            
            # 5. Click the search button
            print("Waiting for search button...")
            search_button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#content > div.wrap_srch_lecture > div > div.enrolmentSrch.open > fieldset > button"))
            )
            search_button.click()
            print("Clicked search button")
            
            # Wait for search results to load - increased wait time
            print("Waiting for search results to load...")
            time.sleep(10)
            
            # Verify that results are loaded by checking for the presence of the table
            try:
                # Using the CSS selector for the table
                self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#bbsList"))
                )
                print("Search results table found")
                
                # Additional check: verify that rows are present
                rows = self.driver.find_elements(By.CSS_SELECTOR, "#bbsList > tbody > tr")
                if len(rows) > 0:
                    print(f"Found {len(rows)} rows in search results")
                else:
                    print("Warning: No rows found in search results table")
            except TimeoutException:
                print("Error: Search results table not found after waiting")
                return False
            
            return True
        
        except Exception as e:
            print(f"Error applying filters: {e}")
            return False
        
    def reset_lecture_data(self):
        """Reset the lecture_data dictionary to initial state"""
        self.lecture_data = {
            "City": "경기도 성남시",
            "Title": "Not found",
            "Recruitment_period": "Not found",
            "Education_period": "Not found",
            "Date": "Not found",
            "Quota": "Not found",
            "Institution": "Not found",
            "Address": "Not found",
            "Tel": "Not found",
            "State": "Not found",
            "Detail": "Not found",
            "Fee": "Not found",
        }
    
    def count_rows_on_page(self):
        """Count the number of table rows on the current page"""
        try:
            # Wait for the table to be present
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#bbsList"))
            )
            
            # Get all rows
            rows = self.driver.find_elements(By.CSS_SELECTOR, "#bbsList > tbody > tr")
            
            # Check if we have any data rows
            if len(rows) == 1:
                # Check if this is a "no data" message
                text = rows[0].text.strip()
                if "데이터가 없습니다" in text or "No data available" in text or not text:
                    print("No data row detected")
                    return 0
            
            # Get a more accurate count of actual data rows
            data_rows = []
            for i, row in enumerate(rows):
                try:
                    # Try to find a title cell in this row to confirm it's a data row
                    title_cells = row.find_elements(By.CSS_SELECTOR, "td.subject.tal.mobile")
                    if title_cells and len(title_cells) > 0:
                        data_rows.append(i+1)  # Store the row number (1-based indexing)
                except:
                    continue
            
            if data_rows:
                print(f"Detected {len(data_rows)} actual data rows on the current page")
                # FIXED: Limit to maximum of 10 rows per page
                return min(len(data_rows), 10)
            else:
                print(f"Detected {len(rows)} total rows, but none appear to be data rows")
                # FIXED: Limit to maximum of 10 rows per page
                return min(len(rows), 10)
                
        except TimeoutException:
            print("Timeout waiting for table to load")
            return 0
        except Exception as e:
            print(f"Error counting rows: {e}")
            return 0
    
    def extract_lecture_data(self, row_number):
        """Extract lecture data from the table row and detail page"""
        print(f"Extracting data from row {row_number}")
        
        # First, check if we can see the row
        try:
            # Try to find the entire row first
            row_selector = f"#bbsList > tbody > tr:nth-child({row_number})"
            try:
                row = self.driver.find_element(By.CSS_SELECTOR, row_selector)
            except NoSuchElementException:
                print(f"Row {row_number} does not exist in the table. Skipping.")
                return False
                
            # Try to find the title element which must exist for a valid row
            title_selector = f"#bbsList > tbody > tr:nth-child({row_number}) > td.subject.tal.mobile"
            try:
                title_element = self.driver.find_element(By.CSS_SELECTOR, title_selector)
                # Check if the title element actually contains text
                title_text = title_element.text.strip()
                if not title_text:
                    print(f"Row {row_number} exists but title is empty. Skipping.")
                    return False
            except NoSuchElementException:
                print(f"No title element found in row {row_number}. Skipping.")
                return False
                
            # Reset lecture data for this row
            self.reset_lecture_data()
            
            # Now extract all the data fields
            
            # Extract title (save for clicking later)
            self.lecture_data["Title"] = title_text
            print(f"Title: {title_text}")
            
            # Extract education period
            try:
                education_period_selector = f"#bbsList > tbody > tr:nth-child({row_number}) > td:nth-child(4)"
                education_period = self.driver.find_element(By.CSS_SELECTOR, education_period_selector).text.strip()
                if education_period:
                    self.lecture_data["Education_period"] = education_period
                    print(f"Education period: {education_period}")
                else:
                    print("Education period is empty")
                    self.lecture_data["Education_period"] = "Not found"
            except NoSuchElementException:
                print(f"Education period element not found for row {row_number}")
                self.lecture_data["Education_period"] = "Not found"
            
            # Extract institution
            try:
                institution_selector = f"#bbsList > tbody > tr:nth-child({row_number}) > td.subject.tac.mobile"
                institution = self.driver.find_element(By.CSS_SELECTOR, institution_selector).text.strip()
                if institution:
                    self.lecture_data["Institution"] = institution
                    print(f"Institution: {institution}")
                else:
                    print("Institution is empty")
                    self.lecture_data["Institution"] = "Not found"
            except NoSuchElementException:
                print(f"Institution element not found for row {row_number}")
                self.lecture_data["Institution"] = "Not found"
            
            # Extract quota
            try:
                quota_selector = f"#bbsList > tbody > tr:nth-child({row_number}) > td:nth-child(6)"
                quota = self.driver.find_element(By.CSS_SELECTOR, quota_selector).text.strip()
                if quota:
                    self.lecture_data["Quota"] = quota
                    print(f"Quota: {quota}")
                else:
                    print("Quota is empty")
                    self.lecture_data["Quota"] = "Not found"
            except NoSuchElementException:
                print(f"Quota element not found for row {row_number}")
                self.lecture_data["Quota"] = "Not found"
            
            # Extract state
            try:
                state_selector = f"#bbsList > tbody > tr:nth-child({row_number}) > td:nth-child(7) > span"
                state = self.driver.find_element(By.CSS_SELECTOR, state_selector).text.strip()
                if state:
                    self.lecture_data["State"] = state
                    print(f"State: {state}")
                else:
                    print("State is empty")
                    self.lecture_data["State"] = "Not found"
            except NoSuchElementException:
                print(f"State element not found for row {row_number}")
                self.lecture_data["State"] = "Not found"
            
            # Now click on the title to access detail page
            try:
                print("Clicking on title to access detail page...")
                # FIXED: Use a direct link to the detail page instead of clicking
                # Find the anchor tag that contains the link
                link_element = title_element.find_element(By.TAG_NAME, "a")
                detail_url = link_element.get_attribute("href")
                
                # Check if we have a valid URL
                if not detail_url or detail_url.startswith("data:") or "#" in detail_url:
                    print(f"Invalid detail URL found: {detail_url}")
                    # Try JavaScript click as a fallback
                    print("Attempting JavaScript click as fallback...")
                    self.driver.execute_script("arguments[0].click();", title_element)
                else:
                    # Directly navigate to the URL instead of clicking
                    print(f"Navigating directly to detail URL: {detail_url}")
                    self.driver.get(detail_url)
                
                # Wait for detail page to load
                time.sleep(5)
                
                # Verify we're on a detail page
                current_url = self.driver.current_url
                if "detail" not in current_url.lower() and "view" not in current_url.lower():
                    print(f"Warning: Not on a detail page after navigation. Current URL: {current_url}")
                    # Try to find detail content to confirm we're on the right page
                    try:
                        # Look for elements that only exist on detail page
                        detail_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                                                                  "#content > div.conWrap > div.form_group")
                        if not detail_elements:
                            print("Detail page elements not found. Returning to listing page.")
                            self.driver.get(self.checkpoint["last_url"])
                            time.sleep(5)
                            filter_success = self.apply_filters()
                            if not filter_success:
                                print("Failed to reapply filters.")
                            # Navigate to the correct page if necessary
                            if self.checkpoint["current_page"] > 1:
                                self.navigate_to_checkpoint(self.checkpoint["last_url"])
                            return False
                    except:
                        print("Error checking for detail elements")
                        self.driver.get(self.checkpoint["last_url"])
                        time.sleep(5)
                        return False
                
                # Extract data from detail page
                detail_success = self.extract_detail_page_data()
                if not detail_success:
                    print("Failed to extract detail page data")
                    
                # Go back to the listing page
                print("Going back to listing page...")
                self.driver.get(self.checkpoint["last_url"])
                time.sleep(5)  # Increased wait time for page reload
                
                # Reapply filters
                filter_success = self.apply_filters()
                if not filter_success:
                    print("Failed to reapply filters after returning from detail page.")
                    return False
                
                # Navigate to the correct page if necessary
                if self.checkpoint["current_page"] > 1:
                    page_set = (self.checkpoint["current_page"] - 1) // 10
                    page_in_set = self.checkpoint["current_page"] % 10
                    if page_in_set == 0:
                        page_in_set = 10
                        
                    # Navigate to the correct page set
                    for i in range(page_set):
                        success = self.click_next_page_set()
                        if not success:
                            print(f"Failed to navigate to page set {i+1}")
                            return False
                        time.sleep(3)
                    
                    # Navigate to the correct page within the set
                    if page_in_set > 1:
                        success = self.navigate_to_pagination_number(page_in_set)
                        if not success:
                            print(f"Failed to navigate to page {page_in_set} within the set")
                            return False
                
                # Verify we're back on the listing page
                try:
                    self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "#bbsList"))
                    )
                    print("Successfully returned to listing page")
                except TimeoutException:
                    print("Timeout waiting for listing page to reload after detail page. Returning to base URL.")
                    # Go back to the base URL if we can't find the table
                    self.driver.get(self.checkpoint["last_url"])
                    time.sleep(5)
                    filter_success = self.apply_filters()
                    if not filter_success:
                        print("Failed to reapply filters.")
                    # Navigate to the correct page if necessary
                    if self.checkpoint["current_page"] > 1:
                        self.navigate_to_checkpoint(self.checkpoint["last_url"])
                    return False
                
            except Exception as e:
                print(f"Error accessing or extracting from detail page: {e}")
                # Try to navigate back to the listing page if we're stuck on the detail page
                try:
                    current_url = self.driver.current_url
                    print(f"Current URL after error: {current_url}")
                    # Go back to the base URL
                    self.driver.get(self.checkpoint["last_url"])
                    time.sleep(5)
                    filter_success = self.apply_filters()
                    if not filter_success:
                        print("Failed to reapply filters.")
                    # Navigate to the correct page if necessary
                    if self.checkpoint["current_page"] > 1:
                        self.navigate_to_checkpoint(self.checkpoint["last_url"])
                except:
                    print("Could not determine page status. Returning to base URL...")
                    self.driver.get(self.checkpoint["last_url"])
                    time.sleep(5)
                    filter_success = self.apply_filters()
                    if not filter_success:
                        print("Failed to reapply filters.")
                return False
            
            # Final validation check - if we have too many "Not found" values, skip this row
            not_found_count = sum(1 for value in self.lecture_data.values() if value == "Not found")
            if not_found_count > 3:  # If more than 3 fields are "Not found"
                print(f"Too many missing values ({not_found_count}) for row {row_number}, skipping")
                return False
                
            print(f"Successfully extracted data for row {row_number}")
            return True
                
        except Exception as e:
            print(f"Error extracting data from row {row_number}: {e}")
            return False
    
    def extract_detail_page_data(self):
        """Extract additional data from the detail page"""
        try:
            # Debug information
            print(f"Detail page URL: {self.driver.current_url}")
            
            # Check if we're actually on a detail page
            if "detail" not in self.driver.current_url.lower() and "view" not in self.driver.current_url.lower():
                print("Not on a detail page. URL does not contain 'detail' or 'view'")
                return False
            
            # Save the detail URL
            self.lecture_data["Detail"] = self.driver.current_url
            
            # CSS selectors for detail page fields
            success_count = 0
            
            try:
                # Recruitment period
                recruitment_period_selector = "#content > div.conWrap > div.form_group.col02.line2 > dl > dd > strong"
                recruitment_element = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, recruitment_period_selector))
                )
                recruitment_period = recruitment_element.text.strip()
                if recruitment_period:
                    self.lecture_data["Recruitment_period"] = recruitment_period
                    print(f"Found recruitment period: {recruitment_period}")
                    success_count += 1
                else:
                    print("Recruitment period element found but text is empty")
                    self.lecture_data["Recruitment_period"] = "Not found"
            except (NoSuchElementException, TimeoutException) as e:
                print(f"Recruitment period not found in detail page: {e}")
                self.lecture_data["Recruitment_period"] = "Not found"
            
            try:
                # Fee
                fee_selector = "#content > div.conWrap > div:nth-child(7) > dl:nth-child(1) > dd"
                fee_element = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, fee_selector))
                )
                fee = fee_element.text.strip()
                if fee:
                    self.lecture_data["Fee"] = fee
                    print(f"Found fee: {fee}")
                    success_count += 1
                else:
                    print("Fee element found but text is empty")
                    self.lecture_data["Fee"] = "Not found"
            except (NoSuchElementException, TimeoutException) as e:
                print(f"Fee not found in detail page: {e}")
                self.lecture_data["Fee"] = "Not found"
            
            try:
                # Address
                address_selector = "#content > div > div:nth-child(17) > dl > dd > p"
                address_element = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, address_selector))
                )
                address = address_element.text.strip()
                if address:
                    self.lecture_data["Address"] = address
                    print(f"Found address: {address}")
                    success_count += 1
                else:
                    print("address element found but text is empty")
                    self.lecture_data["Address"] = "Not found"
            except (NoSuchElementException, TimeoutException) as e:
                print(f"Address not found in detail page: {e}")
                self.lecture_data["Address"] = "Not found"
            
            try:
                # Phone number
                tel_selector = "#content > div.conWrap > div:nth-child(4) > dl:nth-child(2) > dd > strong"
                tel_element = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, tel_selector))
                )
                tel = tel_element.text.strip()
                if tel:
                    self.lecture_data["Tel"] = tel
                    print(f"Found telephone: {tel}")
                    success_count += 1
                else:
                    print("Telephone element found but text is empty")
                    self.lecture_data["Tel"] = "Not found"
            except (NoSuchElementException, TimeoutException) as e:
                print(f"Telephone number not found in detail page: {e}")
                self.lecture_data["Tel"] = "Not found"
                
            # Try to extract additional date information from the detail page if available
            try:
                # Look for a date field in the detail page
                date_selectors = [
                    "#content > div.conWrap > div:nth-child(6) > dl:nth-child(2) > dd > strong"
                    
                ]
                
                for selector in date_selectors:
                    try:
                        date_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        date = date_element.text.strip()
                        if date:
                            self.lecture_data["Date"] = date
                            print(f"Found date: {date}")
                            success_count += 1
                            break
                    except:
                        continue
                        
                if self.lecture_data["Date"] == "Not found":
                    print("Could not find date in any of the selectors")
            except Exception as e:
                print(f"Error extracting date information: {e}")
                
            print(f"Successfully extracted data from detail page with {success_count} fields found")
            
            # Return success if we found at least some data
            return success_count > 0
            
        except Exception as e:
            print(f"Error extracting data from detail page: {e}")
            return False
    
    def navigate_to_pagination_number(self, target_number):
        """Navigate to a specific page number in the current pagination set (1-10)"""
        try:
            print(f"Navigating to pagination number {target_number}...")
            
            # Pagination links are typically numbered from 4 to 12 in the selector
            # where 4 corresponds to page 1, 5 to page 2, and so on
            link_index = target_number + 3  # Convert page number to selector index
            
            if link_index > 12:  # Out of range for normal pagination
                print(f"Page number {target_number} is out of range for direct pagination (index {link_index})")
                return False
            
            # Find the pagination link
            selector = f"#content > div:nth-child(5) > div.normal_pagination > a:nth-child({link_index})"
            
            try:
                pagination_link = self.driver.find_element(By.CSS_SELECTOR, selector)
                link_text = pagination_link.text.strip()
                print(f"Found pagination link {link_index} with text: {link_text}")
                
                # Verify this is the correct link by checking the text matches the target number
                if link_text != str(target_number):
                    print(f"Warning: Link text '{link_text}' doesn't match target number {target_number}")
                
                # Click the pagination link
                self.driver.execute_script("arguments[0].scrollIntoView(true);", pagination_link)
                time.sleep(0.5)
                pagination_link.click()
                print(f"Clicked on pagination link for page {target_number}")
                time.sleep(5)
                return True
            except NoSuchElementException:
                print(f"Pagination link for page {target_number} (selector index {link_index}) not found")
                return False
                
        except Exception as e:
            print(f"Error navigating to pagination number {target_number}: {e}")
            return False
    
    def click_next_page_set(self):
        """Click the 'next' button to go to the next set of pagination numbers"""
        try:
            print("Clicking 'next' button to go to the next set of pages...")
            
            # Try the specific selector for the next button
            try:
                next_button = self.driver.find_element(By.CSS_SELECTOR, "#content > div:nth-child(5) > div.normal_pagination > a.page_next")
                print("Found next button using specific selector")
                self.driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                time.sleep(0.5)
                next_button.click()
                print("Clicked next button")
                time.sleep(5)
                return True
            except NoSuchElementException:
                print("Next button not found using specific selector, trying alternative approach")
            
            # Alternative: find by text content
            pagination_links = self.driver.find_elements(By.CSS_SELECTOR, "#content > div:nth-child(5) > div.normal_pagination > a")
            for link in pagination_links:
                link_text = link.text.strip()
                if "다음" in link_text or ">" in link_text:
                    print(f"Found next button with text: {link_text}")
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", link)
                    time.sleep(0.5)
                    link.click()
                    print("Clicked next button")
                    time.sleep(5)
                    return True
            
            print("Could not find next button")
            return False
            
        except Exception as e:
            print(f"Error clicking next page set button: {e}")
            return False
    
    def save_to_csv(self, filename="seongnam_education.csv"):
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
                df_combined = df_combined.drop_duplicates(subset=['Title', 'Education_period', 'Institution'], keep='last')
                
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
        """Navigate to the page specified in the checkpoint and reapply filters"""
        self.navigate_to_url(base_url)
        
        # Apply the filters regardless of checkpoint
        print("Applying filters...")
        filter_success = self.apply_filters()
        if not filter_success:
            print("Failed to apply filters. Trying again...")
            # Try refreshing the page and applying filters again
            self.driver.refresh()
            time.sleep(5)
            filter_success = self.apply_filters()
            if not filter_success:
                print("Failed to apply filters again. Ending crawl.")
                return False
        
        target_page = self.checkpoint["current_page"]
        
        # If we're not on page 1, navigate to the checkpoint page
        if target_page > 1:
            print(f"Navigating to checkpoint page {target_page}...")
            
            # Calculate which set of 10 pages we're in and which page within that set
            page_set = (target_page - 1) // 10  # 0 for pages 1-10, 1 for pages 11-20, etc.
            page_in_set = target_page % 10
            if page_in_set == 0:
                page_in_set = 10
            
            # If we need to navigate to a different set of pages
            for i in range(page_set):
                success = self.click_next_page_set()
                if not success:
                    print(f"Failed to navigate to page set {i+1}")
                    return False
                time.sleep(3)
            
            # Now navigate to the specific page within the set
            if page_in_set > 1:  # Page 1 is already selected by default in each set
                success = self.navigate_to_pagination_number(page_in_set)
                if not success:
                    print(f"Failed to navigate to page {page_in_set} within the set")
                    return False
        
        return True
    
    def handle_pagination(self, current_page, row_count):
        """Handle pagination based on current page and row count"""
        # If we're on the first page and there are fewer than 10 rows, this is the only page
        if current_page == 1 and row_count < 10:
            print("First page has fewer than 10 rows, this is the only page")
            return False, 0
        
        # If we're not on the first page and there are fewer than 10 rows, this is the last page
        if current_page > 1 and row_count < 10:
            print(f"Page {current_page} has fewer than 10 rows, this is the last page")
            return False, 0
        
        # Calculate which set of 10 pages we're in and which page within that set
        page_in_set = current_page % 10
        if page_in_set == 0:
            page_in_set = 10
        
        next_page = current_page + 1
        
        # If we're at the end of a set (page 10, 20, 30, etc.), click the next set button
        if page_in_set == 10:
            print(f"At the end of page set (page {current_page}), clicking next set button")
            success = self.click_next_page_set()
            if not success:
                print("Failed to navigate to next set of pages")
                return False, 0
            return True, next_page
        
        # Otherwise, navigate to the next numbered page
        print(f"Navigating from page {current_page} to page {next_page} within the current set")
        success = self.navigate_to_pagination_number(page_in_set + 1)
        if not success:
            print(f"Failed to navigate to page {page_in_set + 1}")
            return False, 0
        
        return True, next_page
    
    def run(self, start_url, max_pages=100):
        """Run the scraping process for the Seongnam education programs"""
        # Load checkpoint if it exists
        checkpoint_exists = self.load_checkpoint()
        
        try:
            # Navigate to the appropriate starting point and apply filters
            if checkpoint_exists:
                navigation_success = self.navigate_to_checkpoint(start_url)
                if not navigation_success:
                    print("Failed to navigate to checkpoint. Starting from beginning.")
                    self.navigate_to_url(start_url)
                    filter_success = self.apply_filters()
                    if not filter_success:
                        print("Failed to apply filters. Ending crawl.")
                        return
                    start_page = 1
                    start_row = 1
                else:
                    start_page = self.checkpoint["current_page"]
                    start_row = self.checkpoint["last_processed_row"] + 1  # Start from the next row
                    # If last processed row was 10, go to next page
                    if start_row > 10:
                        print(f"Last processed row was {start_row-1}, moving to next page")
                        success, next_page = self.handle_pagination(start_page, 10)  # Assume full page for checkpoint
                        if success:
                            start_page = next_page
                            start_row = 1
                            self.checkpoint["current_page"] = start_page
                            self.checkpoint["last_processed_row"] = 0
                            self.save_checkpoint()
                        else:
                            print("Failed to move to next page. Starting from the beginning of current page.")
                            start_row = 1
            else:
                self.navigate_to_url(start_url)
                filter_success = self.apply_filters()
                if not filter_success:
                    print("Failed to apply filters. Ending crawl.")
                    return
                start_page = 1
                start_row = 1
            
            current_page = start_page
            
            while current_page <= max_pages:
                print(f"\n--- Scraping page {current_page} ---")
                
                # Update checkpoint with current page
                self.checkpoint["current_page"] = current_page
                self.save_checkpoint()
                
                # Count rows on this page - FIXED: Maximum of 10 rows per page
                row_count = self.count_rows_on_page()
                if row_count == 0:
                    print("No rows found on this page. Trying to refresh and reapply filters...")
                    
                    # Try refreshing page and reapplying filters
                    self.driver.refresh()
                    time.sleep(5)
                    filter_success = self.apply_filters()
                    if not filter_success:
                        print("Failed to reapply filters after refresh. Ending crawl.")
                        break
                    
                    # Try counting rows again
                    row_count = self.count_rows_on_page()
                    if row_count == 0:
                        print("Still no rows found after refresh. Ending crawl.")
                        break
                
                # FIXED: Ensure we only process up to 10 rows per page
                row_count = min(row_count, 10)
                print(f"Found {row_count} rows on page {current_page}, will process all of them")
                
                # Process each row on the page
                for row_num in range(start_row, row_count + 1):
                    print(f"\nProcessing row {row_num}/{row_count} on page {current_page}")
                    
                    try:
                        # Extract data from this row
                        success = self.extract_lecture_data(row_num)
                        
                        if success:
                            # Add the lecture data to our collection
                            self.lectures.append(self.lecture_data.copy())
                            
                            # Verify we have meaningful data before saving
                            not_found_count = sum(1 for value in self.lecture_data.values() if value == "Not found")
                            print(f"Row has {not_found_count} 'Not found' values out of {len(self.lecture_data)} fields")
                            
                            if not_found_count <= 3:  # Only save if we have meaningful data
                                # Save data after each lecture is extracted
                                self.save_to_csv("seongnam_education.csv")
                                print(f"Saved data for row {row_num}")
                            else:
                                print(f"Too many missing values, not saving row {row_num}")
                        else:
                            print(f"Failed to extract meaningful data from row {row_num}")
                        
                        # Update checkpoint regardless of success
                        self.checkpoint["last_processed_row"] = row_num
                        self.save_checkpoint()
                        
                    except Exception as e:
                        print(f"Error processing row {row_num}: {e}")
                        self.checkpoint["last_processed_row"] = row_num
                        self.save_checkpoint()
                    
                    # Small delay between rows
                    time.sleep(1)
                
                # FIXED: Special case for first page with fewer than 10 rows
                if current_page == 1 and row_count < 10:
                    print(f"First page has only {row_count} rows which is less than 10. This is the last page. Ending crawl.")
                    break
                
                # FIXED: If not first page and fewer than 10 rows, this is the last page
                if current_page > 1 and row_count < 10:
                    print(f"Page {current_page} has fewer than 10 rows, this is the last page. Ending crawl.")
                    break
                
                # Reset for next page
                start_row = 1
                
                # Navigate to the next page
                try:
                    print(f"Finished processing page {current_page} with all {row_count} rows, moving to next page")
                    
                    # FIXED: Improved navigation logic
                    if row_count == 10:  # Only try to go to next page if we had a full page
                        success, next_page = self.handle_pagination(current_page, row_count)
                        if not success:
                            print("Could not navigate to next page. Ending crawl.")
                            break
                        
                        current_page = next_page
                        self.checkpoint["current_page"] = current_page
                        self.checkpoint["last_processed_row"] = 0  # Reset row counter for new page
                        self.save_checkpoint()
                    else:
                        print(f"Page {current_page} has fewer than 10 rows, this is the last page. Ending crawl.")
                        break
                except Exception as e:
                    print(f"Error navigating to next page: {e}")
                    break
            
            print("Crawling completed successfully.")
            
        except KeyboardInterrupt:
            print("\nCrawling interrupted by user. Saving progress...")
            # Save current data and checkpoint
            if self.lectures:
                self.save_to_csv("seongnam_education.csv")
            self.save_checkpoint()
            print("Progress saved. You can resume later from this point.")
            
        except Exception as e:
            print(f"Error during scraping process: {e}")
            
            # Save whatever data we've collected so far
            if self.lectures:
                self.save_to_csv("seongnam_education.csv")
            # Make sure the checkpoint is saved
            self.save_checkpoint()
            print("Saved checkpoint. You can resume from this point later.")
            
        finally:
            self.close()

# Run the crawler
if __name__ == "__main__":
    # URL for Seongnam education listings
    url = 'https://sugang.seongnam.go.kr/ilms/learning/learningList.do#'
    
    # Create and run the crawler - set headless=False to see the browser in action
    crawler = SeongnamEducationCrawler(headless=False)
    crawler.run(url, max_pages=100)  # Crawl up to 100 pages