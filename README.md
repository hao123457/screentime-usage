之前用ai手搓的一个小程序
# App Usage Tracker — 应用使用时间追踪器

Windows 桌面应用使用时间追踪器。后台静默记录每天各应用的使用时长，系统托盘常驻，图形化界面查看统计。

## 特性

- **后台静默追踪** — 每 3 秒检测前台窗口，自动记录应用名称与窗口标题
- **空闲检测** — 5 分钟无键鼠操作自动暂停，数据真实不虚增
- **系统托盘常驻** — 左键单击打开面板，右键菜单：打开/设置/退出
- **多视图统计** — 日/周/月三种聚合视图，日期导航
- **应用图标** — 自动提取 exe 真实图标，未运行应用显示彩色默认图标
- **柱状图可视化** — Top 10 应用横向柱状图，时长一目了然
- **搜索过滤** — 输入关键字即时过滤应用列表
- **历史跳转** — 下拉框快速跳转到任意有记录的历史日期
- **设置面板** — 多标签页：追踪配置 / 帮助 / 更新日志 / 关于
- **数据导出** — 一键导出 CSV，Excel 直接打开（UTF-8 BOM 编码）
- **亮暗主题** — 一键切换亮色/暗色主题，自适应标签
- **AI 智能分析** — 本地规则 + 多模型 AI（Claude / GPT / DeepSeek / Ollama），生成使用习惯分析报告
- **开机自启** — 勾选即写入 Windows 启动文件夹

## 快速开始

```bash
pip install -r requirements.txt
python main.py
```

或双击 `AppUsageTracker.exe`（单文件，约 20MB），桌面快捷方式已自动创建。

自行构建：

```bash
pip install pyinstaller
pyinstaller AppUsageTracker.spec
```

## 使用方法

| 操作 | 说明 |
|------|------|
| 启动程序 | 统计面板打开，后台开始记录 |
| 日 / 周 / 月 | 切换统计视图聚合维度 |
| ◀ ▶ | 前一天/后一天（周、月模式下按周/月切换） |
| 今天 | 快速跳转到今天 |
| 搜索框 | 输入字母/汉字即时过滤应用 |
| ⚙ 设置 | 打开设置窗口（追踪参数/帮助/更新日志/关于） |
| 左键托盘 | 打开统计面板 |
| 右键托盘 → 设置... | 打开设置窗口 |
| 右键托盘 → 退出 | 停止追踪并退出 |
| 关闭窗口（X） | 隐藏到托盘，不退出 |
| 🌙 / ☀️ | 切换亮色/暗色主题 |
| 🤖 AI 分析 | 查看 AI 使用分析报告（需配置 API Key） |

### 键盘快捷键

| 快捷键 | 功能 |
|--------|------|
| ← → | 前一天 / 后一天 |
| Ctrl+D | 跳转到今天 |
| Ctrl+F | 聚焦搜索框 |
| Ctrl+T | 切换亮色/暗色主题 |
| Escape | 清除搜索 |

### AI 智能分析

设置 → 关于 标签页中可找到 AI 分析面板。支持两种分析模式：

| 模式 | 说明 |
|------|------|
| **本地分析** | 无需联网，基于规则分析使用模式、趋势变化、分类统计并给出建议 |
| **云端 AI** | 调用大模型生成更深入的分析报告，支持多种提供商 |

**支持的 AI 提供商：**

| 提供商 | 默认模型 | 说明 |
|--------|---------|------|
| Anthropic | Claude Haiku 4.5 | 需在 [console.anthropic.com](https://console.anthropic.com) 获取 API Key |
| OpenAI | GPT-4o-mini | 需在 [platform.openai.com](https://platform.openai.com) 获取 API Key |
| DeepSeek | deepseek-chat | 需在 [platform.deepseek.com](https://platform.deepseek.com) 获取 API Key |
| Ollama | llama3.2 | 本地运行，无需 API Key（需先安装 [Ollama](https://ollama.com)） |
| 自定义 | 任意模型 | 兼容 OpenAI 协议的第三方 API 端点 |

配置方式：设置 → AI 配置 → 输入 API Key → 选择提供商 → 保存。

## 项目结构

```
app_usage_tracker/
├── main.py              # 入口：tkinter 主循环 + pystray 托盘
├── tracker.py           # 前台窗口追踪（主线程 root.after 轮询）
├── database.py          # SQLite 数据层 + 旧数据自动迁移 + 进程信息持久化
├── gui.py               # tkinter 统计面板 + 柱状图 + 图标提取 + 设置窗口
├── analysis.py          # AI 分析引擎（本地规则分析 + 多模型 AI API）
├── tray_icon.py         # pystray 系统托盘（左键打开 + 右键菜单）
├── config.py            # 配置常量、版本号、更新日志、帮助文本
├── testify2.png         # 托盘/窗口图标
├── app.ico              # EXE 图标
├── AppUsageTracker.spec # PyInstaller 构建配置
└── requirements.txt     # Python 依赖
```

## 技术栈

Python 3.12 + tkinter + pystray + Pillow + pywin32 + psutil + SQLite + sv_ttk

## 架构说明

- **系统托盘** — pystray 运行在独立 daemon 线程，托盘回调通过 `root.after(0, ...)` 安全切换到 tkinter 主线程
- **窗口追踪** — `root.after(3000, callback)` 在主线程轮询前台窗口，无独立线程
- **数据存储** — SQLite + JSON 设置文件，统一存放在 `%USERPROFILE%\.app_usage_tracker\`
- **图标提取** — `ExtractIconEx` + `DrawIconEx` 从 exe 提取图标，三级缓存（TK → PIL → 磁盘）
- **进程信息持久化** — `process_info` 表存储进程名→exe路径映射，历史应用即使未运行也能显示真实图标

## 故障排除

### 图标不显示
确保 `testify2.png` 与 `main.py` 在同一目录。

### 程序在 msys2 / Git Bash 中闪退
msys2 运行时与 Python GIL 存在已知冲突。请使用 **cmd** 或 **PowerShell** 启动程序，或直接双击 `AppUsageTracker.exe`。

### 数据找不到
数据库已统一迁移至 `%USERPROFILE%\.app_usage_tracker\usage.db`。首次运行时会自动从旧位置导入历史数据。

## License

MIT
