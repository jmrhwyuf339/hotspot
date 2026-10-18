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
import html
from pathlib import Path

import streamlit as st
import pydeck as pdk

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

# 常见标签名 -> 中文名（字典里没有的标签原样显示英文，全量对照见右下角 JSON 下载）
TAG_TITLES = {
    # 系统 / ExifTool
    "ExifToolVersion": "ExifTool 版本",
    "Warning": "警告",
    "Error": "错误",
    # File（文件）
    "FileName": "文件名",
    "Directory": "所在目录",
    "FileSize": "文件大小",
    "FileModifyDate": "文件修改时间",
    "FileCreateDate": "文件创建时间",
    "FileAccessDate": "文件访问时间",
    "FileInodeChangeDate": "文件状态变更时间",
    "FilePermissions": "文件权限",
    "FileType": "文件类型",
    "FileTypeExtension": "扩展名",
    "MIMEType": "MIME 类型",
    "ExifByteOrder": "字节序",
    "EncodingProcess": "编码方式",
    "BitsPerSample": "位深",
    "ColorComponents": "颜色分量数",
    "YCbCrSubSampling": "色度抽样",
    "ImageWidth": "图像宽度",
    "ImageHeight": "图像高度",
    "ImageSize": "图像尺寸",
    "Megapixels": "像素数（百万）",
    # IFD0（图像基础）
    "Make": "设备制造商",
    "Model": "设备型号",
    "Orientation": "方向",
    "XResolution": "水平分辨率",
    "YResolution": "垂直分辨率",
    "ResolutionUnit": "分辨率单位",
    "Software": "处理软件",
    "ModifyDate": "修改时间",
    "Artist": "作者",
    "Copyright": "版权",
    "HostComputer": "创建主机",
    "Rating": "评分",
    "YCbCrPositioning": "色度位置",
    "WhitePoint": "白点坐标",
    "PrimaryChromaticities": "原色色度坐标",
    "YCbCrCoefficients": "色度系数",
    "ReferenceBlackWhite": "黑白参考值",
    "ThumbnailOffset": "缩略图数据偏移",
    "ThumbnailLength": "缩略图数据长度",
    "ThumbnailWidth": "缩略图宽度",
    "ThumbnailHeight": "缩略图高度",
    "ThumbnailImage": "缩略图",
    "XPKeywords": "关键词",
    "ExifOffset": "Exif 数据偏移",
    # ExifIFD（拍摄参数）
    "ExposureTime": "曝光时间",
    "FNumber": "光圈值",
    "ExposureProgram": "曝光程序",
    "ISO": "感光度 ISO",
    "ISOSpeedRatings": "感光度 ISO",
    "SensitivityType": "感光度类型",
    "RecommendedExposureIndex": "推荐曝光指数",
    "ExifVersion": "Exif 版本",
    "FlashpixVersion": "Flashpix 版本",
    "DateTimeOriginal": "拍摄时间",
    "CreateDate": "创建时间",
    "OffsetTime": "时区偏移",
    "OffsetTimeOriginal": "拍摄时区偏移",
    "SubSecTimeOriginal": "拍摄时间（亚秒）",
    "ComponentsConfiguration": "色彩分量配置",
    "CompressedBitsPerPixel": "压缩位深",
    "ShutterSpeedValue": "快门速度（APEX）",
    "ApertureValue": "光圈值（APEX）",
    "BrightnessValue": "亮度值",
    "ExposureCompensation": "曝光补偿",
    "MaxApertureValue": "最大光圈",
    "SubjectDistance": "被摄距离",
    "SubjectDistanceRange": "被摄距离范围",
    "SubjectArea": "主体区域",
    "MeteringMode": "测光模式",
    "LightSource": "光源",
    "Flash": "闪光灯",
    "FocalLength": "焦距",
    "FocalLengthIn35mmFormat": "等效焦距（35mm）",
    "LensInfo": "镜头信息",
    "LensMake": "镜头制造商",
    "LensModel": "镜头型号",
    "LensSerialNumber": "镜头序列号",
    "LensID": "镜头标识",
    "Lens": "镜头",
    "ColorSpace": "色彩空间",
    "ExifImageWidth": "主图宽度",
    "ExifImageHeight": "主图高度",
    "SensingMethod": "感光元件类型",
    "FileSource": "文件来源",
    "SceneType": "场景类型",
    "CustomRendered": "自定义渲染",
    "ExposureMode": "曝光模式",
    "WhiteBalance": "白平衡",
    "DigitalZoomRatio": "数码变焦比",
    "SceneCaptureType": "场景拍摄类型",
    "GainControl": "增益控制",
    "Contrast": "对比度",
    "Saturation": "饱和度",
    "Sharpness": "锐度",
    "BodySerialNumber": "机身序列号",
    "CameraOwnerName": "相机所有者",
    "InteropIndex": "互操作索引",
    "InteropVersion": "互操作版本",
    # GPS（定位）
    "GPSVersionID": "GPS 版本",
    "GPSLatitudeRef": "纬度方向",
    "GPSLatitude": "纬度",
    "GPSLongitudeRef": "经度方向",
    "GPSLongitude": "经度",
    "GPSAltitudeRef": "海拔基准",
    "GPSAltitude": "海拔高度",
    "GPSTimeStamp": "GPS 时间",
    "GPSDateStamp": "GPS 日期",
    "GPSDateTime": "GPS 日期时间",
    "GPSSpeedRef": "速度单位",
    "GPSSpeed": "移动速度",
    "GPSTrackRef": "移动方向基准",
    "GPSTrack": "移动方向",
    "GPSImgDirectionRef": "拍摄方向基准",
    "GPSImgDirection": "拍摄方向（正北为 0°）",
    "GPSHPositioningError": "定位精度（米）",
    "GPSDOP": "精度因子 DOP",
    "GPSProcessingMethod": "定位方式",
    "GPSPosition": "经纬度",
    # Composite（综合计算）
    "Aperture": "光圈",
    "ShutterSpeed": "快门速度",
    "LightValue": "曝光值 EV",
    "ScaleFactor35efl": "35mm 等效系数",
    "CircleOfConfusion": "弥散圆直径",
    "FOV": "视场角",
    "FocalLength35efl": "等效焦距",
    "HyperfocalDistance": "超焦距",
    "DOF": "景深",
    "DateTimeCreated": "创建日期时间",
    "SubSecCreateDate": "创建时间（含亚秒）",
    "SubSecDateTimeOriginal": "拍摄时间（含亚秒）",
    # ICC（色彩配置）
    "ProfileCMMType": "色彩管理厂商",
    "ProfileVersion": "配置文件版本",
    "ProfileClass": "配置文件类别",
    "ColorSpaceData": "色彩空间数据",
    "ProfileConnectionSpace": "连接空间",
    "ProfileDateTime": "配置文件生成时间",
    "ProfileFileSignature": "配置文件签名",
    "PrimaryPlatform": "主平台",
    "DeviceManufacturer": "设备制造商",
    "DeviceModel": "设备型号",
    "DeviceAttributes": "设备属性",
    "RenderingIntent": "渲染意图",
    "ConnectionSpaceIlluminant": "连接空间光源",
    "ProfileCreator": "配置文件创建者",
    "ProfileID": "配置文件 ID",
    "ProfileDescription": "配置文件描述",
    "ProfileCopyright": "配置文件版权",
    "MediaWhitePoint": "媒体白点",
    "MediaBlackPoint": "媒体黑点",
    "RedTRC": "红色色调曲线",
    "GreenTRC": "绿色色调曲线",
    "BlueTRC": "蓝色色调曲线",
    "ChromaticAdaptation": "色适应矩阵",
    # XMP / Photoshop / JFIF
    "XMPToolkit": "XMP 工具包",
    "CreatorTool": "创建工具",
    "MetadataDate": "元数据更新时间",
    "Format": "格式",
    "SerialNumber": "序列号",
    "AlreadyApplied": "已应用",
    "InstanceID": "实例 ID",
    "DocumentID": "文档 ID",
    "OriginalDocumentID": "原始文档 ID",
    "IPTCDigest": "IPTC 摘要",
    "Comment": "注释",
    "JFIFVersion": "JFIF 版本",
    "ColorTransform": "颜色变换",
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
                cn = TAG_TITLES.get(tag.split(":")[0])  # 兼容 exiftool 给重复标签加的 ":1" 后缀
                st.markdown(f"- **{cn}（{tag}）**：`{v_text}`" if cn else f"- **{tag}**：`{v_text}`")
    if "GPS" in groups:
        st.warning("⚠️ 此照片包含 GPS 定位信息，分享或发布前请自行确认是否需要抹除坐标！")


def human_size(num_bytes: int) -> str:
    """把字节数变成易读的大小。"""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def render_summary(meta: dict, size_bytes: int, gps: dict | None) -> None:
    """页面顶部：最重要的几项信息，用指标卡片展示。"""

    def first(*keys: str) -> str | None:
        for key in keys:
            value = meta.get(key)
            if value not in (None, ""):
                return str(value)
        return None

    make, model = first("IFD0:Make"), first("IFD0:Model")
    if make and model and make.lower() in model.lower():
        device = model  # Model 里已带品牌（如 "Apple iPhone 15 Pro"）时不重复
    else:
        device = " ".join(x for x in (make, model) if x) or None

    pixels = first("File:ImageSize", "Composite:ImageSize", "ExifIFD:ExifImageSize")
    if pixels and len(pixels.split()) == 2 and all(p.isdigit() for p in pixels.split()):
        pixels = "×".join(pixels.split())  # exiftool -n 可能输出 "640 480"，改成 "640×480"
    megapixels = first("Composite:Megapixels", "File:Megapixels")
    if pixels and megapixels:
        pixels = f"{pixels}（{megapixels} MP）"

    taken = first("ExifIFD:DateTimeOriginal", "ExifIFD:CreateDate", "IFD0:ModifyDate")
    if taken:
        taken = taken.replace(":", "-", 2)  # 2026:10:18 03:12:45 -> 2026-10-18 03:12:45

    items = [
        ("📱 设备", device or "未知"),
        ("🖼 像素尺寸", pixels or "未知"),
        ("📦 文件大小", human_size(size_bytes)),
        ("🕒 拍摄时间", taken or "未知"),
        ("📍 定位信息", "有 GPS" if gps else "无"),
    ]
    cards = "".join(
        f'<div class="kv-card"><div class="kv-label">{label}</div>'
        f'<div class="kv-value">{html.escape(value)}</div></div>'
        for label, value in items
    )
    st.markdown(
        """<style>
        .kv-row { display: flex; flex-wrap: wrap; gap: 12px; }
        .kv-card { flex: 1 1 160px; min-width: 150px; padding: 10px 14px; border-radius: 10px;
                   background: var(--secondary-background-color);
                   border: 1px solid rgba(128, 128, 128, 0.25); }
        .kv-label { font-size: 0.8rem; opacity: 0.7; }
        .kv-value { font-size: 1.05rem; font-weight: 600; line-height: 1.35; word-break: break-word; }
        </style>"""
        f'<div class="kv-row">{cards}</div>',
        unsafe_allow_html=True,
    )


def extract_gps(meta: dict) -> dict | None:
    """从元数据中提取拍摄位置；没有有效坐标时返回 None。"""
    gps = {k.split(":", 1)[1]: v for k, v in meta.items() if k.startswith("GPS:")}

    def number(key: str) -> float | None:
        try:
            return float(gps[key])
        except (KeyError, TypeError, ValueError):
            return None

    lat = lon = None
    position = gps.get("GPSPosition")  # -n 下形如 "39.9042 116.4074"
    if isinstance(position, str) and len(position.split()) >= 2:
        try:
            lat, lon = (float(x) for x in position.split()[:2])
        except ValueError:
            lat = lon = None
    if lat is None or lon is None:  # 回退：分标签 + Ref 定符号（-n 可能输出无符号小数）
        lat, lon = number("GPSLatitude"), number("GPSLongitude")
        if lat and str(gps.get("GPSLatitudeRef", "")).upper().startswith("S"):
            lat = -lat
        if lon and str(gps.get("GPSLongitudeRef", "")).upper().startswith("W"):
            lon = -lon
    if lat is None or lon is None or (lat == 0 and lon == 0):
        return None  # 无坐标，或 (0,0) 这种无效定位
    alt = number("GPSAltitude")
    if alt is not None and str(gps.get("GPSAltitudeRef", "0")).startswith("1"):
        alt = -alt  # 海平面以下为负
    stamp = " ".join(str(gps[k]) for k in ("GPSDateStamp", "GPSTimeStamp") if gps.get(k))
    return {"lat": lat, "lon": lon, "alt": alt, "acc": number("GPSHPositioningError"), "stamp": stamp}


def render_map(gps: dict) -> None:
    """页面下方的交互式地图：打点 + 精度圈 + 悬停详情 + 外部地图链接。"""
    lat, lon, acc = gps["lat"], gps["lon"], gps["acc"]
    details = [f"纬度 {lat:.6f}", f"经度 {lon:.6f}"]
    if gps["alt"] is not None:
        details.append(f"海拔 {gps['alt']:.1f} 米")
    if acc:
        details.append(f"定位精度 ±{acc:.0f} 米")
    if gps["stamp"]:
        details.append(f"GPS 时间 {gps['stamp']}")

    layers = [pdk.Layer("ScatterplotLayer", data=[gps], get_position=["lon", "lat"],
                        get_fill_color=[230, 57, 70, 200], get_radius=12,
                        radius_min_pixels=8, radius_max_pixels=28, pickable=True)]
    if acc:  # 精度圈：半径 = GPSHPositioningError（米）
        layers.append(pdk.Layer("ScatterplotLayer", data=[gps], get_position=["lon", "lat"],
                                get_fill_color=[230, 57, 70, 40], get_radius=acc, pickable=False))
    st.pydeck_chart(pdk.Deck(
        layers=layers,
        initial_view_state=pdk.ViewState(latitude=lat, longitude=lon, zoom=13 if (acc or 0) >= 100 else 16),
        map_style="light",
        tooltip={"html": "<br/>".join(details), "style": {"backgroundColor": "#222", "color": "#fff"}},
    ))
    st.caption(" · ".join(details))
    c1, c2, _ = st.columns([1, 1, 4])
    c1.link_button("🌍 OpenStreetMap", f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=16/{lat}/{lon}")
    c2.link_button("🧭 高德地图", f"https://uri.amap.com/marker?position={lon},{lat}")
    st.caption("提示：高德等国内地图使用 GCJ-02 坐标系，与照片中的 WGS-84 坐标存在少量偏移。")


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

    gps = extract_gps(meta)

    st.subheader("📌 关键信息")
    render_summary(meta, len(uploaded.getvalue()), gps)
    st.divider()

    left, right = st.columns([1, 2.6], gap="medium")
    with left:
        st.subheader("🖼 图片预览")
        render_image(uploaded.getvalue(), uploaded.name)
    with right:
        st.subheader("📋 元数据（ExifTool 结果）")
        render_metadata(group_metadata(meta))

    st.divider()
    if gps:
        st.subheader("🗺 拍摄位置（可拖动、滚轮缩放）")
        render_map(gps)
    else:
        st.caption("📍 无位置信息")
finally:
    # 无论成功还是失败，都删除临时文件
    try:
        os.remove(tmp_file.name)
    except OSError:
        pass
