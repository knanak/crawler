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

class YeonsuEducationCrawler:
    def __init__(self, headless=True, checkpoint_file="yeonsu_education_checkpoint.json"):
        try:
            # Configure Chrome options with enhanced stability settings
            self.chrome_options = Options()
            if headless:
                self.chrome_options.add_argument('--headless=new')
            self.chrome_options.add_argument('--window-size=1920,1080')
            self.chrome_options.add_argument('--disable-gpu')
            self.chrome_options.add_argument('--no-sandbox')
            self.chrome_options.add_argument('--disable-dev-shm-usage')
            # Additional stability options
            self.chrome_options.add_argument('--disable-extensions')
            self.chrome_options.add_argument('--disable-popup-blocking')
            self.chrome_options.add_argument('--ignore-certificate-errors')
            self.chrome_options.add_argument('--ignore-ssl-errors')
            self.chrome_options.add_argument('--disable-web-security')
            self.chrome_options.add_argument('--allow-running-insecure-content')
            # Added options to fix SSL errors
            self.chrome_options.add_argument('--ignore-certificate-errors-spki-list')
            # Prevent detection
            self.chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            self.chrome_options.add_experimental_option('excludeSwitches', ['enable-automation', 'enable-logging'])
            self.chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Initialize the driver
            self.driver = webdriver.Chrome(options=self.chrome_options)
            self.driver.set_page_load_timeout(60)
            self.wait = WebDriverWait(self.driver, 30)
            
            # URL 목록 정의
            self.urls = [
                'https://www.yeonsu.go.kr/lll/edu/global_request.asp',
                'https://www.yeonsu.go.kr/lll/edu/happylife_request.asp'
            ]
            self.url_names = ["글로벌", "행복생활"]  # URL 구분용 이름
            
            # Structure for lecture data
            self.lecture_data = {
                "City": "인천시 연수구",
                "Category": "",  # URL 카테고리 저장
                "Title": "",
                "Recruitment_period": "",
                "Education_period": "",
                "Quota": "",
                "Institution": "",
                "Address": "",
                "Tel": "",
                "Detail": "",
                "Fee": ""
            }
            
            # Storage for collected lectures
            self.lectures = []
            
            # Checkpoint configuration
            self.checkpoint_file = checkpoint_file
            self.checkpoint = {
                "current_url_index": 0,  # 현재 처리 중인 URL 인덱스
                "current_page": 1,
                "last_processed_row": 0,
                "last_url": "",
                "timestamp": ""
            }
            
            # Add user agent to appear more like a regular browser
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
            })
            
        except Exception as e:
            print(f"Error during initialization: {e}")
            raise e
        
    def navigate_to_url(self, url):
        """Navigate to the main lecture listing URL"""
        print(f"Navigating to {url}")
        try:
            self.driver.get(url)
            time.sleep(5)
            self.checkpoint["last_url"] = url
            self.save_checkpoint()
        except Exception as e:
            print(f"Error during navigation: {e}")
            print("Trying with SSL error bypass...")
            try:
                self.driver.execute_cdp_cmd('Security.setIgnoreCertificateErrors', {'ignore': True})
                self.driver.get(url)
                time.sleep(5)
                self.checkpoint["last_url"] = url
                self.save_checkpoint()
            except Exception as e2:
                print(f"Second navigation attempt failed: {e2}")
                time.sleep(10)
                self.driver.get(url)
                time.sleep(10)
                self.checkpoint["last_url"] = url
                self.save_checkpoint()
    
    def reset_lecture_data(self):
        """Reset the lecture_data dictionary to initial state"""
        # URL 카테고리 값은 유지
        category = self.lecture_data.get("Category", "")
        
        self.lecture_data = {
            "City": "인천시 연수구",
            "Category": category,
            "Title": "Not found",
            "Recruitment_period": "Not found",
            "Education_period": "Not found",
            "Quota": "Not found",
            "Institution": "Not found",
            "Address": "Not found",
            "Tel": "Not found",
            "Detail": "Not found",
            "Fee": "Not found"
        }
    
    def find_courses_accepting_applications(self):
        """Find all courses on current page that are currently accepting applications"""
        available_rows = []
        
        try:
            print("Looking for courses accepting applications...")
            
            # 페이지에 있는 총 강좌 목록 확인
            course_rows = []
            try:
                course_rows = self.driver.find_elements(By.CSS_SELECTOR, "#detail_con > div.board_list > table > tbody > tr")
                print(f"Total courses found on page: {len(course_rows)}")
            except Exception as e:
                print(f"Error finding course rows: {e}")
                return []
            
            # 각 강좌의 신청 상태 확인 (최대 10개)
            for i in range(1, min(11, len(course_rows) + 1)):
                try:
                    # 상태 확인용 셀렉터
                    status_selector = f"#detail_con > div.board_list > table > tbody > tr:nth-child({i}) > td:nth-child(5) > span"
                    status_elements = self.driver.find_elements(By.CSS_SELECTOR, status_selector)
                    
                    if status_elements and len(status_elements) > 0:
                        status_text = status_elements[0].text.strip()
                        print(f"Row {i} status: '{status_text}'")
                        
                        # 신청중인 강좌만 추가
                        if status_text == "신청중":
                            available_rows.append(i)
                            print(f"Row {i} is accepting applications, adding to list")
                except Exception as e:
                    print(f"Error checking status for row {i}: {e}")
            
            print(f"Found {len(available_rows)} courses accepting applications: {available_rows}")
            return available_rows
            
        except Exception as e:
            print(f"Error finding available courses: {e}")
            return []
    
    def extract_lecture_data(self, row_number):
        """Extract lecture data from the course row and detail page"""
        print(f"\n>>> Extracting data from course {row_number}")
        
        try:
            # 먼저 강좌 데이터 초기화
            self.reset_lecture_data()
            
            # 강좌 목록 페이지 URL 저장
            list_page_url = self.driver.current_url
            
            # 강좌 링크 찾아서 클릭
            course_link_selector = f"#detail_con > div.board_list > table > tbody > tr:nth-child({row_number}) > td.title > a"
            
            try:
                # 링크 요소 찾기
                course_link_element = self.driver.find_element(By.CSS_SELECTOR, course_link_selector)
                
                # 링크 URL 저장 (Detail)
                detail_url = course_link_element.get_attribute('href')
                self.lecture_data["Detail"] = detail_url
                print(f"Detail page URL: {detail_url}")
                
                # 클릭하여 상세 페이지로 이동
                print(f"Clicking on course {row_number} to access detail page...")
                self.driver.execute_script("arguments[0].scrollIntoView(true);", course_link_element)
                time.sleep(1)
                
                # JavaScript 클릭 시도
                self.driver.execute_script("arguments[0].click();", course_link_element)
                
                # 상세 페이지 로딩 대기
                time.sleep(3)
                
                # 상세 페이지로 제대로 이동했는지 확인
                current_url = self.driver.current_url
                print(f"Current URL after click: {current_url}")
                
                # URL이 그대로라면 다른 방법으로 클릭 시도
                if current_url == list_page_url and detail_url != list_page_url:
                    print("JavaScript click failed. Trying native click...")
                    try:
                        # 네이티브 클릭 시도
                        course_link_element.click()
                        time.sleep(3)
                        
                        # 여전히 같은 페이지면 직접 이동
                        if self.driver.current_url == list_page_url:
                            print("Native click failed. Navigating directly to detail page...")
                            self.driver.get(detail_url)
                            time.sleep(3)
                    except Exception as click_e:
                        print(f"Native click failed: {click_e}. Navigating directly to detail page...")
                        self.driver.get(detail_url)
                        time.sleep(3)
                
                # 상세 페이지에서 데이터 추출
                detail_success = self.extract_detail_page_data()
                if not detail_success:
                    print(f"Failed to extract data from detail page for course {row_number}")
                
                # 목록 페이지로 돌아가기
                print("Going back to listing page...")
                self.driver.back()
                time.sleep(3)
                
                # 목록 페이지로 제대로 돌아왔는지 확인
                if list_page_url not in self.driver.current_url:
                    print(f"Navigation back failed. Directly navigating to list page: {list_page_url}")
                    self.driver.get(list_page_url)
                    time.sleep(3)
                
                # 충분한 데이터를 수집했는지 확인
                not_found_count = sum(1 for value in self.lecture_data.values() if value == "Not found")
                if not_found_count > 5:  # 5개 이상의 필드가 "Not found"면
                    print(f"Too many missing values ({not_found_count}) for course {row_number}, skipping")
                    return False
                
                print(f"Successfully extracted data for course {row_number}")
                return True
                
            except NoSuchElementException as e:
                print(f"Course element not found for row {row_number}: {e}")
                return False
                
            except Exception as e:
                print(f"Error accessing or extracting from detail page: {e}")
                # 목록 페이지로 복귀 시도
                try:
                    self.driver.get(list_page_url)
                    time.sleep(3)
                except:
                    print("Failed to return to listing page after error")
                return False
                
        except Exception as e:
            print(f"Error extracting data from course {row_number}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def extract_detail_page_data(self):
        """Extract detailed lecture information from the detail page using the provided CSS selectors"""
        try:
            print("Extracting data from detail page...")
            
            # Title
            try:
                title_selector = "#detail_con > div.board_view > div"
                title_element = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, title_selector)))
                title = title_element.text.strip()
                if title:
                    self.lecture_data["Title"] = title
                    print(f"Title: {title}")
            except Exception as e:
                print(f"Failed to extract title: {e}")
            
            # Institution
            try:
                institution_selector = "#detail_con > div.board_view > ul:nth-child(5) > li:nth-child(1) > dl > dd"
                institution_element = self.driver.find_element(By.CSS_SELECTOR, institution_selector)
                institution = institution_element.text.strip()
                if institution:
                    self.lecture_data["Institution"] = institution
                    print(f"Institution: {institution}")
            except Exception as e:
                print(f"Failed to extract institution: {e}")
            
            # Address
            try:
                address_selector = "#detail_con > div.board_view > ul:nth-child(5) > li:nth-child(2) > dl > dd"
                address_element = self.driver.find_element(By.CSS_SELECTOR, address_selector)
                address = address_element.text.strip()
                if address:
                    self.lecture_data["Address"] = address
                    print(f"Address: {address}")
            except Exception as e:
                print(f"Failed to extract address: {e}")
            
            # Tel
            try:
                tel_selector = "#detail_con > div.board_view > ul:nth-child(5) > li:nth-child(3) > dl > dd"
                tel_element = self.driver.find_element(By.CSS_SELECTOR, tel_selector)
                tel = tel_element.text.strip()
                if tel:
                    self.lecture_data["Tel"] = tel
                    print(f"Tel: {tel}")
            except Exception as e:
                print(f"Failed to extract tel: {e}")
            
            # Recruitment period
            try:
                recruitment_selector = "#detail_con > div.board_view > ul:nth-child(3) > li:nth-child(4) > dl > dd"
                recruitment_element = self.driver.find_element(By.CSS_SELECTOR, recruitment_selector)
                recruitment = recruitment_element.text.strip()
                if recruitment:
                    self.lecture_data["Recruitment_period"] = recruitment
                    print(f"Recruitment period: {recruitment}")
            except Exception as e:
                print(f"Failed to extract recruitment period: {e}")
            
            # Education period
            try:
                education_selector = "#detail_con > div.board_view > ul:nth-child(3) > li:nth-child(5) > dl > dd"
                education_element = self.driver.find_element(By.CSS_SELECTOR, education_selector)
                education = education_element.text.strip()
                if education:
                    self.lecture_data["Education_period"] = education
                    print(f"Education period: {education}")
            except Exception as e:
                print(f"Failed to extract education period: {e}")
            
            # Quota
            try:
                quota_selector = "#detail_con > div.board_view > ul:nth-child(3) > li:nth-child(2) > dl > dd"
                quota_element = self.driver.find_element(By.CSS_SELECTOR, quota_selector)
                quota = quota_element.text.strip()
                if quota:
                    self.lecture_data["Quota"] = quota
                    print(f"Quota: {quota}")
            except Exception as e:
                print(f"Failed to extract quota: {e}")
            
            # Fee
            try:
                fee_selector = "#detail_con > div.board_view > ul:nth-child(3) > li:nth-child(1) > dl > dd"
                fee_element = self.driver.find_element(By.CSS_SELECTOR, fee_selector)
                fee = fee_element.text.strip()
                if fee:
                    self.lecture_data["Fee"] = fee
                    print(f"Fee: {fee}")
            except Exception as e:
                print(f"Failed to extract fee: {e}")
            
            # 데이터 추출 상태 확인
            not_found_fields = [key for key, value in self.lecture_data.items() if value == "Not found"]
            if not_found_fields:
                print(f"Fields still not found: {', '.join(not_found_fields)}")
            else:
                print("All fields were successfully extracted!")
            
            return True
            
        except Exception as e:
            print(f"Error extracting data from detail page: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def go_to_next_page(self):
        """Navigate to the next page of results"""
        try:
            print("\nAttempting to navigate to next page...")
            
            # 현재 페이지 저장
            current_page_url = self.driver.current_url
            current_page_source = self.driver.page_source
            
            # 페이지네이션 영역 확인
            pagination_area = self.driver.find_elements(By.CSS_SELECTOR, "#detail_con > div.paging.dp_pc")
            
            if not pagination_area:
                print("No pagination area found. This might be the last page.")
                return False
            
            # 다음 페이지 버튼 찾기
            for i in range(2, 11):  # a:nth-child(2)부터 a:nth-child(10)까지 시도
                next_page_selector = f"#detail_con > div.paging.dp_pc > a:nth-child({i})"
                next_page_links = self.driver.find_elements(By.CSS_SELECTOR, next_page_selector)
                
                if not next_page_links or len(next_page_links) == 0:
                    continue
                
                next_page_link = next_page_links[0]
                next_page_text = next_page_link.text.strip()
                next_page_class = next_page_link.get_attribute("class")
                
                print(f"Found pagination link {i}: text='{next_page_text}', class='{next_page_class}'")
                
                # 현재 페이지가 아닌 링크만 클릭 (current 클래스가 없는 것)
                if "current" not in next_page_class:
                    # 클릭 시도
                    try:
                        print(f"Clicking on page link: '{next_page_text}'")
                        # 스크롤 후 클릭
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", next_page_link)
                        time.sleep(1)
                        self.driver.execute_script("arguments[0].click();", next_page_link)
                        time.sleep(3)
                        
                        # 페이지가 변경되었는지 확인
                        new_url = self.driver.current_url
                        new_source = self.driver.page_source
                        
                        if new_url != current_page_url or new_source != current_page_source:
                            print(f"Successfully navigated to page {next_page_text}")
                            return True
                        else:
                            print("Page didn't change after click, trying native click...")
                            
                            # 네이티브 클릭 시도
                            next_page_link.click()
                            time.sleep(3)
                            
                            if self.driver.current_url != current_page_url or self.driver.page_source != current_page_source:
                                print(f"Successfully navigated to page {next_page_text} with native click")
                                return True
                            else:
                                print("Native click also failed")
                    except Exception as e:
                        print(f"Error clicking page link: {e}")
            
            print("No valid next page link found or all navigation attempts failed")
            return False
            
        except Exception as e:
            print(f"Error trying to navigate to next page: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def save_to_csv(self, filename="yeonsu_education.csv"):
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
                
                # Remove duplicates (consider Category as well)
                df_combined = df_combined.drop_duplicates(subset=['Title', 'Education_period', 'Institution', 'Category'], keep='last')
                
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
                print(f"Loaded checkpoint: URL Index {self.checkpoint['current_url_index']}, Page {self.checkpoint['current_page']}, Row {self.checkpoint['last_processed_row']}")
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
                
            print(f"Checkpoint saved for URL Index {self.checkpoint['current_url_index']}, Page {self.checkpoint['current_page']}, Row {self.checkpoint['last_processed_row']}")
        except Exception as e:
            print(f"Error saving checkpoint: {e}")
    
    def navigate_to_checkpoint(self, url_index):
        """Navigate to the page specified in the checkpoint"""
        # First navigate to the current URL
        base_url = self.urls[url_index]
        self.navigate_to_url(base_url)
        time.sleep(3)
        
        # If we need to go to a page other than the first page
        target_page = self.checkpoint["current_page"]
        if target_page > 1:
            print(f"Navigating to checkpoint page {target_page}...")
            
            # Click through pages until we reach our target
            current_page = 1
            while current_page < target_page:
                if not self.go_to_next_page():
                    print(f"Failed to navigate to page {current_page + 1}")
                    return False
                current_page += 1
                time.sleep(2)
        
        return True
    
    def process_url(self, url_index, max_pages=100):
        """Process a single URL from the list"""
        url = self.urls[url_index]
        category = self.url_names[url_index]
        print(f"\n=== Processing URL: {url} (Category: {category}) ===\n")
        
        # Set the category for all lectures from this URL
        self.lecture_data["Category"] = category
        
        # Navigate to the URL
        self.navigate_to_url(url)
        time.sleep(3)
        
        # Start from page 1 or checkpoint
        current_page = self.checkpoint["current_page"] if self.checkpoint["current_page"] > 0 else 1
        last_processed_row = self.checkpoint["last_processed_row"]
        total_processed_lectures = 0
        consecutive_empty_pages = 0
        
        while current_page <= max_pages:
            print(f"\n--- Scraping page {current_page} of {category} ---")
            
            # Update checkpoint with current page
            self.checkpoint["current_page"] = current_page
            self.save_checkpoint()
            
            # Find all courses that are accepting applications
            available_rows = self.find_courses_accepting_applications()
            
            if not available_rows:
                print(f"No courses accepting applications found on page {current_page}")
                consecutive_empty_pages += 1
                
                # 연속 3개 페이지에서 데이터를 찾지 못하면 다음 URL로 이동
                if consecutive_empty_pages >= 3:
                    print("Found 3 consecutive empty pages. Moving to next URL.")
                    return total_processed_lectures
                
                # Try moving to next page
                print("Moving to next page since no eligible courses were found")
                success = self.go_to_next_page()
                if not success:
                    print("No more pages available. Moving to next URL.")
                    return total_processed_lectures
                
                current_page += 1
                self.checkpoint["current_page"] = current_page
                self.checkpoint["last_processed_row"] = 0
                self.save_checkpoint()
                continue
            else:
                # 데이터가 있는 페이지를 찾았으므로 연속 빈 페이지 카운터 초기화
                consecutive_empty_pages = 0
            
            # 첫 페이지 시작 시에는 모든 행을 처리, 아니면 체크포인트 이후의 행만 처리
            if current_page == 1 and last_processed_row == 0:
                rows_to_process = available_rows
            else:
                rows_to_process = [row for row in available_rows if row > last_processed_row]
            
            if not rows_to_process:
                print(f"All available courses on page {current_page} have been processed")
                
                # Try moving to next page
                print("Moving to next page since all courses were processed")
                success = self.go_to_next_page()
                if not success:
                    print("No more pages available. Moving to next URL.")
                    return total_processed_lectures
                
                current_page += 1
                self.checkpoint["current_page"] = current_page
                self.checkpoint["last_processed_row"] = 0
                self.save_checkpoint()
                last_processed_row = 0
                continue
            
            print(f"Processing {len(rows_to_process)} courses on page {current_page}")
            
            # Process each eligible course
            for row_num in rows_to_process:
                print(f"\nProcessing course {row_num} on page {current_page} of {category}")
                
                try:
                    # Extract data from this course
                    success = self.extract_lecture_data(row_num)
                    
                    if success:
                        # Add the lecture data to our collection
                        self.lectures.append(self.lecture_data.copy())
                        print(f"Added course '{self.lecture_data['Title']}' to collection")
                        total_processed_lectures += 1
                        
                        # Save after each successful extraction
                        self.save_to_csv("yeonsu_education.csv")
                    else:
                        print(f"Failed to extract lecture data from course {row_num}")
                    
                    # Update checkpoint
                    self.checkpoint["last_processed_row"] = row_num
                    self.save_checkpoint()
                    last_processed_row = row_num
                    
                except Exception as e:
                    print(f"Error processing course {row_num}: {e}")
                    self.checkpoint["last_processed_row"] = row_num
                    self.save_checkpoint()
                    last_processed_row = row_num
                
                # Delay between processing courses
                time.sleep(2)
            
            # Move to next page after processing all courses on current page
            print(f"Finished processing courses on page {current_page}. Moving to next page...")
            success = self.go_to_next_page()
            
            if not success:
                print("No more pages available. Moving to next URL.")
                return total_processed_lectures
            
            current_page += 1
            self.checkpoint["current_page"] = current_page
            self.checkpoint["last_processed_row"] = 0
            self.save_checkpoint()
            last_processed_row = 0
        
        print(f"Finished processing URL {url} (Category: {category}). Total lectures processed: {total_processed_lectures}")
        return total_processed_lectures
    
    def run(self, max_pages=100):
        """Run the scraping process for all URLs"""
        # Load checkpoint if it exists
        checkpoint_exists = self.load_checkpoint()
        total_processed_lectures = 0
        
        try:
            # 시작할 URL 인덱스 결정
            start_url_index = self.checkpoint["current_url_index"] if checkpoint_exists else 0
            
            # 각 URL 처리
            for url_index in range(start_url_index, len(self.urls)):
                print(f"\n\n==========================================")
                print(f"PROCESSING URL {url_index + 1} OF {len(self.urls)}")
                print(f"==========================================\n\n")
                
                # 현재 URL 인덱스 업데이트
                self.checkpoint["current_url_index"] = url_index
                self.checkpoint["current_page"] = 1  # 새 URL은 페이지 1부터 시작
                self.checkpoint["last_processed_row"] = 0  # 새 URL은 행 0부터 시작
                self.save_checkpoint()
                
                # 해당 URL 처리
                url_lectures = self.process_url(url_index, max_pages)
                total_processed_lectures += url_lectures
                
                print(f"\nCompleted URL {url_index + 1} of {len(self.urls)}: {self.urls[url_index]}")
                print(f"Lectures collected from this URL: {url_lectures}")
                print(f"Total lectures collected so far: {total_processed_lectures}")
                
                # URL 처리 완료 후, 체크포인트 정보 업데이트 (다음 URL 준비)
                if url_index < len(self.urls) - 1:  # 마지막 URL이 아니면
                    self.checkpoint["current_url_index"] = url_index + 1
                    self.checkpoint["current_page"] = 1
                    self.checkpoint["last_processed_row"] = 0
                    self.save_checkpoint()
                
                # 잠시 쉬기 (다음 URL로 이동하기 전)
                print(f"Waiting 5 seconds before moving to next URL...")
                time.sleep(5)
            
            print(f"\n\n==========================================")
            print(f"CRAWLING COMPLETED SUCCESSFULLY!")
            print(f"Total lectures processed across all URLs: {total_processed_lectures}")
            print(f"==========================================\n\n")
            
        except KeyboardInterrupt:
            print("\nCrawling interrupted by user. Saving progress...")
            if self.lectures:
                self.save_to_csv("yeonsu_education.csv")
            self.save_checkpoint()
            print(f"Progress saved. You can resume later from this point. Total lectures processed: {total_processed_lectures}")
            
        except Exception as e:
            print(f"Error during scraping process: {e}")
            import traceback
            traceback.print_exc()
            
            # Save whatever data we've collected so far
            if self.lectures:
                self.save_to_csv("yeonsu_education.csv")
            # Make sure the checkpoint is saved
            self.save_checkpoint()
            print(f"Saved checkpoint. You can resume from this point later. Total lectures processed: {total_processed_lectures}")
            
        finally:
            print("Crawling process complete. Closing browser...")
            self.close()


# Run the crawler
if __name__ == "__main__":
    try:
        # Create and run the crawler - set headless=False to see the browser in action
        crawler = YeonsuEducationCrawler(headless=False)
        crawler.run(max_pages=100)
    except Exception as e:
        print(f"Fatal error in crawler execution: {e}")
        import traceback
        traceback.print_exc()