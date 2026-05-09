# ======================================================
# IMPORT
# ======================================================

import streamlit as st
import pandas as pd
import plotly.express as px

import requests
import re
import os

from datetime import datetime


# ======================================================
# PAGE CONFIG
# ======================================================

st.set_page_config(
    page_title="하루한의원 대시보드",
    layout="wide"
)


# ======================================================
# MODERN UI
# ======================================================

st.markdown("""
<style>

/* 전체 */

.stApp {
    background-color: #f3f6fb;
}


/* 폰트 */

html, body, [class*="css"] {
    font-family: Inter, sans-serif;
    color: #111827;
}


/* 메인 */

.block-container {
    max-width: 1300px;
    padding-top: 30px;
    padding-bottom: 80px;
}


/* 헤더 */

.main-title {

    font-size: 42px;

    font-weight: 800;

    color: #111827;

    margin-bottom: 6px;

    letter-spacing: -1px;
}

.main-sub {

    color: #6b7280;

    font-size: 16px;

    margin-bottom: 40px;
}


/* KPI 카드 */

.kpi-card {

    background: white;

    padding: 28px;

    border-radius: 24px;

    border: 1px solid #e5e7eb;

    box-shadow:
        0 10px 30px rgba(15,23,42,0.04);

    min-height: 160px;
}

.kpi-label {

    font-size: 14px;

    color: #6b7280;

    margin-bottom: 16px;

    font-weight: 600;
}

.kpi-value {

    font-size: 42px;

    font-weight: 800;

    color: #111827;

    line-height: 1;
}

.kpi-desc {

    margin-top: 16px;

    color: #9ca3af;

    font-size: 14px;
}


/* 섹션 */

.section-title {

    font-size: 24px;

    font-weight: 700;

    margin-top: 50px;

    margin-bottom: 20px;

    color: #111827;
}


/* 카드 */

.content-card {

    background: white;

    border-radius: 24px;

    padding: 24px;

    border: 1px solid #e5e7eb;

    box-shadow:
        0 10px 30px rgba(15,23,42,0.04);
}


/* plotly */

.js-plotly-plot {
    border-radius: 20px;
}


/* dataframe */

[data-testid="stDataFrame"] {

    border-radius: 18px;

    overflow: hidden;
}


/* 인사이트 */

.insight-box {

    background:
        linear-gradient(
            135deg,
            #111827,
            #1f2937
        );

    border-radius: 24px;

    padding: 32px;

    color: white;

    margin-top: 30px;
}

.insight-title {

    font-size: 24px;

    font-weight: 700;

    margin-bottom: 16px;
}

.insight-text {

    font-size: 16px;

    line-height: 1.8;

    color: #d1d5db;
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
# 리뷰 수집
# ======================================================

@st.cache_data(ttl=3600)
def get_naver_review_data(url):

    headers = {
        "User-Agent":
        "Mozilla/5.0"
    }

    visitor_reviews = 0
    blog_reviews = 0

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=10
        )

        html = response.text

        visitor_match = re.search(
            r'방문자 리뷰\s*([0-9,]+)',
            html
        )

        if visitor_match:

            visitor_reviews = int(
                visitor_match.group(1).replace(",", "")
            )

        blog_match = re.search(
            r'블로그 리뷰\s*([0-9,]+)',
            html
        )

        if blog_match:

            blog_reviews = int(
                blog_match.group(1).replace(",", "")
            )

    except:
        pass

    return visitor_reviews, blog_reviews


# ======================================================
# 데이터 수집
# ======================================================

hospital_data = []

with st.spinner("데이터 수집중..."):

    for hospital, url in hospital_urls.items():

        visitor_reviews, blog_reviews = get_naver_review_data(url)

        total_reviews = (
            visitor_reviews +
            blog_reviews
        )

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
# CSV 저장
# ======================================================

os.makedirs("data", exist_ok=True)

DATA_PATH = "data/reviews.csv"

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

main_df = df[
    df["병원명"] == main_hospital
]

main_data = main_df.iloc[0]


# ======================================================
# 증가량
# ======================================================

weekly_new = 0

try:

    history_df = updated_df[
        updated_df["병원명"] == main_hospital
    ]

    weekly_new = int(

        history_df.iloc[-1]["총리뷰수"] -

        history_df.iloc[0]["총리뷰수"]
    )

except:
    pass


# ======================================================
# HEADER
# ======================================================

st.markdown(f"""

<div class="main-title">
하루한의원 리뷰 대시보드
</div>

<div class="main-sub">
네이버 플레이스 리뷰 기반 실시간 모니터링
</div>

""", unsafe_allow_html=True)


# ======================================================
# KPI
# ======================================================

col1, col2, col3, col4 = st.columns(4)

with col1:

    st.markdown(f"""
    <div class="kpi-card">

        <div class="kpi-label">
        총 리뷰
        </div>

        <div class="kpi-value">
        {int(main_data['총리뷰수']):,}개
        </div>

        <div class="kpi-desc">
        방문자 + 블로그 리뷰
        </div>

    </div>
    """, unsafe_allow_html=True)


with col2:

    st.markdown(f"""
    <div class="kpi-card">

        <div class="kpi-label">
        방문자 리뷰
        </div>

        <div class="kpi-value">
        {int(main_data['방문자리뷰']):,}개
        </div>

        <div class="kpi-desc">
        실제 방문 인증 리뷰
        </div>

    </div>
    """, unsafe_allow_html=True)


with col3:

    st.markdown(f"""
    <div class="kpi-card">

        <div class="kpi-label">
        블로그 리뷰
        </div>

        <div class="kpi-value">
        {int(main_data['블로그리뷰']):,}개
        </div>

        <div class="kpi-desc">
        블로그 후기 리뷰
        </div>

    </div>
    """, unsafe_allow_html=True)


with col4:

    st.markdown(f"""
    <div class="kpi-card">

        <div class="kpi-label">
        최근 증가
        </div>

        <div class="kpi-value">
        +{weekly_new}개
        </div>

        <div class="kpi-desc">
        최근 리뷰 증가량
        </div>

    </div>
    """, unsafe_allow_html=True)


# ======================================================
# 리뷰 추이
# ======================================================

st.markdown(
    '<div class="section-title">리뷰 추이</div>',
    unsafe_allow_html=True
)

history_df = updated_df[
    updated_df["병원명"] == main_hospital
]

fig = px.line(

    history_df,

    x="date",

    y="총리뷰수",

    markers=True
)

fig.update_layout(

    plot_bgcolor="white",

    paper_bgcolor="white",

    font=dict(
        family="Inter",
        size=14
    ),

    margin=dict(
        l=10,
        r=10,
        t=10,
        b=10
    )
)

fig.update_traces(

    line_color="#111827",

    line_width=4
)

st.markdown(
    '<div class="content-card">',
    unsafe_allow_html=True
)

st.plotly_chart(
    fig,
    use_container_width=True
)

st.markdown(
    '</div>',
    unsafe_allow_html=True
)


# ======================================================
# 경쟁 병원 비교
# ======================================================

st.markdown(
    '<div class="section-title">경쟁 병원 비교</div>',
    unsafe_allow_html=True
)

bar_fig = px.bar(

    df,

    x="병원명",

    y="총리뷰수"
)

bar_fig.update_traces(

    marker_color=[

        "#111827"

        if x == main_hospital

        else "#d1d5db"

        for x in df["병원명"]
    ]
)

bar_fig.update_layout(

    plot_bgcolor="white",

    paper_bgcolor="white",

    font=dict(
        family="Inter"
    )
)

st.markdown(
    '<div class="content-card">',
    unsafe_allow_html=True
)

st.plotly_chart(
    bar_fig,
    use_container_width=True
)

st.markdown(
    '</div>',
    unsafe_allow_html=True
)


# ======================================================
# 테이블
# ======================================================

st.markdown(
    '<div class="section-title">전체 데이터</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="content-card">',
    unsafe_allow_html=True
)

st.dataframe(
    df,
    use_container_width=True
)

st.markdown(
    '</div>',
    unsafe_allow_html=True
)


# ======================================================
# 인사이트
# ======================================================

top_competitor = df.iloc[0]["병원명"]

st.markdown(f"""

<div class="insight-box">

<div class="insight-title">
마케팅 인사이트
</div>

<div class="insight-text">

현재 리뷰 수 기준 가장 강한 경쟁 병원은
<b>{top_competitor}</b> 입니다.<br><br>

하루한의원은 네이버 리뷰 흐름을 기준으로
꾸준한 리뷰 증가 흐름을 유지중입니다.

</div>

</div>

""", unsafe_allow_html=True)