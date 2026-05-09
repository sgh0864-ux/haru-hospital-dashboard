# ======================================================
# IMPORT
# ======================================================

import streamlit as st
import pandas as pd
import plotly.express as px

import os
import re
import time

from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


# ======================================================
# PAGE CONFIG
# ======================================================

st.set_page_config(
    page_title="하루한의원 리뷰 인사이트",
    layout="wide"
)


# ======================================================
# MODERN UI
# ======================================================

st.markdown("""
<style>

.stApp {
    background-color: #f4f7fb;
}

html, body, [class*="css"] {
    font-family: Inter, sans-serif;
    color: #111827;
}

.block-container {
    max-width: 1280px;
    padding-top: 32px;
    padding-bottom: 60px;
}

.main-title {
    font-size: 42px;
    font-weight: 700;
    color: #111827;
    letter-spacing: -1px;
    margin-bottom: 8px;
}

.sub-title {
    font-size: 16px;
    color: #6b7280;
    margin-bottom: 40px;
}

.kpi-card {

    background: white;

    border-radius: 28px;

    padding: 28px;

    border: 1px solid #edf2f7;

    box-shadow:
        0 6px 24px rgba(15,23,42,0.04);

    min-height: 150px;
}

.kpi-label {
    font-size: 14px;
    color: #6b7280;
    font-weight: 500;
    margin-bottom: 18px;
}

.kpi-value {
    font-size: 42px;
    font-weight: 700;
    color: #111827;
    line-height: 1;
}

.kpi-desc {
    margin-top: 14px;
    font-size: 14px;
    color: #9ca3af;
}

.section-title {
    font-size: 24px;
    font-weight: 700;
    color: #111827;
    margin-top: 50px;
    margin-bottom: 24px;
}

.chart-card {

    background: white;

    border-radius: 28px;

    padding: 20px;

    border: 1px solid #edf2f7;

    box-shadow:
        0 6px 24px rgba(15,23,42,0.04);
}

.table-card {

    background: white;

    border-radius: 28px;

    padding: 20px;

    border: 1px solid #edf2f7;

    box-shadow:
        0 6px 24px rgba(15,23,42,0.04);
}

.insight-card {

    background: linear-gradient(
        135deg,
        #111827,
        #1f2937
    );

    border-radius: 28px;

    padding: 32px;

    color: white;

    margin-top: 30px;
}

.insight-title {
    font-size: 22px;
    font-weight: 700;
    margin-bottom: 12px;
}

.insight-desc {
    font-size: 16px;
    color: #d1d5db;
    line-height: 1.7;
}

[data-testid="stDataFrame"] {
    border-radius: 18px;
    overflow: hidden;
}

</style>
""", unsafe_allow_html=True)


# ======================================================
# 병원 설정
# ======================================================

main_hospital = "하루한의원"

hospital_urls = {
    "하루한의원": "https://naver.me/xHg774HK",
    "이로움한의원": "https://naver.me/5WOuxbRt",
    "경희본한의원": "https://naver.me/GyYrk7Bl",
    "왕십리옥토한의원": "https://naver.me/5CW490lL",
    "함소아한의원 왕십리": "https://naver.me/5pwZ4BWi"
}


# ======================================================
# DATA PATH
# ======================================================

DATA_PATH = "data/hospital_reviews.csv"


# ======================================================
# NAVER REVIEW CRAWLING
# ======================================================

@st.cache_data(ttl=3600)
def get_naver_review_data(place_url):

    options = webdriver.ChromeOptions()

    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(
        service=Service(
            ChromeDriverManager().install()
        ),
        options=options
    )

    visitor_reviews = 0
    blog_reviews = 0

    try:

        driver.get(place_url)

        time.sleep(5)

        driver.switch_to.frame("entryIframe")

        time.sleep(3)

        body_text = driver.find_element(
            By.TAG_NAME,
            "body"
        ).text

        visitor_match = re.search(
            r'방문자 리뷰\s*([0-9,]+)',
            body_text
        )

        if visitor_match:

            visitor_reviews = int(
                visitor_match.group(1).replace(",", "")
            )

        blog_match = re.search(
            r'블로그 리뷰\s*([0-9,]+)',
            body_text
        )

        if blog_match:

            blog_reviews = int(
                blog_match.group(1).replace(",", "")
            )

    except:
        pass

    driver.quit()

    return visitor_reviews, blog_reviews


# ======================================================
# 데이터 수집
# ======================================================

hospital_data = []

with st.spinner("네이버 리뷰 데이터를 수집중입니다..."):

    for hospital, url in hospital_urls.items():

        visitor_reviews, blog_reviews = get_naver_review_data(url)

        total_reviews = visitor_reviews + blog_reviews

        hospital_data.append({
            "병원명": hospital,
            "방문자리뷰": visitor_reviews,
            "블로그리뷰": blog_reviews,
            "총리뷰수": total_reviews
        })


# ======================================================
# DATAFRAME
# ======================================================

df = pd.DataFrame(hospital_data)

df = df.sort_values(
    by="총리뷰수",
    ascending=False
)


# ======================================================
# 저장
# ======================================================

os.makedirs("data", exist_ok=True)

today = datetime.now().strftime("%Y-%m-%d")

df["date"] = today


if os.path.exists(DATA_PATH):

    old_df = pd.read_csv(DATA_PATH)

    updated_df = pd.concat([old_df, df])

else:

    updated_df = df


updated_df.to_csv(DATA_PATH, index=False)


# ======================================================
# 메인 데이터
# ======================================================

main_df = df[df["병원명"] == main_hospital]
main_data = main_df.iloc[0]


# ======================================================
# 리뷰 증가량
# ======================================================

history_df = updated_df[
    updated_df["병원명"] == main_hospital
]

weekly_new = 0

try:

    if len(history_df) >= 2:

        weekly_new = int(
            history_df.iloc[-1]["총리뷰수"] -
            history_df.iloc[0]["총리뷰수"]
        )

except:
    pass


# ======================================================
# HEADER
# ======================================================

st.markdown(
    """
    <div class="main-title">
        하루한의원 리뷰 인사이트
    </div>
    <div class="sub-title">
        실시간 네이버 플레이스 리뷰 모니터링
    </div>
    """,
    unsafe_allow_html=True
)


# ======================================================
# KPI
# ======================================================

st.markdown(
    '<div class="section-title">핵심 지표</div>',
    unsafe_allow_html=True
)

col1, col2, col3, col4 = st.columns(4)


with col1:

    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">총 리뷰</div>
        <div class="kpi-value">{int(main_data['총리뷰수']):,}개</div>
        <div class="kpi-desc">방문자 + 블로그</div>
    </div>
    """, unsafe_allow_html=True)


with col2:

    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">방문자 리뷰</div>
        <div class="kpi-value">{int(main_data['방문자리뷰']):,}개</div>
        <div class="kpi-desc">실제 방문 인증</div>
    </div>
    """, unsafe_allow_html=True)


with col3:

    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">블로그 리뷰</div>
        <div class="kpi-value">{int(main_data['블로그리뷰']):,}개</div>
        <div class="kpi-desc">블로그 후기</div>
    </div>
    """, unsafe_allow_html=True)


with col4:

    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">최근 7일 증가</div>
        <div class="kpi-value">+{weekly_new}개</div>
        <div class="kpi-desc">최근 리뷰 증가량</div>
    </div>
    """, unsafe_allow_html=True)


# ======================================================
# 리뷰 추이
# ======================================================

st.markdown(
    '<div class="section-title">리뷰 추이</div>',
    unsafe_allow_html=True
)

history_chart = px.line(
    history_df,
    x="date",
    y="총리뷰수",
    markers=True
)

history_chart.update_layout(

    plot_bgcolor="white",
    paper_bgcolor="white",

    font=dict(
        family="Inter",
        size=14,
        color="#111827"
    ),

    margin=dict(
        l=10,
        r=10,
        t=30,
        b=10
    )
)

history_chart.update_traces(
    line_color="#111827",
    line_width=4
)

st.markdown('<div class="chart-card">', unsafe_allow_html=True)

st.plotly_chart(
    history_chart,
    use_container_width=True
)

st.markdown('</div>', unsafe_allow_html=True)


# ======================================================
# 병원 비교
# ======================================================

st.markdown(
    '<div class="section-title">병원별 리뷰 비교</div>',
    unsafe_allow_html=True
)

fig1 = px.bar(
    df,
    x="병원명",
    y="총리뷰수"
)

fig1.update_traces(
    marker_color=[
        "#111827" if x == main_hospital
        else "#d1d5db"
        for x in df["병원명"]
    ]
)

fig1.update_layout(

    plot_bgcolor="white",
    paper_bgcolor="white",

    font=dict(
        family="Inter",
        size=14,
        color="#111827"
    )
)

st.markdown('<div class="chart-card">', unsafe_allow_html=True)

st.plotly_chart(
    fig1,
    use_container_width=True
)

st.markdown('</div>', unsafe_allow_html=True)


# ======================================================
# 비교표
# ======================================================

st.markdown(
    '<div class="section-title">경쟁 병원 비교</div>',
    unsafe_allow_html=True
)

compare_df = df[df["병원명"] != main_hospital]

st.markdown('<div class="table-card">', unsafe_allow_html=True)

st.dataframe(
    compare_df,
    use_container_width=True
)

st.markdown('</div>', unsafe_allow_html=True)


# ======================================================
# 인사이트
# ======================================================

top_competitor = compare_df.iloc[0]["병원명"]

st.markdown(f"""
<div class="insight-card">

<div class="insight-title">
마케팅 인사이트
</div>

<div class="insight-desc">
현재 리뷰 수 기준 경쟁 우위 병원은
<b>{top_competitor}</b> 입니다.<br><br>

하루한의원은 최근 리뷰 증가 흐름이
안정적으로 유지되고 있습니다.
</div>

</div>
""", unsafe_allow_html=True)