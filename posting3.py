import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import json
import os
from datetime import datetime
import requests
from dotenv import load_dotenv
import pyperclip, pyautogui

# Load environment variables from .env file
load_dotenv()

class NaverBlogPoster:
    def __init__(self, naver_id=None, naver_pw=None, blog_id=None):
        """
        Initialize Naver Blog Poster
        
        Args:
            naver_id: Naver ID for login
            naver_pw: Naver password for login
            blog_id: Naver blog ID (e.g., 'myblog' from blog.naver.com/myblog)
        """
        self.naver_id = naver_id
        self.naver_pw = naver_pw
        self.blog_id = blog_id
        self.posted_jobs_file = "posted_items.json"
        self.posted_items = self.load_posted_items()
        
        # Chrome options for Selenium
        self.chrome_options = Options()
        self.chrome_options.add_argument('--window-size=1920,1080')
        self.chrome_options.add_argument('--disable-gpu')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        self.chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        self.chrome_options.add_experimental_option('useAutomationExtension', False)
        
    def load_posted_items(self):
        """Load already posted item IDs from file"""
        if os.path.exists(self.posted_jobs_file):
            try:
                with open(self.posted_jobs_file, 'r', encoding='utf-8') as f:
                    return set(json.load(f))
            except:
                return set()
        return set()
    
    def save_posted_items(self):
        """Save posted item IDs to file"""
        with open(self.posted_jobs_file, 'w', encoding='utf-8') as f:
            json.dump(list(self.posted_items), f, ensure_ascii=False, indent=2)
    
    def check_new_items(self):
        """Check for new items in CSV files that haven't been posted yet"""
        print("\n=== Starting check_new_items method ===")
        new_items = []
        
        # Check all CSV files in current directory
        csv_files = [f for f in os.listdir('.') if f.endswith('.csv')]
        print(f"Found CSV files: {csv_files}")
        
        for csv_file in csv_files:
            print(f"\nChecking file: {csv_file}")
            
            try:
                # Try different encodings
                encodings = ['utf-8-sig', 'utf-8', 'cp949', 'euc-kr']
                df = None
                
                for encoding in encodings:
                    try:
                        df = pd.read_csv(csv_file, encoding=encoding)
                        print(f"Successfully read CSV with encoding: {encoding}")
                        break
                    except Exception as e:
                        continue
                
                if df is None:
                    raise Exception("Could not read CSV with any encoding")
                
                print(f"Total rows in CSV: {len(df)}")
                print(f"Columns: {', '.join(df.columns.tolist())}")
                
                # Add 'Post' column if it doesn't exist
                if 'Post' not in df.columns:
                    df['Post'] = ''
                    df.to_csv(csv_file, index=False, encoding='utf-8-sig')
                    print("Added 'Post' column to CSV")
                
                # Determine content type based on filename
                content_type = self.get_content_type(csv_file)
                print(f"Content type: {content_type}")
                
                # Find first item not yet posted
                for idx, item in df.iterrows():
                    if pd.isna(item.get('Post')) or str(item.get('Post')).strip().upper() != 'Y':
                        item_dict = item.to_dict()
                        item_dict['ContentType'] = content_type
                        item_dict['FileName'] = csv_file
                        item_dict['RowIndex'] = idx
                        
                        # Create unique item ID
                        item_id = self.create_unique_id(item, csv_file)
                        new_items.append((item_id, item_dict))
                        
                        # Only get the first unposted item from this file
                        print(f"Found unposted item at row {idx}")
                        break
                        
            except Exception as e:
                print(f"Error reading {csv_file}: {e}")
        
        print(f"\n=== Finished check_new_items, found {len(new_items)} new items ===")
        return new_items
    
    def mark_as_posted(self, filename, row_index):
        """Mark an item as posted by setting Post column to 'Y'"""
        try:
            # Read with proper encoding
            encodings = ['utf-8-sig', 'utf-8', 'cp949', 'euc-kr']
            df = None
            
            for encoding in encodings:
                try:
                    df = pd.read_csv(filename, encoding=encoding)
                    break
                except:
                    continue
            
            if df is None:
                raise Exception("Could not read CSV with any encoding")
            
            # Add 'Post' column if it doesn't exist
            if 'Post' not in df.columns:
                df['Post'] = ''
            
            # Mark as posted
            df.loc[row_index, 'Post'] = 'Y'
            
            # Save the updated CSV with UTF-8 BOM encoding
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"Marked row {row_index} as posted in {filename}")
            
        except Exception as e:
            print(f"Error updating {filename}: {e}")
    
    def get_content_type(self, filename):
        """Determine content type based on filename"""
        filename_lower = filename.lower()
        if 'job' in filename_lower:
            return 'job'
        elif 'facility' in filename_lower:
            return 'facility'
        elif 'culture' in filename_lower:
            return 'culture'
        else:
            return 'general'
    
    def create_unique_id(self, item, filename):
        """Create a unique ID for the item"""
        id_parts = [filename]
        
        # Add relevant columns if they exist
        for col in ['Title', 'CompanyName', 'Name', 'ID', 'DateofRegistration', 'Date', 'Deadline']:
            if col in item and pd.notna(item[col]):
                id_parts.append(str(item[col]))
        
        return "_".join(id_parts)
    
    def format_post(self, item_data):
        """Format item data into a blog post based on content type"""
        content_type = item_data.get('ContentType', 'general')
        
        if content_type == 'job':
            return self.format_job_post(item_data)
        elif content_type == 'facility':
            return self.format_facility_post(item_data)
        elif content_type == 'culture':
            return self.format_culture_post(item_data)
        else:
            return self.format_general_post(item_data)
    
    def format_job_post(self, job_data):
        """Format job data into a blog post"""
        print("\n=== Formatting job post ===")
        
        # Get title from CSV
        title = str(job_data.get('Title', '채용정보')).strip()
        if not title or title == 'nan':
            title = f"채용정보 #{job_data.get('RowIndex', 0) + 1}"
        
        print(f"Title: {title}")
        
        # Create content from CSV data
        content = "<div style='font-family: \"Noto Sans KR\", sans-serif; line-height: 1.8; padding: 20px;'>"
        content += f"<h2 style='color: #2E86AB; border-bottom: 2px solid #2E86AB; padding-bottom: 10px; margin-bottom: 20px;'>📋 {title}</h2>"
        content += "<table style='width: 100%; border-collapse: collapse; background-color: #f8f9fa; border-radius: 10px;'>"
        
        # Define display names for common columns
        column_display_names = {
            'Title': '제목',
            'CompanyName': '회사명',
            'JobType': '직종',
            'Salary': '급여',
            'WorkHours': '근무시간',
            'Location': '근무지',
            'Deadline': '마감일',
            'Contact': '연락처',
            'Description': '상세내용'
        }
        
        # Add all CSV data as table rows
        for key, value in job_data.items():
            if key not in ['ContentType', 'FileName', 'RowIndex', 'Post']:
                display_key = column_display_names.get(key, key)
                display_value = str(value) if pd.notna(value) else '정보 없음'
                
                content += f"""
                <tr style='border-bottom: 1px solid #ddd;'>
                    <td style='padding: 12px; font-weight: bold; width: 30%; background-color: #e9ecef;'>{display_key}</td>
                    <td style='padding: 12px;'>{display_value}</td>
                </tr>
                """
        
        content += "</table>"
        content += "<div style='margin-top: 20px; padding: 15px; background-color: #e8f4fd; border-left: 4px solid #2E86AB;'>"
        content += "<p style='margin: 0;'>💡 <strong>문의사항이 있으시면 위 연락처로 직접 문의해주세요.</strong></p>"
        content += "</div>"
        content += "</div>"
        
        tags = ['노인일자리', '노인고용', '노인구직', '시니어일자리', '시니어고용', '시니어구직']
        
        return title, content, tags
    
    def format_facility_post(self, facility_data):
        """Format facility data into a blog post"""
        title = facility_data.get('Name', facility_data.get('Title', '시설명 없음'))
        if not title or title == 'nan':
            title = f"복지시설 정보 #{facility_data.get('RowIndex', 0) + 1}"
        
        title = f"[복지시설 정보] {title}"
        
        content = "<div style='font-family: \"Noto Sans KR\", sans-serif; line-height: 1.8; padding: 20px;'>"
        content += f"<h2 style='color: #2E86AB; border-bottom: 2px solid #2E86AB; padding-bottom: 10px;'>🏥 {facility_data.get('Name', '시설명')}</h2>"
        content += "<table style='width: 100%; border-collapse: collapse; background-color: #f8f9fa; border-radius: 10px;'>"
        
        for key, value in facility_data.items():
            if key not in ['ContentType', 'FileName', 'RowIndex', 'Post']:
                display_value = str(value) if pd.notna(value) else '정보 없음'
                content += f"""
                <tr style='border-bottom: 1px solid #ddd;'>
                    <td style='padding: 12px; font-weight: bold; width: 30%; background-color: #e9ecef;'>{key}</td>
                    <td style='padding: 12px;'>{display_value}</td>
                </tr>
                """
        
        content += "</table></div>"
        
        tags = ['노인복지정책', '노인정책', '노인복지정보', '시니어복지정책', '시니어정책', 
                '시니어복지정보', '장기요양기관추천', '방문요양센터추천', '복지관추천', 
                '노인교실추천', '경로당추천']
        
        return title, content, tags
    
    def format_culture_post(self, culture_data):
        """Format culture data into a blog post"""
        title = culture_data.get('Title', culture_data.get('Name', '프로그램명 없음'))
        if not title or title == 'nan':
            title = f"문화프로그램 #{culture_data.get('RowIndex', 0) + 1}"
            
        title = f"[문화프로그램] {title}"
        
        content = "<div style='font-family: \"Noto Sans KR\", sans-serif; line-height: 1.8; padding: 20px;'>"
        content += f"<h2 style='color: #2E86AB; border-bottom: 2px solid #2E86AB; padding-bottom: 10px;'>🎭 {culture_data.get('Title', '프로그램명')}</h2>"
        content += "<table style='width: 100%; border-collapse: collapse; background-color: #f8f9fa; border-radius: 10px;'>"
        
        for key, value in culture_data.items():
            if key not in ['ContentType', 'FileName', 'RowIndex', 'Post']:
                display_value = str(value) if pd.notna(value) else '정보 없음'
                content += f"""
                <tr style='border-bottom: 1px solid #ddd;'>
                    <td style='padding: 12px; font-weight: bold; width: 30%; background-color: #e9ecef;'>{key}</td>
                    <td style='padding: 12px;'>{display_value}</td>
                </tr>
                """
        
        content += "</table></div>"
        
        tags = ['문화프로그램', '노인여가', '시니어여가']
        
        return title, content, tags
    
    def format_general_post(self, data):
        """Format general data into a blog post"""
        title = data.get('Title', data.get('Name', '제목 없음'))
        if not title or title == 'nan': <div style='font-family: "Noto Sans KR", sans-serif; line-height: 1.8; padding: 20px;'><h2 style='color: #2E86AB; border-bottom: 2px solid #2E86AB; padding-bottom: 10px;'>📌 [정보] 주민대화방</h2><table style='width: 100%; border-collapse: collapse; background-color: #f8f9fa; border-radius: 10px;'>
                <tr style='border-bottom: 1px solid #ddd;'>
                    <td style='padding: 12px; font-weight: bold; width: 30%; background-color: #e9ecef;'>City</td>
                    <td style='padding: 12px;'>경기도 안양시</td>
                </tr>
                
                <tr style='border-bottom: 1px solid #ddd;'>
                    <td style='padding: 12px; font-weight: bold; width: 30%; background-color: #e9ecef;'>Lecture_Category</td>
                    <td style='padding: 12px;'>회의실 개방</td>
                </tr>
                
                <tr style='border-bottom: 1px solid #ddd;'>
                    <td style='padding: 12px; font-weight: bold; width: 30%; background-color: #e9ecef;'>Title</td>
                    <td style='padding: 12px;'>주민대화방</td>
                </tr>
                
                <tr style='border-bottom: 1px solid #ddd;'>
                    <td style='padding: 12px; font-weight: bold; width: 30%; background-color: #e9ecef;'>Recruitment_period</td>
                    <td style='padding: 12px;'>수시모집</td>
                </tr>
                
                <tr style='border-bottom: 1px solid #ddd;'>
                    <td style='padding: 12px; font-weight: bold; width: 30%; background-color: #e9ecef;'>Education_period</td>
                    <td style='padding: 12px;'>추후협의</td>
                </tr>
                
                <tr style='border-bottom: 1px solid #ddd;'>
                    <td style='padding: 12px; font-weight: bold; width: 30%; background-color: #e9ecef;'>Institution</td>
                    <td style='padding: 12px;'>범계동행정복지센터</td>
                </tr>
                
                <tr style='border-bottom: 1px solid #ddd;'>
                    <td style='padding: 12px; font-weight: bold; width: 30%; background-color: #e9ecef;'>Address</td>
                    <td style='padding: 12px;'>범계동 행정복지센터 1층</td>
                </tr>
                
                <tr style='border-bottom: 1px solid #ddd;'>
                    <td style='padding: 12px; font-weight: bold; width: 30%; background-color: #e9ecef;'>Quota</td>
                    <td style='padding: 12px;'>0/8
(0/0)</td>
                </tr>
                
                <tr style='border-bottom: 1px solid #ddd;'>
                    <td style='padding: 12px; font-weight: bold; width: 30%; background-color: #e9ecef;'>State</td>
                    <td style='padding: 12px;'>모집중</td>
                </tr>
                
                <tr style='border-bottom: 1px solid #ddd;'>
                    <td style='padding: 12px; font-weight: bold; width: 30%; background-color: #e9ecef;'>Register</td>
                    <td style='padding: 12px;'>방문접수</td>
                </tr>
                
                <tr style='border-bottom: 1px solid #ddd;'>
                    <td style='padding: 12px; font-weight: bold; width: 30%; background-color: #e9ecef;'>Detail</td>
                    <td style='padding: 12px;'>https://www.anyang.go.kr/reserve/eduLctreWebView.do?pageUnit=10&pageIndex=1&searchCnd=all&key=1376&searchUseAt=Y&eduLctreNo=923</td>
                </tr>
                </table></div>
            title = f"정보 #{data.get('RowIndex', 0) + 1}"
            
        title = f"[정보] {title}"
        
        content = "<div style='font-family: \"Noto Sans KR\", sans-serif; line-height: 1.8; padding: 20px;'>"
        content += f"<h2 style='color: #2E86AB; border-bottom: 2px solid #2E86AB; padding-bottom: 10px;'>📌 {title}</h2>"
        content += "<table style='width: 100%; border-collapse: collapse; background-color: #f8f9fa; border-radius: 10px;'>"
        
        for key, value in data.items():
            if key not in ['ContentType', 'FileName', 'RowIndex', 'Post']:
                display_value = str(value) if pd.notna(value) else '정보 없음'
                content += f"""
                <tr style='border-bottom: 1px solid #ddd;'>
                    <td style='padding: 12px; font-weight: bold; width: 30%; background-color: #e9ecef;'>{key}</td>
                    <td style='padding: 12px;'>{display_value}</td>
                </tr>
                """
        
        content += "</table></div>"
        
        tags = ['정보', '노인', '시니어']
        
        return title, content, tags
    
    def login_naver(self, driver):
        """Login to Naver"""
        try:
            driver.get("https://nid.naver.com/nidlogin.login?mode=form&url=https%3A%2F%2Fwww.naver.com&locale=ko_KR&svctype=1")
            time.sleep(2)
            
            # Execute JavaScript to input credentials
            driver.execute_script(f"""
                document.getElementById('id').value = '{self.naver_id}';
                document.getElementById('pw').value = '{self.naver_pw}';
            """)
            time.sleep(1)
            
            # Click login button
            login_btn = driver.find_element(By.ID, "log.login")
            login_btn.click()
            time.sleep(3)
            
            # Handle device registration if needed
            try:
                device_reg_btn = driver.find_element(By.CSS_SELECTOR, "#new\\.save")
                if device_reg_btn.is_displayed():
                    driver.execute_script("arguments[0].click();", device_reg_btn)
                    time.sleep(2)
                    print("Device registered successfully")
            except:
                pass
            
            return True
            
        except Exception as e:
            print(f"Error during login: {e}")
            return False
    
    def post_to_naver_blog(self, title, content, tags, content_type):
        """Post to Naver blog using the new editor workflow"""
        driver = None
        try:
            driver = webdriver.Chrome(options=self.chrome_options)
            driver.implicitly_wait(10)
            
            # Login to Naver
            if not self.login_naver(driver):
                return False
            
            # Navigate to blog editor
            blog_url = f"https://blog.naver.com/{self.blog_id}/postwrite"
            driver.get(blog_url)
            time.sleep(5)
            
            # Close help dialog if exists
            try:
                close_selectors = [
                    "button.se-help-close",
                    "button.close",
                    "button[aria-label='닫기']",
                    "button[title='닫기']"
                ]
                
                for selector in close_selectors:
                    try:
                        close_btn = driver.find_element(By.CSS_SELECTOR, selector)
                        if close_btn.is_displayed():
                            close_btn.click()
                            time.sleep(1)
                            print("Closed help dialog")
                            break
                    except:
                        continue
            except:
                pass
            
            # Input title
            try:
                print("Inputting title...")
                
                # Find first contenteditable div (usually title)
                title_element = driver.find_element(By.CSS_SELECTOR, "#SE-1a46ef9f-4595-4548-9376-0819dca2428f")
                title_element.click()
                time.sleep(0.5)
                
                # Use pyperclip to paste title
                pyperclip.copy(title)
                time.sleep(0.3)
                pyautogui.hotkey('ctrl', 'v')
                time.sleep(0.5)
                
                print("Title input complete")
                
            except Exception as e:
                print(f"Error with title input: {e}")
            
            # Input content
            try:
                print("Inputting content...")
                
                # Press Tab to move to content area
                pyautogui.press('tab')
                time.sleep(0.5)
                
                # Paste content
                pyperclip.copy(content)
                time.sleep(0.3)
                pyautogui.hotkey('ctrl', 'v')
                time.sleep(1)
                
                print("Content input complete")
                
            except Exception as e:
                print(f"Error with content input: {e}")
            
            # Wait before publishing
            time.sleep(2)
            
            # Step 1: Click publish button to open publish dialog
            try:
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(1)
                
                publish_btn = driver.find_element(By.CSS_SELECTOR, "button.publish_btn__m9KHH")
                driver.execute_script("arguments[0].click();", publish_btn)
                time.sleep(2)
                print("Opened publish dialog")
                
            except Exception as e:
                print(f"Error opening publish dialog: {e}")
                return False
            
            # Step 2: Click category dropdown
            try:
                category_dropdown = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "#root > div > div.header__Ceaap > div > div.publish_btn_area__KjA2i > div:nth-child(2) > div > div > div > div.option_category___kpJc > div > div > button"))
                )
                category_dropdown.click()
                time.sleep(1)
                print("Opened category dropdown")
            except Exception as e:
                print(f"Error opening category dropdown: {e}")
            
            # Step 3: Select category based on content type
            try:
                if content_type == 'job':
                    category_selector = "#root > div > div.header__Ceaap > div > div.publish_btn_area__KjA2i > div:nth-child(2) > div > div > div > div.option_category___kpJc > div > div > div:nth-child(3) > div > ul > li:nth-child(5) > span > label"
                elif content_type == 'facility':
                    category_selector = "#root > div > div.header__Ceaap > div > div.publish_btn_area__KjA2i > div:nth-child(2) > div > div > div > div.option_category___kpJc > div > div > div:nth-child(3) > div > ul > li:nth-child(4) > span > label"
                elif content_type == 'culture':
                    category_selector = "#root > div > div.header__Ceaap > div > div.publish_btn_area__KjA2i > div:nth-child(2) > div > div > div > div.option_category___kpJc > div > div > div:nth-child(3) > div > ul > li:nth-child(5) > span > label"
                else:
                    # Default to first category if type is unknown
                    category_selector = "#root > div > div.header__Ceaap > div > div.publish_btn_area__KjA2i > div:nth-child(2) > div > div > div > div.option_category___kpJc > div > div > div:nth-child(3) > div > ul > li:nth-child(5) > span > label"
                
                category_element = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, category_selector))
                )
                category_element.click()
                time.sleep(1)
                print(f"Selected {content_type} category")
            except Exception as e:
                print(f"Error selecting category: {e}")
            
            # Step 4: Add tags
            try:
                tag_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#tag-input"))
                )
                
                tag_input.click()
                time.sleep(0.5)
                
                for tag in tags:
                    pyperclip.copy(tag)
                    time.sleep(0.3)
                    pyautogui.hotkey('ctrl', 'v')
                    time.sleep(0.3)
                    pyautogui.press('enter')
                    time.sleep(0.5)
                    
                print("Tags added successfully")
            except Exception as e:
                print(f"Error adding tags: {e}")
            
            # Step 5: Click final publish button
            try:
                final_publish_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "#root > div > div.header__Ceaap > div > div.publish_btn_area__KjA2i > div:nth-child(2) > div > div > div > div.layer_btn_area__UzyKH > div > button"))
                )
                final_publish_btn.click()
                time.sleep(3)
                print(f"Successfully posted: {title}")
                return True
            except Exception as e:
                print(f"Error clicking final publish button: {e}")
                return False
                
        except Exception as e:
            print(f"Error posting to blog: {e}")
            return False
        finally:
            if driver:
                driver.quit()
    
    def post_new_items(self, max_posts=1):
        """Check for new items and post them to Naver blog"""
        print("\n========== Starting post_new_items ==========")
        
        new_items = self.check_new_items()
        
        if not new_items:
            print("No new items to post")
            return
        
        print(f"\n=== Found {len(new_items)} new items to post ===")
        
        # Post only the first new item
        posts_made = 0
        for item_id, item_data in new_items:
            if posts_made >= max_posts:
                break
                
            print(f"\n=== Processing item from {item_data['FileName']} row {item_data['RowIndex']} ===")
            
            try:
                title, content, tags = self.format_post(item_data)
                content_type = item_data.get('ContentType', 'general')
                
                print(f"Formatted title: {title}")
                print(f"Content type: {content_type}")
                print(f"Tags: {tags}")
                
                # Post to blog
                success = self.post_to_naver_blog(title, content, tags, content_type)
                
                if success:
                    # Mark as posted in CSV file
                    self.mark_as_posted(item_data['FileName'], item_data['RowIndex'])
                    
                    # Save to posted items file
                    self.posted_items.add(item_id)
                    self.save_posted_items()
                    
                    print(f"\n✅ Successfully posted: {title}")
                    posts_made += 1
                else:
                    print(f"\n❌ Failed to post: {title}")
                    
            except Exception as e:
                print(f"\n❌ Error processing item: {e}")
                import traceback
                traceback.print_exc()
    
    def run_continuous(self, check_interval=3600):
        """Run continuously, checking for new items periodically"""
        print(f"Starting continuous posting service...")
        print(f"Checking every {check_interval} seconds for new items")
        
        while True:
            try:
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking for new items...")
                self.post_new_items(max_posts=1)
                
                print(f"Next check in {check_interval} seconds...")
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                print("\nStopping posting service...")
                break
            except Exception as e:
                print(f"Error in continuous run: {e}")
                print(f"Retrying in {check_interval} seconds...")
                time.sleep(check_interval)


# Main execution
if __name__ == "__main__":
    # Load configuration from .env file
    NAVER_ID = os.getenv('NAVER_ID')
    NAVER_PW = os.getenv('NAVER_PW')
    BLOG_ID = os.getenv('BLOG_ID')
    
    # Check if all required environment variables are set
    if not all([NAVER_ID, NAVER_PW, BLOG_ID]):
        print("Error: Missing required environment variables!")
        print("Please create a .env file with the following variables:")
        print("NAVER_ID=your_naver_id")
        print("NAVER_PW=your_naver_password")
        print("BLOG_ID=your_blog_id")
        exit(1)
    
    # Create poster instance
    poster = NaverBlogPoster(
        naver_id=NAVER_ID,
        naver_pw=NAVER_PW,
        blog_id=BLOG_ID
    )
    
    # Option 1: Post new items once (one row at a time)
    poster.post_new_items(max_posts=1)
    
    # Option 2: Run continuously
    # poster.run_continuous(check_interval=3600)  # Check every hour