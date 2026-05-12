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
import plotly.graph_objects as go
import requests


# ============================================
# 페이지 설정
# ============================================
st.set_page_config(
    page_title="네이버 SA 일별 대시보드",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 기본 CSS 커스터마이징
st.markdown("""
<style>
    /* 폰트 */
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css');
    html, body, [class*="css"] {
        font-family: 'Pretendard Variable', Pretendard, sans-serif;
    }
    /* 진단 배지 */
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
    /* KPI 카드 강조 */
    [data-testid="metric-container"] {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        padding: 12px;
        border-radius: 10px;
    }
    /* 액션 아이템 */
    .action-item {
        padding: 10px 14px;
        background: #f7f8fa;
        border-left: 3px solid #d1d5db;
        border-radius: 4px;
        margin-bottom: 8px;
        font-size: 13px;
    }
    .action-item.priority-high   { border-left-color: #dc3545; }
    .action-item.priority-medium { border-left-color: #f0ad4e; }
    .action-item.priority-good   { border-left-color: #28a745; }
    .action-item strong { display: block; margin-bottom: 4px; }
    .action-item .meta { color: #6b7280; font-size: 12px; margin-top: 4px; }
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
        # st.secrets 또는 기본값
        default_url = ""
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

    kpi_cols = st.columns(7)
    kpi_cols[0].metric("광고비", fmt_won(total_cost))
    kpi_cols[1].metric("DB수", fmt_db(total_db) + " 건")
    kpi_cols[2].metric("DB단가", fmt_won(total_cpa))
    kpi_cols[3].metric("노출수", fmt_int(total_imp))
    kpi_cols[4].metric("클릭수", fmt_int(total_clk))
    kpi_cols[5].metric("CTR", fmt_pct(total_ctr))
    kpi_cols[6].metric("CVR", fmt_pct(total_cvr))


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


# ----- 차트: 일별 트렌드 -----
st.subheader("📈 일별 트렌드")
date_agg = aggregate_by_date(df_filtered)
if not date_agg.empty:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=date_agg["date"], y=date_agg["cost"],
        name="광고비 (₩)", marker_color="rgba(31, 111, 235, 0.6)",
        yaxis="y",
    ))
    fig.add_trace(go.Scatter(
        x=date_agg["date"], y=date_agg["db"],
        name="DB수 (건)", line=dict(color="#e0794b", width=2),
        marker=dict(size=8), mode="lines+markers",
        yaxis="y2",
    ))
    fig.update_layout(
        height=320,
        yaxis=dict(title="광고비", side="left"),
        yaxis2=dict(title="DB수", side="right", overlaying="y"),
        legend=dict(orientation="h", y=1.1),
        margin=dict(l=40, r=40, t=40, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)


# ----- 차트: DB단가 추이 -----
st.subheader("📉 일별 DB단가 추이")
if not date_agg.empty:
    cpa_series = date_agg.apply(lambda r: r["cost"] / r["db"] if r["db"] > 0 else None, axis=1)
    total_db_period = date_agg["db"].sum()
    avg_cpa = date_agg["cost"].sum() / total_db_period if total_db_period > 0 else None

    fig_cpa = go.Figure()
    fig_cpa.add_trace(go.Scatter(
        x=date_agg["date"], y=cpa_series,
        name="DB단가", line=dict(color="#5b8c5a", width=2),
        marker=dict(size=8), mode="lines+markers",
        connectgaps=False,
    ))
    if avg_cpa is not None:
        fig_cpa.add_trace(go.Scatter(
            x=date_agg["date"], y=[avg_cpa] * len(date_agg),
            name=f"기간 평균 ({fmt_won(avg_cpa)})",
            line=dict(color="#9aa0a8", width=1.5, dash="dash"),
            mode="lines",
        ))
    fig_cpa.update_layout(
        height=280,
        yaxis=dict(title="DB단가 (₩)"),
        legend=dict(orientation="h", y=1.1),
        margin=dict(l=40, r=40, t=40, b=40),
    )
    st.plotly_chart(fig_cpa, use_container_width=True)
    st.caption("※ DB가 0건인 일자는 단가 계산 불가로 차트에서 빠집니다.")


# ----- 캠페인별 표 -----
st.subheader("🎯 캠페인별 현황")
camp_df = by_camp.copy()
camp_df["진단"] = [diagnose(r.to_dict(), st.session_state.settings)["label"] for _, r in camp_df.iterrows()]
# 포맷팅된 표시용 컬럼
display_camp = pd.DataFrame({
    "캠페인": camp_df["campaign"],
    "광고비": camp_df["cost"].apply(fmt_won),
    "DB수": camp_df["db"].apply(fmt_db),
    "DB단가": camp_df["cpa"].apply(fmt_won),
    "노출수": camp_df["impressions"].apply(fmt_int),
    "클릭수": camp_df["clicks"].apply(fmt_int),
    "CTR": camp_df["ctr"].apply(fmt_pct),
    "CVR": camp_df["cvr"].apply(fmt_pct),
    "진단": camp_df["진단"],
})
st.dataframe(display_camp, use_container_width=True, hide_index=True)


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
st.subheader("📦 광고그룹별 현황")
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
    "광고비": ag_df["cost"].apply(fmt_won),
    "DB수(추정)": ag_df["db"].apply(fmt_db),
    "DB단가": ag_df["cpa"].apply(fmt_won),
    "노출수": ag_df["impressions"].apply(fmt_int),
    "클릭수": ag_df["clicks"].apply(fmt_int),
    "CTR": ag_df["ctr"].apply(fmt_pct),
    "CVR": ag_df["cvr"].apply(fmt_pct),
    "진단": ag_df["진단"],
})
st.caption(f"{len(ag_df):,}개 광고그룹")
st.dataframe(display_ag, use_container_width=True, hide_index=True)


# ----- 키워드별 표 -----
st.subheader("🔑 키워드별 현황")
kw_col1, _ = st.columns([1, 3])
with kw_col1:
    kw_min_cost = st.number_input("최소 광고비 (₩)", min_value=0, value=1, step=1, key="kw_min_cost")

kw_df = aggregate_by_keyword(df_filtered)
kw_df = kw_df[kw_df["cost"] >= kw_min_cost]
kw_df["진단"] = [diagnose(r.to_dict(), st.session_state.settings, is_keyword=True)["label"] for _, r in kw_df.iterrows()]

display_kw = pd.DataFrame({
    "캠페인": kw_df["campaign"],
    "광고그룹": kw_df["adgroup"],
    "키워드": kw_df["keyword"],
    "광고비": kw_df["cost"].apply(fmt_won),
    "노출수": kw_df["impressions"].apply(fmt_int),
    "클릭수": kw_df["clicks"].apply(fmt_int),
    "CTR": kw_df["ctr"].apply(fmt_pct),
    "DB수": "—",
    "DB단가": "—",
    "CVR": "—",
    "진단": kw_df["진단"],
})
st.caption(f"{len(kw_df):,}개 키워드")
st.dataframe(display_kw, use_container_width=True, hide_index=True)

st.caption("""
※ DB수·DB단가·CVR은 키워드 단위로 집계되지 않습니다. 네이버 파워링크 검색어별 보고서는
노출·클릭·광고비만 제공하며, 구글 시트 DB는 캠페인 단위로만 귀속됩니다.
""")

st.divider()
st.caption(f"마지막 갱신: {datetime.now().strftime('%Y-%m-%d %H:%M')} · 캐시 TTL 10분")
