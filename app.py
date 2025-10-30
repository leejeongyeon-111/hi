import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from branca.colormap import linear

# Geocoding을 위한 라이브러리 추가
import time
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

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
# 2. 데이터 불러오기 (Geocoding 포함)
# -----------------------------
@st.cache_data
def load_data():
    df_taxi = None
    df_garage = None
    
    try:
        df_taxi = pd.read_csv("seoul_taxi_SAMPLE_500.csv")
    except FileNotFoundError:
        st.error("⚠️ 'seoul_taxi_SAMPLE_500.csv' 파일을 찾을 수 없습니다.")
    
    try:
        # === 수정: 업로드된 파일명으로 변경 ===
        df_garage = pd.read_csv("info.csv")
    except FileNotFoundError:
        st.error("⚠️ '서울시설공단_장애인콜택시 차고지 정보_20250724.csv' 파일을 찾을 수 없습니다.")

    # === 수정: 차고지 데이터가 있을 경우 Geocoding 수행 ===
    if df_garage is not None:
        geolocator = Nominatim(user_agent="seoul-taxi-dashboard-app")
        
        latitudes = []
        longitudes = []
        
        # 주소 컬럼 찾기 ('상세주소' 또는 '주소' 포함)
        address_col = next((c for c in df_garage.columns if "주소" in c), None)
        if not address_col:
            st.error("⚠️ 차고지 파일에서 '주소' 관련 컬럼을 찾을 수 없습니다.")
            return df_taxi, None
        
        # Geocoding이 느리므로 진행 상황 표시
        progress_bar = st.progress(0, text="차고지 주소 변환 중... (첫 실행 시 시간이 소요됩니다)")
        
        for i, address in enumerate(df_garage[address_col]):
            try:
                # '서울'을 추가하여 검색 정확도 향상
                location = geolocator.geocode(f"서울 {address}", timeout=5) 
                
                if location:
                    latitudes.append(location.latitude)
                    longitudes.append(location.longitude)
                else:
                    latitudes.append(None)
                    longitudes.append(None)
            
            except (GeocoderTimedOut, GeocoderUnavailable):
                latitudes.append(None)
                longitudes.append(None)
            
            # Nominatim 서버 과부하 방지를 위한 Rate limiting
            time.sleep(0.5) 
            progress_bar.progress((i + 1) / len(df_garage), text=f"차고지 주소 변환 중... ({i+1}/{len(df_garage)})")

        progress_bar.empty()
        
        df_garage['latitude'] = latitudes
        df_garage['longitude'] = longitudes
        
        # Geocoding 실패한 주소는 제외
        df_garage_geocoded = df_garage.dropna(subset=['latitude', 'longitude'])
        
        failed_count = len(df_garage) - len(df_garage_geocoded)
        if failed_count > 0:
            st.warning(f"총 {len(df_garage)}개 차고지 중 {failed_count}개의 주소를 변환하지 못했습니다.")
        
        return df_taxi, df_garage_geocoded
    
    return df_taxi, None # 차고지 파일 로드 실패 시

# -----------------------------
# 3. Streamlit 설정
# -----------------------------
st.set_page_config(page_title="서울시 장애인 콜택시 수요·공급 대시보드", layout="wide")
st.title("🚕 서울특별시 장애인 콜택시 수요·공급 통합 대시보드")

df_taxi, df_garage = load_data()

# === 수정: 택시 데이터(수요)가 없으면 중지 ===
if df_taxi is None:
    st.warning("택시 수요 데이터를 불러올 수 없어 대시보드를 중지합니다.")
    st.stop()

# -----------------------------
# 4. 데이터 전처리
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
# 5. 지도 시각화 (수요 + 공급)
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

# ✅ 수요 원 표시 (확대 반영)
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

# === 수정: 공급(차고지) 정확한 위치(Geocoding) 표시 ===
if df_garage is not None:
    # 차고지명, 주차대수 컬럼 자동 찾기
    name_col = next((c for c in df_garage.columns if "명" in c or "차고지" in c or "센터" in c), "차고지명")
    parking_col = next((c for c in df_garage.columns if "주차" in c), None)
    
    for _, row in df_garage.iterrows():
        # load_data에서 NaN이 필터링되었으므로 바로 사용
        lat = row['latitude']
        lon = row['longitude']
        
        # 팝업 텍스트 구성
        name = str(row[name_col]) if name_col in row else "차고지"
        popup_text = f"🚗 <b>{name}</b>"
        if parking_col and pd.notna(row[parking_col]):
            popup_text += f"<br>주차대수: {int(row[parking_col])}대"
        
        folium.Marker(
            [lat, lon],
            popup=folium.Popup(popup_text, max_width=200),
            tooltip=name,
            icon=folium.Icon(color="darkblue", icon="car", prefix="fa")
        ).add_to(m)

st_folium(m, width=950, height=600)

# -----------------------------
# 6. 통계 시각화 (Plotly)
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
