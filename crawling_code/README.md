# SBIZ24 크롤링 파이프라인
`crawling_code.py`는 SBIZ24 공고를 Selenium으로 크롤링한 뒤, 텍스트 가공/메타데이터 생성/임베딩까지 한 번에 수행하는 스크립트.

## 요구 사항
- Python 3.9+ 권장
- Google Chrome (Selenium용)
- 아래 패키지 설치

## 설치
```bash
pip install -r requirements.txt
```

## 환경 변수
`.env` 파일에 API 키를 설정.
```
GOOGLE_API_KEY=YOUR_KEY
```

## 실행
```bash
python crawling_code.py
```

## 출력 경로
실행 경로 기준으로 아래 디렉터리에 결과가 생성.
- 원본 크롤링 데이터  
  - `data/crawled_raw/crawled_raw.csv`  
  - `data/crawled_raw/crawled_raw.json`
- 가공된 텍스트 데이터  
  - `data/text_fomatting/policy.csv`  
  - `data/text_fomatting/policy.json`  
  - `data/text_fomatting/policy.jsonl`
- 메타데이터  
  - `data/policy_metadata/policy_metadata.json`
- 임베딩 결과  
  - `data/policy_embedding/policy_embedding.csv`  
  - `data/policy_embedding/policy_embedding.json`
- 첨부파일 다운로드  
  - `downloads_final/`

## 주의 사항
- Selenium이 Chrome을 제어하므로 GUI 환경이 필요.
- 임베딩 차원은 `output_dimensionality=1536`으로 요청하지만, 모델이 지원하지 않으면 실제 반환 차원이 다를 수 있음.
- 대상 사이트 구조가 변경되면 셀렉터 수정이 필요.
