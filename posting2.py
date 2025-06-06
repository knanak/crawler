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
        
        # Check specific CSV file
        csv_file = 'seoul_job.csv'
        print(f"Looking for file: {csv_file}")
        print(f"Current directory: {os.getcwd()}")
        
        if os.path.exists(csv_file):
            print(f"File {csv_file} exists!")
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
                        print(f"Failed to read with {encoding}: {e}")
                        continue
                
                if df is None:
                    raise Exception("Could not read CSV with any encoding")
                
                print(f"\n=== Reading CSV file: {csv_file} ===")
                print(f"Total rows in CSV: {len(df)}")
                print(f"Columns: {', '.join(df.columns.tolist())}")
                
                # Print first row to debug
                if len(df) > 0:
                    print("\nFirst row data:")
                    first_row = df.iloc[0]
                    for col in df.columns:
                        print(f"  {col}: {first_row[col]}")
                
                # Add 'Post' column if it doesn't exist
                if 'Post' not in df.columns:
                    df['Post'] = ''
                    # Save with the same encoding that worked
                    df.to_csv(csv_file, index=False, encoding='utf-8-sig')
                    print("Added 'Post' column to CSV")
                
                # Determine content type based on filename
                content_type = self.get_content_type(csv_file)
                print(f"Content type: {content_type}")
                
                # Count items not yet posted
                not_posted_count = 0
                
                for idx, item in df.iterrows():
                    # Check if this item has been posted (Post column is not 'Y')
                    if pd.isna(item.get('Post')) or str(item.get('Post')).strip().upper() != 'Y':
                        not_posted_count += 1
                        item_dict = item.to_dict()
                        item_dict['ContentType'] = content_type
                        item_dict['FileName'] = csv_file
                        item_dict['RowIndex'] = idx  # Store row index for updating later
                        
                        # Create unique item ID
                        item_id = self.create_unique_id(item, csv_file)
                        new_items.append((item_id, item_dict))
                
                print(f"\nItems not yet posted: {not_posted_count}")
                print(f"Items already posted: {len(df) - not_posted_count}")
                        
            except Exception as e:
                print(f"Error reading {csv_file}: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"File {csv_file} not found in current directory: {os.getcwd()}")
        
        print(f"=== Finished check_new_items, found {len(new_items)} items ===\n")
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
        # Use available columns to create a unique identifier
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
        # Print CSV data for debugging
        print("\n=== CSV Data to be posted ===")
        print(f"File: {job_data.get('FileName', 'Unknown')}")
        print(f"Row Index: {job_data.get('RowIndex', 'Unknown')}")
        
        # Title from CSV 'Title' column - handle encoding properly
        title = job_data.get('Title', '제목 없음')
        
        # Try to fix encoding if it's corrupted
        if isinstance(title, str):
            try:
                # If the string is already corrupted, try to decode it
                if '�' in title or any(ord(c) > 65000 for c in title):
                    # This might be a cp949 or euc-kr string incorrectly decoded
                    # Use fallback title
                    print(f"Encoding issue detected in title: {repr(title)}")
                    title = f"채용정보 #{job_data.get('RowIndex', 0) + 1}"
                    print(f"Using fallback title: {title}")
            except:
                title = f"채용정보 #{job_data.get('RowIndex', 0) + 1}"
        
        # Ensure title is properly encoded
        title = str(title).strip()
        
        print(f"Final Title: {title}")
        
        # Create content from all CSV data
        content = "<div style='font-family: \"Noto Sans KR\", sans-serif; line-height: 1.8; padding: 20px;'>"
        content += "<h2 style='color: #2E86AB; border-bottom: 2px solid #2E86AB; padding-bottom: 10px; margin-bottom: 20px;'>📋 상세 정보</h2>"
        content += "<table style='width: 100%; border-collapse: collapse; background-color: #f8f9fa; border-radius: 10px;'>"
        
        # Add all CSV data as table rows
        for key, value in job_data.items():
            # Skip internal fields
            if key not in ['ContentType', 'FileName', 'RowIndex', 'Post']:
                # Clean up the key name for display
                display_key = key.replace('_', ' ').title()
                
                # Handle encoding for values too
                if isinstance(value, str) and ('�' in str(value) or any(ord(c) > 65000 for c in str(value))):
                    display_value = '정보 확인 필요'
                else:
                    display_value = str(value) if pd.notna(value) else '정보 없음'
                    
                content += f"""
                <tr style='border-bottom: 1px solid #ddd;'>
                    <td style='padding: 12px; font-weight: bold; width: 30%; background-color: #e9ecef;'>{display_key}</td>
                    <td style='padding: 12px;'>{display_value}</td>
                </tr>
                """
        
        content += "</table>"
        content += "</div>"
        
        tags = ['노인일자리', '노인고용', '노인구직', '시니어일자리', '시니어고용', '시니어구직']
        
        print(f"Tags to be added: {', '.join(tags)}")
        
        return title, content, tags
    
    def format_facility_post(self, facility_data):
        """Format facility data into a blog post"""
        title = f"[복지시설 정보] {facility_data.get('Name', facility_data.get('Title', '시설명 없음'))}"
        
        content = f"""
<div style="font-family: 'Noto Sans KR', sans-serif; line-height: 1.8; padding: 20px;">
    <h2 style="color: #2E86AB; border-bottom: 2px solid #2E86AB; padding-bottom: 10px;">
        🏥 {facility_data.get('Name', facility_data.get('Title', '시설명 없음'))}
    </h2>
    
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0;">
        <h3 style="color: #333; margin-bottom: 15px;">📋 시설 정보</h3>
        <p>노인복지시설 정보를 제공합니다.</p>
    </div>
</div>
"""
        
        tags = ['노인복지정책', '노인정책', '노인복지정보', '시니어복지정책', '시니어정책', 
                '시니어복지정보', '장기요양기관추천', '방문요양센터추천', '복지관추천', 
                '노인교실추천', '경로당추천']
        
        return title, content, tags
    
    def format_culture_post(self, culture_data):
        """Format culture data into a blog post"""
        title = f"[문화프로그램] {culture_data.get('Title', culture_data.get('Name', '프로그램명 없음'))}"
        
        content = f"""
<div style="font-family: 'Noto Sans KR', sans-serif; line-height: 1.8; padding: 20px;">
    <h2 style="color: #2E86AB; border-bottom: 2px solid #2E86AB; padding-bottom: 10px;">
        🎭 {culture_data.get('Title', culture_data.get('Name', '프로그램명 없음'))}
    </h2>
    
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0;">
        <h3 style="color: #333; margin-bottom: 15px;">📋 프로그램 정보</h3>
        <p>노인 문화프로그램 정보를 제공합니다.</p>
    </div>
</div>
"""
        
        tags = ['문화프로그램', '노인여가', '시니어여가']
        
        return title, content, tags
    
    def format_general_post(self, data):
        """Format general data into a blog post"""
        title = f"[정보] {data.get('Title', data.get('Name', '제목 없음'))}"
        
        content = f"""
<div style="font-family: 'Noto Sans KR', sans-serif; line-height: 1.8; padding: 20px;">
    <h2 style="color: #2E86AB; border-bottom: 2px solid #2E86AB; padding-bottom: 10px;">
        📌 {data.get('Title', data.get('Name', '제목 없음'))}
    </h2>
    
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0;">
        <p>상세 정보를 제공합니다.</p>
    </div>
</div>
"""
        
        tags = ['정보', '노인', '시니어']
        
        return title, content, tags
    
    def login_naver(self, driver):
        """Login to Naver"""
        try:
            # Navigate to Naver login page
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
            time.sleep(5)  # Wait longer for editor to fully load
            
            # Close help dialog
            try:
                # Try multiple possible close button selectors
                close_selectors = [
                    "#SE-a20eda71-d0e9-4f9c-9555-362ea3f7d944 > div.se-wrap.se-dnd-wrap > div > div.se-container > article > div > header > button",
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
            
            # Input title - find by placeholder text "제목"
            try:
                print("Attempting to input title...")
                
                # Title is already cleaned in format_job_post method
                title_to_use = title
                
                print(f'Title to input: {repr(title_to_use)}')
                
                # Wait for page to be fully loaded
                time.sleep(3)
                
                try:
                    # Method 1: Find element containing "제목" text using XPath
                    title_element = driver.find_element(By.CSS_SELECTOR, "#SE-1a46ef9f-4595-4548-9376-0819dca2428f")
                    
                    # Get the parent element that's clickable
                    # parent = title_element.find_element(By.XPATH, "./ancestor::*[@contenteditable='true' or contains(@class, 'se-')]")
                    
                    # # Click on the element
                    # action = ActionChains(driver)
                    # action.move_to_element(parent).pause(1).click().perform()
                    # time.sleep(0.5)
                    
                    # Copy and paste title
                    pyperclip.copy(title_element)
                    time.sleep(0.3)
                    pyautogui.hotkey('ctrl', 'v')
                    time.sleep(0.5)
                    
                    print("제목 작성 완료 (found by text)")
                    
                except Exception as e:
                    print(f"Finding title by text failed: {e}")
                    
                    # Method 2: Find by placeholder span containing "제목"
                    try:
                        title_placeholder = driver.find_element(By.XPATH, "//span[contains(@class, 'se-placeholder') and contains(text(), '제목')]")
                        title_placeholder.click()
                        time.sleep(0.5)
                        
                        pyperclip.copy(title_to_use)
                        time.sleep(0.3)
                        pyautogui.hotkey('ctrl', 'v')
                        
                        print("제목 작성 완료 (placeholder method)")
                        
                    except Exception as e2:
                        print(f"Placeholder method failed: {e2}")
                        
                        # Method 3: Find first contenteditable
                        try:
                            first_editable = driver.find_element(By.CSS_SELECTOR, "div[contenteditable='true']")
                            first_editable.click()
                            time.sleep(0.5)
                            
                            pyperclip.copy(title_to_use)
                            pyautogui.hotkey('ctrl', 'v')
                            
                            print("제목 작성 완료 (first contenteditable)")
                        except:
                            print("All title input methods failed")
                
                time.sleep(1)
                
            except Exception as e:
                print(f"Error with title input: {e}")
                import traceback
                traceback.print_exc()
            
            # Input content - find by placeholder text "나만의 일상을"
            try:
                print("Attempting to input content...")
                print(f"Content preview: {content[:50]}...")
                time.sleep(1)
                
                try:
                    # Method 1: Find element containing "나만의 일상을" text using XPath
                    content_element = driver.find_element(By.XPATH, "//*[contains(text(), '나만의 일상을')]")
                    
                    # Get the parent element that's clickable
                    parent = content_element.find_element(By.XPATH, "./ancestor::*[@contenteditable='true' or contains(@class, 'se-')]")
                    
                    # Click on the element
                    action = ActionChains(driver)
                    action.move_to_element(parent).pause(1).click().perform()
                    time.sleep(0.5)
                    
                    # Copy content to clipboard
                    pyperclip.copy(content)
                    time.sleep(0.5)
                    
                    # Paste content
                    pyautogui.hotkey('ctrl', 'v')
                    time.sleep(1)
                    
                    print("Content input successful (found by text)")
                    
                except Exception as e:
                    print(f"Finding content by text failed: {e}")
                    
                    # Method 2: Find by placeholder span containing "나만의 일상을"
                    try:
                        content_placeholder = driver.find_element(By.XPATH, "//span[contains(@class, 'se-placeholder') and contains(text(), '나만의 일상을')]")
                        content_placeholder.click()
                        time.sleep(0.5)
                        
                        pyperclip.copy(content)
                        time.sleep(0.3)
                        pyautogui.hotkey('ctrl', 'v')
                        
                        print("Content input successful (placeholder method)")
                        
                    except Exception as e2:
                        print(f"Content placeholder method failed: {e2}")
                        
                        # Method 3: Find second contenteditable or use Tab
                        try:
                            # Try to find all contenteditable divs
                            content_editables = driver.find_elements(By.CSS_SELECTOR, "div[contenteditable='true']")
                            
                            if len(content_editables) > 1:
                                # Second one should be content
                                content_editables[1].click()
                                time.sleep(0.5)
                            else:
                                # Press Tab from title to content
                                pyautogui.press('tab')
                                time.sleep(0.5)
                            
                            pyperclip.copy(content)
                            time.sleep(0.3)
                            pyautogui.hotkey('ctrl', 'v')
                            
                            print("Content input successful (contenteditable/tab method)")
                            
                        except Exception as e3:
                            print(f"Alternative content method failed: {e3}")
                            
                            # Final fallback - JavaScript
                            try:
                                driver.execute_script("""
                                    // Find element with "나만의 일상을" text
                                    var elements = document.evaluate("//*[contains(text(), '나만의 일상을')]", 
                                        document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                                    if (elements) {
                                        var parent = elements.closest('[contenteditable="true"]');
                                        if (parent) {
                                            parent.focus();
                                            parent.innerHTML = arguments[0];
                                        }
                                    } else {
                                        // Fallback to second contenteditable
                                        var editables = document.querySelectorAll('div[contenteditable="true"]');
                                        if (editables.length > 1) {
                                            editables[1].focus();
                                            editables[1].innerHTML = arguments[0];
                                        }
                                    }
                                """, content)
                                print("Content input with JavaScript")
                            except:
                                print("All content input methods failed")
                
                time.sleep(1)
                
            except Exception as e:
                print(f"Error with content input: {e}")
                import traceback
                traceback.print_exc()
            
            # Wait a bit before trying to publish
            time.sleep(2)
            
            # Step 1: Click publish button to open publish page
            try:
                # Scroll to top to ensure publish button is visible
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(1)
                
                # Try multiple selectors for publish button
                publish_selectors = [
                    "button.publish_btn__m9KHH",
                    "button[class*='publish_btn']",
                    "#root > div > div.header__Ceaap > div > div.publish_btn_area__KjA2i > div:nth-child(2) > button",
                    "button:contains('발행')"
                ]
                
                publish_btn = None
                for selector in publish_selectors:
                    try:
                        if selector.endswith("('발행')"):
                            # Use XPath for text content
                            publish_btn = driver.find_element(By.XPATH, "//button[contains(text(), '발행')]")
                        else:
                            publish_btn = driver.find_element(By.CSS_SELECTOR, selector)
                        if publish_btn and publish_btn.is_displayed():
                            break
                    except:
                        continue
                
                if publish_btn:
                    driver.execute_script("arguments[0].click();", publish_btn)
                    time.sleep(2)
                    print("Opened publish page")
                else:
                    print("Could not find publish button")
                    return False
                    
            except Exception as e:
                print(f"Error opening publish page: {e}")
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
                    category_selector = "#root > div > div.header__Ceaap > div > div.publish_btn_area__KjA2i > div:nth-child(2) > div > div > div > div.option_category___kpJc > div > div > div:nth-child(3) > div > ul > li:nth-child(3) > span > label"
                elif content_type == 'facility':
                    category_selector = "#root > div > div.header__Ceaap > div > div.publish_btn_area__KjA2i > div:nth-child(2) > div > div > div > div.option_category___kpJc > div > div > div:nth-child(3) > div > ul > li:nth-child(4) > span > label"
                elif content_type == 'culture':
                    category_selector = "#root > div > div.header__Ceaap > div > div.publish_btn_area__KjA2i > div:nth-child(2) > div > div > div > div.option_category___kpJc > div > div > div:nth-child(3) > div > ul > li:nth-child(5) > span > label"
                else:
                    category_selector = "#root > div > div.header__Ceaap > div > div.publish_btn_area__KjA2i > div:nth-child(2) > div > div > div > div.option_category___kpJc > div > div > div:nth-child(3) > div > ul > li:nth-child(3) > span > label"
                
                category_element = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, category_selector))
                )
                category_element.click()
                time.sleep(1)
                print(f"Selected {content_type} category")
            except Exception as e:
                print(f"Error selecting category: {e}")
            
            # Step 4: Add tags - using pyperclip and pyautogui
            try:
                tag_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#tag-input"))
                )
                
                # Click on tag input field
                tag_input.click()
                time.sleep(0.5)
                
                for tag in tags:
                    # Copy tag to clipboard
                    pyperclip.copy(tag)
                    time.sleep(0.3)
                    
                    # Paste tag
                    pyautogui.hotkey('ctrl', 'v')
                    time.sleep(0.3)
                    
                    # Press Enter to add tag
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
    
    def post_new_items(self, max_posts=5):
        """Check for new items and post them to Naver blog"""
        print("\n========== Starting post_new_items ==========")
        
        new_items = self.check_new_items()
        
        if not new_items:
            print("No new items to post")
            return
        
        print(f"\n=== Found {len(new_items)} new items to post ===")
        
        # Post only the first new item (one row at a time)
        if new_items:
            item_id, item_data = new_items[0]
            
            print(f"\n=== Processing item from row {item_data['RowIndex']} ===")
            print(f"Item data keys: {item_data.keys()}")
            print(f"Title field value: {item_data.get('Title', 'NO TITLE FIELD')}")
            
            try:
                title, content, tags = self.format_post(item_data)
                content_type = item_data.get('ContentType', 'general')
                
                print(f"\n=== Formatted data ===")
                print(f"Title: {title}")
                print(f"Content length: {len(content)}")
                print(f"Content preview: {content[:100]}...")
                print(f"Tags: {tags}")
                
                # Post to blog
                success = self.post_to_naver_blog(title, content, tags, content_type)
                
                if success:
                    # Mark as posted in CSV file
                    self.mark_as_posted(item_data['FileName'], item_data['RowIndex'])
                    
                    # Also save to posted items file (optional backup)
                    self.posted_items.add(item_id)
                    self.save_posted_items()
                    
                    print(f"\n✅ Successfully posted item: {title}")
                else:
                    print(f"\n❌ Failed to post item: {title}")
                    
            except Exception as e:
                print(f"\n❌ Error processing item {item_id}: {e}")
                import traceback
                traceback.print_exc()
    
    def run_continuous(self, check_interval=3600):
        """Run continuously, checking for new items periodically"""
        print(f"Starting continuous posting service...")
        print(f"Checking every {check_interval} seconds for new items")
        
        while True:
            try:
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking for new items...")
                self.post_new_items(max_posts=1)  # Post one item at a time
                
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