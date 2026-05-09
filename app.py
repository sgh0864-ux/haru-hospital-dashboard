import subprocess
import sys

try:
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)
except Exception:
    pass

import re
import sqlite3
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd
import plotly.express as px
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


st.set_page_config(page_title="하루한의원 리뷰 대시보드", layout="wide")


# ======================================================
# CSS
# ======================================================

st.markdown("""
<style>
.stApp {
    background: radial-gradient(circle at top left, #1f2937 0, #0b1020 38%, #060914 100%);
    color: #e5e7eb;
}
.block-container {
    max-width: 1280px;
    padding-top: 36px;
    padding-bottom: 80px;
}
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.badge {
    display: inline-block;
    padding: 7px 12px;
    border-radius: 999px;
    background: rgba(59,130,246,.14);
    color: #93c5fd;
    font-size: 13px;
    font-weight: 700;
    margin-bottom: 14px;
}
.main-title {
    font-size: 42px;
    font-weight: 850;
    letter-spacing: -1.3px;
    color: #f9fafb;
    margin-bottom: 10px;
}
.main-sub {
    color: #9ca3af;
    font-size: 16px;
    margin-bottom: 28px;
}
.section-title {
    margin-top: 34px;
    margin-bottom: 14px;
    font-size: 21px;
    font-weight: 850;
    color: #f9fafb;
}
.card, .kpi-card {
    background: rgba(17,24,39,.82);
    border: 1px solid rgba(255,255,255,.08);
    border-radius: 22px;
    box-shadow: 0 16px 38px rgba(0,0,0,.28);
}
.card {
    padding: 22px;
}
.kpi-card {
    padding: 22px;
    min-height: 132px;
}
.kpi-label {
    color: #9ca3af;
    font-size: 13px;
    font-weight: 750;
    margin-bottom: 14px;
}
.kpi-value {
    color: #f9fafb;
    font-size: 32px;
    line-height: 1;
    font-weight: 850;
    letter-spacing: -1px;
}
.kpi-help {
    color: #6b7280;
    font-size: 13px;
    margin-top: 13px;
}
.insight-card {
    background: linear-gradient(135deg, rgba(37,99,235,.25), rgba(17,24,39,.9));
    border: 1px solid rgba(147,197,253,.22);
    border-radius: 24px;
    padding: 26px;
    box-shadow: 0 18px 45px rgba(0,0,0,.28);
}
.insight-title {
    color: #f9fafb;
    font-size: 22px;
    font-weight: 850;
    margin-bottom: 12px;
}
.insight-text {
    color: #d1d5db;
    font-size: 15px;
    line-height: 1.8;
}
</style>
""", unsafe_allow_html=True)


# ======================================================
# SETTINGS
# ======================================================

MAIN_HOSPITAL = "하루한의원"
DB_PATH = "naver_review_history.db"

HOSPITALS = [
    {
        "name": "이로운 한의원",
        "url": "https://naver.me/5WOuxbRt",
    },
    {
        "name": "함소아한의원 왕십리",
        "url": "https://naver.me/5pwZ4BWi",
    },
    {
        "name": "경희본한의원",
        "url": "https://naver.me/GyYrk7Bl",
    },
    {
        "name": "하루한의원",
        "url": "https://naver.me/xHg774HK",
    },
    {
        "name": "왕십리옥토한의원",
        "url": "https://naver.me/5CW490lL",
    },
]


# ======================================================
# DB
# ======================================================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS review_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hospital_name TEXT NOT NULL,
        visitor_reviews INTEGER NOT NULL,
        blog_reviews INTEGER NOT NULL,
        total_reviews INTEGER NOT NULL,
        status TEXT,
        place_url TEXT,
        collected_at TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()


def save_snapshot(row):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO review_snapshots (
        hospital_name,
        visitor_reviews,
        blog_reviews,
        total_reviews,
        status,
        place_url,
        collected_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        row["병원명"],
        int(row["방문자리뷰"]),
        int(row["블로그리뷰"]),
        int(row["총리뷰수"]),
        row["조회상태"],
        row.get("플레이스URL", ""),
        row["조회시간"],
    ))

    conn.commit()
    conn.close()


def load_history(hospital_name):
    conn = sqlite3.connect(DB_PATH)

    history_df = pd.read_sql_query(
        """
        SELECT
            hospital_name,
            visitor_reviews,
            blog_reviews,
            total_reviews,
            status,
            place_url,
            collected_at
        FROM review_snapshots
        WHERE hospital_name = ?
        ORDER BY collected_at ASC
        """,
        conn,
        params=(hospital_name,),
    )

    conn.close()

    if not history_df.empty:
        history_df["collected_at"] = pd.to_datetime(history_df["collected_at"])

    return history_df


def get_nearest_before(history_df, target_time):
    if history_df.empty:
        return None

    before_df = history_df[history_df["collected_at"] <= target_time]

    if before_df.empty:
        return None

    return before_df.iloc[-1]


def calc_delta(history_df, current_total, days):
    if history_df.empty:
        return None

    target_time = datetime.now() - timedelta(days=days)
    past_row = get_nearest_before(history_df, target_time)

    if past_row is None:
        return None

    return int(current_total - past_row["total_reviews"])


def format_delta(value):
    if value is None:
        return "기록 부족"
    return f"{value:+,}개"


# ======================================================
# NAVER CRAWLING
# ======================================================

def to_int(num_text):
    if not num_text:
        return 0
    return int(num_text.replace(",", "").strip())


def parse_review_counts(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    visitor = 0
    blog = 0

    visitor_patterns = [
        r"방문자리뷰\s*([0-9,]+)",
        r"방문자 리뷰\s*([0-9,]+)",
        r"방문자\s*리뷰\s*([0-9,]+)",
    ]

    blog_patterns = [
        r"블로그리뷰\s*([0-9,]+)",
        r"블로그 리뷰\s*([0-9,]+)",
        r"블로그\s*리뷰\s*([0-9,]+)",
    ]

    for pattern in visitor_patterns:
        match = re.search(pattern, text)
        if match:
            visitor = to_int(match.group(1))
            break

    for pattern in blog_patterns:
        match = re.search(pattern, text)
        if match:
            blog = to_int(match.group(1))
            break

    return visitor, blog


def normalize_place_url(url):
    if "/home" in url:
        return url

    clean_url = url.split("?")[0].rstrip("/")

    if any(path in clean_url for path in ["/hospital/", "/place/", "/restaurant/", "/clinic/"]):
        return clean_url + "/home"

    return url


def get_naver_place_review_data(hospital):
    result = {
        "병원명": hospital["name"],
        "방문자리뷰": 0,
        "블로그리뷰": 0,
        "총리뷰수": 0,
        "조회상태": "실패",
        "조회시간": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "입력URL": hospital["url"],
        "플레이스URL": "",
    }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )

            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                    "Version/16.0 Mobile/15E148 Safari/604.1"
                ),
                viewport={"width": 390, "height": 844},
                locale="ko-KR",
            )

            page = context.new_page()

            page.goto(hospital["url"], wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            final_url = page.url
            place_url = normalize_place_url(final_url)

            result["플레이스URL"] = place_url

            page.goto(place_url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(4000)

            html = page.content()
            visitor, blog = parse_review_counts(html)

            browser.close()

            result["방문자리뷰"] = visitor
            result["블로그리뷰"] = blog
            result["총리뷰수"] = visitor + blog

            if visitor > 0 or blog > 0:
                result["조회상태"] = "성공"
            else:
                result["조회상태"] = "리뷰 미검출"

            return result

    except Exception as e:
        result["조회상태"] = f"오류: {str(e)[:120]}"
        return result


@st.cache_data(ttl=60 * 30, show_spinner=False)
def load_review_data(hospitals):
    rows = []

    for hospital in hospitals:
        rows.append(get_naver_place_review_data(hospital))

    df = pd.DataFrame(rows)

    df["총리뷰수"] = df["방문자리뷰"] + df["블로그리뷰"]

    df["방문자비율"] = df.apply(
        lambda row: round(row["방문자리뷰"] / row["총리뷰수"] * 100, 1)
        if row["총리뷰수"] > 0 else 0,
        axis=1,
    )

    df = df.sort_values("총리뷰수", ascending=False).reset_index(drop=True)
    df["순위"] = df.index + 1

    return df


# ======================================================
# APP
# ======================================================

init_db()

st.sidebar.title("설정")

main_hospital = st.sidebar.selectbox(
    "대표 병원",
    [h["name"] for h in HOSPITALS],
    index=[h["name"] for h in HOSPITALS].index(MAIN_HOSPITAL),
)

save_history_enabled = st.sidebar.checkbox(
    "이번 조회 결과를 히스토리에 저장",
    value=True,
)

if st.sidebar.button("데이터 새로고침"):
    st.cache_data.clear()
    st.rerun()


st.markdown(f"""
<div>
    <div class="badge">Live Naver Place Review Dashboard</div>
    <div class="main-title">{main_hospital} 리뷰 대시보드</div>
    <div class="main-sub">
        등록된 네이버 플레이스 URL을 직접 조회하고, 조회 시점별 데이터를 저장해 일/주/월 증감 추이를 계산합니다.
    </div>
</div>
""", unsafe_allow_html=True)


with st.spinner("네이버 플레이스 리뷰 데이터를 조회하는 중입니다..."):
    df = load_review_data(HOSPITALS)

if df.empty:
    st.error("조회된 데이터가 없습니다.")
    st.stop()

if save_history_enabled:
    for _, row in df.iterrows():
        if row["조회상태"] == "성공":
            save_snapshot(row)

main_df = df[df["병원명"] == main_hospital]

if main_df.empty:
    st.error("대표 병원 데이터가 없습니다.")
    st.stop()

main_data = main_df.iloc[0]
main_rank = int(main_data["순위"])
top_data = df.iloc[0]

review_gap = int(top_data["총리뷰수"] - main_data["총리뷰수"])
avg_total = df["총리뷰수"].mean()
success_count = len(df[df["조회상태"] == "성공"])

history_df = load_history(main_hospital)

daily_delta = calc_delta(history_df, int(main_data["총리뷰수"]), 1)
weekly_delta = calc_delta(history_df, int(main_data["총리뷰수"]), 7)
monthly_delta = calc_delta(history_df, int(main_data["총리뷰수"]), 30)


# ======================================================
# KPI
# ======================================================

col1, col2, col3, col4, col5 = st.columns(5)

kpis = [
    ("총 리뷰", f"{int(main_data['총리뷰수']):,}개", "방문자 + 블로그 리뷰"),
    ("방문자 리뷰", f"{int(main_data['방문자리뷰']):,}개", "네이버 방문자 리뷰"),
    ("블로그 리뷰", f"{int(main_data['블로그리뷰']):,}개", "네이버 블로그 리뷰"),
    ("리뷰 순위", f"{main_rank}위", "비교군 내 리뷰 수 기준"),
    ("조회 성공", f"{success_count}/{len(df)}", "데이터 수집 상태"),
]

for col, item in zip([col1, col2, col3, col4, col5], kpis):
    with col:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{item[0]}</div>
            <div class="kpi-value">{item[1]}</div>
            <div class="kpi-help">{item[2]}</div>
        </div>
        """, unsafe_allow_html=True)


# ======================================================
# DELTA KPI
# ======================================================

st.markdown('<div class="section-title">리뷰 증감 추이</div>', unsafe_allow_html=True)

d1, d2, d3 = st.columns(3)

delta_kpis = [
    ("일간 증감", format_delta(daily_delta), "약 24시간 전 대비"),
    ("주간 증감", format_delta(weekly_delta), "약 7일 전 대비"),
    ("월간 증감", format_delta(monthly_delta), "약 30일 전 대비"),
]

for col, item in zip([d1, d2, d3], delta_kpis):
    with col:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{item[0]}</div>
            <div class="kpi-value">{item[1]}</div>
            <div class="kpi-help">{item[2]}</div>
        </div>
        """, unsafe_allow_html=True)


# ======================================================
# HISTORY CHART
# ======================================================

if not history_df.empty and len(history_df) >= 2:
    st.markdown(f'<div class="section-title">{main_hospital} 누적 리뷰 추이</div>', unsafe_allow_html=True)

    fig_history = px.line(
        history_df,
        x="collected_at",
        y="total_reviews",
        markers=True,
        text="total_reviews",
    )

    fig_history.update_traces(
        line=dict(color="#60a5fa", width=4),
        marker=dict(size=8, color="#bfdbfe"),
        textposition="top center",
    )

    fig_history.update_layout(
        height=380,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#d1d5db", size=13),
        margin=dict(l=10, r=20, t=10, b=10),
        xaxis=dict(title="", gridcolor="rgba(255,255,255,.06)"),
        yaxis=dict(title="누적 리뷰 수", gridcolor="rgba(255,255,255,.06)"),
    )

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.plotly_chart(fig_history, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.info("일/주/월 추이는 데이터가 쌓여야 정확히 표시됩니다. 오늘부터 조회 기록이 저장됩니다.")


# ======================================================
# COMPARE + INSIGHT
# ======================================================

left, right = st.columns([1.35, 1])

with left:
    st.markdown('<div class="section-title">경쟁 병원 리뷰 비교</div>', unsafe_allow_html=True)

    chart_df = df.sort_values("총리뷰수", ascending=True)

    fig = px.bar(
        chart_df,
        x="총리뷰수",
        y="병원명",
        orientation="h",
        text="총리뷰수",
    )

    colors = [
        "#60a5fa" if name == main_hospital else "rgba(156,163,175,.45)"
        for name in chart_df["병원명"]
    ]

    fig.update_traces(
        marker_color=colors,
        texttemplate="%{text:,}개",
        textposition="outside",
    )

    fig.update_layout(
        height=430,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#d1d5db", size=13),
        margin=dict(l=10, r=50, t=10, b=10),
        xaxis=dict(title="", gridcolor="rgba(255,255,255,.06)"),
        yaxis=dict(title=""),
    )

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with right:
    st.markdown('<div class="section-title">마케팅 인사이트</div>', unsafe_allow_html=True)

    if review_gap > 0:
        gap_text = f"현재 1위는 <b>{top_data['병원명']}</b>이며, {main_hospital}과의 리뷰 격차는 <b>{review_gap:,}개</b>입니다."
    else:
        gap_text = f"현재 {main_hospital}이 비교군 내 리뷰 수 기준 <b>1위</b>입니다."

    if main_data["총리뷰수"] >= avg_total:
        avg_text = f"비교군 평균 리뷰 수 <b>{avg_total:,.0f}개</b>보다 높은 수준입니다."
    else:
        avg_text = f"비교군 평균 리뷰 수 <b>{avg_total:,.0f}개</b>보다 낮은 수준입니다."

    st.markdown(f"""
    <div class="insight-card">
        <div class="insight-title">현재 상태 요약</div>
        <div class="insight-text">
            {main_hospital}의 현재 리뷰 순위는 <b>{main_rank}위</b>입니다.<br><br>
            {gap_text}<br><br>
            {avg_text}<br><br>
            일간 증감: <b>{format_delta(daily_delta)}</b><br>
            주간 증감: <b>{format_delta(weekly_delta)}</b><br>
            월간 증감: <b>{format_delta(monthly_delta)}</b><br><br>
            마지막 조회 시간은 <b>{main_data['조회시간']}</b>입니다.
        </div>
    </div>
    """, unsafe_allow_html=True)


# ======================================================
# TABLES
# ======================================================

st.markdown('<div class="section-title">실시간 조회 데이터</div>', unsafe_allow_html=True)

display_df = df[
    [
        "순위",
        "병원명",
        "방문자리뷰",
        "블로그리뷰",
        "총리뷰수",
        "방문자비율",
        "조회상태",
        "조회시간",
        "입력URL",
        "플레이스URL",
    ]
].copy()

st.markdown('<div class="card">', unsafe_allow_html=True)
st.dataframe(display_df, use_container_width=True, hide_index=True)
st.markdown('</div>', unsafe_allow_html=True)


if not history_df.empty:
    st.markdown('<div class="section-title">저장된 히스토리</div>', unsafe_allow_html=True)

    show_history = history_df.rename(columns={
        "hospital_name": "병원명",
        "visitor_reviews": "방문자리뷰",
        "blog_reviews": "블로그리뷰",
        "total_reviews": "총리뷰수",
        "status": "조회상태",
        "place_url": "플레이스URL",
        "collected_at": "수집시간",
    })

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.dataframe(
        show_history.sort_values("수집시간", ascending=False),
        use_container_width=True,
        hide_index=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)


st.caption(
    "주의: 일/주/월 증감은 네이버가 과거 데이터를 제공하는 것이 아니라, "
    "이 앱이 조회 시점마다 저장한 스냅샷을 기준으로 계산합니다. "
    "처음 실행한 날에는 기록 부족으로 표시될 수 있습니다."
)