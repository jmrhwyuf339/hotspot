"""Streamlit 展示页：卡片式 UI（阶段九美化）。

后端逻辑（查询 / 去重 / 打分 / 反馈）与阶段八完全一致，仅重写展示层。
"""

import html

import streamlit as st
from streamlit_extras.metric_cards import style_metric_cards

from src.db import add_feedback, get_conn, init_db

st.set_page_config(page_title="我的个人热榜", page_icon="🔥", layout="wide")

INTEREST_OPTIONS = [
    "全部",
    "AI工具与Agent生态",
    "免费/低成本AI资源",
    "ComfyUI与本地AI图像/视频生成",
]

# 分数标签阈值：按本库真实分布标定（中位数 ~2.1，最高 ~7.8）。
# 取 4.0 / 2.0 时大约 11% 绿、52% 黄、37% 灰，三档都有内容。
# （若用 8 / 5，106 条里只有 1 条不是灰色，标签就失去意义了。）
SCORE_HIGH = 4.0
SCORE_MID = 2.0

BRAND = "#6366f1"

CSS = """
<style>
/* ---------- 页面排版 ---------- */
.block-container { padding-top: 2.4rem; padding-bottom: 3.5rem; max-width: 1200px; }

.ph-hero { display: flex; align-items: baseline; gap: .7rem; flex-wrap: wrap; }
.ph-hero h1 { font-size: 1.9rem; font-weight: 800; letter-spacing: -.02em; margin: 0; }
.ph-hero .ph-sub { font-size: .88rem; opacity: .55; }
.ph-rule { height: 3px; width: 64px; border-radius: 3px; margin: .7rem 0 1.3rem 0;
           background: linear-gradient(90deg, %(brand)s, %(brand)s55); }

/* ---------- 卡片 ---------- */
div[class*="st-key-item_"] {
    background: var(--secondary-background-color);
    border: 1px solid rgba(128,128,128,.18);
    border-radius: 14px;
    padding: 15px 18px 11px 18px;
    margin-bottom: 10px;
    box-shadow: 0 1px 2px rgba(0,0,0,.05), 0 4px 14px rgba(0,0,0,.04);
    transition: box-shadow .18s ease, border-color .18s ease, transform .18s ease;
}
div[class*="st-key-item_"]:hover {
    border-color: %(brand)s;
    box-shadow: 0 7px 24px rgba(0,0,0,.10);
    transform: translateY(-1px);
}
.ph-title a { font-size: 1.04rem; font-weight: 650; line-height: 1.45; text-decoration: none;
              color: inherit; }
.ph-title a:hover { color: %(brand)s; text-decoration: underline; }
.ph-meta { display: flex; align-items: center; gap: .45rem; flex-wrap: wrap;
           margin-top: .45rem; font-size: .78rem; opacity: .75; }
.ph-chip { background: rgba(128,128,128,.13); padding: .08rem .45rem; border-radius: 6px; }

/* ---------- 分数标签 ---------- */
.ph-badge { padding: .1rem .55rem; border-radius: 999px; font-weight: 700; font-size: .76rem;
            letter-spacing: .01em; }
.ph-badge.high { background: #dcfce7; color: #15803d; }
.ph-badge.mid  { background: #fef3c7; color: #b45309; }
.ph-badge.low  { background: rgba(128,128,128,.18); color: inherit; opacity: .8; }

/* ---------- 卡片内按钮 ---------- */
div[class*="st-key-item_"] div[data-testid="stButton"] > button {
    border-radius: 10px; border: 1px solid rgba(128,128,128,.22);
    background: transparent; font-size: .82rem; padding: .3rem .4rem;
    transition: all .15s ease;
}
div[class*="st-key-item_"] div[data-testid="stButton"] > button:hover {
    border-color: %(brand)s; color: %(brand)s;
    background: %(brand)s14;
}

/* ---------- 侧边栏 ---------- */
section[data-testid="stSidebar"] {
    background: var(--secondary-background-color);
    border-right: 1px solid rgba(128,128,128,.15);
}
section[data-testid="stSidebar"] .block-container { padding-top: 1.6rem; }
</style>
""" % {"brand": BRAND}

st.markdown(CSS, unsafe_allow_html=True)


def score_badge(score: float) -> str:
    """按分数给彩色标签：>=7 绿 / >=4.5 黄 / 其余灰。"""
    if score >= SCORE_HIGH:
        tier, label = "high", "高"
    elif score >= SCORE_MID:
        tier, label = "mid", "中"
    else:
        tier, label = "low", "低"
    return f'<span class="ph-badge {tier}" title="热度分">{score:.2f} {label}</span>'


# ---------------- 侧边栏 ----------------
with st.sidebar:
    st.markdown("### ⚙️ 筛选")
    hide_read = st.toggle("隐藏已读", value=True)
    hide_hidden = st.toggle("隐藏已隐藏", value=True)
    interest = st.selectbox("筛选兴趣", INTEREST_OPTIONS, index=0)
    limit = st.number_input("显示条数", min_value=10, max_value=200, value=30, step=10)

# 确保 items 表存在：空库 / 首次运行时也能正常显示「暂无数据」提示
init_db().close()
conn = get_conn()

total = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
updated = conn.execute("SELECT MAX(fetched_at) FROM items").fetchone()[0]

# ---------------- 顶部标题 ----------------
st.markdown(
    '<div class="ph-hero"><h1>🔥 我的个人热榜</h1>'
    '<span class="ph-sub">按你的兴趣权重自动抓取 · 去重 · 打分 · 排序</span></div>'
    '<div class="ph-rule"></div>',
    unsafe_allow_html=True,
)

if updated:
    with st.sidebar:
        st.caption(f"数据更新于 {str(updated)[:19].replace('T', ' ')}")

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

saved = conn.execute("SELECT COUNT(*) FROM items WHERE is_saved = 1").fetchone()[0]
hidden_n = conn.execute("SELECT COUNT(*) FROM items WHERE is_hidden = 1").fetchone()[0]

# ---------------- 顶部统计卡（streamlit-extras）----------------
m1, m2, m3, m4 = st.columns(4)
m1.metric("数据库总条数", total)
m2.metric("当前筛选显示", len(rows))
m3.metric("已收藏", saved)
m4.metric("已隐藏", hidden_n)
style_metric_cards(border_left_color=BRAND, border_radius_px=12)

st.write("")

if not rows:
    st.info("当前筛选条件下没有内容")
    conn.close()
    st.stop()

# ---------------- 卡片列表 ----------------
for row in rows:
    score = row["final_score"] if row["final_score"] is not None else 0.0
    published = row["published_at"]
    published = published[:19].replace("T", " ") if published else "未知时间"

    with st.container(key=f"item_{row['id']}"):
        left, c1, c2, c3 = st.columns([5.6, 1, 1, 1], vertical_alignment="center")

        with left:
            title = html.escape(row["title"] or "(无标题)")
            url = html.escape(row["url"] or "#", quote=True)
            st.markdown(
                f'<div class="ph-title"><a href="{url}" target="_blank">{title}</a></div>'
                f'<div class="ph-meta">'
                f'<span class="ph-chip">{html.escape(row["source_name"] or "未知来源")}</span>'
                f'<span class="ph-chip">{html.escape(row["interest"] or "未分类")}</span>'
                f"{score_badge(score)}"
                f"<span>{published}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        with c1:
            if st.button(
                "已读", key=f"read_{row['id']}", icon=":material/check_circle:",
                use_container_width=True,
            ):
                conn.execute("UPDATE items SET is_read = 1 WHERE id = ?", (row["id"],))
                conn.commit()
                st.rerun()

        with c2:
            if st.button(
                "收藏", key=f"save_{row['id']}", icon=":material/star:",
                use_container_width=True,
            ):
                conn.execute("UPDATE items SET is_saved = 1 WHERE id = ?", (row["id"],))
                add_feedback(row["source_name"], "like", conn)
                conn.commit()
                st.rerun()

        with c3:
            if st.button(
                "隐藏", key=f"hide_{row['id']}", icon=":material/visibility_off:",
                use_container_width=True,
            ):
                conn.execute("UPDATE items SET is_hidden = 1 WHERE id = ?", (row["id"],))
                add_feedback(row["source_name"], "hide", conn)
                conn.commit()
                st.rerun()

conn.close()
