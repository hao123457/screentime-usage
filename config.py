import os
import sys
import json

if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".app_usage_tracker")
DB_PATH = os.path.join(CONFIG_DIR, "usage.db")
SETTINGS_PATH = os.path.join(CONFIG_DIR, "settings.json")

STARTUP_DIR = os.path.join(
    os.getenv("APPDATA", ""),
    r"Microsoft\Windows\Start Menu\Programs\Startup"
)
ICON_PATH = os.path.join(BASE_DIR, "app.ico")

# Static fallback for system processes whose FileDescription may be
# unavailable or unhelpful.  Most apps are resolved automatically via
# the exe's version-info FileDescription field in tracker.py.
PROCESS_NAME_MAP = {
    "applicationframehost": "Settings",
    "conhost": "Windows Console",
    "dwm": "Desktop Window Manager",
    "explorer": "File Explorer",
    "lockapp": "Windows Lock Screen",
    "mstsc": "Remote Desktop",
    "openwith": "Open With",
    "pickerhost": "File Picker",
    "searchhost": "Windows Search",
    "shellexperiencehost": "Windows Shell",
    "snippingtool": "Snipping Tool",
    "startmenuexperiencehost": "Start Menu",
    "windowsterminal": "Windows Terminal",
}


def get_friendly_name(proc_name):
    """将进程名映射为友好名称，无匹配时返回原值。"""
    key = proc_name.lower().removesuffix(".exe")
    return PROCESS_NAME_MAP.get(key, proc_name)


_DEFAULTS = {
    "poll_interval": 3,
    "idle_threshold": 300,
    "start_minimized": False,
    "theme": "light",
    "api_key": "",
    "api_provider": "anthropic",
    "api_endpoint": "",
    "api_model": "",
    "app_categories": {},
}

# ── App metadata (displayed in Settings → 关于 / 更新日志 / 帮助) ──

APP_VERSION = "1.4.0"

CHANGELOG = [
    ("1.4.0", "2026-06-29", [
        "新增 AI 智能分析功能（设置 → AI 分析）",
        "新增本地分析报告：总览、Top 5 应用、变化趋势、分类统计、使用建议",
        "新增多模型 AI 分析支持：Anthropic Claude / OpenAI / DeepSeek / Ollama",
        "新增自定义 API 端点支持，兼容 OpenAI 协议的第三方服务",
        "新增 AI 分析面板：显示/复制分析结果、刷新、保存为文本文件",
        "新增 AI 配置页：API Key 输入、模型提供商选择、自定义端点/模型设置",
        "新增应用分类映射表，支持自定义分类标签",
        "修复：任务栏图标显示为 Python 图标的问题（添加 AppUserModelID + 提前 iconbitmap 调用时机）",
        "更新：托盘与窗口图标统一使用 app.ico",
    ]),
    ("1.3.0", "2026-06-28", [
        "新增设置窗口多标签页：帮助、更新日志、关于",
        "新增应用图标显示（从 exe 提取真实图标，含默认图标回退）",
        "新增日/周/月视图模式切换，含周报/月报聚合统计",
        "新增使用时长柱状图可视化（Top 10 应用）",
        "新增托盘左键单击打开统计面板",
        "新增托盘菜单\"设置...\"入口",
        "优化：持久化应用 exe 路径到数据库，历史应用也能显示真实图标",
        "优化：搜索框与设置按钮移至独立行，不再被挤压",
        "优化：窗口最小宽度约束，默认尺寸加宽",
    ]),
    ("1.2.0", "2026-06-15", [
        "新增搜索过滤功能",
        "新增亮色/暗色主题切换",
        "新增开机自启选项",
        "新增设置面板（轮询间隔/空闲阈值可配）",
        "新增 CSV 数据导出",
        "新增右键菜单查看应用位置",
        "数据存储迁移到用户目录 ~/.app_usage_tracker",
    ]),
    ("1.1.0", "2026-06-15", [
        "新增搜索过滤功能",
        "新增亮色/暗色主题切换",
        "新增开机自启选项",
        "新增设置面板（轮询间隔/空闲阈值可配）",
        "新增 CSV 数据导出",
        "新增右键菜单查看应用位置",
        "数据存储迁移到用户目录 ~/.app_usage_tracker",
    ]),
    ("1.0.0", "2026-05-20", [
        "首个版本",
        "后台前台窗口追踪",
        "SQLite 本地数据存储",
        "系统托盘常驻",
        "空闲检测自动暂停",
        "日报统计面板",
    ]),
]

HELP_TEXT = """\
快捷键
  ← →        前一天 / 后一天
  Ctrl+D      跳转到今天
  Ctrl+F      聚焦搜索框
  Ctrl+T      切换亮色/暗色主题
  Escape      清除搜索

视图模式
  日 — 单日统计，按应用汇总使用时长
  周 — 当周（周一~周日）聚合统计
  月 — 当月聚合统计

搜索
  在搜索框中输入关键字即时过滤应用列表
  支持应用名称的任意部分匹配

托盘图标
  左键单击 — 打开统计面板
  右键单击 — 显示菜单（打开/退出）
  关闭窗口（X）— 隐藏到托盘，不退出程序

开机自启
  勾选后自动在 Windows 启动文件夹创建快捷方式
  取消勾选即删除

数据导出
  设置 → 导出数据为 CSV
  导出的 CSV 使用 UTF-8 BOM 编码，Excel 可直接打开\
"""


def load_settings():
    try:
        with open(SETTINGS_PATH, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    return {k: data.get(k, v) for k, v in _DEFAULTS.items()}


def save_settings(data):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump({k: data[k] for k in _DEFAULTS}, f, indent=2)


_settings = load_settings()
POLL_INTERVAL = _settings["poll_interval"]
IDLE_THRESHOLD = _settings["idle_threshold"]
START_MINIMIZED = _settings["start_minimized"]
