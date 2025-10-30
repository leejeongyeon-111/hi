# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium

# -----------------------------
# 1. 데이터 불러오기
# -----------------------------
@st.cache_data
def load_data():
    try:
        df_taxi = pd.read_csv("seoul_taxi_SAMPLE_500.csv")
        df_garage = pd.read_csv("info.csv")
        return df_taxi, df_garage
    except FileNotFoundError:
        st.error("⚠️ 데이터를 불러오지 못했습니다. 파일 경로를 확인하세요.")
        return None, None


# -----------------------------
# 2. Streamlit 앱 구조
# -----------------------------
st.set_page_config(page_title="장애인 콜택시 수요-공급 대시보드", layout="wide")
st.title("🚕 (서울시) 장애인 콜택시 수요-공급 통합 대시보드")

df_taxi, df_garage = load_data()

if df_taxi is None or df_garage is None:
    st.stop()

# -----------------------------
# 3. 데이터 전처리
# -----------------------------
# 날짜/시간 파싱
datetime_col = next((c for c in df_taxi.columns if "일시" in c or "시간" in c), None)
if datetime_col:
    df_taxi[datetime_col] = pd.to_datetime(df_taxi[datetime_col], errors="coerce")
    df_taxi["hour"] = df_taxi[datetime_col].dt.hour
    df_taxi["weekday"] = df_taxi[datetime_col].dt.day_name()
else:
    st.warning("⚠️ 일시/시간 관련 컬럼이 없어 시간대 분석은 생략됩니다.")

# 지역명 컬럼 자동 탐색
region_col = next((c for c in df_taxi.columns if "지역" in c or "구" in c), None)
if region_col is None:
    st.warning("⚠️ 지역명 관련 컬럼이 없어 지역 분석은 생략됩니다.")
else:
    df_taxi[region_col] = df_taxi[region_col].astype(str)

# -----------------------------
# 4. 시각화 — 지도
# -----------------------------
st.subheader("🗺️ 서울시 장애인 콜택시 현황 (기본 지도)")

SEOUL_CENTER = [37.5665, 126.9780]
m = folium.Map(location=SEOUL_CENTER, zoom_start=11)

# 차고지 표시
if "위도" in df_garage.columns and "경도" in df_garage.columns:
    for _, row in df_garage.iterrows():
        folium.Marker(
            [row["위도"], row["경도"]],
            popup=row.get("차고지명", "차고지"),
            icon=folium.Icon(color="blue", icon="car", prefix="fa")
        ).add_to(m)
else:
    folium.Marker(
        SEOUL_CENTER,
        popup="서울특별시 중심",
        icon=folium.Icon(color="red", icon="info-sign")
    ).add_to(m)

st_folium(m, width=700, height=500)

# -----------------------------
# 5. 시각화 — 숫자형 요약
# -----------------------------
st.subheader("📊 수요 분석 대시보드")

col1, col2 = st.columns(2)

# (1) 요일별 수요
if "weekday" in df_taxi.columns:
    weekday_counts = df_taxi["weekday"].value_counts().reindex(
        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        fill_value=0
    )
    fig1 = px.bar(
        x=weekday_counts.index,
        y=weekday_counts.values,
        labels={"x": "요일", "y": "콜 수"},
        title="요일별 콜택시 호출 수요"
    )
    col1.plotly_chart(fig1, use_container_width=True)
else:
    col1.warning("요일 데이터 없음")

# (2) 시간대별 수요
if "hour" in df_taxi.columns:
    hour_counts = df_taxi["hour"].value_counts().sort_index()
    fig2 = px.line(
        x=hour_counts.index,
        y=hour_counts.values,
        markers=True,
        labels={"x": "시간대", "y": "콜 수"},
        title="시간대별 콜택시 호출 수요"
    )
    col2.plotly_chart(fig2, use_container_width=True)
else:
    col2.warning("시간대 데이터 없음")

# (3) 지역별 수요 (선택)
if region_col:
    st.subheader("🏙️ 지역별 콜택시 호출량")
    region_counts = df_taxi[region_col].value_counts().head(15)
    fig3 = px.bar(
        x=region_counts.index,
        y=region_counts.values,
        labels={"x": "지역", "y": "콜 수"},
        title="상위 15개 지역별 호출량"
    )
    st.plotly_chart(fig3, use_container_width=True)
