# -*- coding: utf-8 -*-

# ==========================================
# 필요한 라이브러리 임포트
# ==========================================
import pandas as pd
import re
import json
from datetime import datetime
import os
import time
import csv
from dotenv import load_dotenv

# Selenium 관련
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from langchain_google_genai import GoogleGenerativeAIEmbeddings

# .env 파일에서 환경 변수 로드 (GOOGLE_API_KEY 등)
load_dotenv()


# ==========================================
# 0. 지역-기관 사전 
# ==========================================
REGION_CENTERS = {
    "서울특별시": ["서울 문래", "서울 상생", "서울 창신", "서울 광진", "서울 봉익", "서울 장위", "서울"],
    "경기도": ["파주", "포천 가산", "시흥 정왕", "동탄", "안양", "고양 장항", "군포 당정", "성남 상대원", "시흥 대야", "부천 신흥", "화성 향남", "용인영덕", "경기"],
    "인천광역시": ["인천 송림", "인천"],
    "부산광역시": ["부산 서동", "부산범천", "부산 범일", "부산 범천", "부산"],
    "대구광역시": ["대구 노원", "대구 대봉", "대구 성내", "대구"],
    "광주광역시": ["광주 충장", "광주 서남"],
    "대전광역시": ["대전 덕암", "대전 오정", "대전 정동", "대전"],
    "강원특별자치도": ["영월", "강원"],
    "충청북도": ["청주 중앙", "충북"],
    "충청남도": ["충남 금산", "공주", "충남"],
    "전북특별자치도": ["전북 상생", "전주 팔복", "순창", "전북"],
    "전라남도": ["무안", "전남"],
    "경상남도": ["경남 상생", "김해 진례", "경남"],
    "경상북도": ["경북"], "울산광역시": ["울산"], "세종특별자치시": ["세종"], "제주특별자치도": ["제주"]
}
region_centers = REGION_CENTERS


# ==========================================
# 1. 크롤링 관련 함수
# ==========================================

def setup_driver():
    """Selenium WebDriver를 설정하고 반환합니다."""
    print("WebDriver 설정 중...")
    download_dir = os.path.abspath("downloads_final")
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    options = webdriver.ChromeOptions()
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "profile.default_content_settings.popups": 0,
        "profile.default_content_setting_values.automatic_downloads": 1,
        "plugins.always_open_pdf_externally": True
    }
    options.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(options=options)
    driver.get("https://www.sbiz24.kr/#/combinePbancList")
    time.sleep(2)
    driver.maximize_window()
    print("WebDriver 설정 완료.")
    return driver

def set_initial_conditions(driver):
    """초기 검색 조건을 설정합니다."""
    print("초기 검색 조건 설정 중...")
    try:
        # 필터 창이 없으면 열기
        if not driver.find_elements(By.CSS_SELECTOR, ".modal_style"):
            WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".f_rcrtTypeCdNmListDisplay button"))).click()
            time.sleep(2)

        # 버튼 클릭 (소상공인, 예비창업자 등)
        for idx in [1, 2, 3, 5]:
            btn = driver.find_element(By.CSS_SELECTOR, f".modal_style .option-area > button:nth-child({idx})")
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(0.1)

        # 선택완료 및 '마감 공고 제외' 체크
        driver.execute_script("arguments[0].click();", driver.find_element(By.CSS_SELECTOR, "div.modal_style div.btn-actions > button"))
        time.sleep(1)
        driver.execute_script("arguments[0].click();", driver.find_element(By.CSS_SELECTOR, "#container > div.sub-main-content > div.table-top-area > div > div > label"))
        time.sleep(1)
        print("초기 조건 설정 완료.")
    except Exception as e:
        print(f"조건 설정 중 오류 발생 : {e}")

def scrape_all_links(driver):
    """모든 페이지를 순회하며 공고 링크를 수집"""
    all_links = []
    page_count = 1
    print("\n전체 페이지 공고 링크 수집 시작...")
    
    while True:
        print(f"📄 페이지 {page_count} 링크 읽는 중...")
        try:
            WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "td.c_pbancNm > a")))
            elements = driver.find_elements(By.CSS_SELECTOR, "td.c_pbancNm > a")
            
            count_in_page = 0
            for el in elements:
                link = el.get_attribute("href")
                try: # '대출상품'인 경우 URL 주소 변경
                    if "대출상품" in el.find_element(By.XPATH, "./ancestor::tr").text and link and "pbanc" in link:
                        link = link.replace("pbanc", "loanProduct")
                except Exception: pass
                
                if link:
                    all_links.append(link)
                    count_in_page += 1
            print(f"   - {count_in_page}개 링크 확보.")

            # 다음 페이지 이동
            next_btn_li = driver.find_element(By.CSS_SELECTOR, "ul.pagination li.btn-next")
            if "disabled" in next_btn_li.get_attribute("class") or next_btn_li.find_element(By.TAG_NAME, "button").get_attribute("disabled"):
                print("마지막 페이지 도달.")
                break
            
            driver.execute_script("arguments[0].click();", next_btn_li.find_element(By.TAG_NAME, "button"))
            page_count += 1
            time.sleep(2)
        
        except Exception as e:
            print(f"페이지 순회 중 오류 발생, 수집 종료: {e}")
            break
            
    print(f"✅ 총 {len(all_links)}개 링크 수집 완료.\n")
    return all_links

def crawl_details_from_links(driver, target_links):
    """수집된 링크를 방문하여 상세 정보와 파일을 크롤링"""
    print(f"총 {len(target_links)}개 공고 상세 정보 수집 시작...\n")
    crawled_data = []
    main_window = driver.current_window_handle 

    for idx, link in enumerate(target_links):
        print(f"[{idx+1}/{len(target_links)}] 접속: {link}")
        try:
            driver.get(link)
            time.sleep(3) 

            try:
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#contents > div.u-page.cont-max")))
            except TimeoutException:
                print("본문 로딩 시간 초과 (건너뜀)")
                if len(driver.window_handles) > 1: # 팝업창 닫기
                    driver.switch_to.window(driver.window_handles[1])
                    driver.close()
                    driver.switch_to.window(main_window)
                continue

            title_text, content_body, file_names = "제목 없음", "본문 없음", []
            
            try:
                title_text = driver.find_element(By.CSS_SELECTOR, "#contents > div.page-header > h2").text.strip()
                if "소진공 공고조회" in title_text:
                    print(f"   ⏳ '{title_text}' 감지, 데이터 로딩을 위해 11초 대기...")
                    time.sleep(11)
            except:
                pass

            print("   상세 내용 및 파일 확인 중...")
            try:
                content_body = driver.find_element(By.CSS_SELECTOR, "#contents > div.u-page.cont-max").text
            except:
                pass

            files = driver.find_elements(By.CSS_SELECTOR, "div.file-group button")
            if files:
                print(f"      첨부파일 {len(files)}개 다운로드 시도...")
                for f in files:
                    try:
                        f_name = f.text.strip()
                        if not f_name: continue
                        file_names.append(f_name)
                        driver.execute_script("arguments[0].click();", f)
                        time.sleep(2)
                        
                        if len(driver.window_handles) > 1:
                            for handle in driver.window_handles:
                                if handle != main_window:
                                    driver.switch_to.window(handle)
                                    driver.close()
                            driver.switch_to.window(main_window)
                    except Exception:
                        pass
            
            crawled_data.append({
                "제목": title_text, "URL": link, "본문": content_body, "첨부파일": ", ".join(file_names)
            })
            print("   저장 완료")
        except Exception as e:
            print(f"   에러 발생 (건너뜀): {e}")

    return crawled_data


# ==========================================
# 2. 데이터 처리 및 가공 함수
# ==========================================

def get_val_from_body_data(data_dict, key, default="정보 없음"):
    """
    body_data 딕셔너리에서 값을 가지고 옴.
    값이 없거나 비어있는 경우(None, '-', 'nan', '') default 값을 반환.
    """
    val = data_dict.get(key)
    if val is None or str(val).strip() in ['-', '', 'nan']:
        return default
    return str(val).strip()


def parse_body(body_text):
    """
    '본문' 텍스트에서 주요 정보를 파싱하여 딕셔너리로 반환.
    대출상품 관련 상세 필드를 추가로 파싱.
    """
    if not isinstance(body_text, str):
        return {}

    patterns = {
        '공고명': r"공고명\n(.*?)\n",
        '지원대상': r"지원대상\n(.*?)\n",
        '소관기관': r"소관기관\n(.*?)\n",
        '지원분야(대)': r"지원분야\(대\)\n(.*?)\n",
        '지원분야(중)': r"지원분야\(중\)\n(.*?)\n",
        '사업수행기관': r"사업수행기관\n(.*?)\n",
        '문의처': r"문의처\n(.*?)\n",
        '신청기간': r"신청기간\n(.*?)\n",
        '공고내용': r"공고내용\n(.*?)\n(사업신청방법설명|첨부파일|$)", 
        '사업신청방법설명': r"사업신청방법설명\n(.*?)\n첨부파일",
        # Loan-specific fields
        '금리(%)': r"금리\(స్య\)\n(.*?)\n",
        '최대한도(만원)': r"최대한도\(만원\)\n(.*?)\n",
        '용도': r"용도\n(.*?)\n",
        '취급기관': r"취급기관\n(.*?)\n",
        '대출기간(년)': r"대출기간\(년\)\n(.*?)\n",
        '상환방법': r"상환방법\n(.*?)\n",
        '대출한도(만원)': r"대출한도\(만원\)\n(.*?)\n", 
        '총대출기간(년)': r"총대출기간\(년\)\n(.*?)\n",
        '금리(%)(금리구분)': r"금리\(స్య\)\(금리구분\)\n(.*?)\n",
        '지원대상 상세조건': r"지원대상 상세조건\n(.*?)\n",
        '소득기준': r"소득기준\n(.*?)\n",
        '신용조건': r"신용조건\n(.*?)\n",
        '연령대': r"연령대\n(.*?)\n",
        '특이사항': r"특이사항\n(.*?)\n",
        '제공기관/취급기관': r"제공기관/취급기관\n(.*?)\n",
        '신청(가입)방법': r"신청\(가입\)방법\n(.*?)\n",
        '중도상환수수료': r"중도상환수수료\n(.*?)\n",
        '대출부대비용': r"대출부대비용\n(.*?)\n",
        '연체이자율(%)': r"연체이자율\(స్య\)\n(.*?)\n",
        '우대/가산금리 조건': r"우대/가산금리 조건\n(.*?)\n",
        '기타 참고사항': r"기타 참고사항\n(.*?)\n",
        '관련사이트': r"관련사이트\n(.*?)\n",
        '운영기한': r"운영기한\n(.*?)\n",
        '금융상품명': r"(금융상품명|상품명)\n(.*?)\n"
    }
    
    data = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, body_text, re.DOTALL)
        if match:
            # '공고내용'
            if key == '공고내용':
                data[key] = match.group(1).strip()
            elif key == '금융상품명':
                data[key] = match.group(2).strip()
            else:
                data[key] = match.group(1).strip()
        else:
            data[key] = None
            
    # 지역 정보는 '공고명'에서 추출
    if data.get('공고명'):
        match = re.match(r'\[(.*?)\]', data['공고명'])
        if match:
            data['지역'] = match.group(1).strip()
        else:
            data['지역'] = '무관' # 기본값
            
    return data

def get_closing_info(period_text):
    """
    접수기간 텍스트를 분석하여 마감 타입과 파싱된 마감일을 반환.
    """
    if not isinstance(period_text, str):
        return "UNKNOWN", "2099-12-31"

    period_text = period_text.strip()
    if "예산 소진시" in period_text or "소진시까지" in period_text:
        return "BUDGET", "2099-12-31"
    if "상시" in period_text or "수시" in period_text:
        return "상시", "2099-12-31"
    
    match = re.search(r'~\s*(\d{4}[-.]\d{2}[-.]\d{2})', period_text)
    if match:
        try:
            end_date = match.group(1).replace('.', '-')
            datetime.strptime(end_date, '%Y-%m-%d')
            return "DATE", end_date
        except ValueError:
            return "DATE", "2099-12-31"
            
    return "UNKNOWN", "2099-12-31"

def create_policy_record(row):
    """
    데이터 행을 바탕으로 content 텍스트와 metadata 딕셔너리를 생성.
    카테고리별로 다른 로직을 적용.
    """
    category_from_csv = str(row['제목']) if pd.notna(row['제목']) else "기타"
    body_data = parse_body(row['본문'])

    
    def get_body_val(key, default="정보 없음"):
        return get_val_from_body_data(body_data, key, default)

    title = get_body_val('공고명', f"{category_from_csv} 정보")
    region = get_body_val('지역', '전국')
    target_main = get_body_val('지원대상', '전체')
    if category_from_csv == "대출상품 조회" and '본문' in row and pd.notna(row['본문']):
        body_text = str(row['본문'])
        match = re.search(r"지원대상요건\n대상\n(.*?)\n", body_text, re.DOTALL)
        if match:
            extracted_target = match.group(1).strip()
            if extracted_target:
                target_main = extracted_target

    period = get_body_val('신청기간', '별도 안내')
    
    # Metadata 
    metadata = {
        "url": str(row['URL']) if pd.notna(row['URL']) else "",
        "title": title,
        "region": region,
        "target": target_main,
        "category": category_from_csv,
        "closing_type": get_closing_info(period)[0],
        "parsed_end_date": get_closing_info(period)[1],
        "attachment": "1" if pd.notna(row['첨부파일']) and row['첨부파일'].strip() != "" else "0"
    }
    
    content = "" 

    if category_from_csv == "유관사업 공고조회":
        content_text = get_body_val('공고내용', '')
        content_text = " ".join(content_text.split())
        method = get_body_val('사업신청방법설명', '공고문 참조')
        contact = get_body_val('문의처', '문의처 확인 필요')
        
        # 항상 region_centers를 통해 지역을 표준화: 먼저 기존 region으로 시도, 실패하면 title로 시도
        found_region = False
        candidates = []
        try:
            if isinstance(region, str) and region.strip() not in ['', '정보 없음', '무관']:
                candidates.append(region.strip())
        except Exception:
            pass
        if isinstance(title, str) and title.strip() != '':
            candidates.append(title.strip())

        for candidate in candidates:
            for full_region, prefixes in region_centers.items():
                for prefix in prefixes:
                    if candidate.startswith(prefix) or prefix in candidate:
                        region = full_region
                        found_region = True
                        break
                if found_region:
                    break
            if found_region:
                break

        if not found_region:
            region = '무관'

        period_suffix = "입니다." if str(period).strip().endswith("까지") else "까지입니다."

        content = (
            f"이 공고의 제목은 '{title}'이며, 분류는 '{category_from_csv}'에 해당합니다. "
            f"주로 {region} 지역의 {target_main}을(를) 대상으로 지원합니다. "
            f"주요 공고 내용은 {content_text} 등이며, 접수 기간은 {period}{period_suffix} "
            f"신청 방법은 {method}을(를) 따르며, 자세한 문의처는 {contact}입니다."
        )

    elif category_from_csv == "소진공 공고조회":
        # '소진공 공고조회'의 경우 공고명에서 지역정보를 추출
        found_region = False
        for full_region, prefixes in region_centers.items():
            for prefix in prefixes:
                if title.startswith(prefix):
                    region = full_region
                    found_region = True
                    break
            if found_region:
                break
        
        
        if not found_region:
            region = '무관'

        if '본문' in row and pd.notna(row['본문']):
            body_text = str(row['본문'])
            match = re.search(r'모집유형\n(.*?)\n', body_text)
            if match:
                extracted_target = match.group(1).strip()
                if extracted_target:
                    target_main = extracted_target
                
        content_text = get_body_val('공고내용', '')
        content_text = " ".join(content_text.split())
        
        period_suffix = "입니다." if str(period).strip().endswith("까지") else "까지입니다."

        content = (
            f"이 공고의 제목은 '{title}'이며, '{category_from_csv}' 카테고리에 해당합니다. "
            f"지원 지역은 {region}이며, 지원 대상은 {target_main}입니다. "
            f"접수 기간은 {period}{period_suffix} "
            f"주요 공고 내용은 다음과 같습니다: {content_text}"
        )

    elif category_from_csv == "대출상품 조회":
        if '본문' in row and pd.notna(row['본문']):
            body_text = str(row['본문'])
            match = re.search(r"서비스제공지역\n(.*?)\n특이사항", body_text, re.DOTALL)
            if match:
                extracted_region = match.group(1).strip()
                if extracted_region:
                    
                    extracted_region = re.sub(r"[\r\n]+", " ", extracted_region)
                    extracted_region = re.sub(r"\s{2,}", " ", extracted_region).strip()

                    
                    if extracted_region in ['전국', '전체'] or '전국' in extracted_region:
                        region = '전국'
                    else:
                        # 시군구/권역 등 매칭이 가능하면 region_centers로 매핑
                        found_region = False
                        for full_region, prefixes in region_centers.items():
                            for prefix in prefixes:
                                if extracted_region.startswith(prefix) or prefix in extracted_region:
                                    region = full_region
                                    found_region = True
                                    break
                            if found_region:
                                break
                        # 매핑 불가하면 추출 문자열을 그대로 사용 (or 필요시 '무관'으로 바꿀 수 있음)
                        if not found_region:
                            region = extracted_region
        
        title = get_body_val('금융상품명', '대출상품')
        limit = get_body_val('최대한도(만원)')
        if limit != "정보 없음" and str(limit).replace(',', '').isdigit(): limit = f"{limit}만원"
        
        rate = get_body_val('금리(%)')
        rate_desc = f"{rate}%" if rate != "정보 없음" else "금리는 별도 문의가 필요합니다"

        loan_period = get_body_val('대출기간(년)')
        if str(loan_period).replace(',', '').isdigit(): loan_period = f"{loan_period}년"
        repay_method = get_body_val('상환방법')
        
        institution = get_body_val('취급기관')
        provider_institution = get_body_val('제공기관/취급기관')
        if provider_institution != "정보 없음" and "/" in provider_institution:
            institution = f"{institution} / {provider_institution.split('/')[0].strip()}"
        elif provider_institution != "정보 없음":
            institution = f"{institution} / {provider_institution}"


        condition_detail = get_body_val('지원대상 상세조건', '')
        income_cond = get_body_val('소득기준', '')
        credit_cond = get_body_val('신용조건', '')
        
        eligibility_text = f"기본 지원 대상은 {target_main}입니다."
        if condition_detail != "정보 없음":
            eligibility_text += f" 상세 자격 요건은 다음과 같습니다. {condition_detail}."
        if income_cond != "정보 없음" and income_cond not in condition_detail:
            eligibility_text += f" 소득 기준으로는 {income_cond}이어야 합니다."
        if credit_cond != "정보 없음" and credit_cond not in condition_detail:
            eligibility_text += f" 신용 조건은 {credit_cond}입니다."

        costs = get_body_val('대출부대비용')
        fees = get_body_val('중도상환수수료')
        etc_notes = get_body_val('기타 참고사항')
        
        contact = get_body_val('문의처')
        deadline_loan = get_body_val('운영기한', period) 
        
        content = (
            f"이 상품은 {region} 지역의 '{title}' 공고입니다. "
            f"카테고리는 {category_from_csv}이며, 주요 취급 및 제공 기관은 {institution}입니다.\n\n"
            
            f"대출 최대 한도는 {limit}이며, {rate_desc}. "
            f"대출 기간은 {loan_period}이며, 상환 방식은 {repay_method}입니다. "
            f"(총 대출 기간 참고: {get_body_val('총대출기간(년)')})\n\n"
            
            f"{eligibility_text}\n\n"
            
            f"대출 부대 비용으로는 {costs}이 발생하며, 중도상환수수료는 {fees}입니다. "
            f"기타 참고사항으로 {etc_notes} 조건이 있습니다.\n\n"
            
            f"신청 및 문의는 {contact}로 가능하며, 운영 기한은 {deadline_loan}입니다."
        )
        
        metadata["deadline"] = deadline_loan 

    else: 
        title = get_body_val('공고명', f"{category_from_csv} 정보")
        content_text = get_body_val('공고내용', '')
        content_text = " ".join(content_text.split())

        content = (
            f"'{title}'에 대한 안내입니다. "
            f"이 정보는 '{category_from_csv}'로 분류됩니다. "
            f"상세 내용은 다음과 같습니다: {content_text}. "
            f"신청 기간 등 자세한 내용은 원문을 참조해주시기 바랍니다."
        )


    effective_period_for_closing = deadline_loan if category_from_csv == "대출상품 조회" else period
    metadata.update({
        "title": title,
        "region": region,
        "target": target_main,
        "closing_type": get_closing_info(effective_period_for_closing)[0],
        "parsed_end_date": get_closing_info(effective_period_for_closing)[1],
    })
    
    return {"content": content, "metadata": metadata}

# ==========================================
# 3. 파일 저장 관련 함수
# ==========================================

def save_raw_crawled_data(crawled_data, output_dir):
    """크롤링한 원본 데이터를 CSV, JSON으로 저장"""
    os.makedirs(output_dir, exist_ok=True)
    df = pd.DataFrame(crawled_data)
    df.to_csv(os.path.join(output_dir, 'crawled_raw.csv'), index=False, encoding='utf-8-sig')
    with open(os.path.join(output_dir, 'crawled_raw.json'), 'w', encoding='utf-8') as f:
        json.dump(crawled_data, f, ensure_ascii=False, indent=4)
    print(f"원본 크롤링 데이터(CSV, JSON)가 '{output_dir}'에 저장되었습니다.")

def save_formatted_files(records, output_dir):
    """가공된 레코드를 CSV, JSON, JSONL 포맷으로 저장"""
    os.makedirs(output_dir, exist_ok=True)
    df = pd.DataFrame({
        'content': [r['content'] for r in records],
        'metadata': [json.dumps(r['metadata'], ensure_ascii=False) for r in records]
    })
    df.to_csv(os.path.join(output_dir, 'policy.csv'), index=False, encoding='utf-8-sig')
    
    with open(os.path.join(output_dir, 'policy.json'), 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=4)
        
    with open(os.path.join(output_dir, 'policy.jsonl'), 'w', encoding='utf-8') as f:
        for r in records: f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(f"포맷된 파일들(CSV, JSON, JSONL)이 '{output_dir}'에 저장되었습니다.")

def save_metadata_file(records, output_dir):
    """메타데이터만 추출하여 JSON 파일로 저장"""
    os.makedirs(output_dir, exist_ok=True)
    metadata_list = [r['metadata'] for r in records]
    with open(os.path.join(output_dir, 'policy_metadata.json'), 'w', encoding='utf-8') as f:
        json.dump(metadata_list, f, ensure_ascii=False, indent=4)
    print(f"메타데이터 파일이 '{output_dir}'에 저장되었습니다.")

def save_embeddings_files(records, output_dir):
    """텍스트 임베딩을 생성하고 CSV, JSON 파일로 저장"""
    os.makedirs(output_dir, exist_ok=True)
    print("\n임베딩 생성 시작 (모델: gemini-embedding-001)...")
    try:
        model = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    except Exception as e:
        print(f"모델 로딩 실패: {e}\n'GOOGLE_API_KEY' 환경변수 또는 라이브러리 설치를 확인하세요.")
        return

    texts = [item["content"] for item in records]
    print(f"   - 총 {len(texts)}개 문서 처리 중...")
    
    # 임베딩 차원을 1536으로 지정
    embeddings = model.embed_documents(texts, output_dimensionality=1536)
    dimension = len(embeddings[0]) if embeddings else 1536
    print(f"임베딩 생성 완료 (차원: {dimension}).")

    df = pd.DataFrame({"embedding": embeddings, "dimension": dimension})
    df.to_csv(os.path.join(output_dir, 'policy_embedding.csv'), index=False, encoding='utf-8-sig')
    df.to_json(os.path.join(output_dir, 'policy_embedding.json'), orient='records', indent=4, force_ascii=False)
    print(f"임베딩 파일(CSV, JSON)이 '{output_dir}'에 저장되었습니다.")


# ==========================================
# 4. 메인 실행 함수
# ==========================================

def main():
    """크롤링부터 데이터 처리, 임베딩까지 모든 과정을 실행"""
    
    # --- 1단계: 웹 크롤링 ---
    driver = setup_driver()
    set_initial_conditions(driver)
    crawled_links = scrape_all_links(driver)
    
    if not crawled_links:
        print("크롤링된 링크가 없습니다. 프로그램을 종료합니다.")
        driver.quit()
        return
        
    crawled_data = crawl_details_from_links(driver, crawled_links)
    driver.quit()

    if not crawled_data:
        print("상세 정보 수집에 실패했습니다. 프로그램을 종료합니다.")
        return
    
    print(f"\n크롤링 완료! 총 {len(crawled_data)}건의 데이터를 수집했습니다.")
    
    # --- 2단계: 데이터 가공 및 저장 ---
    print("\n데이터 처리 및 파일 생성 시작...")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_base_dir = os.path.join(script_dir, 'data')
    raw_dir = os.path.join(output_base_dir, 'crawled_raw')
    text_format_dir = os.path.join(output_base_dir, 'text_fomatting')
    metadata_dir = os.path.join(output_base_dir, 'policy_metadata')
    embedding_dir = os.path.join(output_base_dir, 'policy_embedding')

    df = pd.DataFrame(crawled_data)

    # --- 원본 크롤링 데이터 저장 ---
    save_raw_crawled_data(crawled_data, raw_dir)
    
    # "접수 기간이 마감 되었습니다." 문장이 포함된 행 제외
    original_count = len(df)
    df = df[~df['본문'].str.contains("접수 기간이 마감 되었습니다.", na=False)]
    if original_count > len(df):
        print(f"   - 마감된 공고 {original_count - len(df)}건 제외.")

    processed_records = [create_policy_record(row) for _, row in df.iterrows()]
    print(f"   - {len(processed_records)}건 데이터 처리 완료.")

    save_formatted_files(processed_records, text_format_dir)
    save_metadata_file(processed_records, metadata_dir)
    
    # --- 3단계: 임베딩 생성 ---
    save_embeddings_files(processed_records, embedding_dir)
    
    print("\n\n+++ 모든 작업이 성공적으로 완료되었습니다! +++")

if __name__ == '__main__':
    main()
