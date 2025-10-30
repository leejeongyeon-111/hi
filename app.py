import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from branca.colormap import linear
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# -----------------------------
# 1. 서울시 25개 구 중심 좌표
# -----------------------------
SEOUL_GU_COORDS = {
    "종로구": [37.573050, 126.979189],
    "중구": [37.563569, 126.997753],
    "용산구": [37.532473, 126.990963],
    "성동구": [37.563341, 127.036409],
    "광진구": [37.538484, 127.082293],
    "동대문구": [37.574368, 127.039585],
    "중랑구": [37.606560, 127.092651],
    "성북구": [37.589400, 127.016742],
    "강북구": [37.639749, 127.025490],
    "도봉구": [37.668768, 127.047163],
    "노원구": [37.654358, 127.056473],
    "은평구": [37.617612, 126.922700],
    "서대문구": [37.579115, 126.936778],
    "마포구": [37.563756, 126.908421],
    "양천구": [37.516873, 126.866398],
    "강서구": [37.550937, 126.849642],
    "구로구": [37.495485, 126.887960],
    "금천구": [37.460096, 126.900154],
    "영등포구": [37.526371, 126.896228],
    "동작구": [37.512402, 126.939252],
    "관악구": [37.478406, 126.951613],
    "서초구": [37.483570, 127.032661],
    "강남구": [37.517236, 127.047325],
    "송파구": [37.514543, 127.105918],
    "강동구": [37.530126, 127.123770],
}

# -----------------------------
# 2. 데이터 불러오기
# -----------------------------
@st.cache_data
def load_data():
    try:
        df_taxi = pd.read_csv("seoul_taxi_SAMPLE_500.csv")
        df_garage = pd.read_csv("info.csv")
        return df_taxi, df_garage
    except FileNotFoundError:
        st.error("⚠️ CSV 파일을 찾을 수 없습니다. 파일 경로를 확인하세요.")
        return None, None

# -----------------------------
# 3. 주소 → 위도·경도 변환 함수
# -----------------------------
@st.cache_data
def geocode_addresses(addresses):
    geolocator = Nominatim(user_agent="seoul_garages")
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
    coords = {}
    for addr in addresses:
        try:
            loc = geocode(addr)
            if loc:
                coords[addr] = (loc.latitude, loc.longitude)
            else:
                coords[addr] = None
        except Exception:
            coords[addr] = None
    return coords

# -----------------------------
# 4. Streamlit 설정
# -----------------------------
st.set_page_config(page_title="서울시 장애인 콜택시 대시보드", layout="wide")
st.title("🚕 서울특별시 장애인 콜택시 수요·공급 통합 대시보드")

df_taxi, df_garage = load_data()
if df_taxi is None or df_garage is None:
    st.stop()

# -----------------------------
# 5. 데이터 전처리
# -----------------------------
datetime_col = next((c for c in df_taxi.columns if "일시" in c or "시간" in c), None)
if datetime_col:
    df_taxi[datetime_col] = pd.to_datetime(df_taxi[datetime_col], errors="coerce")
    df_taxi["hour"] = df_taxi[datetime_col].dt.hour
    df_taxi["weekday"] = df_taxi[datetime_col].dt.day_name()

region_col = next((c for c in df_taxi.columns if "지역" in c or "구" in c), None)
if region_col:
    df_taxi[region_col] = df_taxi[region_col].astype(str).str.replace(" ", "")
else:
    st.warning("⚠️ 지역 정보가 없어 지도 표시가 제한됩니다.")
    st.stop()

# -----------------------------
# 6. 지도 생성
# -----------------------------
st.subheader("🗺️ 서울특별시 장애인 콜택시 수요(원) vs 공급(차고지) 지도")

SEOUL_CENTER = [37.5665, 126.9780]
m = folium.Map(location=SEOUL_CENTER, zoom_start=11.3, tiles="cartodbpositron")

# ✅ 수요 집계
region_counts = df_taxi[region_col].value_counts().reset_index()
region_counts.columns = ["region", "count"]

colormap = linear.Blues_09.scale(region_counts["count"].min(), region_counts["count"].max())
colormap.caption = "콜택시 호출 수 (수요)"
colormap.add_to(m)

# ✅ 수요 원 표시
for _, row in region_counts.iterrows():
    region = row["region"]
    count = row["count"]
    if region in SEOUL_GU_COORDS:
        lat, lon = SEOUL_GU_COORDS[region]
        color = colormap(count)
        radius = max(8, min(35, count / region_counts["count"].max() * 36))
        folium.CircleMarker(
            location=[lat, lon],
            radius=radius,
            color="black",
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            popup=f"📍 {region}\n수요: {count}건"
        ).add_to(m)

# ✅ 공급(차고지) 표시 (주소 기반)
if "주소" in df_garage.columns:
    addr_list = df_garage["주소"].dropna().unique().tolist()
    coords_dict = geocode_addresses(addr_list)

    for _, row in df_garage.iterrows():
        name = row.get("차고지명", "차고지")
        addr = row.get("주소", "")
        cars = row.get("주차대수", "정보없음")

        coord = coords_dict.get(addr)
        if coord:
            lat, lon = coord
            folium.Marker(
                [lat, lon],
                popup=f"🚗 {name}<br>📍 {addr}<br>🚘 주차대수: {cars}",
                icon=folium.Icon(color="darkblue", icon="car", prefix="fa")
            ).add_to(m)
else:
    st.warning("⚠️ '주소' 컬럼을 찾을 수 없습니다. 파일을 확인하세요.")

st_folium(m, width=950, height=600)

# -----------------------------
# 7. 통계 시각화
# -----------------------------
st.subheader("📊 시간대별 / 요일별 / 지역별 수요 분석")

col1, col2 = st.columns(2)

if "weekday" in df_taxi.columns:
    weekday_counts = df_taxi["weekday"].value_counts().reindex(
        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        fill_value=0
    )
    fig1 = px.bar(
        x=weekday_counts.index, y=weekday_counts.values,
        labels={"x": "요일", "y": "콜 수"}, title="요일별 호출 수요"
    )
    col1.plotly_chart(fig1, use_container_width=True)

if "hour" in df_taxi.columns:
    hour_counts = df_taxi["hour"].value_counts().sort_index()
    fig2 = px.line(
        x=hour_counts.index, y=hour_counts.values, markers=True,
        labels={"x": "시간대", "y": "콜 수"}, title="시간대별 호출 수요"
    )
    col2.plotly_chart(fig2, use_container_width=True)

st.subheader("🏙️ 지역별 콜택시 호출량 Top 15")
region_counts_sorted = df_taxi[region_col].value_counts().head(15)
fig3 = px.bar(
    x=region_counts_sorted.index, y=region_counts_sorted.values,
    labels={"x": "지역", "y": "콜 수"}, title="상위 15개 지역별 호출량"
)
st.plotly_chart(fig3, use_container_width=True)
