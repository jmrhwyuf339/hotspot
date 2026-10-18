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
  · 兴趣只换显示短名（INTEREST_LABELS），SQL / 打分用的还是完整值
  · 未读按钮的红色描边：shadcn 没有「红描边」变体，只能在 Shadow DOM 外的
    宿主元素上改写 --border（见 unread_outline_css）
"""

import hashlib
import html

import streamlit as st
import streamlit_shadcn_ui as ui

from src.db import add_feedback, get_conn, init_db

st.set_page_config(layout="wide", page_title="我的个人热榜", page_icon="🔥")

# 兴趣「显示名 → 真实值」映射：只换下拉框和徽章上看到的字，
# 真实值仍是 config/interests.yaml 与 items.interest 里的完整名 ——
# 筛选 SQL 传的、徽章对上的都还是完整名，映射表只是给它换了个短标签。
INTEREST_LABELS = {
    "全部": "全部",
    "AI工具与Agent生态": "AI工具",
    "免费/低成本AI资源": "免费资源",
    "ComfyUI与本地AI图像/视频生成": "图像生成",
}
INTEREST_OPTIONS = list(INTEREST_LABELS)

# 分数档位：按本库真实分布标定（中位数 ~2.1、最高 ~7.8）
# shadcn 的 Badge 只有 variant、没有自定义色，所以档位用 variant 表达：
# 深色实心 = 高分 / 浅灰 = 中分 / 描边 = 低分
SCORE_HIGH = 4.0
SCORE_MID = 2.0

# run_fetch.py 翻译后给标题加的英文前缀，展示时摘出来做成「译」标签
TRANS_PREFIX = "[译] "

# 「未读」按钮的红色描边（shadcn destructive 那一族的红）
UNREAD_RED = "#dc2626"

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


def interest_label(value: str | None) -> str:
    """徽章上的兴趣短名；映射表里没有就原样显示（兼容旧数据或以后新增的兴趣）。"""
    if not value:
        return "未分类"
    return INTEREST_LABELS.get(value, value)


def elements_host_class(public_key: str) -> str:
    """ui.elements 的 key → 它挂载后宿主元素的 class。

    streamlit-shadcn-ui 会把我们传的 key 哈希成一个私有挂载 key
    （见其 private_component_key：sha256("user\\0" + key)），组件宿主因此带
    st-key-<私有 key>。拿到它才能在「这一张卡片」的控件区里改写 --border。
    库哪天换了这套取名规则，这里会静默失效：按钮退回灰色描边，不会报错。
    """
    digest = hashlib.sha256(("user\0" + public_key).encode("utf-8")).hexdigest()
    return "ssui_v2_component_" + digest


def unread_outline_css(rows) -> str:
    """未读卡片的控件区：把 --border 改成红色，使「已读」按钮呈红色描边。

    已读的卡片不出现在这里，保持中性灰描边 —— 这就是点与没点的区别。
    shadcn 组件跑在 Shadow DOM 里，外面只能改它宿主上的 CSS 变量，改不进去内部。
    """
    rules = [
        # 组件真正的 Shadow DOM 宿主可能是这层 wrapper 本身、也可能是它的子元素，
        # 两个都写上；!important 才能压过宿主内部 :host 里的同名变量。
        "div.st-key-{c}, div.st-key-{c} * {{ --border: {red} !important; }}".format(
            c=elements_host_class("ctrl_%d" % row["id"]), red=UNREAD_RED
        )
        for row in rows
        if not row["is_read"]
    ]
    if not rules:
        return ""
    return "<style>\n%s\n</style>" % "\n".join(rules)


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
        "筛选兴趣",
        INTEREST_OPTIONS,
        index=0,
        key="filter_interest",
        format_func=lambda v: INTEREST_LABELS.get(v, v),
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
                        interest_label(row["interest"]),
                        key="interest%d" % item_id,
                        variant="secondary",
                    )
                    if translated:
                        el.badge("译", key="trans%d" % item_id, variant="secondary")

                # 右：三个操作按钮（收藏用 secondary，避免整屏黑按钮）
                with el.stack(
                    direction="horizontal", gap="xs", align="center", justify="end"
                ):
                    # 未读 = 红色描边（见 unread_outline_css），已读 = 灰色描边并停用
                    handles.append(
                        (
                            "read",
                            item_id,
                            row["source_name"],
                            el.button(
                                "已读 ✓" if row["is_read"] else "标记已读",
                                key="read%d" % item_id,
                                variant="outline",
                                size="sm",
                                disabled=bool(row["is_read"]),
                                help="已标记为已读" if row["is_read"] else "标记为已读",
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
# 未读卡片的红描边：按卡片单独改写控件区的 --border（已读的卡片不在其中）
outline_css = unread_outline_css(rows)
if outline_css:
    st.markdown(outline_css, unsafe_allow_html=True)
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
