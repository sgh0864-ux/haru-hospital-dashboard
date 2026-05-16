import streamlit as st
import pandas as pd
import plotly.express as px
import re
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


st.set_page_config(
    page_title="하루한의원 리뷰 눈팅",
    layout="wide"
)

st.markdown("""
<style>
.stApp { background-color: #0f1117; color: white; }
.block-container { max-width: 1350px; padding-top: 35px; padding-bottom: 80px; }

html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    color: white;
}

.main-title { font-size: 48px; font-weight: 800; color: white; margin-bottom: 10px; }
.main-sub { color: #9ca3af; font-size: 17px; margin-bottom: 45px; }

.kpi-card {
    background: #171b26;
    border-radius: 24px;
    padding: 26px;
    border: 1px solid #262b36;
    min-height: 150px;
}

.kpi-title { color: #9ca3af; font-size: 14px; font-weight: 600; margin-bottom: 16px; }
.kpi-value { color: white; font-size: 38px; font-weight: 800; line-height: 1; }
.kpi-desc { margin-top: 14px; color: #9ca3af; font-size: 13px; line-height: 1.5; }

.section-title {
    color: white;
    font-size: 28px;
    font-weight: 700;
    margin-top: 55px;
    margin-bottom: 22px;
}

.content-card {
    background: #171b26;
    border-radius: 24px;
    padding: 24px;
    border: 1px solid #262b36;
}
</style>
""", unsafe_allow_html=True)


def kpi_card(title, value, desc):
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-title">{title}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-desc">{desc}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


main_hospital = "하루한의원"

hospital_urls = {
    "하루한의원": "https://naver.me/xHg774HK",
    "이로움한의원": "https://naver.me/5WOuxbRt",
    "경희본한의원": "https://naver.me/GyYrk7Bl",
    "왕십리옥토한의원": "https://naver.me/5CW490lL",
    "함소아한의원 왕십리": "https://naver.me/5pwZ4BWi"
}


def make_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1500,1300")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    return webdriver.Chrome(options=options)


def parse_total_counts(text):
    visitor = 0
    blog = 0

    visitor_patterns = [
        r"방문자\s*리뷰\s*([0-9,]+)",
        r"방문자리뷰\s*([0-9,]+)"
    ]

    blog_patterns = [
        r"블로그\s*리뷰\s*([0-9,]+)",
        r"블로그리뷰\s*([0-9,]+)"
    ]

    for pattern in visitor_patterns:
        match = re.search(pattern, text)
        if match:
            visitor = int(match.group(1).replace(",", ""))
            break

    for pattern in blog_patterns:
        match = re.search(pattern, text)
        if match:
            blog = int(match.group(1).replace(",", ""))
            break

    return visitor, blog


def extract_dates(text):
    today = datetime.now()
    dates = []

    patterns = [
        r"(20\d{2})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})",
        r"(\d{1,2})[.\-/월\s]+(\d{1,2})[일.]?"
    ]

    for match in re.finditer(patterns[0], text):
        y, m, d = match.groups()
        dates.append((int(y), int(m), int(d)))

    for match in re.finditer(patterns[1], text):
        m, d = match.groups()
        dates.append((today.year, int(m), int(d)))

    return dates


def count_month_reviews(dates, year, month):
    return sum(1 for y, m, d in dates if y == year and m == month)


def click_review_tab(driver, keyword):
    candidates = driver.find_elements(By.XPATH, f"//*[contains(text(), '{keyword}')]")

    for el in candidates:
        try:
            driver.execute_script("arguments[0].click();", el)
            time.sleep(2)
            return True
        except:
            pass

    return False


def collect_visible_text_with_scroll(driver, scroll_count=5):
    texts = []

    for _ in range(scroll_count):
        text = driver.find_element(By.TAG_NAME, "body").text
        texts.append(text)

        driver.execute_script("window.scrollBy(0, 900);")
        time.sleep(1.2)

    return "\n".join(texts)


@st.cache_data(ttl=600)
def get_naver_place_data(url):
    driver = make_driver()

    visitor_total = 0
    blog_total = 0

    visitor_this_month = 0
    visitor_prev_month = 0
    blog_this_month = 0
    blog_prev_month = 0

    try:
        driver.get(url)

        WebDriverWait(driver, 12).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        time.sleep(3)

        try:
            WebDriverWait(driver, 8).until(
                EC.frame_to_be_available_and_switch_to_it("entryIframe")
            )
            time.sleep(2)
        except:
            pass

        base_text = driver.find_element(By.TAG_NAME, "body").text
        visitor_total, blog_total = parse_total_counts(base_text)

        today = datetime.now()
        this_year = today.year
        this_month = today.month

        prev_month = this_month - 1
        prev_year = this_year

        if prev_month == 0:
            prev_month = 12
            prev_year -= 1

        # 방문자 리뷰 탭
        click_review_tab(driver, "방문자")
        visitor_text = collect_visible_text_with_scroll(driver, scroll_count=6)
        visitor_dates = extract_dates(visitor_text)

        visitor_this_month = count_month_reviews(
            visitor_dates,
            this_year,
            this_month
        )

        visitor_prev_month = count_month_reviews(
            visitor_dates,
            prev_year,
            prev_month
        )

        # 블로그 리뷰 탭
        click_review_tab(driver, "블로그")
        blog_text = collect_visible_text_with_scroll(driver, scroll_count=6)
        blog_dates = extract_dates(blog_text)

        blog_this_month = count_month_reviews(
            blog_dates,
            this_year,
            this_month
        )

        blog_prev_month = count_month_reviews(
            blog_dates,
            prev_year,
            prev_month
        )

    except Exception as e:
        print("수집 실패:", e)

    finally:
        driver.quit()

    return {
        "방문자 리뷰": visitor_total,
        "블로그 리뷰": blog_total,
        "총 리뷰": visitor_total + blog_total,
        "이번달 방문자": visitor_this_month,
        "이번달 블로그": blog_this_month,
        "저번달 방문자": visitor_prev_month,
        "저번달 블로그": blog_prev_month,
    }


today = datetime.now()
today_label = f"{today.month}월 {today.day}일"
this_month_label = f"{today.month}월"

data = []

with st.spinner("네이버 플레이스 데이터를 조회중입니다..."):
    for name, url in hospital_urls.items():
        result = get_naver_place_data(url)

        data.append({
            "병원명": name,
            "방문자 리뷰": result["방문자 리뷰"],
            "블로그 리뷰": result["블로그 리뷰"],
            "총 리뷰": result["총 리뷰"],
            "이번달 방문자": result["이번달 방문자"],
            "이번달 블로그": result["이번달 블로그"],
            "저번달 방문자": result["저번달 방문자"],
            "저번달 블로그": result["저번달 블로그"],
        })


df = pd.DataFrame(data)
df = df.sort_values("총 리뷰", ascending=False)

main = df[df["병원명"] == main_hospital].iloc[0]

this_month_visitor = int(main["이번달 방문자"])
this_month_blog = int(main["이번달 블로그"])
this_month_total = this_month_visitor + this_month_blog

prev_month_visitor = int(main["저번달 방문자"])
prev_month_blog = int(main["저번달 블로그"])
prev_month_total = prev_month_visitor + prev_month_blog

trend_total = this_month_total - prev_month_total
trend_visitor = this_month_visitor - prev_month_visitor
trend_blog = this_month_blog - prev_month_blog


st.markdown(f"""
<div class="main-title">하루한의원 리뷰 눈팅</div>
<div class="main-sub">
네이버 플레이스 리뷰 기반 실시간 모니터링 · 기준일 {today_label}
</div>
""", unsafe_allow_html=True)


col1, col2, col3 = st.columns(3)

with col1:
    kpi_card(
        "총 리뷰",
        f"{int(main['총 리뷰']):,}개",
        "방문자 + 블로그 리뷰"
    )

with col2:
    kpi_card(
        "방문자 리뷰",
        f"{int(main['방문자 리뷰']):,}개",
        "네이버 방문 인증 리뷰"
    )

with col3:
    kpi_card(
        "블로그 리뷰",
        f"{int(main['블로그 리뷰']):,}개",
        "네이버 블로그 후기"
    )


st.markdown(
    '<div class="section-title">신규 리뷰 트렌드</div>',
    unsafe_allow_html=True
)

k1, k2 = st.columns(2)

with k1:
    kpi_card(
        "월간 신규 리뷰",
        f"+{this_month_total}개",
        f"{this_month_label} 작성일 기준<br>"
        f"방문자 +{this_month_visitor}개 · 블로그 +{this_month_blog}개"
    )

with k2:
    kpi_card(
        "증감 추이",
        f"{trend_total:+}개",
        f"이번달 - 저번달<br>"
        f"방문자 {trend_visitor:+}개 · 블로그 {trend_blog:+}개"
    )


st.markdown(
    '<div class="section-title">주변 병원 리뷰 비교</div>',
    unsafe_allow_html=True
)

bar_fig = px.bar(
    df,
    x="병원명",
    y="총 리뷰"
)

bar_fig.update_traces(
    marker_color=[
        "#60a5fa" if x == main_hospital else "#374151"
        for x in df["병원명"]
    ]
)

bar_fig.update_layout(
    plot_bgcolor="#171b26",
    paper_bgcolor="#171b26",
    font=dict(color="white"),
    xaxis_title="",
    yaxis_title="리뷰 수",
    xaxis=dict(showgrid=False),
    yaxis=dict(gridcolor="#2b3240")
)

st.markdown('<div class="content-card">', unsafe_allow_html=True)
st.plotly_chart(bar_fig, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)


st.markdown(
    '<div class="section-title">전체 병원 데이터</div>',
    unsafe_allow_html=True
)

st.markdown('<div class="content-card">', unsafe_allow_html=True)
st.dataframe(df, use_container_width=True, hide_index=True)
st.markdown('</div>', unsafe_allow_html=True)