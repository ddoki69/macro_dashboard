글로벌 매크로 & 국내 증시 대시보드 (v21 - Stable Rollback)

이 Streamlit 앱은 yfinance와 fredapi를 사용하여 주요 거시 경제 지표와 KOSPI/KOSDAQ 및 AI 관련 기술주 ETF를 추적하는 대시보드입니다.

v21은 pykrx와 FinanceDataReader로 인한 배포 오류를 해결하기 위해, 해당 기능(외국인 수급)을 제외한 안정 버전입니다.

주요 기능

다중 소스 데이터: YFinance (주식, ETF, 선물), FRED (경제 지표)

핵심 지표: 금리, 신용, 원자재, AI 프록시(SMH, SKYY), 국내 증시

기간 선택: 1개월, 3개월, YTD, 10년, 전체 등 빠른 기간 선택

종합 비교: Z-Score 표준화를 통해 모든 지표의 상대적 위치 비교

배포 (Streamlit Cloud)

1. GitHub에 업로드 (★중요★)

dashboard.py (v21 코드)

requirements.txt (v21 코드 - pykrx/fdr 제거됨)

README.md (본 파일)

runtime.txt (이 파일은 GitHub에서 삭제해주세요. 꼭 삭제해야 합니다.)

2. Streamlit Cloud 설정 (중요: API 키)

Streamlit Cloud에 GitHub 계정으로 로그인합니다.

"New app" -> "From GitHub"를 선택하고, 이 저장소를 선택합니다.

"Advanced settings..." (고급 설정)을 클릭합니다.

"Secrets" 탭으로 이동합니다.

아래 내용을 그대로 복사하여 붙여넣고, ... 부분에 본인의 32자리 FRED API 키를 입력합니다.

FRED_API_KEY = "YOUR_32_DIGIT_KEY_GOES_HERE"


"Save"를 누른 후 "Deploy!" 버튼을 클릭합니다.
