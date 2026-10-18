# personal-hotspot

一个给自己用的「信息 + 照片」小工具集，跑在 Streamlit 上，一共两个页面：

| 页面 | 文件 | 干什么的 |
| --- | --- | --- |
| 🔥 个人热榜 | `app.py` | 每天自动抓取感兴趣的资讯，去重、翻译、打分后按分数排出个人版「热榜」，可已读 / 收藏 / 隐藏 |
| 📸 图片底层信息查看器 | `image_inspector.py` | 上传一张照片，用 ExifTool 把里面的元数据（拍摄参数、GPS 定位等）全部摊开给你看 |

两个页面都只是「展示层」，真正的抓取、过滤、打分逻辑收在 `src/` 里，由 `run_fetch.py` 驱动，正常情况下由 GitHub Actions 定时跑，你只需要看结果。

---

## 一、🔥 个人热榜

### 它能做什么

- **自动抓取**：读 `config/sources.yaml`，从 12 个 RSS / API 源拉取文章（掘金、Hacker News、TechCrunch、量子位、InfoQ 中文、阮一峰的网络日志、OpenAI News、GitHub Blog、ComfyUI Blog、开源中国……）
- **按兴趣过滤**：读 `config/interests.yaml` 的关键词，命中才留下；命中排除词的直接丢掉
- **打分排序**：文章分数 = 关键词匹配 + 兴趣权重 + 来源质量分。来源质量分是动态的 —— 你点「收藏」给它点赞就加分，点「隐藏」就减分
- **自动去重**：URL 归一化后算哈希，同一条内容不会重复出现
- **过滤过期**：发布时间距今超过 30 天的条目直接丢弃
- **自动翻译**：英文源（Hacker News、TechCrunch）的标题会翻成中文，显示时带一个「译」标签，原文也保留在括号里
- **卡片式界面**：左上角是分数徽章（深色=高分、浅灰=中分、描边=低分）、兴趣徽章，右侧是「已读 / 收藏 / 隐藏」三个按钮，点一下立刻写进数据库
- **侧边栏筛选**：隐藏已读、隐藏已隐藏、按兴趣筛选、调整显示条数

### 数据从哪来

所有数据存在根目录的 `hotspot.db`（SQLite），两张表：

- `items` —— 抓到的每一条资讯，以及它的分数、兴趣分类、来源、已读/收藏/隐藏状态
- `user_feedback` —— 你在页面上的每次「收藏 / 隐藏」，用来计算来源质量分

抓取由 `.github/workflows/fetch.yml` 每 2 小时跑一次（也可在 Actions 页面手动触发），跑完自动把 `hotspot.db` 提交回仓库。云端应用只读这个库。

---

## 二、📸 图片底层信息查看器

### 它能做什么

- **上传即看**：支持 JPG / PNG / HEIC / WebP / TIFF / GIF / AVIF / BMP
- **全量元数据**：调用 ExifTool，把文件信息、IFD0、ExifIFD（曝光时间、光圈、ISO、镜头……）、GPS、XMP、ICC 色彩配置等分组折叠展示，常用标签名都翻译成了中文
- **关键信息卡片**：设备型号、像素尺寸、文件大小、拍摄时间、有没有 GPS，一眼看完
- **JSON 下载**：一键导出原始元数据，方便进一步处理
- **地图定位**：照片带 GPS 时，在页面下方显示高德底图的交互式地图（打点 + 定位精度圈 + 悬停详情），并提供 OpenStreetMap / 高德地图的外部链接
- **坐标纠偏**：照片里存的是 WGS-84 坐标，高德底图用的是 GCJ-02「火星坐标」，两者在国内能差几百米。这里会自动做 WGS-84 → GCJ-02 转换，打点和高德链接都是纠偏后的坐标（页面上显示的经纬度仍是照片原始的 WGS-84）
- **隐私**：图片只写进系统临时目录供 ExifTool 读取，用完立刻删除，不会上传到任何服务器

---

## 三、在本地运行

### 前置条件

- Python 3.11 或更高（本项目在 3.12 上开发）
- ExifTool（只有图片查看器需要）：
  - **Windows**：把官方的 `exiftool.exe` 和 `exiftool_files/` 放进项目的 `tools/` 目录。注意这两个文件被 `.gitignore` 排除了，克隆仓库后需要自己补上（下载地址：<https://exiftool.org/>）
  - **Linux / macOS**：装系统包即可，脚本会自动用 `exiftool` 命令
    - Debian / Ubuntu：`sudo apt install libimage-exiftool-perl`
    - macOS：`brew install exiftool`

### 步骤

```bash
# 1. 进入项目目录并创建虚拟环境
python -m venv venv

# 2. 激活虚拟环境
venv\Scripts\activate        # Windows (PowerShell / CMD)
source venv/bin/activate     # Linux / macOS

# 3. 安装依赖
pip install -r requirements.txt

# 4. 先抓一次数据（不抓的话热榜是空的）
python run_fetch.py

# 5. 启动应用（两个页面各是一个 Streamlit 应用，按需启动）
streamlit run app.py
streamlit run image_inspector.py
```

浏览器会自动打开 `http://localhost:8501`。

> 小提示：`run_fetch.py` 抓取英文源时每条标题之间会 sleep 1 秒（翻译限速），整体跑完需要几分钟，属正常现象。

### 常用命令

```bash
# 手动抓一次：抓取 → 过滤 → 打分 → 去重 → 写入 hotspot.db
python run_fetch.py
```

下面两条是开发时用的，`requirements.txt` 里没有它们，要先自己装：

```bash
pip install pytest ruff   # 装一次就行

pytest                    # 跑测试。提醒：仓库目前还没有 tests/ 目录，现在跑只会显示「0 个测试」
ruff check .              # 代码检查（AGENTS.md 里约定的检查命令）
```

---

## 四、部署到云端（Streamlit Community Cloud）

1. **推到 GitHub**：把代码 push 到一个 GitHub 仓库（`hotspot.db` 也在仓库里，不要加进 `.gitignore`）。
2. **连应用**：打开 <https://share.streamlit.io> → **New app** → 选你的仓库和分支 → **Main file path** 填 `app.py` → Deploy。
3. **再建第二个应用**：重复上一步，Main file path 改填 `image_inspector.py`，得到图片查看器页面。
4. **系统依赖会自动装**：仓库里的 `packages.txt` 写着 `libimage-exiftool-perl`，Streamlit Cloud 会照着装好，所以 Linux 上不用手动放 ExifTool。
5. **数据自动更新**：`.github/workflows/fetch.yml` 每 2 小时抓一次并提交 `hotspot.db`，云端应用下一轮刷新就能看到新内容。想立刻更新，去仓库的 **Actions → Fetch Hotspots → Run workflow** 手动触发。

> 提醒：热榜读的是仓库里的 `hotspot.db`。如果云端页面迟迟不更新，先确认 Actions 是否正常跑、`hotspot.db` 有没有新提交，再重启应用（Manage app → Reboot）。

---

## 五、项目结构

```
personal-hotspot/
├─ app.py                     # 🔥 个人热榜（纯展示层）
├─ image_inspector.py         # 📸 图片底层信息查看器
├─ run_fetch.py               # 抓取入口：抓取 → 过滤 → 打分 → 去重 → 入库
├─ src/                       # 后端逻辑，只被上面的入口复用
│  ├─ config.py               # 读取 config/*.yaml
│  ├─ db.py                   # SQLite 连接与表结构（唯一持有 schema 的地方）
│  ├─ fetchers/               # rss_fetcher.py（feedparser）、api_fetcher.py（Hacker News）
│  ├─ processors/             # filter.py（兴趣匹配）、scorer.py（打分）、dedup.py（URL 去重）
│  └─ utils/                  # http.py（带重试的请求）、translator.py（标题翻译，带降级）
├─ config/
│  ├─ sources.yaml            # 抓取源清单
│  └─ interests.yaml          # 兴趣权重、关键词、排除词（打分的输入）
├─ hotspot.db                 # SQLite 数据库，由 CI 自动提交回仓库
├─ tools/                     # 随仓库分发的 ExifTool（exiftool.exe 本体已 gitignore，需本地自备）
├─ .streamlit/config.toml     # 主题与页面配置，只影响观感
├─ .github/workflows/fetch.yml# 每 2 小时抓取并提交数据库
├─ requirements.txt           # pip 依赖
└─ packages.txt               # Streamlit Cloud 的系统依赖
```

---

## 六、按自己的口味改

- **加/删信息源**：编辑 `config/sources.yaml`，每条需要 `name` / `url` / `type`（`rss` 或 `api`）/ `interest`。
- **改兴趣和打分**：编辑 `config/interests.yaml`，`weight` 是这类兴趣在总分里的权重，`keywords` 命中加分，`exclude` 命中直接丢弃。
- **换主题**：编辑 `.streamlit/config.toml`（只影响界面观感，不影响任何抓取和打分逻辑）。

---

## 七、常见问题

**热榜是空的？**
先跑一次 `python run_fetch.py`，或在 GitHub Actions 里手动触发一次工作流。

**图片查看器报「未找到 exiftool」？**
Windows 下确认 `tools/exiftool.exe` 存在（该文件被 gitignore，克隆后要自己放）；Linux 下确认已安装 `libimage-exiftool-perl`。

**上传 HEIC 后看不到预览图，但元数据正常？**
浏览器本身不支持预览 HEIC，属正常行为，元数据仍会完整解析。

**地图一片空白？**
底图用的是高德瓦片（国内直连、免 key），在国内网络下最稳；境外网络反而可能加载慢。

**点「收藏」有什么额外作用？**
除了标记这条内容，还会给它的来源记一次点赞，来源质量分上升，之后该来源的文章更容易排在前面；「隐藏」则相反。
