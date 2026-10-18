# -*- coding: utf-8 -*-
"""📸 图片底层信息查看器 — 基于 ExifTool 的元数据提取工具（本地/云端跨平台）

- Windows（本地）：调用项目自带的 tools/exiftool.exe
- Linux（Streamlit Cloud）：调用系统 exiftool（由 packages.txt 安装 libimage-exiftool-perl）

文件仅被写入临时目录供 ExifTool 读取，结束后立即清理，不会上传到任何服务器。

运行：在项目根目录执行  streamlit run image_inspector.py
"""
import json
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

import streamlit as st

# ---------- 平台判定 ----------
IS_WINDOWS = platform.system() == "Windows"


def exiftool_cmd() -> tuple[str | None, str | None]:
    """返回可用的 exiftool 可执行文件路径；不可用则返回 (None, 错误信息)。"""
    if IS_WINDOWS:
        exe = Path(__file__).resolve().parent / "tools" / "exiftool.exe"
        if not exe.exists():
            return None, f"未找到 exiftool：{exe}"
        return str(exe), None
    which = shutil.which("exiftool")
    if not which:
        return None, "未找到系统 exiftool（Linux 下请安装 libimage-exiftool-perl）"
    return which, None

# ---------- 页面基础配置 ----------
st.set_page_config(page_title="图片底层信息查看器", page_icon="📸", layout="wide")
st.title("📸 图片底层信息查看器")
st.caption("本地调用 ExifTool 提取照片元数据，图片不会被上传到任何服务器。")

# ---------- ExifTool 路径（与本脚本同目录下的 tools/exiftool.exe） ----------
EXIFTOOL = Path(__file__).resolve().parent / "tools" / "exiftool.exe"

# 分组标题映射（exiftool -G1 输出的组前缀 -> 中文标题）
GROUP_TITLES = {
    "File": "📁 文件信息",
    "System": "💾 系统属性",
    "IFD0": "🖼 IFD0（图像基础）",
    "ExifIFD": "⚙️ ExifIFD（拍摄参数）",
    "GPS": "🧭 GPS 定位",
    "InteropIFD": "🔗 互操作信息",
    "IFD1": "🖼 IFD1（缩略图）",
    "MakerNotes": "🏭 相机厂商私有信息",
    "XMP": "🏷 XMP 元数据",
    "IPTC": "📰 IPTC 说明",
    "Photoshop": "🖌 Photoshop 信息",
    "ICC-header": "🎨 ICC 色彩配置",
    "ICC_Profile": "🎨 ICC 色彩配置",
    "Composite": "🧩 Composite（综合计算）",
    "Comment": "💬 注释信息",
    "Adobe": "🖌 Adobe 信息",
    "ExifTool": "🧳 ExifTool 信息",
    "APP0": "🖼 APP0 (JFIF)",
    "APP14": "🖼 APP14 (Adobe)",
    "PNG": "🖼 PNG 信息",
    "QuickTime": "🎬 QuickTime 信息",
}


@st.cache_data(ttl=600)
def parse_metadata(tmp_name: str, mtime: float) -> tuple[dict | None, str | None]:
    """运行 exiftool.exe 提取元数据。

    返回 (metadata_dict, error_str)；成功时 metadata_dict 不为 None。
    """
    exe, err = exiftool_cmd()
    if err:
        return None, err
    try:
        proc = subprocess.run(
            [exe, "-json", "-n", "-a", "-G1", "-s", "-charset", "filename=UTF8", tmp_name],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        )
    except subprocess.TimeoutExpired:
        return None, "运行 ExifTool 超时（60 秒），请检查文件是否过于复杂或损坏"
    except Exception as exc:  # 兜底：权限等异常
        return None, f"运行 ExifTool 失败：{exc}"
    if proc.returncode != 0 or not proc.stdout.strip():
        return None, f"ExifTool 返回错误（code {proc.returncode}）：{(proc.stderr or '无输出').strip()}"
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return None, f"ExifTool 输出解析失败：{exc}"
    if not data:
        return None, "ExifTool 输出为空"
    meta = data[0] if isinstance(data, list) else data
    if not isinstance(meta, dict):
        return None, "ExifTool 返回了意外的 JSON 结构"
    meta.pop("SourceFile", None)  # 临时路径没意义，不展示
    return meta, None


def group_metadata(meta: dict) -> dict[str, list[tuple[str, object]]]:
    """把 {"IFD0:Make": "Apple"} 变成 {"IFD0": [("Make", "Apple"), ...]}，并保持原文顺序。"""
    groups: dict[str, list[tuple[str, object]]] = {}
    for key, value in meta.items():
        if ":" in key:
            group, _, tag = key.partition(":")
        else:  # 极少数情况下 exiftool 可能输出无 -G1 前缀的普通键
            group, tag = "Other", key
        groups.setdefault(group, []).append((tag, value))
    return groups


def render_image(file_bytes: bytes, name: str) -> None:
    """在左栏预览图片。浏览器不支持的 HEIC/AVIF 会退化为说明文字 + 下载按钮。"""
    try:
        st.image(file_bytes)
    except Exception:
        ext = Path(name).suffix or ".bin"
        st.markdown(f"🖼️ 浏览器无法直接预览 `{ext}` 格式，但元数据已成功读取。")
    with st.expander("文件信息", expanded=True):
        size_kb = len(file_bytes) / 1024
        st.write(f"文件名：`{name}`")
        st.write(f"大小：约 `{size_kb:.1f}` KB")
        st.caption("所有数据均由你本地文件夹中的 ExifTool 处理，运行结束后临时文件会被删除。")
    json_str = json.dumps(meta, ensure_ascii=False, indent=2)
    st.download_button("⬇ 下载 JSON 元数据", json_str, file_name=f"{Path(name).stem}_metadata.json",
                       mime="application/json", use_container_width=True)


def render_metadata(groups: dict[str, list[tuple[str, object]]]) -> None:
    """右栏：按组折叠显示全部元数据 k/v。"""
    order = list(GROUP_TITLES) + sorted(set(groups) - set(GROUP_TITLES))
    for group in order:
        if group not in groups:
            continue
        rows = groups[group]
        icon_title = GROUP_TITLES.get(group, f"❓ {group}")
        with st.expander(f"{icon_title}（{len(rows)} 项）", expanded=group in ("File", "IFD0", "ExifIFD", "GPS")):
            for tag, value in rows:
                v_text = "、".join(str(v) for v in value) if isinstance(value, list) else str(value)
                st.markdown(f"- **{tag}**：`{v_text}`")
    if "GPS" in groups:
        st.warning("⚠️ 此照片包含 GPS 定位信息，分享或发布前请自行确认是否需要抹除坐标！")


# ---------- 主入口 ----------
uploaded = st.file_uploader("上传图片（支持 JPG / PNG / HEIC / WebP / TIFF / GIF 等）",
                            type=["jpg", "jpeg", "jfif", "png", "heic", "heif", "webp", "tif", "tiff", "gif", "avif", "bmp"])
if not uploaded:
    st.info("请上传一张图片开始解析。")
    st.stop()

suffix = Path(uploaded.name).suffix or ".jpg"
tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
try:
    tmp_file.write(uploaded.getvalue())
    tmp_file.close()  # Windows 上若文件仍被 Python 占用，exiftool 可能读取失败，先关闭

    meta, err = parse_metadata(tmp_file.name, os.path.getmtime(tmp_file.name))
    if err:
        st.error(f"❌ {err}")
        st.caption("尝试执行的命令：`exiftool -json -n -a -G1 -s -charset filename=UTF8 <图片>`")
        st.stop()

    left, right = st.columns([1, 2.6], gap="medium")
    with left:
        st.subheader("🖼 图片预览")
        render_image(uploaded.getvalue(), uploaded.name)
    with right:
        st.subheader("📋 元数据（ExifTool 结果）")
        render_metadata(group_metadata(meta))
finally:
    # 无论成功还是失败，都删除临时文件
    try:
        os.remove(tmp_file.name)
    except OSError:
        pass
