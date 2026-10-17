"""个人热榜 —— 展示层（卡片式资讯 App 风格）。

本文件只负责渲染。抓取 / 去重 / 翻译 / 打分 / 反馈写库等后端逻辑一字未动：
- 查询、筛选条件、排序、LIMIT 与阶段八完全一致
- 三个按钮仍然调用 add_feedback(...) 并复用同一个 conn + commit + st.rerun
"""

import html

import streamlit as st
from streamlit_extras.metric_cards import style_metric_cards

from src.db import add_feedback, get_conn, init_db

st.set_page_config(layout="wide", page_title="我的个人热榜", page_icon="🔥")

INTEREST_OPTIONS = [
    "全部",
    "AI工具与Agent生态",
    "免费/低成本AI资源",
    "ComfyUI与本地AI图像/视频生成",
]

# 分数胶囊阈值：按本库真实分布标定（中位数 ~2.1、最高 ~7.8）
SCORE_HIGH = 4.0
SCORE_MID = 2.0

# run_fetch.py 翻译后给标题加的英文前缀，展示时摘出来做成「译」标签
TRANS_PREFIX = "[译] "

BRAND = "#6366f1"

CSS = """
<style>
/* ---------- 0. 全局：干掉 Streamlit 默认留白，宽屏撑满 ---------- */
.block-container {
    padding: 1.4rem 2.6rem 5rem 2.6rem !important;
    max-width: 1400px !important;   /* 宽屏撑满；仅在超宽屏（>1660px）才留白，避免行太长 */
    margin: 0 auto !important;
}
header[data-testid="stHeader"] { background: transparent; }

/* ---------- 1. 品牌标识 ---------- */
.ph-logo {
    display: flex; align-items: center; justify-content: center;
    width: 44px; height: 44px; border-radius: 14px; flex: 0 0 auto;
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 55%, #ec4899 100%);
    box-shadow: 0 8px 20px -6px rgba(99, 102, 241, .55);
    font-size: 1.3rem; line-height: 1;
}

/* ---------- 2. 主区 Hero ---------- */
.ph-hero { display: flex; align-items: center; gap: .85rem; margin: .1rem 0 1.2rem 0; }
.ph-hero h1 {
    margin: 0; font-size: 1.65rem; font-weight: 800;
    letter-spacing: -.025em; color: #0f172a;
}
.ph-sub { margin-top: .2rem; font-size: .82rem; color: #8b93a7; }

/* ---------- 3. 资讯卡片 ---------- */
div[class*="st-key-item_"] {
    background: #ffffff;
    border: 1px solid #eceef3;
    border-radius: 16px;
    padding: 15px 18px;
    margin-bottom: 12px;
    box-shadow: 0 1px 2px rgba(16, 24, 40, .04), 0 6px 18px -10px rgba(16, 24, 40, .10);
    transition: all .3s ease;
}
div[class*="st-key-item_"]:hover {
    transform: translateY(-3px);
    border-color: #dcd8ff;
    box-shadow: 0 12px 30px -10px rgba(79, 70, 229, .28), 0 2px 6px rgba(16, 24, 40, .05);
}
/* 卡片内部紧凑化：压掉 Streamlit 元素之间的默认间距 */
div[class*="st-key-item_"] [data-testid="stVerticalBlock"],
div[class*="st-key-item_"] [data-testid="stHorizontalBlock"] { gap: .3rem !important; }
div[class*="st-key-item_"] .element-container { margin: 0 !important; }
div[class*="st-key-item_"] [data-testid="stMarkdownContainer"] { width: 100%; }
div[class*="st-key-item_"] [data-testid="stMarkdownContainer"] p { margin: 0 !important; }

/* ---------- 4. 标题与元数据 ---------- */
.ph-title {
    font-size: 1.05rem; font-weight: 700; line-height: 1.45;
    letter-spacing: -.01em; color: #0f172a;
}
.ph-title a { color: inherit; text-decoration: none; transition: color .3s ease; }
div[class*="st-key-item_"]:hover .ph-title a { color: #4f46e5; }
.ph-meta {
    display: flex; align-items: center; flex-wrap: wrap; gap: .42rem;
    margin-top: .5rem; font-size: .74rem; color: #98a1b3;
}
.ph-src { font-weight: 600; color: #5b6478; }
.ph-interest {
    padding: .05rem .42rem; border: 1px solid #e5e7eb;
    border-radius: 6px; font-size: .7rem; color: #6b7280;
}
.ph-trans {
    padding: .05rem .38rem; border: 1px solid #ddd6fe;
    border-radius: 6px; font-size: .68rem; color: #7c3aed;
}

/* ---------- 5. 分数胶囊 ---------- */
.ph-score {
    padding: .1rem .48rem; border-radius: 999px;
    font-size: .72rem; font-weight: 700; color: #fff; letter-spacing: .02em;
}
.ph-score.high { background: #0f766e; }
.ph-score.mid  { background: #ea580c; }
.ph-score.low  { background: #94a3b8; }

/* ---------- 6. 幽灵按钮 ----------
   注意：按钮外面套了 help= 的 tooltip <span>，所以必须用后代选择器（不能用 > button） */
div[class*="st-key-item_"] button {
    height: 34px !important; min-height: 34px !important;
    padding: 0 .5rem !important;
    border: 0 !important; box-shadow: none !important; background: transparent !important;
    color: #98a1b3 !important; font-size: .78rem !important;
    border-radius: 10px !important;
    transition: all .25s ease !important;
}
div[class*="st-key-item_"] button p {
    font-size: .78rem !important; font-weight: 500 !important; color: inherit !important;
}
div[class*="st-key-item_"] button:hover {
    background: #eef2ff !important; color: #4f46e5 !important;
}
div[class*="st-key-item_"] button:focus:not(:active) {
    border: 0 !important; color: #4f46e5 !important;
}

/* ---------- 6b. 窄屏：卡片内边距收一点（列的重排交给 Streamlit 原生的堆叠行为） ---------- */
@media (max-width: 640px) {
    div[class*="st-key-item_"] { padding: 14px 14px !important; }
}

/* ---------- 7. 侧边栏 ---------- */
section[data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #eceef3; }
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { padding-top: 1rem; }
section[data-testid="stSidebar"] .block-container { padding-top: 1rem !important; }
/* 侧栏里的指标卡要更紧凑，否则 106 这种数字会被挤成省略号 */
section[data-testid="stSidebar"] [data-testid="stMetric"] { padding: .5rem .55rem !important; }
section[data-testid="stSidebar"] [data-testid="stMetricValue"] {
    font-size: 1.15rem !important; line-height: 1.3 !important;
}
section[data-testid="stSidebar"] [data-testid="stMetricValue"] > div { font-size: 1.15rem !important; }
section[data-testid="stSidebar"] [data-testid="stMetricLabel"] p {
    font-size: .68rem !important; letter-spacing: .01em;
}
.ph-brand { display: flex; align-items: center; gap: .6rem; margin-bottom: .2rem; }
.ph-brand .ph-logo { width: 38px; height: 38px; border-radius: 12px; font-size: 1.05rem; }
.ph-brand-name { font-size: .98rem; font-weight: 800; letter-spacing: -.01em; color: #0f172a; }
.ph-brand-tag { font-size: .7rem; color: #98a1b3; }
.ph-section {
    margin: 1.15rem 0 .4rem 0; font-size: .7rem; font-weight: 700;
    letter-spacing: .1em; text-transform: uppercase; color: #b3bac9;
}
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)


def esc(value) -> str:
    """HTML 转义，避免标题/来源里的 & < > 破坏结构。"""
    return html.escape("" if value is None else str(value))


def score_pill(score: float) -> str:
    """分数胶囊：>=SCORE_HIGH 深绿 / >=SCORE_MID 橙 / 其余灰蓝。"""
    if score >= SCORE_HIGH:
        tier = "high"
    elif score >= SCORE_MID:
        tier = "mid"
    else:
        tier = "low"
    return f'<span class="ph-score {tier}" title="热度分 {score:.2f}">{score:.2f}</span>'


# 确保 items 表存在：空库 / 首次运行时也能正常显示「暂无数据」提示
init_db().close()
conn = get_conn()

total = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
saved_n = conn.execute("SELECT COUNT(*) FROM items WHERE is_saved = 1").fetchone()[0]
hidden_n = conn.execute("SELECT COUNT(*) FROM items WHERE is_hidden = 1").fetchone()[0]
updated = conn.execute("SELECT MAX(fetched_at) FROM items").fetchone()[0]

# ---------------- 侧边栏 ----------------
with st.sidebar:
    st.markdown(
        '<div class="ph-brand">'
        '<div class="ph-logo">🔥</div>'
        '<div><div class="ph-brand-name">我的个人热榜</div>'
        '<div class="ph-brand-tag">Personal Hotspot · v1.0</div></div>'
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="ph-section">数据概况</div>', unsafe_allow_html=True)
    m1, m2, m3 = st.columns(3)
    m1.metric("总条数", total)
    m2.metric("已收藏", saved_n)
    m3.metric("已隐藏", hidden_n)
    style_metric_cards(
        background_color="#ffffff",
        border_color="#eceef3",
        border_left_color=BRAND,
        border_radius_px=12,
    )

    st.markdown('<div class="ph-section">筛选</div>', unsafe_allow_html=True)
    hide_read = st.toggle("隐藏已读", value=True)
    hide_hidden = st.toggle("隐藏已隐藏", value=True)
    interest = st.selectbox("筛选兴趣", INTEREST_OPTIONS, index=0)
    limit = st.number_input("显示条数", min_value=10, max_value=200, value=30, step=10)

    if updated:
        st.caption(f"数据更新于 {str(updated)[:19].replace('T', ' ')}")

# ---------------- 主区 Hero ----------------
st.markdown(
    '<div class="ph-hero">'
    '<div class="ph-logo">🔥</div>'
    "<div><h1>我的个人热榜</h1>"
    '<div class="ph-sub">每天自动抓取 · 去重 · 翻译 · 打分排序</div></div>'
    "</div>",
    unsafe_allow_html=True,
)

if total == 0:
    st.info("暂无数据，请先运行 python run_fetch.py")
    conn.close()
    st.stop()

# ---------------- 组装筛选（逻辑未变）----------------
where: list[str] = []
params: list = []
if hide_read:
    where.append("is_read = 0")
if hide_hidden:
    where.append("is_hidden = 0")
if interest != "全部":
    where.append("interest = ?")
    params.append(interest)

where_sql = ("WHERE " + " AND ".join(where)) if where else ""

rows = conn.execute(
    f"SELECT * FROM items {where_sql} ORDER BY final_score DESC LIMIT ?",
    (*params, int(limit)),
).fetchall()

if not rows:
    st.info("当前筛选条件下没有内容")
    conn.close()
    st.stop()

# ---------------- 卡片列表 ----------------
for row in rows:
    score = row["final_score"] if row["final_score"] is not None else 0.0

    title = row["title"] or "(无标题)"
    translated = title.startswith(TRANS_PREFIX)
    if translated:
        title = title[len(TRANS_PREFIX):]

    published = row["published_at"]
    published = published[:19].replace("T", " ") if published else "未知时间"

    with st.container(key=f"item_{row['id']}"):
        # 左边内容 / 右边三个幽灵按钮（按钮保持原生，回调才不会失效）
        main_col, c1, c2, c3 = st.columns(
            [1, 0.13, 0.13, 0.13], gap="small", vertical_alignment="center"
        )

        with main_col:
            meta = [
                score_pill(score),
                f'<span class="ph-src">{esc(row["source_name"] or "未知来源")}</span>',
                f'<span class="ph-interest">{esc(row["interest"] or "未分类")}</span>',
            ]
            if translated:
                meta.append('<span class="ph-trans">译</span>')
            meta.append(f"<span>{esc(published)}</span>")

            st.markdown(
                f'<div class="ph-title"><a href="{esc(row["url"])}" target="_blank" '
                f'rel="noopener">{esc(title)}</a></div>'
                f'<div class="ph-meta">{"".join(meta)}</div>',
                unsafe_allow_html=True,
            )

        with c1:
            if st.button(
                "已读",
                key=f"read_{row['id']}",
                icon=":material/check_circle:",
                help="标记为已读",
                use_container_width=True,
            ):
                conn.execute("UPDATE items SET is_read = 1 WHERE id = ?", (row["id"],))
                conn.commit()
                st.rerun()

        with c2:
            is_saved = bool(row["is_saved"])
            if st.button(
                "已收藏" if is_saved else "收藏",
                key=f"save_{row['id']}",
                icon=":material/star:",
                help="收藏，并给这个来源点个赞（影响来源质量分）",
                use_container_width=True,
            ):
                conn.execute("UPDATE items SET is_saved = 1 WHERE id = ?", (row["id"],))
                add_feedback(row["source_name"], "like", conn)
                conn.commit()
                st.rerun()

        with c3:
            if st.button(
                "隐藏",
                key=f"hide_{row['id']}",
                icon=":material/visibility_off:",
                help="隐藏这条，并降低该来源的权重",
                use_container_width=True,
            ):
                conn.execute("UPDATE items SET is_hidden = 1 WHERE id = ?", (row["id"],))
                add_feedback(row["source_name"], "hide", conn)
                conn.commit()
                st.rerun()

conn.close()
