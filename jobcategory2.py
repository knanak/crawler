import pandas as pd
import re

# CSV 파일 읽기
df = pd.read_csv(r"C:\crawler\job_data.csv")

# jobCategories 기반 키워드 매핑 딕셔너리
keyword_mapping = {
    # 돌봄·간병 종사자
    '돌봄·간병 종사자': ['요양보호사', '요양보호', '노인요양', '재가요양', '간병인', '간병', '간호조무사', '간호조무'],
    
    # 아이돌보미
    '아이돌보미': ['베이비시터', '육아도우미', '산후도우미', '보육도우미', '아이돌봄', '가사도우미', '가정도우미', '가정부', '파출부'],
    
    # 시설·설비 관리원
    '시설·설비 관리원': ['건물관리', '시설관리', '빌딩관리', '관리소장', '시설물관리', '건물보수', '시설보수', '영선', 
                     '전기관리', '전기안전', '전기기사', '건축설비', '설비기술', '기계정비', '설비정비', '기계수리'],
    
    # 교육 종사자
    '교육 종사자': ['방과후', '방과후교사', '특기교사', '강사', '교사', '시니어강사', '교육'],
    
    # 사회복지사
    '사회복지사': ['사회복지사', '사회복지', '복지사'],
    
    # 환경미화원
    '환경미화원': ['환경미화', '가로미화', '거리미화', '청소원', '청소', '미화원', '미화', '룸메이드', '하우스키퍼'],
    
    # 경비원
    '경비원': ['경비원', '경비', '시설경비', '건물경비', '아파트경비', '보안요원', '경호원', '보안관', 
              '보안관제', 'cctv관제', '관제요원'],
    
    # 운전원
    '운전원': ['버스운전', '시내버스', '마을버스', '통근버스', '관광버스', '택시운전', '개인택시', '법인택시',
             '배송운전', '배달', '택배', '납품운전', '화물운전', '승합차운전', '승합차', '봉고차'],
    
    # 서비스직 종사자
    '서비스직 종사자': ['배식', '서빙', '홀서빙', '접객', '카운터', '음식서비스', '서비스', '단순서비스', 
                   '조리사', '조리원', '급식조리', '주방장', '조리장', '주방보조', '조리보조', '급식보조', '주방도우미'],
    
    # 사무직원
    '사무직원': ['사무', '행정', '사무원', '사서', '안내', '영업지원', '영업사무', '영업관리', 
               '품질관리', '품질검사', '검사원', '총무', '사감', '기숙사'],
    
    # 약국 사무원
    '약국 사무원': ['약국사무', '약국', '의료사무', '보건', '의료지원', '병원지원'],
    
    # 도보 배달원
    '도보 배달원': ['도보배달', '배달', '배송']
}

# 기타 카테고리 (jobCategories에는 없지만 기존 데이터에 있는 것들)
other_categories = {
    '건설 단순 종사원': ['건설현장', '건설단순', '건설일용', '노무', '잡부'],
    '주차 관리원': ['주차관리', '주차안내', '주차요원'],
    '방역원': ['방역', '소독', '방제', '해충퇴치'],
    '산업 안전원': ['안전관리', '산업안전', '안전요원'],
    '건설수주 영업원': ['건설영업', '건설수주'],
    '미디어 콘텐츠 디자이너': ['디자이너', '콘텐츠', '미디어디자인']
}

# 전체 키워드 매핑 합치기
all_keyword_mapping = {**keyword_mapping, **other_categories}

def clean_date_field(value):
    """날짜 필드 정리 함수"""
    if pd.isna(value) or value == "Not found":
        return ""
    
    # 문자열로 변환
    value = str(value)
    
    # '등록일 : ' 또는 '등록일:' 제거
    value = value.replace('등록일 : ', '').replace('등록일:', '').replace('등록일 :', '')
    
    # '마감일 : ' 또는 '마감일:' 제거
    value = value.replace('마감일 : ', '').replace('마감일:', '').replace('마감일 :', '')
    
    # 앞뒤 공백 제거
    return value.strip()

def clean_not_found(value):
    """Not found를 공백으로 처리하는 함수"""
    if pd.isna(value) or value == "Not found":
        return ""
    return value

def extract_category_from_employment_type(employment_type):
    """EmploymentType에서 카테고리를 추출하는 함수"""
    if pd.isna(employment_type) or employment_type == "Not found":
        return None
    
    # 소문자로 변환하여 비교
    employment_type_lower = employment_type.lower()
    
    # 각 카테고리의 키워드를 확인
    for category, keywords in all_keyword_mapping.items():
        for keyword in keywords:
            if keyword in employment_type_lower:
                return category
    
    # 매칭되는 카테고리가 없는 경우 None 반환
    return None

def update_job_category(row):
    """JobCategory를 업데이트하는 함수"""
    current_category = row['JobCategory']
    employment_type = row['EmploymentType']
    
    # JobCategory가 비어있거나 "Not found"인 경우
    if pd.isna(current_category) or current_category == "Not found" or current_category == "":
        # EmploymentType에서 카테고리 추출
        extracted_category = extract_category_from_employment_type(employment_type)
        if extracted_category:
            return extracted_category
    
    # 기존 값 유지
    return current_category

# 업데이트 전 상태 확인
print("업데이트 전:")
print(f"JobCategory가 비어있거나 'Not found'인 행 수: {df[df['JobCategory'].isna() | (df['JobCategory'] == 'Not found') | (df['JobCategory'] == '')].shape[0]}")

# DateOfRegistration과 Deadline 정리
df['DateOfRegistration'] = df['DateOfRegistration'].apply(clean_date_field)
df['Deadline'] = df['Deadline'].apply(clean_date_field)

# 모든 "Not found" 값을 공백으로 처리
for column in df.columns:
    df[column] = df[column].apply(clean_not_found)

# JobCategory 업데이트
df['JobCategory'] = df.apply(update_job_category, axis=1)

# 업데이트 후 상태 확인
print("\n업데이트 후:")
print(f"JobCategory가 비어있거나 'Not found'인 행 수: {df[df['JobCategory'].isna() | (df['JobCategory'] == 'Not found') | (df['JobCategory'] == '')].shape[0]}")

# 날짜 필드 확인 (처음 10개)
print("\n날짜 필드 정리 확인:")
print("DateOfRegistration 샘플:")
print(df['DateOfRegistration'].head(10))
print("\nDeadline 샘플:")
print(df['Deadline'].head(10))

# 업데이트된 예시 확인
print("\n업데이트된 예시 (처음 20개):")
updated_rows = df[df['JobCategory'].notna() & (df['JobCategory'] != 'Not found') & (df['JobCategory'] != '')]
print(updated_rows[['EmploymentType', 'JobCategory', 'DateOfRegistration', 'Deadline']].head(20))

# 카테고리별 개수 확인
print("\nJobCategory 값별 개수:")
category_counts = df['JobCategory'].value_counts()
print(category_counts.head(20))

# jobCategories에 있는 카테고리만 필터링해서 확인
print("\njobCategories 카테고리별 개수:")
job_categories_list = list(keyword_mapping.keys())
for category in job_categories_list:
    count = category_counts.get(category, 0)
    print(f"{category}: {count}")

# CSV 파일로 저장
df.to_csv('job_data_with_updated_category.csv', index=False, encoding='utf-8-sig')
print("\n'job_data_with_updated_category.csv' 파일로 저장되었습니다.")

# 여전히 카테고리가 없는 EmploymentType 확인 (디버깅용)
no_category = df[(df['JobCategory'].isna()) | (df['JobCategory'] == 'Not found') | (df['JobCategory'] == '')]
if not no_category.empty:
    print("\n카테고리가 할당되지 않은 EmploymentType 예시:")
    print(no_category['EmploymentType'].value_counts().head(10))

# "Not found" 값이 남아있는지 확인
print("\n'Not found' 값 확인:")
for column in df.columns:
    not_found_count = (df[column] == "Not found").sum()
    if not_found_count > 0:
        print(f"{column}: {not_found_count}개의 'Not found' 값이 있습니다.")