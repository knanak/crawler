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

class IncheonSeoguEducationCrawler:
    def __init__(self, headless=True, checkpoint_file="incheon_seogu_education_checkpoint.json"):
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
                "Detail": "",
                "Fee": ""
            }
            
            # Storage for collected lectures
            self.lectures = []
            
            # Checkpoint configuration
            self.checkpoint_file = checkpoint_file
            self.checkpoint = {
                "current_page": 1,
                "last_processed_row": 0,
                "last_url": "",
                "last_child_index": 4,  # 마지막으로 클릭한 a:nth-child 인덱스 저장 (기본값 4)
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
            "Detail": "Not found",
            "Fee": "Not found"
        }
    
    def find_rows_with_courses(self):
        """Find all courses on current page and return their row numbers"""
        available_rows = []
        
        try:
            # 페이지에 있는 모든 강좌 목록 찾기
            try:
                self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#detail_con > div.board_list > ul > li"))
                )
            except TimeoutException:
                print("Course list not found within timeout period. Checking if we're still on the correct page...")
                # 페이지 소스를 확인하여 올바른 페이지인지 검증
                if "board_list" not in self.driver.page_source:
                    print("WARNING: We might not be on the correct page. board_list not found in page source.")
                    return []
            
            # Find all course rows in the list
            course_rows = self.driver.find_elements(By.CSS_SELECTOR, "#detail_con > div.board_list > ul > li")
            print(f"Total courses found: {len(course_rows)}")
            
            if len(course_rows) == 0:
                print("No courses found. Checking alternative selectors...")
                # 대체 셀렉터 시도
                alt_selectors = [
                    ".board_list > ul > li",
                    "//div[contains(@class, 'board_list')]/ul/li"
                ]
                
                for selector in alt_selectors:
                    try:
                        if selector.startswith("//"):
                            alt_rows = self.driver.find_elements(By.XPATH, selector)
                        else:
                            alt_rows = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        
                        if alt_rows and len(alt_rows) > 0:
                            course_rows = alt_rows
                            print(f"Found {len(course_rows)} courses using alternative selector: {selector}")
                            break
                    except:
                        continue
            
            # 여전히 강좌를 찾지 못했으면 빈 목록 반환
            if len(course_rows) == 0:
                print("Still no courses found. Returning empty list.")
                return []
            
            # 모든 강좌의 행 번호 저장 (1부터 시작)
            for i in range(1, len(course_rows) + 1):
                # 수정된 CSS 셀렉터로 강좌 링크 확인
                try:
                    # 먼저 div > div 셀렉터로 확인
                    div_selector = f"#detail_con > div.board_list > ul > li:nth-child({i}) > a > div > div"
                    div_elements = self.driver.find_elements(By.CSS_SELECTOR, div_selector)
                    
                    if div_elements and len(div_elements) > 0:
                        available_rows.append(i)
                        continue
                        
                    # 없으면 기본 a 태그 확인
                    link_selector = f"#detail_con > div.board_list > ul > li:nth-child({i}) > a"
                    link_elements = self.driver.find_elements(By.CSS_SELECTOR, link_selector)
                    
                    if link_elements and len(link_elements) > 0:
                        available_rows.append(i)
                except Exception as e:
                    print(f"Error checking course {i}: {e}")
            
            print(f"Found {len(available_rows)} available courses: {available_rows}")
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
            # 수정된 셀렉터: div > div 추가
            course_selector = f"#detail_con > div.board_list > ul > li:nth-child({row_number}) > a > div > div"
            link_selector = f"#detail_con > div.board_list > ul > li:nth-child({row_number}) > a"
            
            try:
                # 먼저 클릭할 요소 찾기
                course_element = self.driver.find_element(By.CSS_SELECTOR, course_selector)
                
                # 링크 URL 저장을 위해 a 태그 요소 찾기
                link_element = self.driver.find_element(By.CSS_SELECTOR, link_selector)
                
                # 링크 URL 저장 (Detail)
                detail_url = link_element.get_attribute('href')
                self.lecture_data["Detail"] = detail_url
                print(f"Detail page URL: {detail_url}")
                
                # 클릭하여 상세 페이지로 이동
                print(f"Clicking on course {row_number} to access detail page...")
                self.driver.execute_script("arguments[0].scrollIntoView(true);", course_element)
                time.sleep(1)
                self.driver.execute_script("arguments[0].click();", course_element)
                
                # 상세 페이지 로딩 대기
                time.sleep(3)
                
                # 상세 페이지로 제대로 이동했는지 확인
                current_url = self.driver.current_url
                print(f"Current URL after click: {current_url}")
                
                # URL이 그대로라면 직접 이동 시도
                if current_url == list_page_url and detail_url != list_page_url:
                    print("Navigation failed. Trying to navigate directly to detail page...")
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
                # 기본 셀렉터로 다시 시도
                try:
                    fallback_selector = f"#detail_con > div.board_list > ul > li:nth-child({row_number}) > a"
                    fallback_element = self.driver.find_element(By.CSS_SELECTOR, fallback_selector)
                    
                    # 링크 URL 저장 (Detail)
                    detail_url = fallback_element.get_attribute('href')
                    self.lecture_data["Detail"] = detail_url
                    print(f"Detail page URL (fallback): {detail_url}")
                    
                    # 클릭하여 상세 페이지로 이동
                    print(f"Clicking on course {row_number} using fallback selector...")
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", fallback_element)
                    time.sleep(1)
                    self.driver.execute_script("arguments[0].click();", fallback_element)
                    
                    # 상세 페이지 로딩 대기
                    time.sleep(3)
                    
                    # 상세 페이지로 제대로 이동했는지 확인
                    current_url = self.driver.current_url
                    print(f"Current URL after fallback click: {current_url}")
                    
                    # URL이 그대로라면 직접 이동 시도
                    if current_url == list_page_url and detail_url != list_page_url:
                        print("Navigation failed. Trying to navigate directly to detail page...")
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
                    
                    print(f"Successfully extracted data for course {row_number} using fallback")
                    return True
                    
                except Exception as fallback_error:
                    print(f"Fallback also failed: {fallback_error}")
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
        """Extract detailed lecture information from the detail page"""
        try:
            print("Extracting data from detail page...")
            
            # Title
            try:
                title_selector = "#detail_con > div.board_view > div.title > p"
                title_element = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, title_selector)))
                title = title_element.text.strip()
                if title:
                    self.lecture_data["Title"] = title
                    print(f"Title: {title}")
            except Exception as e:
                print(f"Failed to extract title: {e}")
            
            # Institution
            try:
                institution_selector = "#detail_con > div.board_view > ul > li:nth-child(1) > dl > dd"
                institution_element = self.driver.find_element(By.CSS_SELECTOR, institution_selector)
                institution = institution_element.text.strip()
                if institution:
                    self.lecture_data["Institution"] = institution
                    print(f"Institution: {institution}")
            except Exception as e:
                print(f"Failed to extract institution: {e}")
            
            # Address
            try:
                address_selector = "#detail_con > div.board_view > ul > li:nth-child(11) > dl:nth-child(1) > dd"
                address_element = self.driver.find_element(By.CSS_SELECTOR, address_selector)
                address = address_element.text.strip()
                if address:
                    self.lecture_data["Address"] = address
                    print(f"Address: {address}")
            except Exception as e:
                print(f"Failed to extract address: {e}")
            
            # Tel
            try:
                tel_selector = "#detail_con > div.board_view > ul > li:nth-child(11) > dl:nth-child(2) > dd"
                tel_element = self.driver.find_element(By.CSS_SELECTOR, tel_selector)
                tel = tel_element.text.strip()
                if tel:
                    self.lecture_data["Tel"] = tel
                    print(f"Tel: {tel}")
            except Exception as e:
                print(f"Failed to extract tel: {e}")
            
            # Recruitment period
            try:
                recruitment_selector = "#detail_con > div.board_view > ul > li:nth-child(4) > dl > dd"
                recruitment_element = self.driver.find_element(By.CSS_SELECTOR, recruitment_selector)
                recruitment = recruitment_element.text.strip()
                if recruitment:
                    self.lecture_data["Recruitment_period"] = recruitment
                    print(f"Recruitment period: {recruitment}")
            except Exception as e:
                print(f"Failed to extract recruitment period: {e}")
            
            # Education period
            try:
                education_selector = "#detail_con > div.board_view > ul > li:nth-child(7) > dl:nth-child(1) > dd"
                education_element = self.driver.find_element(By.CSS_SELECTOR, education_selector)
                education = education_element.text.strip()
                if education:
                    self.lecture_data["Education_period"] = education
                    print(f"Education period: {education}")
            except Exception as e:
                print(f"Failed to extract education period: {e}")
            
            # Date (두 개의 값 합치기)
            try:
                date1_selector = "#detail_con > div.board_view > ul > li:nth-child(7) > dl:nth-child(2) > dd"
                date2_selector = "#detail_con > div.board_view > ul > li:nth-child(8) > dl:nth-child(1) > dd"
                
                date1_element = self.driver.find_element(By.CSS_SELECTOR, date1_selector)
                date2_element = self.driver.find_element(By.CSS_SELECTOR, date2_selector)
                
                date1 = date1_element.text.strip()
                date2 = date2_element.text.strip()
                
                date = f"{date1} {date2}"
                if date.strip():
                    self.lecture_data["Date"] = date
                    print(f"Date: {date}")
            except Exception as e:
                print(f"Failed to extract date: {e}")
            
            # Quota (수강인원 - 현재는 따로 지정된 CSS selector가 없어서 건너뜀)
            # 필요시 추가 가능
            
            # Fee
            try:
                fee_selector = "#detail_con > div.board_view > ul > li:nth-child(10) > dl > dd"
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
            
            # 마지막으로 클릭한 nth-child 인덱스 가져오기 (없으면 4로 초기화)
            last_child_index = self.checkpoint.get("last_child_index", 4)
            print(f"Last clicked child index: {last_child_index}")
            
            # 클릭할 다음 인덱스 계산 (항상 증가)
            next_child_index = last_child_index
            if next_child_index > 12:  # 최대 인덱스를 넘어서면 4로 리셋
                next_child_index = 4
            print(f"Will try to click child index: {next_child_index}")
            
            # 페이지 네비게이션 영역 확인
            pagination_area = self.driver.find_elements(By.CSS_SELECTOR, "#detail_con > div.paging.dp_pc")
            if not pagination_area:
                print("No pagination area found. This might be the last page.")
                return False
            
            # 모든 페이지 링크 찾기
            all_page_links = []
            try:
                all_links = self.driver.find_elements(By.CSS_SELECTOR, "#detail_con > div.paging.dp_pc > a")
                print(f"All page links found: {len(all_links)}")
                
                for i, link in enumerate(all_links):
                    link_text = link.text.strip()
                    link_class = link.get_attribute('class')
                    link_href = link.get_attribute('href')
                    print(f"Link {i+1}: text='{link_text}', class='{link_class}', href='{link_href}'")
                    
                    try:
                        # a 태그의 nth-child 인덱스 확인을 위한 JavaScript 실행
                        nth_child = i + 1
                        all_page_links.append({
                            'text': link_text,
                            'class': link_class,
                            'href': link_href,
                            'element': link,
                            'index': nth_child
                        })
                    except Exception as e:
                        print(f"Error getting nth-child index: {e}")
                        all_page_links.append({
                            'text': link_text,
                            'class': link_class,
                            'href': link_href,
                            'element': link,
                            'index': i + 1
                        })
            except Exception as e:
                print(f"Error getting page links: {e}")
            
            # 다음 페이지 버튼 찾기
            next_page_link = None
            
            # 1. 주어진 nth-child 인덱스로 직접 찾기
            next_child_selector = f"#detail_con > div.paging.dp_pc > a:nth-child({next_child_index})"
            try:
                print(f"Trying to find element with selector: {next_child_selector}")
                next_element = self.driver.find_element(By.CSS_SELECTOR, next_child_selector)
                
                if next_element:
                    next_page_link = next_element
                    link_text = next_element.text.strip()
                    print(f"Found next page element with text: '{link_text}'")
                    
                    # 이전 페이지로 가는 버튼인지 확인
                    prev_indicators = ['이전', 'prev', '<', '«', '‹', '처음', 'first']
                    is_prev_button = any(indicator in link_text.lower() for indicator in prev_indicators)
                    
                    if is_prev_button:
                        print(f"WARNING: Element appears to be a previous/first button (text: '{link_text}')")
                        print("Trying next index...")
                        next_child_index += 1
                        if next_child_index > 12:
                            next_child_index = 4
                        
                        next_child_selector = f"#detail_con > div.paging.dp_pc > a:nth-child({next_child_index})"
                        try:
                            next_element = self.driver.find_element(By.CSS_SELECTOR, next_child_selector)
                            next_page_link = next_element
                            print(f"Found next element with selector {next_child_selector}: '{next_element.text}'")
                        except:
                            print(f"Could not find element with selector {next_child_selector}")
                            next_page_link = None
            except Exception as e:
                print(f"Error finding next page element with selector {next_child_selector}: {e}")
                next_page_link = None
            
            # 2. 다음/다음 페이지 텍스트 또는 클래스 확인
            if not next_page_link:
                print("Looking for 'next' button...")
                for link_info in all_page_links:
                    if (link_info['text'] and any(s in link_info['text'].lower() for s in ['다음', 'next', '>', '»', '›'])) or \
                       (link_info['class'] and 'next' in link_info['class']):
                        next_page_link = link_info['element']
                        next_child_index = link_info['index']
                        print(f"Found 'next' button with text: '{link_info['text']}', index: {next_child_index}")
                        break
            
            # 3. 숫자 버튼 중 현재 페이지보다 큰 것 찾기
            if not next_page_link:
                print("Looking for next number button...")
                # 현재 활성화된 페이지 찾기
                try:
                    active_page_elements = self.driver.find_elements(By.CSS_SELECTOR, "#detail_con > div.paging.dp_pc > strong")
                    if active_page_elements:
                        current_page_text = active_page_elements[0].text.strip()
                        try:
                            current_page_num = int(current_page_text)
                            print(f"Current page number: {current_page_num}")
                            
                            # 다음 숫자 버튼 찾기
                            number_links = []
                            for link_info in all_page_links:
                                try:
                                    page_num = int(link_info['text'])
                                    if page_num > current_page_num:
                                        number_links.append((page_num, link_info))
                                except:
                                    continue
                            
                            if number_links:
                                # 가장 작은 다음 페이지 번호 선택
                                number_links.sort(key=lambda x: x[0])
                                next_link_info = number_links[0][1]
                                next_page_link = next_link_info['element']
                                next_child_index = next_link_info['index']
                                print(f"Found next page number: {number_links[0][0]}, index: {next_child_index}")
                        except ValueError:
                            print(f"Could not parse current page number: '{current_page_text}'")
                except Exception as e:
                    print(f"Error finding active page: {e}")
            
            # 다음 페이지 링크를 찾았으면 클릭
            if next_page_link:
                # checkpoint에 다음 인덱스 저장
                self.checkpoint["last_child_index"] = next_child_index
                self.save_checkpoint()
                
                # 링크의 href 속성 저장
                try:
                    next_page_href = next_page_link.get_attribute('href')
                    next_page_text = next_page_link.text.strip()
                    print(f"Next page href: {next_page_href}, text: '{next_page_text}'")
                except:
                    next_page_href = None
                    next_page_text = "unknown"
                
                # 클릭 시도
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
    
    def save_to_csv(self, filename="incheon_seogu_education.csv"):
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
        """Run the scraping process for Incheon Seogu education programs"""
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
                
                # Find all available courses on current page
                available_rows = self.find_rows_with_courses()
                
                if not available_rows:
                    print(f"No available courses found on page {current_page}")
                    consecutive_empty_pages += 1
                    
                    # 연속 3개 페이지에서 데이터를 찾지 못하면 종료
                    if consecutive_empty_pages >= 3:
                        print("Found 3 consecutive empty pages. Ending crawl.")
                        break
                    
                    # Try moving to next page
                    print("Moving to next page since no courses were found")
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
                
                # 첫 번째 페이지 시작 시에는, 또는 체크포인트 이후의 행을 처리
                if current_page == start_page:
                    if start_page == 1 and last_processed_row == 0:
                        rows_to_process = available_rows
                    else:
                        rows_to_process = [row for row in available_rows if row > last_processed_row]
                else:
                    rows_to_process = available_rows
                
                if not rows_to_process:
                    print(f"All available courses on page {current_page} have been processed")
                    
                    # Try moving to next page
                    print("Moving to next page since all courses were processed")
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
                
                print(f"Processing {len(rows_to_process)} courses on page {current_page}")
                
                # Process each eligible course
                for row_num in rows_to_process:
                    print(f"\nProcessing course {row_num} on page {current_page}")
                    
                    try:
                        # Extract data from this course
                        success = self.extract_lecture_data(row_num)
                        
                        if success:
                            # Add the lecture data to our collection
                            self.lectures.append(self.lecture_data.copy())
                            print(f"Added course '{self.lecture_data['Title']}' to collection")
                            total_processed_lectures += 1
                            
                            # Save after each successful extraction
                            self.save_to_csv("incheon_seogu_education.csv")
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
                
                # 페이지의 마지막 행까지 처리했으면 다음 페이지로 이동
                print(f"\nFinished processing all courses on page {current_page}. Moving to next page...")
                
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
                        # 직접 a:nth-child 링크 찾기
                        for i in range(4, 13):  # 페이지 버튼 범위 (4부터 12까지)
                            try:
                                selector = f"#detail_con > div.paging.dp_pc > a:nth-child({i})"
                                link = self.driver.find_element(By.CSS_SELECTOR, selector)
                                print(f"Found link: {selector} with text '{link.text}'")
                                
                                # 이전 페이지 버튼인지 확인
                                prev_indicators = ['이전', 'prev', '<', '«', '‹', '처음', 'first']
                                if any(indicator in link.text.lower() for indicator in prev_indicators):
                                    continue
                                
                                # 스크롤 및 클릭
                                self.driver.execute_script("arguments[0].scrollIntoView(true);", link)
                                time.sleep(1)
                                link.click()
                                print(f"Clicked on a:nth-child({i})")
                                time.sleep(3)
                                
                                # 페이지가 변경되었는지 확인
                                if self.driver.current_url != before_url:
                                    print("Successfully navigated to next page with direct a:nth-child selector")
                                    # 성공한 인덱스 저장
                                    self.checkpoint["last_child_index"] = i
                                    self.save_checkpoint()
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
                self.save_to_csv("incheon_seogu_education.csv")
            self.save_checkpoint()
            print(f"Progress saved. You can resume later from this point. Total lectures processed: {total_processed_lectures}")
            
        except Exception as e:
            print(f"Error during scraping process: {e}")
            import traceback
            traceback.print_exc()  # 자세한 에러 정보 출력
            
            # Save whatever data we've collected so far
            if self.lectures:
                self.save_to_csv("incheon_seogu_education.csv")
            # Make sure the checkpoint is saved
            self.save_checkpoint()
            print(f"Saved checkpoint. You can resume from this point later. Total lectures processed: {total_processed_lectures}")
            
        finally:
            print("Crawling process complete. Closing browser...")
            self.close()

# Run the crawler
if __name__ == "__main__":
    # URL for Incheon Seogu education listings
    url = 'https://www.seo.incheon.kr/open_content/anyedu/education/dong.jsp?acptrun=y#'
    
    try:
        # Create and run the crawler - set headless=False to see the browser in action
        crawler = IncheonSeoguEducationCrawler(headless=False)
        crawler.run(url, max_pages=100)
    except Exception as e:
        print(f"Fatal error in crawler execution: {e}")
        import traceback
        traceback.print_exc()