# Juliang Ad RPA

> 面向巨量引擎广告创建流程的 Windows 自动化工具：用 Playwright 复用登录态，把重复的广告配置、试跑和批量执行交给脚本完成。

## 这是什么

Juliang Ad RPA 是一个 Python + Playwright 项目，用于辅助操作巨量引擎广告后台。它提供桌面 GUI 和命令行两种入口，支持保存浏览器登录态、填写新建广告参数、单账户试跑、批量执行、失败账号重试，以及配置方案的 YAML/CSV 导入导出。

项目定位是“可检查、可暂停、可重试”的浏览器自动化工具：真正提交广告前可以先使用 Dry Run 打开目标页面并保存调试快照；批量任务会记录成功和失败账号，便于暂停后继续或只重试失败项。

## 当前能力

- **登录态复用**：使用本机 Chrome 的持久化用户目录，登录一次后可继续复用会话。
- **新建广告流程**：打开指定账户的创建页，选择小游戏素材、配置优化目标、深度优化目标、抖音身份、预算、ROI、落地链接、商品信息和行动按钮。
- **Dry Run**：只打开目标页面并保存截图/HTML 调试快照，适合先检查页面和选择器。
- **批量执行**：按账户 ID 队列执行，支持暂停、进度显示、失败账号导出和一键重试。
- **配置方案**：在 GUI 中保存、切换、删除、重载方案，也可以导入或导出 CSV。
- **可配置浏览器**：支持本机 Chrome，也可回退到 Playwright 管理的 Chromium。

## 快速开始

### 环境要求

- Windows
- Python 3.11+
- 已安装的 Google Chrome（推荐）
- 可登录巨量引擎广告后台的账号

### 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e .
python -m playwright install chrome
```

### 启动 GUI

双击 `start_gui.bat`，或执行：

```powershell
.\rpa.ps1 gui
```

首次使用时按这个顺序操作：

1. 点击“打开登录页”，在浏览器中完成巨量引擎登录。
2. 点击“保存登录态并关闭”。登录态会保存在 `.auth/juliang-chrome/`。
3. 在“账户队列”和“广告参数”中填写或导入配置。
4. 先点击“Dry Run”检查目标页面，再运行“新建广告”或“批量运行”。

### 命令行

```powershell
# 检查配置与浏览器启动
.\rpa.ps1 doctor

# 打开登录页并保存登录态
.\rpa.ps1 login

# 使用已保存的登录态打开后台
.\rpa.ps1 open

# 指定账户执行 Dry Run
.\rpa.ps1 new-ad --account-id 123456 --dry-run

# 启动桌面 GUI
.\rpa.ps1 gui
```

完整的新建广告示例：

```powershell
.\rpa.ps1 new-ad `
  --account-id 1868935021932555 `
  --mini-game-name 看你还嘴硬 `
  --mini-game-asset-id 7598217165828816959 `
  --mini-game-app-id tt62e7145afdeec8aa02
```

## 配置文件

- `config/settings.yaml`：站点地址、浏览器、超时、窗口尺寸和产物目录。
- `config/ad_presets.yaml`：GUI 保存的广告参数方案。
- `.auth/`：本地浏览器登录态，已加入 `.gitignore`，不会提交到 Git。
- `logs/`、`recordings/`：运行过程中的截图、HTML 和录制产物，默认保留在本地。

不要把账号密码、Cookie、登录态目录、真实广告链接或业务数据提交到仓库。运行前请确认当前账户、预算和落地链接，自动化脚本只应在你有权操作的广告账户中使用。

## 项目结构

```text
src/juliang_rpa/
├── cli.py                 # 命令行入口
├── gui.py                 # Tkinter 桌面界面
├── browser.py             # Playwright 浏览器与登录态管理
├── config.py              # YAML 配置加载
└── tasks/new_ad.py        # 新建广告与批处理流程
config/                    # 运行配置和广告方案
packaging/                 # Windows 打包脚本
skills/                   # Playwright 自动化开发参考
```

## 当前状态

核心流程已经按巨量引擎当前页面完成了一轮选择器和流程实现，但页面属于第三方动态后台，登录态、账户权限和页面改版都会影响运行结果。建议每次批量执行前先用 Dry Run 检查，并保留 `logs/` 中的调试快照。

## 开发检查

```powershell
python -m compileall src
.\rpa.ps1 doctor
```

欢迎先从 `src/juliang_rpa/tasks/new_ad.py` 和 `src/juliang_rpa/gui.py` 了解自动化流程，再根据实际页面变化补充选择器。
