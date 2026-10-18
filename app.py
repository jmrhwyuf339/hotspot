"""个人热榜 —— 展示层（卡片式资讯 App 风格 · 混合渲染）。

本文件只负责渲染。抓取 / 去重 / 翻译 / 打分 / 反馈写库等后端逻辑一字未动：
- 查询、筛选条件、排序、LIMIT 与阶段八完全一致
- 三个按钮仍然调用 add_feedback(...) 并复用同一个 conn + commit + st.rerun
- 渲染分工：
  · 标题 / 来源时间 —— 自家 HTML。标题必须是原生 <a>：shadcn 的 link_button
    强制 white-space:nowrap，长中文标题在窄屏会被裁掉，只有原生 <a> 才能又
    可点又换行；卡片外壳也因此用自家 CSS（对齐 shadcn Card 的中性观感）。
  · 徽章 / 按钮 —— streamlit-shadcn-ui 的 elements（Components V2，无 iframe）
  · 点击通过 handle.clicked 回到 Python，写库语句与之前逐字相同
"""

import html

import streamlit as st
import streamlit_shadcn_ui as ui

from src.db import add_feedback, get_conn, init_db

st.set_page_config(layout="wide", page_title="我的个人热榜", page_icon="🔥")

INTEREST_OPTIONS = [
    "全部",
    "AI工具与Agent生态",
    "免费/低成本AI资源",
    "ComfyUI与本地AI图像/视频生成",
]

# 分数档位：按本库真实分布标定（中位数 ~2.1、最高 ~7.8）
# shadcn 的 Badge 只有 variant、没有自定义色，所以档位用 variant 表达：
# 深色实心 = 高分 / 浅灰 = 中分 / 描边 = 低分
SCORE_HIGH = 4.0
SCORE_MID = 2.0

# run_fetch.py 翻译后给标题加的英文前缀，展示时摘出来做成「译」标签
TRANS_PREFIX = "[译] "

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
.ph-hero { display: flex; align-items: center; gap: .85rem; margin: .1rem 0 .9rem 0; }
.ph-hero h1 {
    margin: 0; font-size: 1.65rem; font-weight: 800;
    letter-spacing: -.025em; color: #0f172a;
}
.ph-sub { margin-top: .2rem; font-size: .82rem; color: #8b93a7; }

/* ---------- 3. 侧边栏 ---------- */
section[data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #eceef3; }
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { padding-top: 1rem; }
section[data-testid="stSidebar"] .block-container { padding-top: 1rem !important; }
.ph-brand { display: flex; align-items: center; gap: .6rem; margin-bottom: .2rem; }
.ph-brand .ph-logo { width: 38px; height: 38px; border-radius: 12px; font-size: 1.05rem; }
.ph-brand-name { font-size: .98rem; font-weight: 800; letter-spacing: -.01em; color: #0f172a; }
.ph-brand-tag { font-size: .7rem; color: #98a1b3; }
.ph-section {
    margin: 1.15rem 0 .4rem 0; font-size: .7rem; font-weight: 700;
    letter-spacing: .1em; text-transform: uppercase; color: #b3bac9;
}

/* ---------- 4. 资讯卡片 ----------
   外壳用自家 CSS（对齐 shadcn Card 的中性观感），标题是原生 <a>：
   只有这样才能做到「标题可点 + 可换行」，同时把行高攥在自己手里。
   卡片里的徽章 / 按钮仍然是真 shadcn 组件（见 render_card）。 */
div[class*="st-key-item_"] {
    background: #ffffff;
    border: 1px solid #e4e4e7;
    border-radius: 10px;
    padding: .55rem .8rem .5rem .8rem;
    margin-bottom: .5rem !important;
    box-shadow: 0 1px 2px rgba(16, 24, 40, .04);
    transition: border-color .15s ease, box-shadow .15s ease;
}
div[class*="st-key-item_"]:hover {
    border-color: #d4d4d8;
    box-shadow: 0 4px 12px -4px rgba(16, 24, 40, .12);
}
/* 卡内三块（标题 / 元信息 / 控件行）贴紧，别用 Streamlit 默认大间距 */
div[class*="st-key-item_"] > div > [data-testid="stVerticalBlock"] { gap: .22rem !important; }
div[class*="st-key-item_"] [data-testid="stElementContainer"] { margin-bottom: 0 !important; }
div[class*="st-key-item_"] [data-testid="stMarkdownContainer"] p { margin: 0 !important; }

/* 标题：原生链接，可换行、可点击跳原网页 */
.ph-title {
    font-size: 1.02rem; font-weight: 650; line-height: 1.4;
    letter-spacing: -.012em; color: #0f172a !important;
    text-decoration: none !important;
}
.ph-title:hover { text-decoration: underline !important; text-underline-offset: 3px; }
.ph-meta { font-size: .8rem; line-height: 1.35; color: #71717a; }
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)


def score_variant(score: float) -> str:
    """分数徽章档位：高分深色实心 / 中分浅灰 / 低分描边。"""
    if score >= SCORE_HIGH:
        return "default"
    if score >= SCORE_MID:
        return "secondary"
    return "outline"


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
    with m1:
        ui.metric_card("总数", total, key="stat_total", size="sm")
    with m2:
        ui.metric_card("收藏", saved_n, key="stat_saved", size="sm")
    with m3:
        ui.metric_card("隐藏", hidden_n, key="stat_hidden", size="sm")

    st.markdown('<div class="ph-section">筛选</div>', unsafe_allow_html=True)
    hide_read = ui.switch("隐藏已读", value=True, key="filter_hide_read")
    hide_hidden = ui.switch("隐藏已隐藏", value=True, key="filter_hide_hidden")
    interest = ui.select(
        "筛选兴趣", INTEREST_OPTIONS, index=0, key="filter_interest"
    )
    limit = ui.number_input(
        "显示条数",
        30,
        min_value=10,
        max_value=200,
        step=10,
        key="filter_limit",
    )

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
def render_card(row, handles: list) -> None:
    """画一条资讯，并把三个操作按钮的 handle 收集起来。

    标题与来源时间用自家 HTML（标题必须可点可换行），
    徽章与三个按钮用 shadcn 组件（一行内：徽章靠左、按钮靠右）。
    """
    item_id = row["id"]

    title = row["title"] or "(无标题)"
    translated = title.startswith(TRANS_PREFIX)
    if translated:
        title = title[len(TRANS_PREFIX):]

    published = row["published_at"]
    published = published[:19].replace("T", " ") if published else "未知时间"

    score = row["final_score"] if row["final_score"] is not None else 0.0

    with st.container(key="item_%d" % item_id):
        st.markdown(
            '<a class="ph-title" href="%s" target="_blank" rel="noopener">%s</a>'
            % (html.escape(row["url"] or "", quote=True), html.escape(title)),
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="ph-meta">%s · %s</div>'
            % (html.escape(row["source_name"] or "未知来源"), html.escape(published)),
            unsafe_allow_html=True,
        )

        # with 块退出时组件才真正挂载，handle.clicked 也是那时才被写入
        with ui.elements(key="ctrl_%d" % item_id) as el:
            with el.stack(
                direction="horizontal", gap="xs", align="center", justify="between"
            ):
                # 左：分数 / 兴趣 / 「译」
                with el.stack(
                    direction="horizontal", gap="xs", align="center", wrap=True
                ):
                    el.badge(
                        "%.2f" % score,
                        key="score%d" % item_id,
                        variant=score_variant(score),
                    )
                    el.badge(
                        row["interest"] or "未分类",
                        key="interest%d" % item_id,
                        variant="outline",
                    )
                    if translated:
                        el.badge("译", key="trans%d" % item_id, variant="secondary")

                # 右：三个操作按钮（收藏用 secondary，避免整屏黑按钮）
                with el.stack(
                    direction="horizontal", gap="xs", align="center", justify="end"
                ):
                    handles.append(
                        (
                            "read",
                            item_id,
                            row["source_name"],
                            el.button(
                                "已读",
                                key="read%d" % item_id,
                                variant="ghost",
                                size="sm",
                                help="标记为已读",
                            ),
                        )
                    )
                    handles.append(
                        (
                            "save",
                            item_id,
                            row["source_name"],
                            el.button(
                                "已收藏" if row["is_saved"] else "收藏",
                                key="save%d" % item_id,
                                variant="secondary",
                                size="sm",
                                help="收藏，并给这个来源点个赞（影响来源质量分）",
                            ),
                        )
                    )
                    handles.append(
                        (
                            "hide",
                            item_id,
                            row["source_name"],
                            el.button(
                                "隐藏",
                                key="hide%d" % item_id,
                                variant="ghost",
                                size="sm",
                                help="隐藏这条，并降低该来源的权重",
                            ),
                        )
                    )


handles: list = []
for row in rows:
    render_card(row, handles)

# ---------------- 处理点击（写库语句与之前逐字相同）----------------
for action, item_id, source_name, handle in handles:
    if not handle.clicked:
        continue

    if action == "read":
        conn.execute("UPDATE items SET is_read = 1 WHERE id = ?", (item_id,))
        conn.commit()
    elif action == "save":
        conn.execute("UPDATE items SET is_saved = 1 WHERE id = ?", (item_id,))
        add_feedback(source_name, "like", conn)
        conn.commit()
    else:
        conn.execute("UPDATE items SET is_hidden = 1 WHERE id = ?", (item_id,))
        add_feedback(source_name, "hide", conn)
        conn.commit()
    st.rerun()

conn.close()
