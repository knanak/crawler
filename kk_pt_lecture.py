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

class PyeongtaekEducationCrawler:
    def __init__(self, headless=True, checkpoint_file="pyeongtaek_education_checkpoint.json"):
        try:
            # Configure Chrome options with enhanced stability settings
            self.chrome_options = Options()
            if headless:
                self.chrome_options.add_argument('--headless=new')  # 새로운 헤드리스 모드 사용
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
            
            # Structure for lecture data
            self.lecture_data = {
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
                "Registration": ""
            }
            
            # Storage for collected lectures
            self.lectures = []
            
            # Checkpoint configuration
            self.checkpoint_file = checkpoint_file
            self.checkpoint = {
                "current_page": 1,
                "last_processed_row": 0,
                "last_url": "",
                "last_child_index": 1,  # 마지막으로 클릭한 a:nth-child 인덱스 저장
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
        self.lecture_data = {
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
            "Registration": "Not found"
        }
    
    def find_rows_with_application_status(self):
        """Find rows with '신청중' status and return their row numbers"""
        available_rows = []
        
        try:
            # Wait for table to be present
            try:
                self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#listForm > div.tbl-respon > div > table > tbody"))
                )
            except TimeoutException:
                print("Table not found within timeout period. Checking if we're still on the correct page...")
                # 페이지 소스를 확인하여 올바른 페이지인지 검증
                if "listForm" not in self.driver.page_source:
                    print("WARNING: We might not be on the correct page. listForm not found in page source.")
                    return []
            
            # Find all rows in the table
            rows = self.driver.find_elements(By.CSS_SELECTOR, "#listForm > div.tbl-respon > div > table > tbody > tr")
            print(f"Total rows found: {len(rows)}")
            
            if len(rows) == 0:
                print("No rows found in table. Checking alternative selectors...")
                # 대체 셀렉터 시도
                alt_selectors = [
                    "table.board_list tbody tr",
                    ".tbl-respon table tbody tr",
                    "//table//tbody/tr"
                ]
                
                for selector in alt_selectors:
                    try:
                        if selector.startswith("//"):
                            alt_rows = self.driver.find_elements(By.XPATH, selector)
                        else:
                            alt_rows = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        
                        if alt_rows and len(alt_rows) > 0:
                            rows = alt_rows
                            print(f"Found {len(rows)} rows using alternative selector: {selector}")
                            break
                    except:
                        continue
            
            # 여전히 행을 찾지 못했으면 빈 목록 반환
            if len(rows) == 0:
                print("Still no rows found. Returning empty list.")
                return []
            
            # Check each row for status
            for i in range(1, len(rows) + 1):
                try:
                    # 다양한 셀렉터로 상태 확인
                    status_selectors = [
                        f"#listForm > div.tbl-respon > div > table > tbody > tr:nth-child({i}) > td.taL.wb_ba > span",
                        f"#listForm > div.tbl-respon > div > table > tbody > tr:nth-child({i}) span.state",
                        f"//table/tbody/tr[{i}]//span[contains(@class, 'state')]",
                        f"//table/tbody/tr[{i}]//span"
                    ]
                    
                    for selector in status_selectors:
                        try:
                            # 셀렉터 유형에 따라 달리 적용
                            if selector.startswith("//"):
                                status_elements = self.driver.find_elements(By.XPATH, selector)
                            else:
                                status_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            
                            if status_elements and len(status_elements) > 0:
                                status = status_elements[0].text.strip()
                                print(f"Row {i} status: '{status}' (using '{selector}')")
                                
                                # '신청중' 뿐만 아니라 '접수중', '모집중' 등의 유사 상태도 확인
                                if status in ['신청중', '접수중', '모집중']:
                                    available_rows.append(i)
                                    break
                        except Exception:
                            continue
                        
                except Exception as e:
                    print(f"Error checking status for row {i}: {e}")
            
            print(f"Found {len(available_rows)} rows with '신청중' status: {available_rows}")
            return available_rows
            
        except Exception as e:
            print(f"Error finding available rows: {e}")
            return []
    
    def extract_lecture_data(self, row_number):
        """Extract lecture data from the table row and detail page"""
        print(f"\n>>> Extracting data from row {row_number}")
        
        try:
            # First, verify if the row has '신청중' status
            status_selectors = [
                f"#listForm > div.tbl-respon > div > table > tbody > tr:nth-child({row_number}) > td.taL.wb_ba > span",
                f"#listForm > div.tbl-respon > div > table > tbody > tr:nth-child({row_number}) span.state",
                f"//table/tbody/tr[{row_number}]//span[contains(@class, 'state')]",
                f"//table/tbody/tr[{row_number}]//span"
            ]
            
            status_found = False
            for selector in status_selectors:
                try:
                    # 셀렉터 유형에 따라 달리 적용
                    if selector.startswith("//"):
                        status_elements = self.driver.find_elements(By.XPATH, selector)
                    else:
                        status_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if status_elements and len(status_elements) > 0:
                        status = status_elements[0].text.strip()
                        print(f"Status found: '{status}' (using selector '{selector}')")
                        
                        # '신청중' 뿐만 아니라 '접수중', '모집중' 등의 유사 상태도 허용
                        if status in ['신청중', '접수중', '모집중']:
                            self.lecture_data["State"] = status
                            status_found = True
                            break
                        else:
                            print(f"Row {row_number} is not accepting applications (Status: {status}). Skipping.")
                            return False
                            
                except Exception:
                    continue
            
            if not status_found:
                print(f"Status element not found for row {row_number}. Will try to extract data anyway.")
                self.lecture_data["State"] = "Unknown"
            
            # Reset lecture data for this row (keeping the state)
            current_state = self.lecture_data["State"]
            self.reset_lecture_data()
            self.lecture_data["State"] = current_state
            
            # Click on the row title to navigate to detail page
            try:
                # Save the current list page URL
                list_page_url = self.driver.current_url
                
                # 먼저 디테일 페이지 URL을 직접 찾아서 가져오기
                link_selector = f"#listForm > div.tbl-respon > div > table > tbody > tr:nth-child({row_number}) > td.taL.wb_ba > a"
                try:
                    # 앵커 태그가 있는지 확인
                    link_element = self.driver.find_element(By.CSS_SELECTOR, link_selector)
                    detail_url = link_element.get_attribute('href')
                    print(f"Found detail page URL: {detail_url}")
                    
                    # Get the title element
                    title_element = link_element
                except NoSuchElementException:
                    # 앵커 태그가 없으면 td 자체를 선택
                    print("No anchor tag found, trying to find title element directly")
                    title_selector = f"#listForm > div.tbl-respon > div > table > tbody > tr:nth-child({row_number}) > td.taL.wb_ba"
                    title_element = self.driver.find_element(By.CSS_SELECTOR, title_selector)
                
                # Click to go to detail page
                print(f"Clicking on title for row {row_number} to access detail page...")
                self.driver.execute_script("arguments[0].scrollIntoView(true);", title_element)
                time.sleep(1)
                self.driver.execute_script("arguments[0].click();", title_element)
                
                # Wait for detail page to load
                time.sleep(3)
                
                # 디테일 페이지로 제대로 이동했는지 확인
                current_url = self.driver.current_url
                print(f"Current URL after click: {current_url}")
                
                # URL이 리스트 페이지와 같다면 직접 이동 시도
                if current_url == list_page_url:
                    print("Navigation failed. Trying to navigate directly to detail page...")
                    if 'detail_url' in locals() and detail_url:
                        self.driver.get(detail_url)
                        time.sleep(3)
                        print(f"Directly navigated to: {self.driver.current_url}")
                
                # Extract data from detail page
                detail_success = self.extract_detail_page_data()
                if not detail_success:
                    print(f"Failed to extract data from detail page for row {row_number}")
                
                # Go back to the listing page
                print("Going back to listing page...")
                self.driver.back()
                time.sleep(3)
                
                # Check if we're back on the listing page
                if list_page_url not in self.driver.current_url:
                    print(f"Navigation back failed. Directly navigating to list page: {list_page_url}")
                    self.driver.get(list_page_url)
                    time.sleep(3)
                
                # Verify we have enough data
                not_found_count = sum(1 for value in self.lecture_data.values() if value == "Not found")
                if not_found_count > 5:  # If more than 5 fields are "Not found"
                    print(f"Too many missing values ({not_found_count}) for row {row_number}, skipping")
                    return False
                
                print(f"Successfully extracted data for row {row_number}")
                return True
                
            except Exception as e:
                print(f"Error accessing or extracting from detail page: {e}")
                # Try to navigate back to the listing page
                try:
                    self.driver.get(list_page_url if 'list_page_url' in locals() else self.checkpoint["last_url"])
                    time.sleep(3)
                except:
                    print("Failed to return to listing page after error")
                return False
                
        except Exception as e:
            print(f"Error extracting data from row {row_number}: {e}")
            return False
    
    def extract_detail_page_data(self):
        """Extract detailed lecture information from the detail page"""
        try:
            print("Extracting data from detail page...")
            # Save the detail URL
            current_url = self.driver.current_url
            self.lecture_data["Detail"] = current_url
            print(f"Detail page URL: {current_url}")
            
            # 현재 URL이 리스트 페이지인지 확인
            if 'list.do' in current_url and 'detail.do' not in current_url:
                print("WARNING: Still on list page, not detail page! Detail extraction may fail.")
            
            # Title - 더 다양한 셀렉터 시도
            title_selectors = [
                "#detailForm > table > tbody > tr:nth-child(1) > td",
                "//table//tr[1]/td",
                "//h4[@class='view_tit']",
                "//div[contains(@class,'view')]//h4",
                "//table[contains(@class,'board_view')]//th[contains(text(),'제목')]/following-sibling::td"
            ]
            
            title_found = False
            for selector in title_selectors:
                try:
                    if selector.startswith("//"):
                        title_element = self.driver.find_element(By.XPATH, selector)
                    else:
                        title_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    title = title_element.text.strip()
                    if title:
                        self.lecture_data["Title"] = title
                        print(f"Title found using selector '{selector}': {title}")
                        title_found = True
                        break
                except Exception as e:
                    print(f"Selector '{selector}' failed: {str(e)[:100]}...")
            if not title_found:
                print("Failed to find title using all selectors")
            
            # Page Structure 파악을 위한 디버깅
            try:
                # 현재 페이지의 HTML 구조 확인
                page_source = self.driver.page_source
                print(f"Page source length: {len(page_source)} characters")
                if len(page_source) < 1000:
                    print("WARNING: Page source is very short, might not be the correct page!")
                    print(f"Page source excerpt: {page_source[:500]}...")
                
                # 페이지 내 테이블 개수 확인
                tables = self.driver.find_elements(By.TAG_NAME, "table")
                print(f"Found {len(tables)} tables on the page")
                
                # 첫 번째 테이블의 행 수 확인
                if tables and len(tables) > 0:
                    rows = tables[0].find_elements(By.TAG_NAME, "tr")
                    print(f"First table has {len(rows)} rows")
            except Exception as e:
                print(f"Error during page structure analysis: {e}")
            
            # Institution - 다양한 셀렉터 시도
            institution_selectors = [
                "#detailForm > table > tbody > tr:nth-child(5) > td:nth-child(2)",
                "//table//tr[5]/td[1]",
                "//table//th[contains(text(),'기관명')]/following-sibling::td",
                "//table//th[contains(text(),'기관')]/following-sibling::td"
            ]
            
            for selector in institution_selectors:
                try:
                    if selector.startswith("//"):
                        institution_element = self.driver.find_element(By.XPATH, selector)
                    else:
                        institution_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    institution = institution_element.text.strip()
                    if institution:
                        self.lecture_data["Institution"] = institution
                        print(f"Institution found: {institution}")
                        break
                except Exception as e:
                    continue
                
            # Address - 다양한 셀렉터 시도
            address_selectors = [
                "#content > div > div:nth-child(17) > dl > dd > p",
            ]
            
            for selector in address_selectors:
                try:
                    if selector.startswith("//"):
                        address_element = self.driver.find_element(By.XPATH, selector)
                    else:
                        address_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    address = address_element.text.strip()
                    if address:
                        self.lecture_data["Address"] = address
                        print(f"Address found: {address}")
                        break
                except Exception as e:
                    continue
                
            # Tel - 다양한 셀렉터 시도
            tel_selectors = [
                "#detailForm > table > tbody > tr:nth-child(7) > td:nth-child(2)",
                "//table//tr[7]/td[1]",
                "//table//th[contains(text(),'연락처')]/following-sibling::td",
                "//table//th[contains(text(),'전화')]/following-sibling::td"
            ]
            
            for selector in tel_selectors:
                try:
                    if selector.startswith("//"):
                        tel_element = self.driver.find_element(By.XPATH, selector)
                    else:
                        tel_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    tel = tel_element.text.strip()
                    if tel:
                        self.lecture_data["Tel"] = tel
                        print(f"Tel found: {tel}")
                        break
                except Exception as e:
                    continue
                
            # Recruitment period - 다양한 셀렉터 시도
            recruitment_selectors = [
                "#detailForm > table > tbody > tr:nth-child(2) > td:nth-child(4)",
                "//table//tr[2]/td[2]",
                "//table//th[contains(text(),'접수기간')]/following-sibling::td",
                "//table//th[contains(text(),'모집기간')]/following-sibling::td"
            ]
            
            for selector in recruitment_selectors:
                try:
                    if selector.startswith("//"):
                        recruitment_element = self.driver.find_element(By.XPATH, selector)
                    else:
                        recruitment_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    recruitment = recruitment_element.text.strip()
                    if recruitment:
                        self.lecture_data["Recruitment_period"] = recruitment
                        print(f"Recruitment period found: {recruitment}")
                        break
                except Exception as e:
                    continue
                
            # Education period - 다양한 셀렉터 시도
            education_selectors = [
                "#content > div > div:nth-child(6) > dl:nth-child(1) > dd > strong"
            ]
            
            for selector in education_selectors:
                try:
                    if selector.startswith("//"):
                        education_element = self.driver.find_element(By.XPATH, selector)
                    else:
                        education_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    education = education_element.text.strip()
                    if education:
                        self.lecture_data["Education_period"] = education
                        print(f"Education period found: {education}")
                        break
                except Exception as e:
                    continue
                
            # Date - 다양한 셀렉터 시도
            date_selectors = [
                "#detailForm > table > tbody > tr:nth-child(3) > td:nth-child(2)",
                "//table//tr[3]/td[1]",
                "//table//th[contains(text(),'요일/시간')]/following-sibling::td",
                "//table//th[contains(text(),'교육시간')]/following-sibling::td"
            ]
            
            for selector in date_selectors:
                try:
                    if selector.startswith("//"):
                        date_element = self.driver.find_element(By.XPATH, selector)
                    else:
                        date_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    date = date_element.text.strip()
                    if date:
                        self.lecture_data["Date"] = date
                        print(f"Date found: {date}")
                        break
                except Exception as e:
                    continue
                
            # Quota - 다양한 셀렉터 시도
            try:
                quota_text = ""
                
                # 정원 정보
                capacity_selectors = [
                    "#detailForm > table > tbody > tr:nth-child(4) > td:nth-child(2)",
                    "//table//tr[4]/td[1]",
                    "//table//th[contains(text(),'정원')]/following-sibling::td"
                ]
                
                capacity = ""
                for selector in capacity_selectors:
                    try:
                        if selector.startswith("//"):
                            capacity_element = self.driver.find_element(By.XPATH, selector)
                        else:
                            capacity_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        
                        capacity = capacity_element.text.strip()
                        if capacity:
                            quota_text += f"정원: {capacity}"
                            break
                    except Exception:
                        continue
                
                # 신청 정보
                applied_selectors = [
                    "#detailForm > table > tbody > tr:nth-child(4) > td:nth-child(4)",
                    "//table//tr[4]/td[2]",
                    "//table//th[contains(text(),'신청')]/following-sibling::td"
                ]
                
                applied = ""
                for selector in applied_selectors:
                    try:
                        if selector.startswith("//"):
                            applied_element = self.driver.find_element(By.XPATH, selector)
                        else:
                            applied_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        
                        applied = applied_element.text.strip()
                        if applied:
                            if quota_text:
                                quota_text += f" / 신청: {applied}"
                            else:
                                quota_text = f"신청: {applied}"
                            break
                    except Exception:
                        continue
                
                if quota_text:
                    self.lecture_data["Quota"] = quota_text
                    print(f"Quota found: {quota_text}")
                    
            except Exception as e:
                print(f"Failed to extract quota: {e}")
                
            # Fee - 다양한 셀렉터 시도
            fee_selectors = [
                "#detailForm > table > tbody > tr:nth-child(6) > td:nth-child(2)",
                "//table//tr[6]/td[1]",
                "//table//th[contains(text(),'수강료')]/following-sibling::td",
                "//table//th[contains(text(),'비용')]/following-sibling::td"
            ]
            
            for selector in fee_selectors:
                try:
                    if selector.startswith("//"):
                        fee_element = self.driver.find_element(By.XPATH, selector)
                    else:
                        fee_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    fee = fee_element.text.strip()
                    if fee:
                        self.lecture_data["Fee"] = fee
                        print(f"Fee found: {fee}")
                        break
                except Exception:
                    continue
                
            # Registration - 다양한 셀렉터 시도
            registration_selectors = [
                "#detailForm > table > tbody > tr:nth-child(6) > td:nth-child(4)",
                "//table//tr[6]/td[2]",
                "//table//th[contains(text(),'접수방법')]/following-sibling::td",
                "//table//th[contains(text(),'신청방법')]/following-sibling::td"
            ]
            
            for selector in registration_selectors:
                try:
                    if selector.startswith("//"):
                        registration_element = self.driver.find_element(By.XPATH, selector)
                    else:
                        registration_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    registration = registration_element.text.strip()
                    if registration:
                        self.lecture_data["Registration"] = registration
                        print(f"Registration found: {registration}")
                        break
                except Exception:
                    continue
                
            # 데이터 추출 상태 확인
            not_found_fields = [key for key, value in self.lecture_data.items() if value == "Not found"]
            if not_found_fields:
                print(f"Fields still not found: {', '.join(not_found_fields)}")
            else:
                print("All fields were successfully extracted!")
                
            print("Successfully extracted data from detail page")
            return True
            
        except Exception as e:
            print(f"Error extracting data from detail page: {e}")
            return False
    
    def go_to_next_page(self):
        """Navigate to the next page of results"""
        try:
            print("\nAttempting to navigate to next page...")
            
            # 현재 페이지 저장
            current_page_url = self.driver.current_url
            current_page_source = self.driver.page_source
            
            # 현재 페이지 번호 확인 시도
            current_page_num = None
            try:
                # 현재 활성화된 페이지 버튼 찾기
                active_page_elements = self.driver.find_elements(By.CSS_SELECTOR, "#listForm > div.box_page > strong")
                if active_page_elements and len(active_page_elements) > 0:
                    current_page_num = active_page_elements[0].text.strip()
                    print(f"Current page number detected: {current_page_num}")
            except Exception as e:
                print(f"Could not determine current page number: {e}")
            
            # 마지막으로 클릭한 nth-child 인덱스 가져오기 (없으면 1로 초기화)
            last_child_index = self.checkpoint.get("last_child_index", 1)
            print(f"Last clicked child index: {last_child_index}")
            
            # 클릭할 다음 인덱스 계산 (항상 증가)
            next_child_index = last_child_index + 1
            if next_child_index > 10:  # 최대 인덱스를 넘어서면 2로 리셋
                next_child_index = 2
            print(f"Will try to click child index: {next_child_index}")
            
            # 모든 페이지 링크를 출력하여 디버깅
            all_page_links = []
            try:
                all_links = self.driver.find_elements(By.CSS_SELECTOR, "#listForm > div.box_page > a")
                print(f"All page links found: {len(all_links)}")
                for i, link in enumerate(all_links):
                    link_text = link.text.strip()
                    link_class = link.get_attribute('class')
                    link_href = link.get_attribute('href')
                    print(f"Link {i+1}: text='{link_text}', class='{link_class}', href='{link_href}'")
                    all_page_links.append({
                        'text': link_text,
                        'class': link_class,
                        'href': link_href,
                        'element': link,
                        'index': i+1
                    })
            except Exception as e:
                print(f"Error getting page links: {e}")
            
            # 항상 a:nth-child(j)를 누르되, j가 증가하는 방향으로 진행
            next_page_link = None
            next_child_selector = f"#listForm > div.box_page > a:nth-child({next_child_index})"
            
            try:
                print(f"Trying to find element with selector: {next_child_selector}")
                next_element = self.driver.find_element(By.CSS_SELECTOR, next_child_selector)
                link_text = next_element.text.strip()
                
                # 이전 버튼 감지 (이전, prev, <, «, ‹ 등의 텍스트 확인)
                prev_indicators = ['이전', 'prev', '<', '«', '‹']
                is_prev_button = any(indicator in link_text.lower() for indicator in prev_indicators)
                
                if is_prev_button:
                    print(f"WARNING: Element with selector {next_child_selector} appears to be a previous button (text: '{link_text}')")
                    print("Trying next index to avoid clicking previous button")
                    next_child_index += 1
                    next_child_selector = f"#listForm > div.box_page > a:nth-child({next_child_index})"
                    try:
                        next_element = self.driver.find_element(By.CSS_SELECTOR, next_child_selector)
                        print(f"Found next element with selector {next_child_selector}: '{next_element.text}'")
                    except:
                        print(f"Could not find element with selector {next_child_selector}")
                        # 모든 숫자 링크 중 가장 작은 것 선택
                        number_links = []
                        for link in all_page_links:
                            try:
                                num = int(link['text'])
                                number_links.append((num, link['element']))
                            except:
                                continue
                        
                        if number_links:
                            number_links.sort(key=lambda x: x[0])
                            next_element = number_links[0][1]
                            print(f"Selected lowest numbered page: {number_links[0][0]}")
                        else:
                            print("No numbered pages found")
                
                if next_element:
                    next_page_link = next_element
                    # checkpoint에 다음 인덱스 저장
                    self.checkpoint["last_child_index"] = next_child_index
                    self.save_checkpoint()
                
            except Exception as e:
                print(f"Error finding a:nth-child({next_child_index}): {e}")
            
            # a:nth-child 방식으로 못 찾으면 다른 방법 시도
            if not next_page_link:
                print(f"Could not find element with selector {next_child_selector}. Trying alternative methods...")
                
                # 현재 페이지 번호 기반으로 다음 번호 찾기
                if current_page_num:
                    try:
                        current_num = int(current_page_num)
                        next_num = current_num + 1
                        print(f"Looking for page number {next_num}")
                        
                        # 모든 링크에서 해당 숫자 찾기
                        for link_info in all_page_links:
                            if link_info['text'] == str(next_num):
                                next_page_link = link_info['element']
                                print(f"Found link for page {next_num}")
                                break
                    except Exception as e:
                        print(f"Error finding next page by number: {e}")
                
                # 다음 버튼 찾기
                if not next_page_link:
                    print("Looking for 'next' button...")
                    for link_info in all_page_links:
                        if (link_info['text'] and '다음' in link_info['text']) or \
                           (link_info['class'] and 'next' in link_info['class']):
                            next_page_link = link_info['element']
                            print(f"Found 'next' button: {link_info['text']}")
                            break
            
            # 다음 페이지 링크를 찾았으면 클릭
            if next_page_link:
                # 링크의 텍스트와 href 저장
                try:
                    next_page_text = next_page_link.text.strip()
                    next_page_href = next_page_link.get_attribute('href')
                    print(f"Next page link found: text='{next_page_text}', href='{next_page_href}'")
                except:
                    next_page_text = "unknown"
                    next_page_href = None
                
                # 클릭 시도 (JavaScript 방식)
                try:
                    print(f"Clicking next page link: '{next_page_text}'")
                    # 스크롤 후 클릭
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", next_page_link)
                    time.sleep(1)
                    self.driver.execute_script("arguments[0].click();", next_page_link)
                    time.sleep(3)
                    
                    # 페이지가 변경되었는지 확인
                    new_url = self.driver.current_url
                    new_source = self.driver.page_source
                    
                    if new_url != current_page_url or new_source != current_page_source:
                        print("Successfully navigated to next page")
                        return True
                    else:
                        print("Page didn't change after JavaScript click, trying native click...")
                        # JavaScript 클릭이 실패하면 네이티브 클릭 시도
                        next_page_link.click()
                        time.sleep(3)
                        
                        # 다시 변경 확인
                        if self.driver.current_url != current_page_url or self.driver.page_source != current_page_source:
                            print("Successfully navigated to next page with native click")
                            return True
                        else:
                            print("Native click also failed, trying direct href navigation...")
                except Exception as e:
                    print(f"Error clicking next page link: {e}")
                
                # 클릭이 실패하면 href를 사용해 직접 이동
                if next_page_href:
                    try:
                        print(f"Navigating directly to: {next_page_href}")
                        self.driver.get(next_page_href)
                        time.sleep(3)
                        
                        # 페이지가 변경되었는지 확인
                        if self.driver.current_url != current_page_url or self.driver.page_source != current_page_source:
                            print("Successfully navigated to next page using href")
                            return True
                        else:
                            print("Page didn't change after direct navigation.")
                    except Exception as e:
                        print(f"Error navigating to href: {e}")
                
                print("All navigation attempts failed.")
            else:
                print("No next page link found.")
            
            return False
            
        except Exception as e:
            print(f"Error trying to navigate to next page: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def save_to_csv(self, filename="pyeongtaek_education.csv"):
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
    
    def navigate_to_checkpoint(self, base_url):
        """Navigate to the page specified in the checkpoint"""
        # First navigate to the first page
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
    
    def run(self, start_url, max_pages=100):
        """Run the scraping process for Pyeongtaek education programs"""
        # Load checkpoint if it exists
        checkpoint_exists = self.load_checkpoint()
        total_processed_lectures = 0
        
        try:
            # Navigate to the appropriate starting point
            if checkpoint_exists:
                navigation_success = self.navigate_to_checkpoint(start_url)
                if not navigation_success:
                    print("Failed to navigate to checkpoint. Starting from beginning.")
                    self.navigate_to_url(start_url)
                    start_page = 1
                    last_processed_row = 0
                else:
                    start_page = self.checkpoint["current_page"]
                    last_processed_row = self.checkpoint["last_processed_row"]
            else:
                self.navigate_to_url(start_url)
                start_page = 1
                last_processed_row = 0
            
            current_page = start_page
            consecutive_empty_pages = 0  # 연속으로 빈 페이지를 만난 횟수
            
            while current_page <= max_pages:
                print(f"\n--- Scraping page {current_page} ---")
                
                # Update checkpoint with current page
                self.checkpoint["current_page"] = current_page
                self.save_checkpoint()
                
                # 현재 페이지 URL과 제목 출력 (디버깅용)
                try:
                    print(f"Current URL: {self.driver.current_url}")
                    print(f"Page title: {self.driver.title}")
                except:
                    pass
                
                # Find all rows with '신청중' status
                available_rows = self.find_rows_with_application_status()
                
                if not available_rows:
                    print(f"No rows with '신청중' status found on page {current_page}")
                    consecutive_empty_pages += 1
                    
                    # 연속 3개 페이지에서 데이터를 찾지 못하면 종료
                    if consecutive_empty_pages >= 3:
                        print("Found 3 consecutive empty pages. Ending crawl.")
                        break
                    
                    # Try moving to next page
                    print("Moving to next page since no rows with '신청중' status were found")
                    success = self.go_to_next_page()
                    if not success:
                        print("No more pages available. Ending crawl.")
                        break
                    
                    current_page += 1
                    self.checkpoint["current_page"] = current_page
                    self.checkpoint["last_processed_row"] = 0
                    self.save_checkpoint()
                    continue
                else:
                    # 데이터가 있는 페이지를 찾았으므로 연속 빈 페이지 카운터 초기화
                    consecutive_empty_pages = 0
                
                # 첫 번째 페이지 시작 시에는 모든 행을 처리
                if current_page == start_page and start_page == 1 and last_processed_row == 0:
                    rows_to_process = available_rows
                else:
                    # 그 외의 경우 체크포인트 이후 행만 처리
                    rows_to_process = [row for row in available_rows if row > last_processed_row]
                
                if not rows_to_process:
                    print(f"All available rows on page {current_page} have been processed")
                    
                    # Try moving to next page
                    print("Moving to next page since all rows were processed")
                    success = self.go_to_next_page()
                    if not success:
                        print("No more pages available. Ending crawl.")
                        break
                    
                    current_page += 1
                    self.checkpoint["current_page"] = current_page
                    self.checkpoint["last_processed_row"] = 0
                    self.save_checkpoint()
                    last_processed_row = 0
                    continue
                
                print(f"Processing {len(rows_to_process)} rows with '신청중' status on page {current_page}")
                
                # Process each eligible row
                for row_num in rows_to_process:
                    print(f"\nProcessing row {row_num} on page {current_page}")
                    
                    try:
                        # Extract data from this row
                        success = self.extract_lecture_data(row_num)
                        
                        if success:
                            # Add the lecture data to our collection
                            self.lectures.append(self.lecture_data.copy())
                            print(f"Added lecture '{self.lecture_data['Title']}' to collection")
                            total_processed_lectures += 1
                            
                            # Save after each successful extraction
                            self.save_to_csv("pyeongtaek_education.csv")
                        else:
                            print(f"Failed to extract lecture data from row {row_num}")
                        
                        # Update checkpoint
                        self.checkpoint["last_processed_row"] = row_num
                        self.save_checkpoint()
                        last_processed_row = row_num
                        
                    except Exception as e:
                        print(f"Error processing row {row_num}: {e}")
                        self.checkpoint["last_processed_row"] = row_num
                        self.save_checkpoint()
                        last_processed_row = row_num
                    
                    # Delay between processing rows
                    time.sleep(2)
                
                # 페이지의 마지막 행까지 처리했으면 다음 페이지로 이동
                print(f"\nFinished processing all rows on page {current_page}. Moving to next page...")
                
                # 페이지 이동 전 현재 상태 저장
                before_url = self.driver.current_url
                before_source_length = len(self.driver.page_source)
                
                success = self.go_to_next_page()
                
                # 페이지 이동 후 상태 확인
                after_url = self.driver.current_url
                after_source_length = len(self.driver.page_source)
                
                print(f"Navigation result: URL changed = {before_url != after_url}, Source length before = {before_source_length}, after = {after_source_length}")
                
                if not success:
                    print("No more pages available or reached the last page. Ending crawl.")
                    break
                
                # 페이지 이동이 성공했는지 확인하는 추가 검증
                if before_url == after_url and abs(before_source_length - after_source_length) < 100:
                    print("WARNING: Page might not have changed! Attempting one more navigation...")
                    
                    # 한 번 더 명시적으로 다음 페이지 링크 찾기 시도
                    try:
                        # 직접 a:nth-child(2) 등의 링크 찾기
                        for i in range(2, 5):
                            try:
                                selector = f"#listForm > div.box_page > a:nth-child({i})"
                                link = self.driver.find_element(By.CSS_SELECTOR, selector)
                                print(f"Found link: {selector} with text '{link.text}'")
                                
                                # 스크롤 및 클릭
                                self.driver.execute_script("arguments[0].scrollIntoView(true);", link)
                                time.sleep(1)
                                link.click()
                                print(f"Clicked on a:nth-child({i})")
                                time.sleep(3)
                                
                                # 페이지가 변경되었는지 확인
                                if self.driver.current_url != before_url:
                                    print("Successfully navigated to next page with direct a:nth-child selector")
                                    break
                            except:
                                continue
                    except Exception as e:
                        print(f"Error in additional navigation attempt: {e}")
                
                # 페이지 번호 증가
                current_page += 1
                self.checkpoint["current_page"] = current_page
                self.checkpoint["last_processed_row"] = 0
                self.save_checkpoint()
                last_processed_row = 0
            
            print(f"Crawling completed successfully! Total lectures processed: {total_processed_lectures}")
            
        except KeyboardInterrupt:
            print("\nCrawling interrupted by user. Saving progress...")
            if self.lectures:
                self.save_to_csv("pyeongtaek_education.csv")
            self.save_checkpoint()
            print(f"Progress saved. You can resume later from this point. Total lectures processed: {total_processed_lectures}")
            
        except Exception as e:
            print(f"Error during scraping process: {e}")
            import traceback
            traceback.print_exc()  # 자세한 에러 정보 출력
            
            # Save whatever data we've collected so far
            if self.lectures:
                self.save_to_csv("pyeongtaek_education.csv")
            # Make sure the checkpoint is saved
            self.save_checkpoint()
            print(f"Saved checkpoint. You can resume from this point later. Total lectures processed: {total_processed_lectures}")
            
        finally:
            print("Crawling process complete. Closing browser...")
            self.close()

# Run the crawler
if __name__ == "__main__":
    # URL for Pyeongtaek education listings
    url = 'https://www.pyeongtaek.go.kr/learning/eduProgram/list.do?mId=0202010000'
    
    try:
        # Create and run the crawler - set headless=False to see the browser in action
        crawler = PyeongtaekEducationCrawler(headless=False)
        crawler.run(url, max_pages=100)
    except Exception as e:
        print(f"Fatal error in crawler execution: {e}")
        import traceback
        traceback.print_exc()