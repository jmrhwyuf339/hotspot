"""阶段四：Streamlit 展示页，读取 hotspot.db（复用 src/db.py 的连接）。"""

import html

import streamlit as st

from src.db import add_feedback, get_conn, init_db

st.set_page_config(page_title="我的个人热榜", layout="wide")
st.title("🔥 我的个人热榜")

INTEREST_OPTIONS = [
    "全部",
    "AI工具与Agent生态",
    "免费/低成本AI资源",
    "ComfyUI与本地AI图像/视频生成",
]

# ---------------- 侧边栏 ----------------
with st.sidebar:
    st.header("筛选")
    hide_read = st.checkbox("隐藏已读", value=True)
    hide_hidden = st.checkbox("隐藏已隐藏", value=True)
    interest = st.selectbox("筛选兴趣", INTEREST_OPTIONS, index=0)
    limit = st.number_input("显示条数", min_value=10, max_value=200, value=30, step=10)

# 确保 items 表存在：空库 / 首次运行时也能正常显示「暂无数据」提示
init_db().close()
conn = get_conn()

total = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]

if total == 0:
    st.info("暂无数据，请先运行 python run_fetch.py")
    conn.close()
    st.stop()

# ---------------- 组装筛选 ----------------
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

st.caption(f"当前筛选下显示 {len(rows)} 条 · 数据库中总计 {total} 条")

if not rows:
    st.info("当前筛选条件下没有内容")
    conn.close()
    st.stop()

# ---------------- 列表 ----------------
for row in rows:
    cols = st.columns([6, 1, 1, 1])

    with cols[0]:
        title = html.escape(row["title"] or "(无标题)")
        url = html.escape(row["url"] or "#", quote=True)
        st.markdown(
            f'<a href="{url}" target="_blank" '
            f'style="font-size:1.05rem;font-weight:600;">{title}</a>',
            unsafe_allow_html=True,
        )
        published = row["published_at"]
        published = published[:19].replace("T", " ") if published else "未知时间"
        score = row["final_score"] if row["final_score"] is not None else 0.0
        st.caption(
            f"{row['source_name'] or '未知来源'} | {row['interest'] or '未分类'} "
            f"| {score:.3f} | {published}"
        )

    with cols[1]:
        if st.button("已读", key=f"read_{row['id']}", use_container_width=True):
            conn.execute("UPDATE items SET is_read = 1 WHERE id = ?", (row["id"],))
            conn.commit()
            st.rerun()

    with cols[2]:
        if st.button("收藏", key=f"save_{row['id']}", use_container_width=True):
            conn.execute("UPDATE items SET is_saved = 1 WHERE id = ?", (row["id"],))
            add_feedback(row["source_name"], "like", conn)
            conn.commit()
            st.rerun()

    with cols[3]:
        if st.button("隐藏", key=f"hide_{row['id']}", use_container_width=True):
            conn.execute("UPDATE items SET is_hidden = 1 WHERE id = ?", (row["id"],))
            add_feedback(row["source_name"], "hide", conn)
            conn.commit()
            st.rerun()

    st.divider()

conn.close()
