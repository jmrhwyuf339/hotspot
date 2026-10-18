# Project Rules

This is a Python project.

## 核心铁律（必须遵守）
- 这是一个基于 Streamlit 的个人工具项目，包含“个人热榜”和“图片底层信息查看器”。
- 修改 UI 时，绝对不要破坏后端的抓取逻辑（run_fetch.py）和打分逻辑。
- 所有读取 EXIF 的操作，必须通过调用 `tools/exiftool.exe` 实现，严禁自己写底层解析库。
- 测试完成后，记得清理产生的临时文件。

## Project Structure

两个 Streamlit 应用 + 一个抓取流水线，后端逻辑全部收在 `src/` 里。

- `app.py` - Streamlit「个人热榜」：纯展示层，只读 `hotspot.db`（`from src.db import ...`），不抓取、不打分
- `image_inspector.py` - Streamlit「图片底层信息查看器」：调用 `tools/exiftool.exe` 提取元数据，含 pydeck 地图定位
- `run_fetch.py` - 抓取入口（CLI）：抓取 → 过滤 → 打分 → 去重 → 写入 SQLite，由 CI 定时调用
- `src/` - 后端逻辑，只被上面两个入口复用
  - `src/config.py` - 读取 `config/*.yaml`
  - `src/db.py` - SQLite 连接与表结构（`items` / `user_feedback`），唯一持有 schema 的模块
  - `src/fetchers/` - `rss_fetcher.py`（feedparser）、`api_fetcher.py`（Hacker News）
  - `src/processors/` - `filter.py`（兴趣匹配）、`scorer.py`（打分）、`dedup.py`（URL 归一化去重）
  - `src/utils/` - `http.py`（带重试的 httpx 请求）、`translator.py`（标题翻译，带降级）
- `config/sources.yaml` - 抓取源清单（RSS / API）
- `config/interests.yaml` - 兴趣权重、关键词、排除词，是打分的输入
- `hotspot.db` - SQLite 数据库，由 CI 自动提交回仓库
- `tools/` - 随仓库分发的 ExifTool（`exiftool.exe` + `exiftool_files/`，已 gitignore，但必须本地存在）
- `.streamlit/config.toml` - 主题与页面配置，只影响观感
- `.github/workflows/fetch.yml` - 每 2 小时跑一次 `run_fetch.py` 并提交 `hotspot.db`
- `requirements.txt` / `packages.txt` - pip 依赖 / Streamlit Cloud 的系统依赖

## Code Standards

- Follow PEP 8 style guidelines
- Use type hints for function signatures
- Use virtual environments for dependency isolation

## Commands

- **Test:** `pytest`
- **Lint:** `ruff check .`

## Package Manager

This project uses **pip**. Always use `pip` for installing dependencies.

## Custom Agents

The following custom subagents are available (invoke with `@agent-name`):

- **@backend-developer**: Server-side logic, APIs, and data processing
- **@python-pro**: Pythonic patterns, async, and ecosystem best practices
- **@django-developer**: Django ORM, views, middleware, and admin patterns
- **@fastapi-developer**: FastAPI async endpoints, Pydantic, and OpenAPI
- **@devops-engineer**: CI/CD pipelines, infrastructure, and deployment
- **@code-reviewer**: Code review with security and performance focus
- **@ai-engineer**: AI system design, model integration, and inference pipelines
- **@data-engineer**: Data pipelines, ETL workflows, and warehouse design
- **@data-scientist**: Statistical modeling, experiments, and feature engineering
- **@machine-learning-engineer**: ML model training, evaluation, and deployment
- **@prompt-engineer**: Prompt design, chain-of-thought, and LLM optimization
- **@dependency-manager**: Dependency updates, audit, and compatibility checks
- **@git-workflow-manager**: Git workflow, branching strategy, and commit hygiene
- **@test-writer**: Test generation following project patterns

## Conventions

- Use conventional commits: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`
- Write meaningful commit messages that explain the "why"
- Keep PRs focused on a single concern
