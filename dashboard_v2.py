import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import urllib.error

# --- [v15] FRED API 라이브러리 임포트 ---
try:
    from fredapi import Fred
except ImportError:
    st.error("`fredapi` 라이브러리가 설치되지 않았습니다. 터미널에서 `pip install fredapi`를 실행해주세요.")
    st.stop()

# --- [v18] 날짜 계산을 위한 pandas DateOffset 임포트 ---
from pandas.tseries.offsets import DateOffset

# --- 페이지 설정 ---
st.set_page_config(
    page_title="글로벌 매크로 및 국내 증시 대시보드",
    page_icon="📊",
    layout="wide"
)

st.title("📊 글로벌 매크로 & 국내 증시 대시보드")
st.caption(f"데이터 기준일: {datetime.now().strftime('%Y-%m-%d')}")

# --- [v21] FRED API 키는 Streamlit Secrets에서 불러옵니다 ---
# GitHub에 키를 절대 올리지 마세요.
# FRED_API_KEY = "..." <- [v21] 이 줄을 삭제하고 st.secrets를 사용합니다.
# --- [v21] 끝 ---

# --- [v15 & v19] 데이터 소스 분리 (AI 티커 추가) ---
# 1. YFinance로 가져올 티커
YFINANCE_TICKERS = {
    # 금리
    'US_10Y_Yield': '^TNX',
    'US_3M_Yield': '^IRX',
    # 신용
    'High_Yield_Bond': 'HYG',
    'Inv_Grade_Bond': 'LQD',
    # 인플레이션 프록시
    'Crude_Oil': 'CL=F',
    'Gold': 'GC=F',
    'Copper': 'HG=F',
    'TIPS_ETF': 'TIP',
    # 국내 증시
    'KOSPI': '^KS11',
    'KOSDAQ': '^KQ11',
    # [v19] AI 프록시
    'Semiconductor_ETF': 'SMH',  # 반도체 ETF (AI 하드웨어)
    'Cloud_ETF': 'SKYY'  # 클라우드 ETF (AI 플랫폼)
}

# 2. FRED API로 가져올 티커
FRED_TICKERS = {
    'Fed_Funds': 'DFF',  # 연준 실효 금리
    '10Y_Breakeven': 'T10YIE',  # 10년 기대 인플레이션
}


# --- [v15] YFinance 데이터 로더 (캐시) ---
@st.cache_data(ttl=3600)  # 1시간 캐시
# --- [v18] 시작일을 2010년으로 변경 ---
def load_yfinance_data(tickers_map, start_date="2010-01-01"):
    st.info(f"YFinance 데이터 다운로드 시도 (시작일: {start_date}): {list(tickers_map.values())}")
    try:
        data = yf.download(list(tickers_map.values()), start=start_date)
        # --- [v18] 끝 ---
        if data.empty:
            st.error("YFinance: 데이터가 비어있습니다.")
            return pd.DataFrame(), pd.DataFrame()

        # 가격 데이터 추출 (Adj Close 우선, 없으면 Close)
        if 'Adj Close' in data.columns:
            prices_data = data['Adj Close']
            st.info("YFinance: 'Adj Close' (수정 종가) 데이터를 우선 사용합니다.")
        elif 'Close' in data.columns:
            prices_data = data['Close']
            st.info("YFinance: 'Close' (종가) 데이터를 사용합니다.")
        else:
            st.warning("YFinance: 가격 데이터를 찾을 수 없습니다.")
            return pd.DataFrame(), pd.DataFrame()

        # 거래량 데이터 추출
        if 'Volume' not in data.columns:
            volume_data = pd.DataFrame(index=prices_data.index)
        else:
            volume_data = data['Volume']

        # 컬럼 이름 변경
        downloaded_cols = prices_data.columns
        rename_map = {v: k for k, v in tickers_map.items() if v in downloaded_cols}

        adj_close = prices_data.rename(columns=rename_map)
        volume = volume_data.rename(columns=rename_map)

        # 시간대 정보 제거
        try:
            adj_close.index = adj_close.index.tz_localize(None)
            volume.index = volume.index.tz_localize(None)
        except TypeError:
            pass  # 이미 naive

        valid_cols = list(rename_map.values())
        valid_volume_cols = [col for col in valid_cols if col in volume.columns]

        return adj_close[valid_cols], volume[valid_volume_cols]

    except Exception as e:
        st.error(f"YFinance 데이터 로드 중 오류: {e}")
        return pd.DataFrame(), pd.DataFrame()


# --- [v15] FRED API 데이터 로더 (캐시) ---
@st.cache_data(ttl=3600)  # 1시간 캐시
# --- [v21] st.secrets에서 API 키를 가져오도록 수정 ---
def load_fred_data(tickers_map, start_date="2010-01-01"):
    # API 키를 st.secrets에서 불러옵니다.
    api_key = st.secrets.get("FRED_API_KEY")

    if not api_key:
        st.warning("FRED API 키가 설정되지 않았습니다. `DFF`, `T10YIE` 데이터는 생략됩니다.")
        st.info("로컬 실행 시 .streamlit/secrets.toml 파일을, 클라우드 배포 시 Secrets 설정을 확인하세요.")
        return pd.DataFrame()

    st.info(f"FRED API 데이터 다운로드 시도 (시작일: {start_date}): {list(tickers_map.values())}")

    try:
        fred = Fred(api_key=api_key)
        all_series = []

        for name, ticker in tickers_map.items():
            try:
                series = fred.get_series(ticker, start_date=start_date)
                all_series.append(series.rename(name))
            except ValueError as ve:
                st.warning(f"FRED: '{ticker}' ({name}) 데이터를 찾을 수 없습니다. {ve}")
            except Exception as e:
                st.warning(f"FRED: '{ticker}' ({name}) 로드 중 오류: {e}")

        if not all_series:
            st.error("FRED: 모든 티커 로드에 실패했습니다.")
            return pd.DataFrame()

        df_fred = pd.concat(all_series, axis=1)

        # 시간대 정보 제거
        try:
            df_fred.index = df_fred.index.tz_localize(None)
        except TypeError:
            pass  # 이미 naive

        st.success("FRED API 데이터 로드 성공.")
        return df_fred

    except urllib.error.HTTPError as e:
        if "400" in str(e):
            st.error("FRED API 키가 유효하지 않습니다. Streamlit Secrets 설정을 확인하세요.")
        else:
            st.error(f"FRED API 연결 오류: {e}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"FRED API 로드 중 치명적 오류: {e}")
        return pd.DataFrame()


# --- [v15] 메인 데이터 로드 및 병합 ---
with st.spinner("1. YFinance 데이터 로드 중..."):
    df_yf_prices, df_yf_volumes = load_yfinance_data(YFINANCE_TICKERS, start_date="2010-01-01")

with st.spinner("2. FRED 데이터 로드 중... (API 키 확인)"):
    # [v21] API 키 인자 제거. 함수가 내부적으로 st.secrets에서 가져옴
    df_fred_prices = load_fred_data(FRED_TICKERS, start_date="2010-01-01")

# 데이터 병합
if df_yf_prices.empty and df_fred_prices.empty:
    st.error("모든 데이터 소스로부터 데이터를 불러오지 못했습니다. 인터넷 연결 및 API 키를 확인해주세요.")
    st.stop()
elif df_fred_prices.empty:
    st.info("YFinance 데이터만 로드되었습니다.")
    prices = df_yf_prices
elif df_yf_prices.empty:
    st.info("FRED 데이터만 로드되었습니다.")
    prices = df_fred_prices
else:
    st.info("YFinance와 FRED 데이터를 병합합니다.")
    prices = pd.merge(df_yf_prices, df_fred_prices, left_index=True, right_index=True, how='outer')

# 병합 후에는 주말/휴일 등으로 NaN이 발생하므로, ffill()로 채워줍니다.
prices = prices.ffill()
volumes = df_yf_volumes  # 거래량은 YFinance에만 있음

# --- [v14] NAN 리포트 (ffill 후에도 남은 NaN) ---
nan_report = prices.isna().sum()
nan_cols = nan_report[nan_report == len(prices)]
if not nan_cols.empty:
    st.warning("다음 티커는 전체 기간 데이터를 불러오지 못했습니다 (NaN):")
    st.dataframe(nan_cols)
# --- [v14] 끝 ---

# --- 차트 로직 ---
if not prices.empty:

    # --- [v18] 기간 선택 버튼 (Radio) ---
    st.sidebar.header("기간 선택 (Quick Select)")

    # 기준 날짜 설정
    min_date = prices.index.min().date()
    max_date = prices.index.max().date()

    period_options = ["1개월", "3개월", "6개월", "YTD", "1년", "3년", "10년", "전체"]
    selected_period = st.sidebar.radio(
        "기간을 선택하세요:",
        options=period_options,
        index=len(period_options) - 1  # 기본값: "전체"
    )

    # 선택된 기간에 따라 start_date, end_date 계산
    end_date = max_date

    if selected_period == "1개월":
        start_date = (end_date - DateOffset(months=1)).date()
    elif selected_period == "3개월":
        start_date = (end_date - DateOffset(months=3)).date()
    elif selected_period == "6개월":
        start_date = (end_date - DateOffset(months=6)).date()
    elif selected_period == "YTD":
        start_date = end_date.replace(month=1, day=1)
    elif selected_period == "1년":
        start_date = (end_date - DateOffset(years=1)).date()
    elif selected_period == "3년":
        start_date = (end_date - DateOffset(years=3)).date()
    elif selected_period == "10년":
        start_date = (end_date - DateOffset(years=10)).date()
    elif selected_period == "전체":
        start_date = min_date

    # 계산된 시작일이 실제 데이터의 최소 날짜보다 빠르면, 최소 날짜로 조정
    if start_date < min_date:
        start_date = min_date

    st.sidebar.caption(f"선택된 기간: {start_date} ~ {end_date}")
    # --- [v1G] 기간 선택 로직 끝 ---

    # --- 날짜 유효성 검사 (v17의 슬라이더 로직은 삭제됨) ---
    if start_date > end_date:
        st.error(f"시작일({start_date})이 종료일({end_date})보다 늦습니다. (데이터 로딩 오류)")
    else:
        # --- (v10) .index.date와 date 객체를 직접 비교 ---
        prices_filtered = prices[
            (prices.index.date >= start_date) & (prices.index.date <= end_date)
            ].dropna(how='all')

        volumes_filtered = volumes[
            (volumes.index.date >= start_date) & (volumes.index.date <= end_date)
            ].dropna(how='all')

        if prices_filtered.empty:
            st.warning("선택하신 기간에 데이터가 없습니다. 기간을 다시 설정해주세요.")
        else:
            # --- UI 레이아웃 ---
            col1, col2 = st.columns(2)

            # --- 1. 미국 매크로 지표 ---
            with col1:
                st.header("🇺🇸 미국 금리 지표")

                # 1-1. 국채 금리
                st.subheader("정책금리 및 국채 금리 (Yield)")
                fig_yield = go.Figure()

                if 'Fed_Funds' in prices_filtered.columns:
                    fig_yield.add_trace(go.Scatter(
                        x=prices_filtered.index, y=prices_filtered['Fed_Funds'],
                        name='연준 실효 금리 (DFF)', line=dict(color='red', dash='dot')
                    ))
                if 'US_10Y_Yield' in prices_filtered.columns:
                    fig_yield.add_trace(go.Scatter(
                        x=prices_filtered.index, y=prices_filtered['US_10Y_Yield'],
                        name='미 10년물 금리 (%)', line=dict(color='blue')
                    ))
                if 'US_3M_Yield' in prices_filtered.columns:
                    fig_yield.add_trace(go.Scatter(
                        x=prices_filtered.index, y=prices_filtered['US_3M_Yield'],
                        name='미 3개월물 금리 (%)', line=dict(color='orange')
                    ))

                fig_yield.update_layout(
                    yaxis_title="금리 (%)",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig_yield, use_container_width=True)

                # 1-2. 장단기 금리차 (10Y - 3M)
                st.subheader("장단기 금리차 (10Y - 3M)")
                if 'US_10Y_Yield' in prices_filtered.columns and 'US_3M_Yield' in prices_filtered.columns:
                    spread_df = prices_filtered[['US_10Y_Yield', 'US_3M_Yield']].dropna()
                    yield_spread = spread_df['US_10Y_Yield'] - spread_df['US_3M_Yield']

                    if not yield_spread.empty:
                        fig_spread = go.Figure(go.Scatter(
                            x=yield_spread.index, y=yield_spread,
                            name='10Y-3M Spread', line=dict(color='red'), fill='tozeroy'
                        ))
                        fig_spread.add_hline(y=0, line_dash="dash", line_color="grey")
                        st.plotly_chart(fig_spread, use_container_width=True)

            with col2:
                st.header("🇺🇸 신용 & 인플레이션 기대")

                # 1-3. 신용 채권
                st.subheader("신용 채권 (Credit Bonds)")
                if 'High_Yield_Bond' in prices_filtered.columns:
                    fig_credit = go.Figure()
                    fig_credit.add_trace(go.Scatter(
                        x=prices_filtered.index, y=prices_filtered['High_Yield_Bond'],
                        name='HYG (하이일드/위험)', line=dict(color='purple')
                    ))
                    if 'Inv_Grade_Bond' in prices_filtered.columns:
                        fig_credit.add_trace(go.Scatter(
                            x=prices_filtered.index, y=prices_filtered['Inv_Grade_Bond'],
                            name='LQD (투자등급/안전)', line=dict(color='cyan', dash='dash')
                        ))
                    fig_credit.update_layout(
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    st.plotly_chart(fig_credit, use_container_width=True)

                # 1-4. 10년 기대 인플레이션 (Daily FRED)
                st.subheader("10년 기대 인플레이션 (Breakeven)")
                if '10Y_Breakeven' in prices_filtered.columns:
                    fig_breakeven = go.Figure(go.Scatter(
                        x=prices_filtered.index, y=prices_filtered['10Y_Breakeven'],
                        name='10Y Breakeven (%)', line=dict(color='orange')
                    ))
                    fig_breakeven.update_layout(yaxis_title="기대 인플레이션 (%)")
                    st.plotly_chart(fig_breakeven, use_container_width=True)

            st.divider()

            # --- 2. 원자재 및 인플레이션 프록시 ---
            st.header("📈 원자재 및 인플레이션 프록시 (Daily)")
            col3, col4 = st.columns(2)

            with col3:
                st.subheader("WTI 유가 (Crude Oil)")
                if 'Crude_Oil' in prices_filtered.columns:
                    fig_oil = go.Figure(go.Scatter(
                        x=prices_filtered.index, y=prices_filtered['Crude_Oil'],
                        name='WTI Crude Oil ($)', line=dict(color='green')
                    ))
                    st.plotly_chart(fig_oil, use_container_width=True)

                st.subheader("구리 (Dr. Copper)")
                if 'Copper' in prices_filtered.columns:
                    fig_copper = go.Figure(go.Scatter(
                        x=prices_filtered.index, y=prices_filtered['Copper'],
                        name='Copper ($)', line=dict(color='brown')
                    ))
                    st.plotly_chart(fig_copper, use_container_width=True)

            with col4:
                st.subheader("금 (Gold)")
                if 'Gold' in prices_filtered.columns:
                    fig_gold = go.Figure(go.Scatter(
                        x=prices_filtered.index, y=prices_filtered['Gold'],
                        name='Gold ($)', line=dict(color='gold')
                    ))
                    st.plotly_chart(fig_gold, use_container_width=True)

                st.subheader("물가연동채 ETF (TIPS)")
                if 'TIPS_ETF' in prices_filtered.columns:
                    fig_tips = go.Figure(go.Scatter(
                        x=prices_filtered.index, y=prices_filtered['TIPS_ETF'],
                        name='TIPS ETF Price ($)', line=dict(color='teal')
                    ))
                    st.plotly_chart(fig_tips, use_container_width=True)

            st.divider()

            # --- 3. 국내 증시 ---
            st.header("🇰🇷 국내 증시 (KOSPI & KOSDAQ)")
            col5, col6 = st.columns(2)

            with col5:
                st.subheader("KOSPI 지수 및 거래량")
                if 'KOSPI' in prices_filtered.columns:
                    fig_kospi = go.Figure()
                    fig_kospi.add_trace(go.Scatter(
                        x=prices_filtered.index, y=prices_filtered['KOSPI'],
                        name='KOSPI 지수', line=dict(color='blue')
                    ))
                    if 'KOSPI' in volumes.columns:
                        fig_kospi.add_trace(go.Bar(
                            x=volumes_filtered.index, y=volumes_filtered['KOSPI'],
                            name='거래량', yaxis='y2', marker_color='lightblue'
                        ))
                    fig_kospi.update_layout(
                        yaxis=dict(title='KOSPI 지수'),
                        yaxis2=dict(title='거래량', overlaying='y', side='right', showgrid=False),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    st.plotly_chart(fig_kospi, use_container_width=True)

            with col6:
                st.subheader("KOSDAQ 지수 및 거래량")
                if 'KOSDAQ' in prices_filtered.columns:
                    fig_kosdaq = go.Figure()
                    fig_kosdaq.add_trace(go.Scatter(
                        x=prices_filtered.index, y=prices_filtered['KOSDAQ'],
                        name='KOSDAQ 지수', line=dict(color='red')
                    ))
                    if 'KOSDAQ' in volumes.columns:
                        fig_kosdaq.add_trace(go.Bar(
                            x=volumes_filtered.index, y=volumes_filtered['KOSDAQ'],
                            name='거래량', yaxis='y2', marker_color='pink'
                        ))
                    fig_kosdaq.update_layout(
                        yaxis=dict(title='KOSDAQ 지수'),
                        yaxis2=dict(title='거래량', overlaying='y', side='right', showgrid=False),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    st.plotly_chart(fig_kosdaq, use_container_width=True)

            st.divider()  # [v19] 구분선 추가

            # --- [v19] 4. AI & Tech 프록시 ---
            st.header("🤖 AI & Tech 인프라 (Proxies)")
            col7, col8 = st.columns(2)

            with col7:
                st.subheader("반도체 ETF (Hardware)")
                if 'Semiconductor_ETF' in prices_filtered.columns:
                    fig_smh = go.Figure(go.Scatter(
                        x=prices_filtered.index, y=prices_filtered['Semiconductor_ETF'],
                        name='SMH ($)', line=dict(color='cyan')
                    ))
                    st.plotly_chart(fig_smh, use_container_width=True)

            with col8:
                st.subheader("클라우드 ETF (Platform)")
                if 'Cloud_ETF' in prices_filtered.columns:
                    fig_skyy = go.Figure(go.Scatter(
                        x=prices_filtered.index, y=prices_filtered['Cloud_ETF'],
                        name='SKYY ($)', line=dict(color='magenta')
                    ))
                    st.plotly_chart(fig_skyy, use_container_width=True)
            # --- [v19] 끝 ---

            # --- 5. 종합 비교 차트 ---
            st.divider()
            # --- [v20] 헤더 및 안내 문구 수정 ---
            st.header("📈 종합 비교 (Z-Score)")
            st.info("선택된 기간의 평균(μ)을 0, 표준편차(σ)를 1로 표준화하여 각 지표의 상대적 위치(과열/침체)를 비교합니다.")
            # --- [v20] 끝 ---

            available_cols = list(prices_filtered.columns)

            selected_cols = st.multiselect(
                "비교할 지표를 선택하세요:",
                options=available_cols,
                default=available_cols
            )

            if selected_cols:
                df_to_normalize = prices_filtered[selected_cols].dropna(axis=1, how='all')

                if df_to_normalize.empty:
                    st.warning("선택된 지표 중 유효한 데이터가 없습니다.")
                else:
                    try:
                        # --- [v20] Z-Score 정규화 로직으로 변경 ---
                        df_mean = df_to_normalize.mean()
                        df_std = df_to_normalize.std()
                        df_normalized = (df_to_normalize - df_mean) / df_std
                        # --- [v20] 끝 ---

                        fig_all = go.Figure()
                        for col in df_normalized.columns:
                            fig_all.add_trace(go.Scatter(
                                x=df_normalized.index,
                                y=df_normalized[col],
                                name=col
                            ))

                        fig_all.add_hline(y=0, line_dash="dash", line_color="grey")  # 0 = 평균선

                        fig_all.update_layout(
                            yaxis_title="Z-Score (표준편차)",  # [v20] Y축 이름 변경
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                        )

                        st.plotly_chart(fig_all, use_container_width=True)

                    except IndexError:
                        st.warning("선택된 기간이나 지표에 유효한 데이터가 없어 정규화 차트를 그릴 수 없습니다.")
                    except Exception as e:
                        st.error(f"종합 비교 차트 생성 중 오류 발생: {e}")

            else:
                st.info("비교할 지표를 1개 이상 선택해주세요.")

            st.subheader("데이터 원본 (선택된 기간)")
            st.dataframe(prices_filtered.tail(10))

else:
    st.error("데이터를 불러오지 못했습니다. 인터넷 연결, 티커, FRED API 키를 확인해주세요.")

# --- 사이드바 ---
st.sidebar.header("안내")
st.sidebar.info(
    """
    이 대시보드는 `yfinance`와 `fredapi`를 함께 사용하여 데이터를 시각화합니다.
    Streamlit Cloud Secrets에 `FRED_API_KEY`가 설정되어야 합니다.

    **[AI/Tech 프록시]**
    - `SMH`: 반도체 ETF
    - `SKYY`: 클라우드 ETF
    """
)
st.sidebar.header("실행 방법")
st.sidebar.code("streamlit run dashboard.py")

# --- 캐시 지우기 버튼 ---
st.sidebar.header("문제 해결")
if st.sidebar.button("데이터 캐시 지우기"):
    st.cache_data.clear()
    st.info("데이터 캐시를 지웠습니다. 앱을 새로고침합니다.")
    st.rerun()