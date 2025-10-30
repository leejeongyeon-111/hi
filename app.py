# app.py
import streamlit as st
import pandas as pd
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
import plotly.express as px

# -------------------------------
# 데이터 로드 함수
# -------------------------------
@st.cache_data
def load_data():
    try:
        df_taxi = pd.read_csv("seoul_taxi_SAMPLE_500.csv")
        df_garage = pd.read_csv("서울시설공단_장애인콜택시 차고지 정보_20250724.csv")
    except FileNotFoundError:
        st.error("🚨 CSV 파일을 찾을 수 없습니다. 파일 경로를 확인하세요.")
        return None, None

    # 시간 관련 컬럼 감지 및 처리
    datetime_col = None
    for col in df_taxi.columns:
        if "일시" in col:
            datetime_col = col
            break

    if datetime_col:
        df_taxi[datetime_col] = pd.to_datetime(df_taxi[datetime_col], errors="coerce")
        df_taxi["hour"] = df_taxi[datetime_col].dt.hour
        df_taxi["weekday"] = df_taxi[datetime_col].dt.day_name()
        df_taxi["date"] = df_taxi[datetime_col].dt.date
    else:
        st.warning("⚠️ '일시'가 포함된 컬럼이 없습니다. 시간 분석이 제한됩니다.")

    # 위경도 컬럼 이름 감지
    lat_col = next((c for c in df_taxi.columns if "위도" in c), None)
    lon_col = next((c for c in df_taxi.columns if "경도" in c), None)
    if lat_col and lon_col:
        df_taxi = df_taxi.dropna(subset=[lat_col, lon_col])
    else:
        st.error("🚨 위도/경도 컬럼이 없습니다.")
        return None, None

    # 컬럼명 통일
    df_taxi = df_taxi.rename(columns={lat_col: "위도", lon_col: "경도"})

    return df_taxi, df_garage

# -------------------------------
# 데이터 로드
# -------------------------------
df_taxi, df_garage = load_data()

if df_taxi is not None:
    # -------------------------------
    # 사이드바 필터
    # -------------------------------
    st.sidebar.header("📍 필터 설정")

    day_options = ["전체"] + sorted(df_taxi["weekday"].dropna().unique().tolist())
    selected_day = st.sidebar.selectbox("요일 선택", day_options)
    selected_hour = st.sidebar.slider("시간대 선택", 0, 23, (7, 9))

    filtered = df_taxi.copy()
    if selected_day != "전체":
        filtered = filtered[filtered["weekday"] == selected_day]
    if "hour" in filtered.columns:
        filtered = filtered[(filtered["hour"] >= selected_hour[0]) & (filtered["hour"] <= selected_hour[1])]

    # -------------------------------
    # 상단 KPI
    # -------------------------------
    st.title("🚖 서울시 장애인 콜택시 수요·공급 대시보드")

    col1, col2, col3 = st.columns(3)
    col1.metric("총 호출 수", f"{len(filtered):,} 건")

    if "배차시간" in filtered.columns:
        col2.metric("평균 배차시간(분)", f"{filtered['배차시간'].mean():.1f}")
    else:
        col2.metric("평균 배차시간(분)", "데이터 없음")

    if "지역" in filtered.columns:
        col3.metric("고유 호출 지역 수", f"{filtered['지역'].nunique():,}")
    else:
        col3.metric("고유 호출 지역 수", "데이터 없음")

    # -------------------------------
    # 1️⃣ 시간대별 수요 그래프
    # -------------------------------
    if "hour" in df_taxi.columns:
        st.subheader("⏰ 시간대별 호출 수")
        hourly = df_taxi.groupby("hour").size().reset_index(name="count")
        fig_hour = px.bar(
            hourly,
            x="hour",
            y="count",
            color="count",
            color_continuous_scale="Blues",
            labels={"hour": "시간", "count": "호출 수"},
        )
        st.plotly_chart(fig_hour, use_container_width=True)

    # -------------------------------
    # 2️⃣ 요일별 수요 그래프
    # -------------------------------
    if "weekday" in df_taxi.columns:
        st.subheader("📅 요일별 호출 수")
        weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        weekday = df_taxi.groupby("weekday").size().reindex(weekday_order).fillna(0).reset_index(name="count")
        fig_day = px.bar(
            weekday,
            x="weekday",
            y="count",
            color="count",
            color_continuous_scale="Greens",
            labels={"weekday": "요일", "count": "호출 수"},
        )
        st.plotly_chart(fig_day, use_container_width=True)

    # -------------------------------
    # 3️⃣ 지도 시각화 (Heatmap + 차고지)
    # -------------------------------
    st.subheader("🗺️ 수요 밀집도 및 차고지 위치")

    m = folium.Map(location=[37.55, 126.98], zoom_start=11, tiles="cartodb positron")

    # 수요 Heatmap
    if not filtered.empty:
        HeatMap(filtered[["위도", "경도"]].values.tolist(), radius=10, blur=15).add_to(m)

    # 차고지 마커 표시
    for _, row in df_garage.iterrows():
        folium.Marker(
            location=[row["위도"], row["경도"]],
            popup=f"차고지명: {row['차고지명']}",
            icon=folium.Icon(color="blue", icon="car", prefix="fa"),
        ).add_to(m)

    st_map = st_folium(m, width=700, height=500)

    # -------------------------------
    # 4️⃣ 지역별 호출 TOP 10
    # -------------------------------
    if "지역" in df_taxi.columns:
        st.subheader("🏙️ 지역별 호출 수 TOP 10")
        top_region = df_taxi["지역"].value_counts().head(10).reset_index()
        top_region.columns = ["지역", "호출 수"]
        st.dataframe(top_region)

else:
    st.warning("⚠️ 데이터를 불러오지 못했습니다. 파일 경로를 확인하세요.")