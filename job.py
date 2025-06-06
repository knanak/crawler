import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import re
import os
import json

class WorkGoKrCrawler:
    def __init__(self, headless=True, checkpoint_file="crawler_checkpoint.json"):
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
        
        # Global storage for job data with the new structure
        self.job_data = {
            "Job Title": "",
            "Date of registration": "",
            "Deadline": "",
            "Job Category": "",
            "Experience Required": "",
            "Employment Type": "",
            "Salary": "",
            "SocialEnsurance": "",
            "RetirementBenefit": "",
            "Location": "",
            "Working Hours": "",
            "Working Type": "",
            "Company Name": "",
            "Job Description": "",
            "ApplicationMethod": "",
            "ApplicationType": "",
            "document": "",
            "Detail" : ""
        }
        
        # Storage for collected jobs
        self.jobs = []
        
        # Current list being processed
        self.current_list = ""
        
        # Checkpoint configuration
        self.checkpoint_file = checkpoint_file
        self.checkpoint = {
            "current_page": 1,
            "current_list_index": 0,
            "current_page_button": 4,
            "last_processed_job_id": "",
            "last_url": "",
            "timestamp": ""
        }
        
        # Keep track of processed jobs in memory (not saved to checkpoint)
        self.processed_job_ids = set()
        
        # Add user agent to appear more like a regular browser
        self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36'
        })
        
    def navigate_to_url(self, url):
        """Navigate to the main job listing URL"""
        print(f"Navigating to {url}")
        self.driver.get(url)
        time.sleep(3)  # Allow the page to load
        self.checkpoint["last_url"] = url
        self.save_checkpoint()
        
    def get_job_links(self, list_selector, link_pattern):
        """Get all job listing links for a particular list selector and extract basic info"""
        print(f"Finding job links with selector: {list_selector} > {link_pattern}")
        try:
            # The full CSS selector is constructed from the list selector and the link pattern
            full_selector = f"{list_selector} > {link_pattern}"
            job_links = self.wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, full_selector))
            )
            print(f"Found {len(job_links)} job links in {list_selector}")
            
            # Extract additional information directly from the listing
            enhanced_links = []
            for link in job_links:
                try:
                    # Reset global job_data for each link
                    self.reset_job_data()
                    
                    # Get link element for navigation
                    link_element = link
                    
                    # Extract the list number from the list_selector
                    list_num = list_selector.replace('#list', '')
                    
                    # Try to get Date of registration using the provided selector pattern
                    try:
                        date_registration_selector = f"#list{list_num} > td:nth-child(5) > div > p:nth-child(2)"
                        print(f"Trying registration date selector: {date_registration_selector}")
                        date_element = self.driver.find_element(By.CSS_SELECTOR, date_registration_selector)
                        date_text = date_element.text.strip()
                        if date_text:
                            self.job_data["Date of registration"] = date_text
                            print(f"Found registration date: {date_text} for list {list_num}")
                        else:
                            self.job_data["Date of registration"] = "Not found"
                            print(f"Empty registration date text for list {list_num}")
                    except NoSuchElementException:
                        self.job_data["Date of registration"] = "Not found"
                        print(f"Registration date selector not found for list {list_num}")
                    
                    # Try to get deadline from the listing
                    try:
                        adjusted_list_num = str(int(list_num) - 1)
                        
                        # Try different deadline selectors based on the adjusted list number
                        deadline_selector = f"#spanCloseDt{adjusted_list_num}"
                        print(f"Trying deadline selector: {deadline_selector}")
                        deadline_element = self.driver.find_element(By.CSS_SELECTOR, deadline_selector)
                        deadline_text = deadline_element.text.strip()
                        if deadline_text:  # Only use if we found actual text
                            self.job_data["Deadline"] = deadline_text
                            print(f"Found deadline directly: {deadline_text} (list {list_num}, adjusted to {adjusted_list_num})")
                        else:
                            self.job_data["Deadline"] = "채용시까지"
                            print(f"Empty deadline text, using default: 채용시까지")
                    except NoSuchElementException:
                        self.job_data["Deadline"] = "채용시까지"
                        print(f"Deadline selector not found, using default: 채용시까지")
                    
                    # Try to get job title from the listing
                    try:
                        # Get the text from the link itself - often this is the job title
                        job_title = link.text.strip()
                        if job_title:
                            self.job_data["Job Title"] = job_title 
                        else:
                            # If link text is empty, try to find a title element nearby
                            title_selector = f"{list_selector} > td:nth-child(3) > div > div > strong"
                            title_text = self.driver.find_element(By.CSS_SELECTOR, title_selector).text.strip()
                            if title_text:
                                self.job_data["Job Title"] = title_text
                    except:
                        self.job_data["Job Title"] = "Not found in listing"
                    
                    # Store the link and the additional information
                    enhanced_links.append({
                        "link_element": link_element,
                        "job_data": self.job_data.copy(),  # Create a copy of the current job_data
                        "job_id": self.generate_job_id()  # Add a unique identifier for checkpoint tracking
                    })
                    
                except Exception as e:
                    print(f"Error extracting listing details: {e}")
                    # Still include the link even if additional info extraction failed
                    self.reset_job_data()
                    enhanced_links.append({
                        "link_element": link,
                        "job_data": self.job_data.copy(),
                        "job_id": self.generate_job_id()
                    })
            
            return enhanced_links
        except TimeoutException:
            print(f"Timeout waiting for job links with selector: {list_selector}")
            return []
        except Exception as e:
            print(f"Error getting job links for {list_selector}: {e}")
            return []
    
    def generate_job_id(self):
        """Generate a unique ID for a job based on current data"""
        title = self.job_data.get("Job Title", "unknown")
        company = self.job_data.get("Company Name", "unknown")
        date = self.job_data.get("Date of registration", "unknown")
        deadline = self.job_data.get("Deadline", "unknown")
        # Create a simple hash that can be used for checkpointing
        job_id = f"{title}_{date}_{deadline}"
        return job_id
    
    def reset_job_data(self):
        """Reset the global job_data dictionary to initial state with the new structure"""
        self.job_data = {
            "Job Title": "Not found",
            "Date of registration": "Not found",
            "Deadline": "채용시까지",  # Korean for "until hired"
            "Job Category": "Not found",
            "Experience Required": "Not found",
            "Employment Type": "Not found",
            "Salary": "Not found",
            "SocialEnsurance": "Not found",
            "RetirementBenefit": "Not found",
            "Location": "Not found",
            "Working Hours": "Not found",
            "Working Type": "Not found",
            "Company Name": "Not found",
            "Job Description": "Not found",
            "ApplicationMethod": "Not found",
            "ApplicationType": "Not found",
            "document": "Not found"
        }
            
    def extract_job_details(self):
        """Extract job details from the current page (job detail window) using the new structure"""
        print("Extracting job details")
        try:
            # Wait for page to load completely
            time.sleep(3)  # Give the page more time to load
            
            # First check what kind of page structure we're dealing with
            print("Analyzing page structure...")
            page_html = self.driver.page_source
            
            # Print the page title to help identify what page we're on
            print(f"Page title: {self.driver.title}")
            
            # Print URL to debug potential redirects
            print(f"Current URL: {self.driver.current_url}")
            
            # Try different wait conditions to detect the page type
            try:
                # Try to wait for any of these common elements to appear
                self.wait.until(lambda driver: driver.find_elements(By.CSS_SELECTOR, ".board-view") or 
                                driver.find_elements(By.CSS_SELECTOR, ".careers-area") or
                                driver.find_elements(By.CSS_SELECTOR, ".cp_name") or
                                driver.find_elements(By.CSS_SELECTOR, ".tit"))
                print("Page loaded successfully")
            except TimeoutException:
                print("Warning: Could not detect standard page elements. Continuing anyway...")
            
            # Extract company name 
            try:
                company_name = self.driver.find_element(By.CSS_SELECTOR, "#contents > section > div > div.careers-area > div.careers-new > div.border > div.right > div.info > ul > li:nth-child(1) > div").text.strip()
                if company_name:
                    self.job_data["Company Name"] = company_name
            except NoSuchElementException:
                pass
                
                
            # Extract job title (if not already set from listing)
            if self.job_data["Job Title"] == "Not found" or self.job_data["Job Title"] == "Not found in listing":
                try:
                    title_element = self.driver.find_element(By.CSS_SELECTOR, "#contents > section > div > div.careers-area > div.careers-new > div.border > div.left > div.tit-area > p")
                    job_title = title_element.text.strip()
                    if job_title:
                        self.job_data["Job Title"] = job_title
                except NoSuchElementException:
                    try:
                        # Try alternative selector
                        title_element = self.driver.find_element(By.CSS_SELECTOR, ".tit > em")
                        job_title = title_element.text.strip()
                        if job_title:
                            self.job_data["Job Title"] = job_title
                    except NoSuchElementException:
                        pass

            # Extract job category
            try:
                job_category = self.driver.find_element(By.CSS_SELECTOR, "#contents > section > div > div.careers-area > div:nth-child(6) > table > tbody > tr > td:nth-child(1)").text.strip()
                if job_category:
                    self.job_data["Job Category"] = job_category
            except NoSuchElementException:
                pass
                
            # Extract required experience
            try:
                experience = self.driver.find_element(By.CSS_SELECTOR, "#contents > section > div > div.careers-area > div.careers-new > div.border > div.left > div:nth-child(2) > div:nth-child(1) > div > ul > li:nth-child(1) > span").text.strip()
                if experience:
                    self.job_data["Experience Required"] = experience
            except NoSuchElementException:
                try:
                    experience = self.driver.find_element(By.CSS_SELECTOR, "td.pleft:nth-of-type(3)").text.strip()
                    if experience:
                        self.job_data["Experience Required"] = experience
                except NoSuchElementException:
                    pass
                
            # Extract employment type
            try:
                employment_type = self.driver.find_element(By.CSS_SELECTOR, "#contents > section > div > div.careers-area > div.careers-new > div.border > div.left > div:nth-child(3) > div:nth-child(1) > div > ul > li:nth-child(1) > span").text.strip()
                if employment_type:
                    self.job_data["Employment Type"] = employment_type
            except NoSuchElementException:
                try:
                    employment_type = self.driver.find_element(By.CSS_SELECTOR, "td.pleft:nth-of-type(6)").text.strip()
                    if employment_type:
                        self.job_data["Employment Type"] = employment_type
                except NoSuchElementException:
                    pass
                
            # Extract salary
            try:
                salary = self.driver.find_element(By.CSS_SELECTOR, "#contents > section > div > div.careers-area > div.careers-new > div.border > div.left > div:nth-child(2) > div:nth-child(2) > div > ul > li:nth-child(2) > span").text.strip()
                if salary:
                    self.job_data["Salary"] = salary
            except NoSuchElementException:
                try:
                    salary = self.driver.find_element(By.CSS_SELECTOR, "td.pleft:nth-of-type(7)").text.strip()
                    if salary:
                        self.job_data["Salary"] = salary
                except NoSuchElementException:
                    pass
                
            # Extract location
            try:
                location = self.driver.find_element(By.CSS_SELECTOR, "#contents > section > div > div.careers-area > div.careers-new > div.border > div.left > div:nth-child(2) > div:nth-child(2) > div > ul > li:nth-child(1) > span").text.strip()
                if location:
                    self.job_data["Location"] = location
            except NoSuchElementException:
                try:
                    location = self.driver.find_element(By.CSS_SELECTOR, "td.pleft:nth-of-type(8)").text.strip()
                    if location:
                        self.job_data["Location"] = location
                except NoSuchElementException:
                    pass

            # Extract working type
            try:
                working_type = self.driver.find_element(By.CSS_SELECTOR, "#contents > section > div > div.careers-area > div.careers-new > div.border > div.left > div:nth-child(3) > div:nth-child(1) > div > ul > li:nth-child(2) > span").text.strip()
                if working_type:
                    self.job_data["Working Type"] = working_type
            except NoSuchElementException:
                pass
                
            # Extract working hours
            try:
                working_hours = self.driver.find_element(By.CSS_SELECTOR, "#contents > section > div > div.careers-area > div:nth-child(8) > table > tbody > tr > td:nth-child(2)").text.strip()
                if working_hours:
                    self.job_data["Working Hours"] = working_hours
            except NoSuchElementException:
                try:
                    working_hours = self.driver.find_element(By.CSS_SELECTOR, "td.pleft:nth-of-type(9)").text.strip()
                    if working_hours:
                        self.job_data["Working Hours"] = working_hours
                except NoSuchElementException:
                    pass
                
            # Extract job description
            try:
                job_description = self.driver.find_element(By.CSS_SELECTOR, "#contents > section > div > div.careers-area > div:nth-child(4) > table > tbody > tr > td").text.strip()
                if job_description:
                    self.job_data["Job Description"] = job_description
            except NoSuchElementException:
                pass
                
            # Extract Social Insurance information
            try:
                insurance_elements = self.driver.find_elements(By.CSS_SELECTOR, "#contents > section > div > div.careers-area > div:nth-child(8) > table > tbody > tr > td:nth-child(4)")
                if insurance_elements and len(insurance_elements) > 0:
                    insurance_info = insurance_elements[0].text.strip()
                    if insurance_info:
                        self.job_data["SocialEnsurance"] = insurance_info
            except NoSuchElementException:
                pass
                
            # Extract Retirement Benefit information
            try:
                retirement_elements = self.driver.find_elements(By.CSS_SELECTOR, "#contents > section > div > div.careers-area > div:nth-child(8) > table > tbody > tr > td:nth-child(5)")
                if retirement_elements and len(retirement_elements) > 0:
                    retirement_info = retirement_elements[0].text.strip()
                    if retirement_info:
                        self.job_data["RetirementBenefit"] = retirement_info
            except NoSuchElementException:
                pass
                
            # Extract application method
            try:
                application_method = self.driver.find_element(By.CSS_SELECTOR, "#contents > section > div > div.careers-area > div:nth-child(11) > table > tbody > tr > td:nth-child(3)").text.strip()
                if application_method:
                    self.job_data["ApplicationMethod"] = application_method
            except NoSuchElementException:
                pass

            # Extract Application Type
            try:
                app_type_elements = self.driver.find_elements(By.CSS_SELECTOR, "#contents > section > div > div.careers-area > div:nth-child(11) > table > tbody > tr > td:nth-child(2)")
                if app_type_elements and len(app_type_elements) > 0:
                    app_type_info = app_type_elements[0].text.strip()
                    if app_type_info:
                        self.job_data["ApplicationType"] = app_type_info
            except NoSuchElementException:
                pass
                
            # Extract document requirements
            try:
                document_elements = self.driver.find_elements(By.CSS_SELECTOR, "#contents > section > div > div.careers-area > div:nth-child(11) > table > tbody > tr > td:nth-child(4)")
                if document_elements and len(document_elements) > 0:
                    document_info = document_elements[0].text.strip()
                    if document_info:
                        self.job_data["document"] = document_info
            except NoSuchElementException:
                pass
            
            print(f"Extracted job details for {self.job_data['Job Title']} at {self.job_data['Company Name']}")
            return True
            
        except Exception as e:
            print(f"Error extracting job details: {e}")
            return False
    
    def crawl_specific_job(self, job_link_info):
        """Click on a job link and crawl the details from the new window"""
        main_window = self.driver.current_window_handle
        
        # Extract the link element, initial job data, and job ID from listing page
        job_link = job_link_info["link_element"]
        listing_job_data = job_link_info["job_data"]
        job_id = job_link_info["job_id"]
        
        # Check if we've already processed this job (using in-memory set)
        if job_id in self.processed_job_ids:
            print(f"Skipping already processed job: {listing_job_data['Job Title']}")
            return
        
        # Set global job_data to the data from listing page
        self.job_data = listing_job_data.copy()
        
        try:
            # Get link URL using JavaScript instead of direct clicking
            print("Getting job link URL...")
            link_url = None
            
            try:
                # Try to get href attribute
                link_url = job_link.get_attribute('href')
                print(f"Found link URL: {link_url}")
            except Exception as e:
                print(f"Could not get href attribute: {e}")
                # Try clicking instead
                try:
                    # Make sure element is clickable
                    self.wait.until(EC.element_to_be_clickable((By.XPATH, f".//*[contains(text(), '{job_link.text}')]")))
                    job_link.click()
                    print("Clicked job link directly")
                except Exception as click_error:
                    print(f"Click failed too: {click_error}")
                    # Try JavaScript click as last resort
                    try:
                        self.driver.execute_script("arguments[0].click();", job_link)
                        print("Used JavaScript click as fallback")
                    except:
                        print("All click methods failed")
                        # Add the job data from the listing page
                        self.jobs.append(self.job_data.copy())
                        # Mark this job as processed
                        self.checkpoint["processed_job_ids"].add(job_id)
                        self.save_checkpoint()
                        print(f"Added basic data from listing page for: {self.job_data['Job Title']}")
                        return
            
            # If we got a URL, open it in a new window/tab
            if link_url:
                print(f"Opening URL in new window: {link_url}")
                # Open in new window using JavaScript
                self.driver.execute_script(f"window.open('{link_url}', '_blank');")
                time.sleep(3)  # Wait for new window to open
            else:
                # If we clicked directly, wait for new window
                time.sleep(3)
            
            # Switch to the new window
            all_windows = self.driver.window_handles
            if len(all_windows) > 1:
                for window in all_windows:
                    if window != main_window:
                        self.driver.switch_to.window(window)
                        print("Switched to job details window")
                        break
                
                # Extract job details with extended timeout
                success = self.extract_job_details()
                
                if success:
                    # Add the job data to the collected jobs
                    self.jobs.append(self.job_data.copy())
                    # Mark this job as processed (in memory)
                    self.processed_job_ids.add(job_id)
                    # Update the checkpoint with just the last processed job ID
                    self.checkpoint["last_processed_job_id"] = job_id
                    self.save_checkpoint()
                    print(f"Successfully added job data: {self.job_data['Job Title']}")
                else:
                    # Even if detailed extraction failed, use the data from listing
                    self.jobs.append(self.job_data.copy())
                    # Mark as processed
                    self.checkpoint["processed_job_ids"].add(job_id)
                    self.save_checkpoint()
                    print(f"Added job data with limited details: {self.job_data['Job Title']}")
                
                # Close the job details window and switch back to main window
                try:
                    self.driver.close()
                    self.driver.switch_to.window(main_window)
                    print("Closed job details window and returned to main window")
                except Exception as close_error:
                    print(f"Error closing window: {close_error}")
                    # Force switch to main window
                    self.driver.switch_to.window(main_window)
                
                time.sleep(2)  # Longer pause before next action
            else:
                print("No new window opened after clicking the link")
                # If we couldn't open window but have listing data, still create a record
                self.jobs.append(self.job_data.copy())
                # Mark as processed (in memory)
                self.processed_job_ids.add(job_id)
                # Update the checkpoint with just the last processed job ID
                self.checkpoint["last_processed_job_id"] = job_id
                self.save_checkpoint()
                print(f"Added job data without window: {self.job_data['Job Title']}")
            
        except Exception as e:
            print(f"Error processing job link: {e}")
            # Still add the data we have
            self.jobs.append(self.job_data.copy())
            # Mark as processed despite error (in memory)
            self.processed_job_ids.add(job_id)
            # Update the checkpoint with just the last processed job ID
            self.checkpoint["last_processed_job_id"] = job_id
            self.save_checkpoint()
            print(f"Added job data after error: {self.job_data['Job Title']}")
            
            # Recovery procedure
            try:
                # Make sure all windows except main are closed
                current_windows = self.driver.window_handles
                for window in current_windows:
                    if window != main_window:
                        self.driver.switch_to.window(window)
                        self.driver.close()
                
                # Switch back to main window
                self.driver.switch_to.window(main_window)
                print("Performed emergency recovery")
                time.sleep(2)
            except Exception as recovery_error:
                print(f"Recovery failed: {recovery_error}")
                # Last resort: restart browser
                try:
                    self.driver.quit()
                    print("Restarting browser...")
                    self.driver = webdriver.Chrome(options=self.chrome_options)
                    self.wait = WebDriverWait(self.driver, 10)
                    self.driver.get(self.driver.current_url)
                    time.sleep(5)
                except:
                    print("Could not restart browser")
    
    def crawl_list_jobs(self, list_selector, link_pattern, list_index):
        """Crawl all jobs in a specific list on the current page"""
        self.current_list = list_selector  # Track current list for data tracking
        print(f"Processing jobs in {list_selector}")
        
        # Update checkpoint with current list
        self.checkpoint["current_list_index"] = list_index
        self.save_checkpoint()
        
        # Initialize retry counter
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                # Try with the provided pattern first
                job_links_info = self.get_job_links(list_selector, link_pattern)
                
                # If no links found, try alternative pattern
                if not job_links_info:
                    print(f"No links found with primary pattern, trying alternative...")
                    alternative_pattern = "td:nth-child(3) > div > div > a"  # Alternative pattern
                    job_links_info = self.get_job_links(list_selector, alternative_pattern)
                
                # If still no links, try with a very generic pattern
                if not job_links_info:
                    print(f"Still no links, trying generic pattern...")
                    generic_pattern = "a[href*='empInfo']"  # Very generic pattern
                    job_links_info = self.get_job_links(list_selector, generic_pattern)
                
                if not job_links_info:
                    print(f"No job links found in {list_selector} after trying all patterns")
                    retry_count += 1
                    time.sleep(1)
                    continue
                
                print(f"Found {len(job_links_info)} links to process in {list_selector}")
                for i, link_info in enumerate(job_links_info):
                    print(f"Processing job {i+1}/{len(job_links_info)} from {list_selector}")
                    try:
                        # Scroll to the element to ensure it's clickable
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", link_info["link_element"])
                        time.sleep(0.5)
                        
                        # Crawl this specific job
                        self.crawl_specific_job(link_info)
                        
                    except StaleElementReferenceException:
                        print("Element became stale, refreshing job links")
                        # Try all patterns again when refreshing
                        refreshed_links = self.get_job_links(list_selector, link_pattern)
                        if not refreshed_links:
                            refreshed_links = self.get_job_links(list_selector, "td:nth-child(3) > div > div > a")
                        if not refreshed_links:
                            refreshed_links = self.get_job_links(list_selector, "a[href*='empInfo']")
                            
                        if refreshed_links and i < len(refreshed_links):
                            self.crawl_specific_job(refreshed_links[i])
                        else:
                            print(f"Could not retrieve job link {i} after refresh")
                    
                    except Exception as e:
                        print(f"Error processing job link {i}: {e}")
                
                # If we got here without exceptions, break the retry loop
                break
                
            except Exception as e:
                print(f"Error processing list {list_selector}: {e}")
                retry_count += 1
                if retry_count >= max_retries:
                    print(f"Max retries reached for {list_selector}, moving to next list")
    
    
    def save_to_csv(self, filename="job_data.csv"):
        """Save the collected job data to a CSV file, creating it if it doesn't exist
        and appending to it if it does, ensuring proper line breaks between entries"""
        if not self.jobs:
            print("No jobs to save.")
            return
            
        # Create DataFrame from current job data
        df_new = pd.DataFrame(self.jobs)
        
        # Check if file already exists
        file_exists = os.path.isfile(filename)
        
        if file_exists:
            try:
                # Read existing CSV
                df_existing = pd.read_csv(filename, encoding='utf-8-sig')
                
                # Append new data to existing data
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                
                # Remove duplicates (in case we recrawled some jobs)
                df_combined = df_combined.drop_duplicates(subset=['Job Title', 'Company Name', 'Deadline'], keep='last')
                
                # Save combined dataframe with proper line separator
                df_combined.to_csv(filename, index=False, encoding='utf-8-sig', lineterminator='\n')
                print(f"Appended {len(df_new)} jobs to existing file {filename}. Total: {len(df_combined)} jobs")
                
            except Exception as e:
                print(f"Error appending to existing file: {e}")
                # Fallback to creating a new file with current data only
                df_new.to_csv(filename, index=False, encoding='utf-8-sig', lineterminator='\n')
                print(f"Created new file {filename} with {len(df_new)} jobs")
        else:
            # File doesn't exist, create new
            df_new.to_csv(filename, index=False, encoding='utf-8-sig', lineterminator='\n')
            print(f"Created new file {filename} with {len(df_new)} jobs")
        
        # Reset the jobs list to free memory after saving to CSV
        self.jobs = []
        print("job opening saved successfully")
    
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
                checkpoint_data = json.load(f)
                
                # Add the last processed job ID to our in-memory set
                if "last_processed_job_id" in checkpoint_data and checkpoint_data["last_processed_job_id"]:
                    self.processed_job_ids.add(checkpoint_data["last_processed_job_id"])
                
                self.checkpoint = checkpoint_data
                print(f"Loaded checkpoint: Page {self.checkpoint['current_page']}, List {self.checkpoint['current_list_index']}")
                print(f"Last processed job ID: {self.checkpoint.get('last_processed_job_id', 'None')}")
                return True
        except Exception as e:
            print(f"Error loading checkpoint: {e}")
            return False
        
    def save_checkpoint(self):
        """Save the current crawling state to a checkpoint file"""
        try:
            # Create a copy of the checkpoint for serialization
            checkpoint_data = self.checkpoint.copy()
            checkpoint_data["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
            
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
                
            print(f"Checkpoint saved with last processed job ID: {self.checkpoint.get('last_processed_job_id', 'None')}")
        except Exception as e:
            print(f"Error saving checkpoint: {e}")
    
    def navigate_to_checkpoint(self, start_url):
        """Navigate to the page and position specified in the checkpoint"""
        if not self.checkpoint["last_url"]:
            self.navigate_to_url(start_url)
            return
        
        try:
            # Navigate to the last URL first
            self.navigate_to_url(self.checkpoint["last_url"])
            
            # If we're not on page 1, navigate to the correct page
            current_page = self.checkpoint["current_page"]
            current_button = self.checkpoint["current_page_button"]
            
            if current_page > 1:
                print(f"Navigating to checkpoint page {current_page}")
                
                # Click through pages to get to the checkpoint page
                for page_num in range(1, current_page):
                    button_index = 3 + page_num  # Adjust button index based on page number
                    if button_index > 12:
                        # Reset after reaching the end of pagination set
                        button_index = 4
                        # Click the "next" control instead
                        try:
                            next_control = self.driver.find_element(By.CSS_SELECTOR, "#frm > div.nav_wrp > nav > a.control.next")
                            next_control.click()
                            time.sleep(3)
                        except:
                            print("Error navigating to next pagination set")
                            break
                    else:
                        try:
                            page_button = self.driver.find_element(By.CSS_SELECTOR, f"#frm > div.nav_wrp > nav > a:nth-child({button_index})")
                            page_button.click()
                            time.sleep(3)
                        except:
                            print(f"Error clicking page button {button_index}")
                            break
                
                print(f"Reached checkpoint page {current_page}")
            
        except Exception as e:
            print(f"Error navigating to checkpoint: {e}")
            # Fall back to starting URL if there's an error
            self.navigate_to_url(start_url)

    def go_to_next_page(self, current_button_index):
        """Navigate to the next page using the specified button index or next control button"""
        try: #frm > div.nav_wrp > nav > a.control.next
   
                
            # if current_button_index == 12:  # a:nth-child(12) corresponds to page 10
            #     print("On page 10, need to click next pagination set button...")
            #     next_control_selector = "#frm > div.nav_wrp > nav > a.control.next"
            #     next_control = self.driver.find_element(By.CSS_SELECTOR, next_control_selector)
            #     time.sleep(0.5)
            #     next_control.click()
            #     print("Clicked 'next' control button to move to next page set (pages 11-20)")
            #     time.sleep(3)  # Wait for page to load
                
            #     # After clicking "next", we should be on page 11 which is button 4 in the new set
            #     self.checkpoint["current_page_button"] = 4
                
                # if "disabled" not in next_control.get_attribute("class").split():
                #     # Click the next button to move to the next set of pages
                #     self.driver.execute_script("arguments[0].scrollIntoView(true);", next_control)
                #     time.sleep(0.5)
                #     next_control.click()
                #     print("Clicked 'next' control button to move to next page set (pages 11-20)")
                #     time.sleep(3)  # Wait for page to load
                    
                #     # After clicking "next", we should be on page 11 which is button 4 in the new set
                #     self.checkpoint["current_page_button"] = 4
                #     return True
                # else:
                #     print("Next control button is disabled - reached the end")
                #     return False
            
            # For non-page-10 situations, use the numbered page buttons
            page_button_selector = f"#frm > div.nav_wrp > nav > a:nth-child({current_button_index})"
            print(f"Looking for page button: {page_button_selector}")
            
            try:
                page_button = self.driver.find_element(By.CSS_SELECTOR, page_button_selector)
                button_text = page_button.text.strip()
                page_button.click()
                print(f"Clicked page button #{current_button_index} (page {button_text})")
                time.sleep(3)  # Wait for page to load
                
                # # Check if the button is clickable
                # if page_button.is_displayed() and page_button.is_enabled():
                #     # Scroll to make sure it's visible
                #     self.driver.execute_script("arguments[0].scrollIntoView(true);", page_button)
                #     time.sleep(0.5)
                    
                #     # Click the button
                #     page_button.click()
                #     print(f"Clicked page button #{current_button_index} (page {button_text})")
                #     time.sleep(3)  # Wait for page to load
                #     return True
                # else:
                #     print(f"Page button #{current_button_index} is not clickable")
                #     return False
            except Exception as button_error:
                print(f"Error finding or clicking page button #{current_button_index}: {button_error}")
                
                # Try JavaScript click as fallback
                # try:
                #     print("Trying JavaScript click as fallback")
                #     button = self.driver.find_element(By.CSS_SELECTOR, page_button_selector)
                #     self.driver.execute_script("arguments[0].click();", button)
                #     print(f"Clicked page button #{current_button_index} using JavaScript")
                #     time.sleep(3)
                #     return True
                # except:
                #     print("JavaScript click also failed")
                    
                # As a last resort, try the "next" button
                # try:
                #     next_button = self.driver.find_element(By.CSS_SELECTOR, "#frm > div.nav_wrp > nav > a.control.next")
                #     next_button.click()
                #     print("Used 'next' control as fallback")
                #     time.sleep(3)
                #     # Reset button index after clicking next
                #     self.checkpoint["current_page_button"] = 4
                #     return True
                # except:
                #     print("All pagination attempts failed")
                #     return False
                
        except Exception as e:
            print(f"Error navigating to next page: {e}")
            return False
        
    def run(self, start_url, max_pages=100):
        """Run the comprehensive scraping process for all lists and pages"""
        # Use consistent pattern across all lists
        list_configs = []
        
        # Generate configurations for list1 through list10
        for i in range(1, 11):
            list_configs.append({
                "selector": f"#list{i}", 
                "pattern": "td:nth-child(3) > div > div > a"  # Use the specific pattern as requested
            })
        
        # Load checkpoint if it exists and populate job ID tracking
        checkpoint_exists = self.load_checkpoint()
        
        # If resuming from a checkpoint, load all previously saved jobs to avoid duplicates
        if checkpoint_exists and os.path.exists("job_data.csv"):
            try:
                print("Loading existing job data to avoid duplicates...")
                df_existing = pd.read_csv("job_data.csv", encoding='utf-8-sig')
                # Generate job IDs for all existing jobs and add to processed set
                for _, row in df_existing.iterrows():
                    job_id = f"{row.get('Job Title', 'unknown')}_{row.get('Date of registration', 'unknown')}_{row.get('Deadline', 'unknown')}"
                    self.processed_job_ids.add(job_id)
                print(f"Loaded {len(self.processed_job_ids)} job IDs from existing data to prevent duplicates")
            except Exception as e:
                print(f"Error loading existing job data: {e}")
        
        try:
            # Navigate to the appropriate starting point
            if checkpoint_exists:
                self.navigate_to_checkpoint(start_url)
                # Set the page count and button index from checkpoint
                page_count = self.checkpoint["current_page"]
                current_page_button = self.checkpoint["current_page_button"]
                # Get the list index to start from
                start_list_index = self.checkpoint["current_list_index"]
            else:
                # Start from the URL provided (page 10)
                self.navigate_to_url(start_url)
                page_count = 1
                current_page_button = 4  # Button index for page 10
                start_list_index = 0
            
            while page_count <= max_pages:
                print(f"\n--- Scraping page {page_count} ---")
                
                # Update checkpoint with current page
                self.checkpoint["current_page"] = page_count
                self.checkpoint["current_page_button"] = current_page_button
                self.save_checkpoint()
                
                # Crawl jobs from each list on this page, starting from the checkpoint list
                for list_index, list_config in enumerate(list_configs[start_list_index:], start=start_list_index):
                    print(f"\n--- Processing {list_config['selector']} (index {list_index}) ---")
                    self.crawl_list_jobs(list_config['selector'], list_config['pattern'], list_index)

                    # Save progress to main CSV file after each list
                    self.save_to_csv("job_data.csv")
                    
                
                # Reset the list index for the next page to start from the beginning
                start_list_index = 0

                            # Special case: If we just finished a page that's a multiple of 10 (like 10, 20, 30), go to next page set
                if page_count % 10 == 0 and list_config["selector"] == "#list10":
                    print(f"\n--- Finished page {page_count}, list 10. Moving to page {page_count+1} ---")
                    try:
                        # Navigate to next page using the next button
                        next_control_selector = "#frm > div.nav_wrp > nav > a.control.next"
                        next_control = self.driver.find_element(By.CSS_SELECTOR, next_control_selector)
                        time.sleep(0.5)
                        
                        # Use JavaScript click for more reliability
                        self.driver.execute_script("arguments[0].click();", next_control)
                        print(f"Clicked 'next' control button to move to page {page_count+1}")
                        time.sleep(3)  # Wait for page to load
                        
                        # Update page count and button index for the next page
                        page_count += 1
                        current_page_button = 4  # Button index for page 1 in new set
                        start_list_index = 0  # Start from list 1 on the new page
                        
                        # Update checkpoint
                        self.checkpoint["current_page"] = page_count
                        self.checkpoint["current_page_button"] = current_page_button
                        self.checkpoint["current_list_index"] = start_list_index
                        self.save_checkpoint()
                        
                    except Exception as e:
                        print(f"Error navigating to page {page_count+1}: {e}")

                else :
                    # After crawling all lists (list1 through list10), move to next page
                    print("go to next page")
                    self.go_to_next_page(current_page_button)
                    page_count += 1
                        # Only increment the button index if we didn't just click the "next" control
                        # The go_to_next_page function now handles resetting the button index when needed
                    if current_page_button != 12:  # If we weren't on page 10
                        current_page_button += 1
               
                        
                # If we've finished all lists and haven't navigated to a new page yet
                # if list_index == 9 and not (page_count % 10 == 0 and list_config["selector"] == "#list10"):
                #     # Reset the list index for the next page
                #     start_list_index = 0
                    
                #     # Navigate to the next page using standard navigation for non-multiple-of-10 pages
                #     try:
                #         # Calculate the next button index
                #         next_button_index = current_page_button + 1
                #         page_button_selector = f"#frm > div.nav_wrp > nav > a:nth-child({next_button_index})"
                #         page_button = self.driver.find_element(By.CSS_SELECTOR, page_button_selector)
                #         self.driver.execute_script("arguments[0].scrollIntoView(true);", page_button)
                #         time.sleep(0.5)
                        
                #         # Use JavaScript click for more reliability
                #         self.driver.execute_script("arguments[0].click();", page_button)
                #         print(f"Clicked button to move from page {page_count} to page {page_count+1}")
                #         time.sleep(3)
                        
                #         page_count += 1
                #         current_page_button = next_button_index
                        
                #         # Update checkpoint
                #         self.checkpoint["current_page"] = page_count
                #         self.checkpoint["current_page_button"] = current_page_button
                #         self.checkpoint["current_list_index"] = start_list_index
                #         self.save_checkpoint()
                #     except Exception as e:
                #         print(f"Error navigating from page {page_count} to page {page_count+1}: {e}")
                #         print("Reached the last page or no more pages to scrape")
                #         
                
            # Save the final collected job data
            self.save_to_csv("job_data.csv")
            
            # Keep the checkpoint file for future use
            print("Crawling completed successfully. Checkpoint file preserved for future use.")
            
        except KeyboardInterrupt:
            print("\nCrawling interrupted by user. Saving progress...")
            # Save current data and checkpoint
            self.save_to_csv("job_data.csv")
            self.save_checkpoint()
            print("Progress saved. You can resume later from this point.")
            
        except Exception as e:
            print(f"Error during scraping process: {e}")
            # Save whatever data we've collected so far
            self.save_to_csv("job_data.csv")
            # Make sure the checkpoint is saved
            self.save_checkpoint()
            print("Saved checkpoint. You can resume from this point later.")
            
        finally:
            self.close()



# Run the crawler
if __name__ == "__main__":
    # The URL for job listings
    url = 'https://www.work.go.kr/empInfo/themeEmp/themeEmpInfoSrchList.do?occupation=&currentUri=%2FempInfo%2FthemeEmp%2FthemeEmpInfoSrchList.do&webIsOut=&resultCnt=10&thmaHrplCd=F00030&notSrcKeyword=&isEmptyHeader=&_csrf=098aff9b-05fa-4e36-afe5-4366bdd690ec&currntPageNo=1&listCookieInfo=DTL&isChkLocCall=&pageIndex=1&selTheme=F00030&sortField=DATE&moerButtonYn=&themeListidx=20&keyword=&region=41000&sortOrderBy=DESC'
    
    # Create and run the crawler - set headless=False to see the browser in action
    crawler = WorkGoKrCrawler(headless=False)
    crawler.run(url, max_pages=100)  # Crawl up to 30 pages

    