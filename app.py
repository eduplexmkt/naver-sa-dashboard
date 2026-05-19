"""
네이버 SA 일별 대시보드 — Streamlit 버전
에듀플렉스 마케팅팀 보고용

원본: dashboard.html (로컬 브라우저 전용)
이 파일: Streamlit Cloud 배포 가능 버전
"""

import io
from datetime import datetime, date, timedelta

import pandas as pd
import streamlit as st
import requests
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode


# ============================================
# 페이지 설정
# ============================================
st.set_page_config(
    page_title="네이버 SA 일별 대시보드",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 기본 CSS 커스터마이징 (마케팅 대시보드 디자인 시스템에 통일)
st.markdown("""
<style>
    /* === 폰트 === */
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css');
    html, body, [class*="css"] {
        font-family: 'Pretendard Variable', Pretendard, sans-serif;
    }

    /* === 전체 배경 (옅은 슬레이트) === */
    .stApp {
        background: #f8fafc;
    }
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1400px;
    }

    /* === KPI 카드 (커스텀 HTML) === */
    .kpi-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        min-height: 130px;
        display: flex;
        flex-direction: column;
        gap: 8px;
        transition: box-shadow 0.15s, transform 0.15s;
    }
    .kpi-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        transform: translateY(-1px);
    }
    .kpi-icon {
        width: 36px;
        height: 36px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 18px;
    }
    .kpi-label {
        font-size: 12px;
        color: #64748b;
        font-weight: 500;
        margin-top: auto;
    }
    .kpi-value {
        font-size: 22px;
        font-weight: 700;
        color: #1e293b;
        line-height: 1.2;
    }

    /* === 섹션 헤더 (네이비 바 + 점 마커) === */
    h2 {
        background: #1e293b !important;
        color: #ffffff !important;
        font-size: 15px !important;
        font-weight: 600 !important;
        padding: 12px 16px !important;
        border-radius: 8px !important;
        margin-top: 28px !important;
        margin-bottom: 16px !important;
    }
    h2::before {
        content: "●";
        color: #818cf8;
        margin-right: 8px;
    }
    h3 {
        color: #1e293b !important;
        font-size: 14px !important;
        font-weight: 600 !important;
        margin-top: 16px !important;
    }

    /* === 표 헤더 (네이비) === */
    div[data-testid="stDataFrame"] thead tr th,
    div[data-testid="stDataFrameResizable"] thead tr th {
        background: #1e3a8a !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        border-bottom: 2px solid #1e3a8a !important;
    }
    div[data-testid="stDataFrame"] thead tr th *,
    div[data-testid="stDataFrameResizable"] thead tr th * {
        color: #ffffff !important;
    }
    [data-testid="stDataFrame"] [role="columnheader"] {
        background: #1e3a8a !important;
        color: #ffffff !important;
    }

    /* === 진단 배지 === */
    .diag {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 500;
        white-space: nowrap;
    }
    .diag-expand { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
    .diag-risk   { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    .diag-ctr    { background: #fff3cd; color: #856404; border: 1px solid #ffeaa7; }
    .diag-waste  { background: #343a40; color: #f8f9fa; border: 1px solid #343a40; }
    .diag-low    { background: #f7f8fa; color: #9ca3af; border: 1px solid #e5e7eb; }
    .diag-ok     { background: #f7f8fa; color: #6b7280; border: 1px solid #e5e7eb; }

    /* === 액션 아이템 === */
    .action-item {
        padding: 12px 16px;
        background: #f9fafb;
        border-left: 4px solid #d1d5db;
        border-radius: 6px;
        margin-bottom: 8px;
        font-size: 13px;
    }
    .action-item.priority-high   { border-left-color: #dc3545; background: #fef2f2; }
    .action-item.priority-medium { border-left-color: #f0ad4e; background: #fffaf0; }
    .action-item.priority-good   { border-left-color: #28a745; background: #f0fdf4; }
    .action-item strong { display: block; margin-bottom: 4px; color: #111827; }
    .action-item .meta { color: #6b7280; font-size: 12px; margin-top: 4px; }

    /* === 타이틀 (페이지 제목) === */
    h1 {
        color: #1e293b !important;
        font-weight: 700 !important;
        font-size: 24px !important;
    }

    /* === Streamlit 기본 metric 숨기기 (혹시 남아있는 경우) === */
    /* (커스텀 KPI 카드 사용하므로 stMetric은 사용 안 함) */
</style>
""", unsafe_allow_html=True)


# ============================================
# 기본 설정 / 상수
# ============================================
DEFAULT_SETTINGS = {
    "cpaHigh": 100000,
    "cpaLow": 30000,
    "ctrLow": 0.3,
    "wasteCost": 100000,
    "minClicks": 30,
    "ctrCheckCost": 50000,
}

# GitHub raw CSV URL (매일 자동 갱신되는 데이터 소스)
DEFAULT_CSV_URL = "https://raw.githubusercontent.com/eduplexmkt/naver-sa-dashboard/main/naver_sa_merged.csv"


# ============================================
# 데이터 로드
# ============================================
@st.cache_data(ttl=600)  # 10분 캐시
def load_csv_from_url(url: str) -> pd.DataFrame | None:
    """GitHub raw URL 등 외부에서 CSV 로드. 실패 시 None."""
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return pd.read_csv(io.BytesIO(r.content), encoding="utf-8-sig")
    except Exception as e:
        st.error(f"CSV 로드 실패: {e}")
        return None


@st.cache_data
def parse_uploaded_csv(file_bytes: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(file_bytes), encoding="utf-8-sig")


def normalize_rows(df: pd.DataFrame) -> pd.DataFrame:
    """필수 컬럼 확인 + 타입 정규화"""
    required = ["date", "campaign", "adgroup", "keyword",
                "impressions", "clicks", "cost", "campaign_db_count"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        st.error(f"CSV에 누락된 컬럼: {missing}")
        st.stop()

    df = df.copy()
    df["date"] = df["date"].astype(str)
    for c in ["impressions", "clicks"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    for c in ["cost", "campaign_db_count"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(float)
    return df


# ============================================
# 포맷터
# ============================================
def fmt_won(v):
    if v is None or pd.isna(v):
        return "—"
    return f"₩{int(round(v)):,}"


def fmt_int(v):
    if v is None or pd.isna(v):
        return "—"
    return f"{int(round(v)):,}"


def fmt_db(v):
    if v is None or pd.isna(v):
        return "—"
    if abs(v - round(v)) < 0.05:
        return f"{int(round(v)):,}"
    return f"{v:.1f}"


def fmt_pct(v):
    if v is None or pd.isna(v):
        return "—"
    return f"{v:.2f}%"


# ============================================
# 진단 로직
# ============================================
def diagnose(item: dict, settings: dict, is_keyword: bool = False) -> dict:
    """캠페인/광고그룹/키워드 한 행을 받아 진단 결과 반환"""
    c = item.get("cost", 0) or 0
    clk = item.get("clicks", 0) or 0
    ctr = item.get("ctr")
    db = item.get("db", 0) or 0
    cpa = item.get("cpa")

    # 1. 광고비 낭비
    if not is_keyword and db == 0 and c >= settings["wasteCost"]:
        return {
            "key": "waste", "rank": 5, "cls": "diag-waste",
            "label": "💀 광고비 낭비",
            "tooltip": f"DB 0건인데 광고비 {fmt_won(c)} 집행. 일시중단 검토 권장.",
            "priority": "high",
        }
    # 2. 효율 위험
    if not is_keyword and cpa is not None and not pd.isna(cpa) and cpa > settings["cpaHigh"] and db >= 5:
        return {
            "key": "risk", "rank": 4, "cls": "diag-risk",
            "label": "🚨 효율 위험",
            "tooltip": f"DB단가 {fmt_won(cpa)} (임계 {fmt_won(settings['cpaHigh'])} 초과). 소재·키워드 점검 필요.",
            "priority": "high",
        }
    # 3. CTR 저조
    if ctr is not None and not pd.isna(ctr) and ctr < settings["ctrLow"] and c >= settings["ctrCheckCost"]:
        return {
            "key": "ctr", "rank": 3, "cls": "diag-ctr",
            "label": "⚠️ CTR 저조",
            "tooltip": f"CTR {ctr:.2f}% (임계 {settings['ctrLow']}% 미만). 광고 소재 교체 우선순위.",
            "priority": "medium",
        }
    # 4. 데이터 부족
    if clk < settings["minClicks"]:
        return {
            "key": "low", "rank": 1, "cls": "diag-low",
            "label": "📊 데이터 부족",
            "tooltip": f"클릭 {clk}건 (임계 {settings['minClicks']}건 미만). 비율 지표 신뢰성 낮음.",
            "priority": "good",
        }
    # 5. 확장 후보
    if not is_keyword and cpa is not None and not pd.isna(cpa) and cpa < settings["cpaLow"] and db >= 5:
        return {
            "key": "expand", "rank": 6, "cls": "diag-expand",
            "label": "⭐ 확장 후보",
            "tooltip": f"DB단가 {fmt_won(cpa)} (임계 {fmt_won(settings['cpaLow'])} 미만). 광고비 확장 검토.",
            "priority": "good",
        }
    return {
        "key": "ok", "rank": 2, "cls": "diag-ok",
        "label": "✓ 정상", "tooltip": "특이사항 없음.", "priority": "good",
    }


# ============================================
# 집계 함수
# ============================================
def aggregate_by_campaign(df: pd.DataFrame) -> pd.DataFrame:
    """캠페인별 집계 (DB는 일자×캠페인 단위 중복 제거 후 합산)"""
    if df.empty:
        return pd.DataFrame(columns=["campaign", "cost", "impressions", "clicks", "db", "cpa", "ctr", "cvr"])

    # 키워드 행 합산
    base = df.groupby("campaign", as_index=False).agg(
        cost=("cost", "sum"),
        impressions=("impressions", "sum"),
        clicks=("clicks", "sum"),
    )
    # DB는 (date, campaign) 단위 중복 제거 후 합산
    db = df.drop_duplicates(subset=["date", "campaign"])[["campaign", "campaign_db_count"]] \
        .groupby("campaign", as_index=False).agg(db=("campaign_db_count", "sum"))
    out = base.merge(db, on="campaign", how="left")
    out["db"] = out["db"].fillna(0)
    out["cpa"] = out.apply(lambda r: r["cost"] / r["db"] if r["db"] > 0 else None, axis=1)
    out["ctr"] = out.apply(lambda r: (r["clicks"] / r["impressions"] * 100) if r["impressions"] > 0 else None, axis=1)
    out["cvr"] = out.apply(lambda r: (r["db"] / r["clicks"] * 100) if r["clicks"] > 0 else None, axis=1)
    return out.sort_values("cost", ascending=False).reset_index(drop=True)


def aggregate_by_adgroup(df: pd.DataFrame) -> pd.DataFrame:
    """광고그룹별 집계 (DB는 캠페인 DB를 광고비 비율로 분배)"""
    if df.empty:
        return pd.DataFrame(columns=["campaign", "adgroup", "cost", "impressions", "clicks", "db", "cpa", "ctr", "cvr"])

    # (date, campaign, adgroup) 단위 집계
    by_dca = df.groupby(["date", "campaign", "adgroup"], as_index=False).agg(
        cost=("cost", "sum"),
        impressions=("impressions", "sum"),
        clicks=("clicks", "sum"),
    )
    # 캠페인×일자 광고비 합 (가중치)
    day_camp_cost = df.groupby(["date", "campaign"], as_index=False).agg(camp_cost=("cost", "sum"))
    # 캠페인×일자 DB
    day_camp_db = df.drop_duplicates(subset=["date", "campaign"])[["date", "campaign", "campaign_db_count"]]

    merged = by_dca.merge(day_camp_cost, on=["date", "campaign"]).merge(day_camp_db, on=["date", "campaign"], how="left")
    merged["campaign_db_count"] = merged["campaign_db_count"].fillna(0)
    merged["db_share"] = merged.apply(
        lambda r: r["campaign_db_count"] * (r["cost"] / r["camp_cost"]) if r["camp_cost"] > 0 else 0,
        axis=1,
    )

    # 캠페인+광고그룹 단위 누적
    out = merged.groupby(["campaign", "adgroup"], as_index=False).agg(
        cost=("cost", "sum"),
        impressions=("impressions", "sum"),
        clicks=("clicks", "sum"),
        db=("db_share", "sum"),
    )
    out["cpa"] = out.apply(lambda r: r["cost"] / r["db"] if r["db"] > 0 else None, axis=1)
    out["ctr"] = out.apply(lambda r: (r["clicks"] / r["impressions"] * 100) if r["impressions"] > 0 else None, axis=1)
    out["cvr"] = out.apply(lambda r: (r["db"] / r["clicks"] * 100) if r["clicks"] > 0 else None, axis=1)
    return out.sort_values("cost", ascending=False).reset_index(drop=True)


def aggregate_by_keyword(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["campaign", "adgroup", "keyword", "cost", "impressions", "clicks", "ctr"])
    out = df.groupby(["campaign", "adgroup", "keyword"], as_index=False).agg(
        cost=("cost", "sum"),
        impressions=("impressions", "sum"),
        clicks=("clicks", "sum"),
    )
    out["ctr"] = out.apply(lambda r: (r["clicks"] / r["impressions"] * 100) if r["impressions"] > 0 else None, axis=1)
    return out.sort_values("cost", ascending=False).reset_index(drop=True)


def aggregate_by_date(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["date", "cost", "impressions", "clicks", "db"])

    base = df.groupby("date", as_index=False).agg(
        cost=("cost", "sum"),
        impressions=("impressions", "sum"),
        clicks=("clicks", "sum"),
    )
    db = df.drop_duplicates(subset=["date", "campaign"])[["date", "campaign_db_count"]] \
        .groupby("date", as_index=False).agg(db=("campaign_db_count", "sum"))
    out = base.merge(db, on="date", how="left")
    out["db"] = out["db"].fillna(0)
    return out.sort_values("date").reset_index(drop=True)


# ============================================
# AI 프롬프트 생성
# ============================================
def build_ai_prompt(camp: pd.Series, all_camps: pd.DataFrame, period_label: str) -> str:
    total_cost = all_camps["cost"].sum()
    total_db = all_camps["db"].sum()
    avg_cpa = total_cost / total_db if total_db > 0 else None

    lines = [
        "에듀플렉스(중고등학생 자기주도학습 코칭센터) 네이버 SA 광고 캠페인 성과 분석을 부탁드립니다.",
        "",
        f"## 분석 대상 캠페인: {camp['campaign']}",
        f"- 기간: {period_label}",
        f"- 광고비: {fmt_won(camp['cost'])}",
        f"- DB(상담신청): {fmt_db(camp['db'])}건",
        f"- DB단가: {fmt_won(camp['cpa']) if camp['cpa'] and not pd.isna(camp['cpa']) else '(DB 0건이라 산출 불가)'}",
        f"- 노출수: {fmt_int(camp['impressions'])}",
        f"- 클릭수: {fmt_int(camp['clicks'])}",
        f"- CTR: {fmt_pct(camp['ctr'])}",
        f"- CVR: {fmt_pct(camp['cvr'])}",
        "",
        "## 동일 기간 전체 캠페인 평균 (벤치마크)",
        f"- 총 광고비: {fmt_won(total_cost)}",
        f"- 총 DB: {fmt_db(total_db)}건",
        f"- 평균 DB단가: {fmt_won(avg_cpa) if avg_cpa else '—'}",
        f"- 캠페인 수: {len(all_camps)}개",
        "",
        "## 분석 요청",
        "1. 이 캠페인의 핵심 강점과 약점을 진단해주세요.",
        "2. 평균 대비 위치를 평가하고, 개선이 필요한 영역을 지적해주세요.",
        "3. 구체적인 액션 3가지를 우선순위 순으로 제안해주세요 (예: 광고 소재 변경, 입찰가 조정, 키워드 정리, 광고비 재배분 등).",
        "4. 데이터 신뢰성에 한계가 있다면 그 점도 짚어주세요.",
        "",
        "학부모 타겟 마케팅 관점에서 답변 부탁드립니다.",
    ]
    return "\n".join(lines)


# ============================================
# 메인 앱 시작
# ============================================
st.title("📊 네이버 SA 일별 대시보드")
st.caption("에듀플렉스 마케팅팀 · Streamlit Cloud 호스팅")


# ----- 사이드바: 데이터 소스 및 설정 -----
with st.sidebar:
    st.subheader("📥 데이터 소스")
    data_source = st.radio(
        "데이터 가져오기",
        ["GitHub URL에서 자동 로드", "파일 업로드"],
        index=0,
        help="평소엔 GitHub에서 자동, 수동 검증 시엔 업로드",
    )

    df_raw = None
    if data_source == "GitHub URL에서 자동 로드":
        # 기본 URL은 코드에 박혀있고, secrets로 override 가능
        default_url = DEFAULT_CSV_URL
        if "CSV_URL" in st.secrets:
            default_url = st.secrets["CSV_URL"]
        csv_url = st.text_input(
            "CSV URL",
            value=default_url,
            help="GitHub raw 또는 직접 다운로드 가능한 CSV URL",
        )
        if csv_url:
            df_raw = load_csv_from_url(csv_url)
    else:
        uploaded = st.file_uploader("naver_sa_merged.csv 업로드", type=["csv"])
        if uploaded:
            df_raw = parse_uploaded_csv(uploaded.read())

    st.divider()

    # 진단 임계값 설정
    with st.expander("⚙️ 진단 임계값 설정", expanded=False):
        if "settings" not in st.session_state:
            st.session_state.settings = DEFAULT_SETTINGS.copy()
        s = st.session_state.settings

        s["cpaHigh"] = st.number_input(
            "🚨 효율 위험 — DB단가 임계값 (₩)",
            min_value=0, value=s["cpaHigh"], step=10000,
            help="이 값 초과 + DB ≥ 5건 → 비효율 진단",
        )
        s["cpaLow"] = st.number_input(
            "⭐ 확장 후보 — DB단가 임계값 (₩)",
            min_value=0, value=s["cpaLow"], step=5000,
            help="이 값 미만 + DB ≥ 5건 → 효율 우수 진단",
        )
        s["ctrLow"] = st.number_input(
            "⚠️ CTR 저조 — CTR 임계값 (%)",
            min_value=0.0, max_value=100.0, value=float(s["ctrLow"]), step=0.05,
            help="이 값 미만 + 광고비 ≥ 비용 임계값 → 소재 점검 진단",
        )
        s["wasteCost"] = st.number_input(
            "💀 광고비 낭비 — 광고비 임계값 (₩)",
            min_value=0, value=s["wasteCost"], step=10000,
        )
        s["minClicks"] = st.number_input(
            "📊 데이터 부족 — 클릭 임계값 (건)",
            min_value=0, value=s["minClicks"], step=5,
        )
        s["ctrCheckCost"] = st.number_input(
            "⚠️ CTR 저조 진단 광고비 하한 (₩)",
            min_value=0, value=s["ctrCheckCost"], step=10000,
        )
        if st.button("기본값 복원"):
            st.session_state.settings = DEFAULT_SETTINGS.copy()
            st.rerun()


# ----- 데이터 없을 때 -----
if df_raw is None or df_raw.empty:
    st.info("👈 좌측 사이드바에서 CSV 데이터를 선택하세요.")
    st.markdown("""
    **데이터 소스 옵션:**
    - **GitHub URL**: GitHub private 저장소에 매일 자동 업로드된 CSV의 raw URL 입력
    - **파일 업로드**: 본인 PC의 `naver_sa_merged.csv` 직접 업로드 (테스트용)
    
    데이터 수집은 본인 PC의 `fetch_data.py`에서 진행하며,
    이 대시보드는 생성된 CSV를 시각화만 합니다.
    """)
    st.stop()


# ----- 데이터 정규화 -----
df = normalize_rows(df_raw)
ALL_DATES = sorted(df["date"].unique())
ALL_CAMPAIGNS = sorted(df["campaign"].unique())

st.caption(f"데이터 범위: **{ALL_DATES[0]} ~ {ALL_DATES[-1]}** · 총 **{len(ALL_DATES)}일** · 행 수 **{len(df):,}**")


# ----- 필터 (상단) -----
col1, col2, col3, col4 = st.columns([1.5, 1.5, 1, 1])
with col1:
    period_options = ["전체", "최근 7일", "최근 3일", "직접 지정"] + ALL_DATES[::-1]
    period = st.selectbox("기간", period_options, index=0)
with col2:
    campaign_filter = st.selectbox("캠페인", ["전체"] + ALL_CAMPAIGNS, index=0)
with col3:
    if period == "직접 지정":
        min_d = datetime.strptime(ALL_DATES[0], "%Y-%m-%d").date()
        max_d = datetime.strptime(ALL_DATES[-1], "%Y-%m-%d").date()
        date_from = st.date_input("시작일", value=min_d, min_value=min_d, max_value=max_d)
    else:
        date_from = None
with col4:
    if period == "직접 지정":
        date_to = st.date_input("종료일", value=max_d, min_value=min_d, max_value=max_d)
    else:
        date_to = None


# ----- 기간 필터 적용 -----
def apply_period_filter(df: pd.DataFrame, period: str) -> pd.DataFrame:
    if period == "전체":
        return df
    if period == "최근 7일":
        recent = set(ALL_DATES[-7:])
        return df[df["date"].isin(recent)]
    if period == "최근 3일":
        recent = set(ALL_DATES[-3:])
        return df[df["date"].isin(recent)]
    if period == "직접 지정" and date_from and date_to:
        sd, ed = date_from.strftime("%Y-%m-%d"), date_to.strftime("%Y-%m-%d")
        return df[(df["date"] >= sd) & (df["date"] <= ed)]
    # 특정 일자
    return df[df["date"] == period]


df_filtered = apply_period_filter(df, period)
if campaign_filter != "전체":
    df_filtered = df_filtered[df_filtered["campaign"] == campaign_filter]


# ----- KPI -----
if not df_filtered.empty:
    by_camp = aggregate_by_campaign(df_filtered)
    total_cost = by_camp["cost"].sum()
    total_db = by_camp["db"].sum()
    total_imp = by_camp["impressions"].sum()
    total_clk = by_camp["clicks"].sum()
    total_cpa = total_cost / total_db if total_db > 0 else None
    total_ctr = (total_clk / total_imp * 100) if total_imp > 0 else None
    total_cvr = (total_db / total_clk * 100) if total_clk > 0 else None

    # KPI 카드 (마케팅 대시보드 스타일 - 이모지 아이콘 + 컬러 박스)
    kpi_data = [
        ("💰", "총 광고비", fmt_won(total_cost), "#fef3c7", "#d97706"),
        ("📋", "DB수",      fmt_db(total_db) + "건", "#dbeafe", "#2563eb"),
        ("💵", "DB단가",    fmt_won(total_cpa), "#fee2e2", "#dc2626"),
        ("👁️", "노출수",    fmt_int(total_imp), "#e0e7ff", "#4f46e5"),
        ("🖱️", "클릭수",    fmt_int(total_clk), "#dcfce7", "#16a34a"),
        ("🎯", "CTR",       fmt_pct(total_ctr), "#fce7f3", "#db2777"),
        ("📈", "CVR",       fmt_pct(total_cvr), "#f3e8ff", "#9333ea"),
    ]
    kpi_cols = st.columns(7)
    for col, (icon, label, value, bg, fg) in zip(kpi_cols, kpi_data):
        col.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-icon" style="background:{bg}; color:{fg};">{icon}</div>
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
        </div>
        """, unsafe_allow_html=True)


# ----- 액션 요약 카드 -----
st.subheader("📋 이번 기간 주요 액션")
camps_with_diag = []
for _, row in by_camp.iterrows():
    diag = diagnose(row.to_dict(), st.session_state.settings)
    camps_with_diag.append({**row.to_dict(), "diagnosis": diag})

priority_order = {"waste": 1, "risk": 2, "ctr": 3, "expand": 4, "low": 99, "ok": 99}
actionable = sorted(
    [c for c in camps_with_diag if c["diagnosis"]["key"] in ["waste", "risk", "ctr", "expand"]],
    key=lambda c: (priority_order[c["diagnosis"]["key"]], -c["cost"]),
)[:8]

if not actionable:
    st.info("현재 기간에 특이 액션 항목이 없습니다. 모든 캠페인이 정상 운영 중이거나 데이터가 부족합니다.")
else:
    for c in actionable:
        d = c["diagnosis"]
        icon = d["label"].split(" ")[0]
        label_text = " ".join(d["label"].split(" ")[1:])
        meta_text = f"광고비 {fmt_won(c['cost'])} · DB {fmt_db(c['db'])}건 · CTR {fmt_pct(c.get('ctr'))} · DB단가 {fmt_won(c.get('cpa'))}"
        st.markdown(f"""
        <div class="action-item priority-{d['priority']}">
            <strong>{icon} {c['campaign']} — {label_text}</strong>
            {d['tooltip']}
            <div class="meta">{meta_text}</div>
        </div>
        """, unsafe_allow_html=True)


# ----- 캠페인 성과 표 -----
st.subheader("🎯 캠페인별 성과")
camp_df = by_camp.copy()
camp_df["진단"] = [diagnose(r.to_dict(), st.session_state.settings)["label"] for _, r in camp_df.iterrows()]

# 표시용 DataFrame (숫자 값 그대로 유지 → 헤더 클릭 정렬 시 숫자 기준)
display_camp = pd.DataFrame({
    "캠페인": camp_df["campaign"],
    "광고비": camp_df["cost"],
    "DB수": camp_df["db"],
    "DB단가": camp_df["cpa"],
    "노출수": camp_df["impressions"],
    "클릭수": camp_df["clicks"],
    "CTR": camp_df["ctr"],
    "CVR": camp_df["cvr"],
    "진단": camp_df["진단"],
})
st.dataframe(
    display_camp,
    use_container_width=True,
    hide_index=True,
    column_config={
        "광고비": st.column_config.NumberColumn(format="₩%d"),
        "DB수":  st.column_config.NumberColumn(format="%.1f"),
        "DB단가": st.column_config.NumberColumn(format="₩%d"),
        "노출수": st.column_config.NumberColumn(format="%d"),
        "클릭수": st.column_config.NumberColumn(format="%d"),
        "CTR":   st.column_config.NumberColumn(format="%.2f%%"),
        "CVR":   st.column_config.NumberColumn(format="%.2f%%"),
    },
)


# ----- AI 프롬프트 복사 영역 -----
with st.expander("🤖 캠페인 AI 분석 프롬프트 생성"):
    selected_camp = st.selectbox("분석할 캠페인 선택", camp_df["campaign"].tolist())
    if selected_camp:
        camp_row = camp_df[camp_df["campaign"] == selected_camp].iloc[0]
        period_label = period if period != "직접 지정" else f"{date_from} ~ {date_to}"
        prompt = build_ai_prompt(camp_row, camp_df, period_label)
        st.code(prompt, language=None)
        st.caption("📋 위 박스 우측 상단의 복사 버튼 → claude.ai 에 붙여넣어 분석을 받으세요.")


# ----- 광고그룹별 표 -----
st.subheader("📦 광고그룹별 성과")
st.caption("예산 증액·삭감 의사결정용. DB는 광고비 비율로 분배된 추정값입니다.")

ag_col1, ag_col2, ag_col3 = st.columns([1, 2, 1])
with ag_col1:
    ag_min_cost = st.number_input("최소 광고비 (₩)", min_value=0, value=10000, step=1000, key="ag_min_cost")
with ag_col2:
    ag_query = st.text_input("광고그룹 검색", placeholder="예: 자기주도, 학습법", key="ag_query")

ag_df = aggregate_by_adgroup(df_filtered)
ag_df = ag_df[ag_df["cost"] >= ag_min_cost]
if ag_query:
    q = ag_query.lower()
    ag_df = ag_df[
        ag_df["adgroup"].str.lower().str.contains(q, na=False) |
        ag_df["campaign"].str.lower().str.contains(q, na=False)
    ]
ag_df["진단"] = [diagnose(r.to_dict(), st.session_state.settings)["label"] for _, r in ag_df.iterrows()]

display_ag = pd.DataFrame({
    "캠페인": ag_df["campaign"],
    "광고그룹": ag_df["adgroup"],
    "광고비": ag_df["cost"],
    "DB수(추정)": ag_df["db"],
    "DB단가": ag_df["cpa"],
    "노출수": ag_df["impressions"],
    "클릭수": ag_df["clicks"],
    "CTR": ag_df["ctr"],
    "CVR": ag_df["cvr"],
    "진단": ag_df["진단"],
})
st.caption(f"{len(ag_df):,}개 광고그룹")
st.dataframe(
    display_ag,
    use_container_width=True,
    hide_index=True,
    column_config={
        "광고비": st.column_config.NumberColumn(format="₩%d"),
        "DB수(추정)": st.column_config.NumberColumn(format="%.1f"),
        "DB단가": st.column_config.NumberColumn(format="₩%d"),
        "노출수": st.column_config.NumberColumn(format="%d"),
        "클릭수": st.column_config.NumberColumn(format="%d"),
        "CTR":   st.column_config.NumberColumn(format="%.2f%%"),
        "CVR":   st.column_config.NumberColumn(format="%.2f%%"),
    },
)


# ----- 키워드별 표 -----
st.subheader("🔑 키워드별 성과")

kw_df = aggregate_by_keyword(df_filtered)
# 광고비 1원 이상만 표시 (0원 키워드 제외)
kw_df = kw_df[kw_df["cost"] >= 1]
kw_df["진단"] = [diagnose(r.to_dict(), st.session_state.settings, is_keyword=True)["label"] for _, r in kw_df.iterrows()]

# AG Grid용 DataFrame (숫자 그대로 유지)
display_kw = pd.DataFrame({
    "캠페인": kw_df["campaign"].values,
    "광고그룹": kw_df["adgroup"].values,
    "키워드": kw_df["keyword"].values,
    "광고비": kw_df["cost"].values,
    "노출수": kw_df["impressions"].values,
    "클릭수": kw_df["clicks"].values,
    "CTR": kw_df["ctr"].values,
    "진단": kw_df["진단"].values,
})
st.caption(f"{len(kw_df):,}개 키워드")

# AG Grid 옵션 설정 (매체별 성과 디자인)
gb = GridOptionsBuilder.from_dataframe(display_kw)
gb.configure_default_column(
    resizable=False,
    sortable=True,
    filter=False,
    suppressMovable=True,
    cellStyle={'fontSize': '13px', 'color': '#1e293b'},
)

# 컬럼별 너비/포맷 설정
gb.configure_column("캠페인",  width=160, cellStyle={'color': '#2563eb', 'fontWeight': '500'})
gb.configure_column("광고그룹", width=160, cellStyle={'color': '#2563eb', 'fontWeight': '500'})
gb.configure_column("키워드",   width=180, cellStyle={'color': '#2563eb', 'fontWeight': '500'})
gb.configure_column(
    "광고비", width=110, type=["numericColumn"],
    valueFormatter=JsCode("function(p){return p.value==null?'-':'₩'+p.value.toLocaleString();}"),
)
gb.configure_column(
    "노출수", width=100, type=["numericColumn"],
    valueFormatter=JsCode("function(p){return p.value==null?'-':p.value.toLocaleString();}"),
)
gb.configure_column(
    "클릭수", width=90, type=["numericColumn"],
    valueFormatter=JsCode("function(p){return p.value==null?'-':p.value.toLocaleString();}"),
)
gb.configure_column(
    "CTR", width=90, type=["numericColumn"],
    valueFormatter=JsCode("function(p){return p.value==null?'-':p.value.toFixed(2)+'%';}"),
)
gb.configure_column("진단", width=110)

# 그리드 전체 옵션
grid_options = gb.build()
grid_options['domLayout'] = 'normal'
grid_options['headerHeight'] = 38
grid_options['rowHeight'] = 36

# 커스텀 CSS (매체별 성과 톤)
custom_css = {
    ".ag-header": {"background-color": "#1e3a8a !important", "color": "#ffffff !important"},
    ".ag-header-cell": {"color": "#ffffff !important", "font-weight": "600 !important", "font-size": "13px !important"},
    ".ag-header-cell-text": {"color": "#ffffff !important"},
    ".ag-row-even": {"background-color": "#ffffff !important"},
    ".ag-row-odd": {"background-color": "#f1f5f9 !important"},
    ".ag-row-hover": {"background-color": "#e0e7ff !important"},
    ".ag-cell": {"border": "none !important"},
}

AgGrid(
    display_kw,
    gridOptions=grid_options,
    custom_css=custom_css,
    allow_unsafe_jscode=True,
    fit_columns_on_grid_load=False,
    height=min(500, 50 + 36 * len(display_kw)),
    theme="streamlit",
)

st.caption("""
※ DB수·DB단가·CVR은 키워드 단위로 집계되지 않습니다. 네이버 파워링크 검색어별 보고서는
노출·클릭·광고비만 제공하며, 구글 시트 DB는 캠페인 단위로만 귀속됩니다.
""")

st.divider()
st.caption(f"페이지 마지막 로드: {datetime.now().strftime('%Y-%m-%d %H:%M')} · 데이터는 10분 캐시 후 자동 갱신")
