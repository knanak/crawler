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
from datetime import datetime
from urllib.parse import unquote, quote

class WorkGoKrCrawler:
    def __init__(self, headless=True, checkpoint_file="crawler_checkpoint.json"):
        # Chrome 옵션 설정
        self.chrome_options = Options()
        
        # 인코그니토 모드 사용
        self.chrome_options.add_argument('--incognito')
        
        if headless:
            self.chrome_options.add_argument('--headless')
        
        self.chrome_options.add_argument('--window-size=1920,1080')
        self.chrome_options.add_argument('--disable-gpu')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.chrome_options.add_argument('--disable-extensions')
        self.chrome_options.add_argument('--disable-popup-blocking')
        self.chrome_options.add_argument('--ignore-certificate-errors')
        self.chrome_options.add_argument('--disable-web-security')
        self.chrome_options.add_argument('--allow-running-insecure-content')
        self.chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        self.chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        self.chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # 로그 레벨 설정
        self.chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        self.chrome_options.add_argument('--log-level=3')
        
        # Chrome 드라이버 초기화
        try:
            self.driver = webdriver.Chrome(options=self.chrome_options)
            self.driver.set_page_load_timeout(30)
            self.wait = WebDriverWait(self.driver, 15)
            print("Chrome WebDriver 초기화 성공!")
        except Exception as e:
            print(f"Chrome 초기화 실패: {e}")
            raise

        # 수집할 데이터 구조 (새로운 구조)
        self.job_data = {
            "Id": "",
            "JobTitle": "",
            "DateOfRegistration": "",
            "Deadline": "",
            "JobCategory": "",
            "ExperienceRequired": "",
            "EmploymentType": "",
            "Salary": "",
            "Address": "",
            "Category": "",
            "WorkingHours": "",
            "CompanyName": "",
            "JobDescription": "",
            "ApplicationMethod": "",
            "Document": "",
            "Detail": ""
        }
        
        # 수집된 job 저장
        self.jobs = []
        
        # ID 카운터
        self.id_counter = 1
        
        # 이미 처리된 job ID 추적
        self.processed_job_ids = set()
        
        # 체크포인트 설정
        self.checkpoint_file = checkpoint_file
        self.checkpoint = {
            "current_page": 1,
            "current_list_index": 0,
            "last_processed_job_id": "",
            "last_url": "",
            "timestamp": ""
        }
        
        # User agent 설정
        self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36'
        })
    
    def navigate_to_url(self, url):
        """URL로 이동"""
        print(f"Navigating to {url}")
        self.driver.get(url)
        time.sleep(3)
        self.checkpoint["last_url"] = url
        self.save_checkpoint()
    
    def reset_job_data(self):
        """job_data 초기화"""
        self.job_data = {
            "Id": "",
            "JobTitle": "Not found",
            "DateOfRegistration": "Not found",
            "Deadline": "채용시까지",
            "JobCategory": "Not found",
            "ExperienceRequired": "Not found",
            "EmploymentType": "Not found",
            "Salary": "Not found",
            "Address": "Not found",
            "Category": "",
            "WorkingHours": "Not found",
            "CompanyName": "Not found",
            "JobDescription": "Not found",
            "ApplicationMethod": "Not found",
            "Document": "Not found",
            "Detail": "Not found"
        }
    
    def extract_listing_data(self, list_num):
        """리스트 페이지에서 기본 정보 추출"""
        print(f"Extracting data from list {list_num}")
        self.reset_job_data()
        
        # ID 할당
        self.job_data["Id"] = str(self.id_counter)
        self.id_counter += 1
        
        try:
            # Job Title
            title_selector = f"#list{list_num} > td.al_left.pd24 > div > div:nth-child(2) > a"
            title_element = self.driver.find_element(By.CSS_SELECTOR, title_selector)
            self.job_data["JobTitle"] = title_element.text.strip()
            
            # Detail URL
            self.job_data["Detail"] = title_element.get_attribute('href')
            
        except NoSuchElementException:
            print(f"Job title not found for list {list_num}")
        
        try:
            # Date of Registration
            date_selector = f"#list{list_num} > td:nth-child(3) > p:nth-child(4)"
            date_element = self.driver.find_element(By.CSS_SELECTOR, date_selector)
            self.job_data["DateOfRegistration"] = date_element.text.strip()
        except NoSuchElementException:
            pass
        
        try:
            # Deadline
            deadline_selector = f"#list{list_num} > td:nth-child(3) > p:nth-child(3)"
            deadline_element = self.driver.find_element(By.CSS_SELECTOR, deadline_selector)
            self.job_data["Deadline"] = deadline_element.text.strip()
        except NoSuchElementException:
            pass
        
        try:
            # Experience Required
            exp_selector = f"#list{list_num} > td.link.pd24 > div > ul > li.member > p > span:nth-child(1)"
            exp_element = self.driver.find_element(By.CSS_SELECTOR, exp_selector)
            self.job_data["ExperienceRequired"] = exp_element.text.strip()
        except NoSuchElementException:
            pass
        
        try:
            # Salary
            salary_selector = f"#list{list_num} > td.link.pd24 > div > ul > li.dollar > p > span"
            salary_element = self.driver.find_element(By.CSS_SELECTOR, salary_selector)
            self.job_data["Salary"] = salary_element.text.strip()
        except NoSuchElementException:
            pass
        
        try:
            # Address
            address_selector = f"#list{list_num} > td.link.pd24 > div > ul > li.site > p"
            address_element = self.driver.find_element(By.CSS_SELECTOR, address_selector)
            address_text = address_element.text.strip()
            self.job_data["Address"] = address_text
            
            # Category (Address의 두번째 텍스트)
            address_parts = address_text.split()
            if len(address_parts) >= 2:
                self.job_data["Category"] = address_parts[1]
            else:
                self.job_data["Category"] = address_text
                
        except NoSuchElementException:
            pass
        
        try:
            # Working Hours
            hours_selector = f"#list{list_num} > td.link.pd24 > div > ul > li.time"
            hours_element = self.driver.find_element(By.CSS_SELECTOR, hours_selector)
            self.job_data["WorkingHours"] = hours_element.text.strip()
        except NoSuchElementException:
            pass
        
        try:
            # Company Name
            company_selector = f"#list{list_num} > td.al_left.pd24 > div > div:nth-child(1) > div > label > span > a"
            company_element = self.driver.find_element(By.CSS_SELECTOR, company_selector)
            self.job_data["CompanyName"] = company_element.text.strip()
        except NoSuchElementException:
            pass
        
        return self.job_data.copy()
    
    def extract_detail_data(self):
        """상세 페이지에서 추가 정보 추출"""
        print("Extracting detail page data")
        
        try:
            # Employment Type
            emp_type_selector = "#tab-panel01 > div.box_table_wrap.write.mt16 > table > tbody > tr:nth-child(2) > td:nth-child(2)"
            emp_type_element = self.driver.find_element(By.CSS_SELECTOR, emp_type_selector)
            self.job_data["EmploymentType"] = emp_type_element.text.strip()
        except NoSuchElementException:
            print("Employment type not found")
        
        try:
            # Job Description
            desc_selector = "#tab-panel01 > div.box_border_type.expand.mt16 > div"
            desc_element = self.driver.find_element(By.CSS_SELECTOR, desc_selector)
            self.job_data["JobDescription"] = desc_element.text.strip()
        except NoSuchElementException:
            print("Job description not found")
        
        try:
            # Application Method
            app_method_selector = "#tab-panel05 > div:nth-child(3) > div > div.flex1 > p:nth-child(2)"
            app_method_element = self.driver.find_element(By.CSS_SELECTOR, app_method_selector)
            self.job_data["ApplicationMethod"] = app_method_element.text.strip()
        except NoSuchElementException:
            print("Application method not found")
        
        try:
            # Document
            doc_selector = "#tab-panel05 > div:nth-child(3) > div > div.flex1 > p:nth-child(4)"
            doc_element = self.driver.find_element(By.CSS_SELECTOR, doc_selector)
            self.job_data["Document"] = doc_element.text.strip()
        except NoSuchElementException:
            print("Document requirements not found")
        
        return True
    
    def crawl_job_detail(self, detail_url):
        """상세 페이지 크롤링"""
        main_window = self.driver.current_window_handle
        
        try:
            # 새 탭에서 상세 페이지 열기
            self.driver.execute_script(f"window.open('{detail_url}', '_blank');")
            time.sleep(3)
            
            # 새 탭으로 전환
            all_windows = self.driver.window_handles
            for window in all_windows:
                if window != main_window:
                    self.driver.switch_to.window(window)
                    break
            
            # 상세 정보 추출
            self.extract_detail_data()
            
            # 탭 닫고 메인 윈도우로 복귀
            self.driver.close()
            self.driver.switch_to.window(main_window)
            time.sleep(1)
            
            return True
            
        except Exception as e:
            print(f"Error crawling detail page: {e}")
            # 에러 발생 시 메인 윈도우로 복귀
            try:
                self.driver.switch_to.window(main_window)
            except:
                pass
            return False
    
    def crawl_page_jobs(self):
        """현재 페이지의 모든 job 크롤링"""
        page_jobs = []
        
        # 각 리스트 (1-10) 크롤링
        for list_num in range(1, 11):
            try:
                # 리스트에서 기본 정보 추출
                job_data = self.extract_listing_data(list_num)
                
                # job ID 생성
                job_id = f"{job_data['JobTitle']}_{job_data['DateOfRegistration']}_{job_data['Deadline']}"
                
                # 이미 처리된 job인지 확인
                if job_id in self.processed_job_ids:
                    print(f"Skipping already processed job: {job_data['JobTitle']}")
                    continue
                
                # 현재 job_data 설정
                self.job_data = job_data
                
                # 상세 페이지 크롤링
                if job_data["Detail"] != "Not found":
                    self.crawl_job_detail(job_data["Detail"])
                
                # 수집된 데이터 저장
                page_jobs.append(self.job_data.copy())
                self.processed_job_ids.add(job_id)
                
                print(f"Successfully crawled job {list_num}: {self.job_data['JobTitle']}")
                
            except Exception as e:
                print(f"Error processing list {list_num}: {e}")
                continue
        
        return page_jobs
    
    def go_to_next_page(self, current_page):
        """다음 페이지로 이동"""
        try:
            # 페이지 하단으로 스크롤
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # 팝업이나 모달 닫기 시도
            try:
                # 일반적인 팝업 닫기 버튼들 시도
                close_buttons = [
                    "button.close", 
                    "button.btn_close",
                    "a.close",
                    ".popup_close",
                    "[class*='close']",
                    "[title*='닫기']"
                ]
                
                for selector in close_buttons:
                    try:
                        close_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if close_btn.is_displayed():
                            close_btn.click()
                            time.sleep(1)
                            break
                    except:
                        continue
            except:
                pass
            
            if current_page % 10 == 0:
                # 11페이지로 가는 버튼 (next 버튼)
                next_button_selector = "#mForm > div.box_group_wrap > div > div.section_bottom > div > div > div > button.btn_page.next"
            else:
                # 페이지 번호 버튼을 직접 찾기
                # 현재 페이지가 1이면 2를 찾고, 2면 3을 찾는 방식
                target_page = current_page + 1
                
                # 방법 1: 텍스트로 버튼 찾기
                try:
                    buttons = self.driver.find_elements(By.CSS_SELECTOR, "#mForm > div.box_group_wrap > div > div.section_bottom > div > div > div > button")
                    for i, button in enumerate(buttons):
                        if button.text.strip() == str(target_page):
                            next_button_selector = f"#mForm > div.box_group_wrap > div > div.section_bottom > div > div > div > button:nth-child({i+1})"
                            print(f"Found button for page {target_page} at index {i+1}")
                            break
                    else:
                        # 버튼을 찾지 못한 경우 기본 계산 사용
                        button_index = target_page + 1  # 조정된 인덱스
                        next_button_selector = f"#mForm > div.box_group_wrap > div > div.section_bottom > div > div > div > button:nth-child({button_index})"
                except:
                    # 에러 시 기본 계산 사용
                    button_index = target_page + 1
                    next_button_selector = f"#mForm > div.box_group_wrap > div > div.section_bottom > div > div > div > button:nth-child({button_index})"
            
            print(f"Looking for next page button: {next_button_selector}")
            
            # 여러 방법으로 클릭 시도
            try:
                # 방법 1: XPath로 정확한 버튼 찾기
                target_page = current_page + 1
                xpath_selector = f"//button[text()='{target_page}']"
                
                try:
                    next_button = self.driver.find_element(By.XPATH, xpath_selector)
                    print(f"Found button using XPath for page {target_page}")
                except:
                    # CSS selector로 시도
                    next_button = self.driver.find_element(By.CSS_SELECTOR, next_button_selector)
                
                # 버튼이 보이도록 스크롤
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                time.sleep(1)
                
                # 추가 스크롤로 버튼이 완전히 보이도록 함
                self.driver.execute_script("window.scrollBy(0, 100);")
                time.sleep(1)
                
                # 버튼이 활성화되어 있는지 확인
                if next_button.get_attribute("disabled"):
                    print(f"Button for page {target_page} is disabled")
                    return False
                
                next_button.click()
                print(f"Clicked button to go to page {current_page + 1}")
                
            except Exception as e:
                print(f"Normal click failed: {e}")
                
                # 방법 2: JavaScript 클릭
                try:
                    next_button = self.driver.find_element(By.CSS_SELECTOR, next_button_selector)
                    self.driver.execute_script("arguments[0].click();", next_button)
                    print(f"JavaScript clicked button to go to page {current_page + 1}")
                    
                except Exception as e2:
                    print(f"JavaScript click also failed: {e2}")
                    
                    # 방법 3: ActionChains 사용
                    try:
                        from selenium.webdriver.common.action_chains import ActionChains
                        next_button = self.driver.find_element(By.CSS_SELECTOR, next_button_selector)
                        actions = ActionChains(self.driver)
                        actions.move_to_element(next_button).click().perform()
                        print(f"ActionChains clicked button to go to page {current_page + 1}")
                        
                    except Exception as e3:
                        print(f"ActionChains click also failed: {e3}")
                        return False
            
            # 페이지 로딩 대기
            time.sleep(3)
            
            # 페이지가 실제로 변경되었는지 확인 (여러 방법 시도)
            try:
                # 방법 1: aria-current 속성으로 확인
                active_page = self.driver.find_element(By.CSS_SELECTOR, "button[aria-current='true']")
                active_page_num = active_page.text.strip()
                expected_page_num = str(current_page + 1)
                
                if active_page_num == expected_page_num:
                    print(f"Successfully moved to page {expected_page_num}")
                    return True
                
                # 방법 2: URL 파라미터 확인
                current_url = self.driver.current_url
                if f"currentPageNo={expected_page_num}" in current_url or f"pageIndex={expected_page_num}" in current_url:
                    print(f"URL confirms page change to {expected_page_num}")
                    return True
                
                # 방법 3: 첫 번째 job의 내용이 변경되었는지 확인
                try:
                    first_job_title = self.driver.find_element(By.CSS_SELECTOR, "#list1 > td.al_left.pd24 > div > div:nth-child(2) > a").text
                    if hasattr(self, 'last_first_job_title') and self.last_first_job_title != first_job_title:
                        print(f"Job content changed, assuming successful page navigation")
                        return True
                except:
                    pass
                
                print(f"Page change verification failed. Expected: {expected_page_num}, Actual: {active_page_num}")
                # 페이지 번호가 맞지 않아도 일단 진행 (때로는 검증이 정확하지 않을 수 있음)
                return True
                    
            except:
                # 페이지 번호 확인이 실패해도 일단 진행
                print("Could not verify page change, but continuing...")
                return True
                
        except Exception as e:
            print(f"Error navigating to next page: {e}")
            
            # 에러 발생 시 페이지 새로고침 후 재시도
            try:
                print("Attempting to refresh and retry...")
                self.driver.refresh()
                time.sleep(3)
                
                # 페이지 하단으로 다시 스크롤
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
                # 다시 버튼 찾아서 클릭
                next_button = self.driver.find_element(By.CSS_SELECTOR, next_button_selector)
                self.driver.execute_script("arguments[0].click();", next_button)
                time.sleep(3)
                return True
                
            except:
                return False
            
    def save_to_csv(self, filename="job_data.csv"):
        """CSV 파일로 저장"""
        if not self.jobs:
            print("No jobs to save.")
            return
        
        df_new = pd.DataFrame(self.jobs)
        
        if os.path.isfile(filename):
            try:
                df_existing = pd.read_csv(filename, encoding='utf-8-sig')
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                df_combined = df_combined.drop_duplicates(subset=['JobTitle', 'CompanyName', 'Deadline'], keep='last')
                df_combined.to_csv(filename, index=False, encoding='utf-8-sig', lineterminator='\n')
                print(f"Appended {len(df_new)} jobs to {filename}. Total: {len(df_combined)} jobs")
            except Exception as e:
                print(f"Error appending to existing file: {e}")
                df_new.to_csv(filename, index=False, encoding='utf-8-sig', lineterminator='\n')
        else:
            df_new.to_csv(filename, index=False, encoding='utf-8-sig', lineterminator='\n')
            print(f"Created new file {filename} with {len(df_new)} jobs")
        
        self.jobs = []
    
    def save_checkpoint(self):
        """체크포인트 저장"""
        try:
            checkpoint_data = self.checkpoint.copy()
            checkpoint_data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
                
            print(f"Checkpoint saved at page {self.checkpoint['current_page']}")
        except Exception as e:
            print(f"Error saving checkpoint: {e}")
    
    def load_checkpoint(self):
        """체크포인트 로드"""
        if not os.path.exists(self.checkpoint_file):
            print("No checkpoint file found")
            return False
        
        try:
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                self.checkpoint = json.load(f)
            print(f"Loaded checkpoint: Page {self.checkpoint['current_page']}")
            return True
        except Exception as e:
            print(f"Error loading checkpoint: {e}")
            return False
    
    def run(self, start_url, max_pages=100):
        """메인 크롤링 실행"""
        # 체크포인트 로드
        checkpoint_exists = self.load_checkpoint()
        
        # 기존 CSV에서 ID 카운터 초기화
        if os.path.exists("job_data.csv"):
            try:
                df_existing = pd.read_csv("job_data.csv", encoding='utf-8-sig')
                if not df_existing.empty and 'Id' in df_existing.columns:
                    self.id_counter = int(df_existing['Id'].max()) + 1
                    print(f"Starting ID counter from: {self.id_counter}")
            except:
                pass
        
        try:
            # 시작 URL로 이동
            self.navigate_to_url(start_url)
            
            # 체크포인트가 있으면 해당 페이지로 이동
            if checkpoint_exists and self.checkpoint["current_page"] > 1:
                print(f"Resuming from page {self.checkpoint['current_page']}")
                # 해당 페이지까지 이동
                for page in range(1, self.checkpoint["current_page"]):
                    self.go_to_next_page(page)
                current_page = self.checkpoint["current_page"]
            else:
                current_page = 1
            
            # 페이지별 크롤링
            while current_page <= max_pages:
                print(f"\n=== Crawling page {current_page} ===")
                
                # 현재 페이지 체크포인트 업데이트
                self.checkpoint["current_page"] = current_page
                self.save_checkpoint()
                
                # 현재 페이지의 모든 job 크롤링
                page_jobs = self.crawl_page_jobs()
                self.jobs.extend(page_jobs)
                
                # CSV 저장 (페이지마다)
                self.save_to_csv()
                
                print(f"Page {current_page} completed. Collected {len(page_jobs)} jobs")
                
                # 다음 페이지로 이동
                if current_page < max_pages:
                    if self.go_to_next_page(current_page):
                        current_page += 1
                    else:
                        print("Failed to navigate to next page. Stopping.")
                        break
                else:
                    break
            
            print(f"\nCrawling completed! Total pages crawled: {current_page}")
            
        except KeyboardInterrupt:
            print("\nCrawling interrupted by user.")
            self.save_to_csv()
            self.save_checkpoint()
            print("Progress saved.")
            
        except Exception as e:
            print(f"Error during crawling: {e}")
            self.save_to_csv()
            self.save_checkpoint()
            
        finally:
            self.close()
    
    def close(self):
        """브라우저 종료"""
        try:
            if hasattr(self, 'driver'):
                self.driver.quit()
                print("Browser closed.")
        except:
            pass

# 실행
if __name__ == "__main__":
    url = 'https://www.work24.go.kr/wk/a/b/1200/retriveDtlEmpSrchList.do?basicSetupYn=&careerTo=&keywordJobCd=&occupation=&seqNo=&cloDateEndtParam=&payGbn=&templateInfo=&rot2WorkYn=&shsyWorkSecd=&resultCnt=10&keywordJobCont=&cert=&moreButtonYn=Y&minPay=&codeDepth2Info=11000&currentPageNo=1&eventNo=&mode=&major=&resrDutyExcYn=&eodwYn=&sortField=DATE&staArea=&sortOrderBy=DESC&keyword=&termSearchGbn=&carrEssYns=&benefitSrchAndOr=O&disableEmpHopeGbn=&actServExcYn=&keywordStaAreaNm=&maxPay=&regionParam=11000&emailApplyYn=&codeDepth1Info=11000&keywordEtcYn=&regDateStdtParam=&publDutyExcYn=&keywordJobCdSeqNo=&viewType=&exJobsCd=&templateDepthNmInfo=&region=11000&employGbn=&empTpGbcd=&computerPreferential=&infaYn=&cloDateStdtParam=&siteClcd=all&searchMode=Y&birthFromYY=&indArea=&careerTypes=&subEmpHopeYn=&tlmgYn=&academicGbn=&templateDepthNoInfo=&foriegn=&entryRoute=&mealOfferClcd=&basicSetupYnChk=&station=&holidayGbn=&srcKeyword=&academicGbnoEdu=noEdu&enterPriseGbn=&cloTermSearchGbn=&birthToYY=&keywordWantedTitle=&stationNm=&benefitGbn=&keywordFlag=&notSrcKeyword=&essCertChk=&depth2SelCode=&keywordBusiNm=&preferentialGbn=&rot3WorkYn=&regDateEndtParam=&pfMatterPreferential=B&pageIndex=1&termContractMmcnt=&careerFrom=&laborHrShortYn=#scrollLoc'
    
    crawler = WorkGoKrCrawler(headless=False)
    crawler.run(url, max_pages=100)