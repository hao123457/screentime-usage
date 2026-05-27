# ScreenTime Usage

Windows 桌面应用使用时间追踪器。后台静默记录每天各应用的使用时长，系统托盘常驻，图形化界面查看统计。

## 特性

- **后台静默追踪** — 每 3 秒检测前台窗口，自动记录应用名称与窗口标题
- **空闲检测** — 5 分钟无键鼠操作自动暂停，数据真实不虚增
- **系统托盘常驻** — 最小化到托盘，自定义图标，不影响工作
- **日报统计** — 按日期查看各应用使用时长排名 + 当日总时长
- **历史记录** — 下拉框快速跳转到任意有记录的历史日期
- **开机自启** — 勾选即写入 Windows 启动文件夹

## 快速开始

```bash
pip install -r requirements.txt
python main.py
```

或运行预构建的 `dist/AppUsageTracker.exe`（单文件，约 19MB），双击即可。

自行构建：

```bash
pip install pyinstaller
pyinstaller AppUsageTracker.spec
```

## 使用方法

| 操作 | 说明 |
|------|------|
| 启动程序 | 系统托盘出现图标，后台开始记录 |
| 左键托盘图标 | 打开统计面板 |
| 右键 → 打开统计面板 | 同上 |
| 右键 → 退出 | 停止追踪并退出 |
| 关闭窗口（X） | 隐藏到托盘，不退出 |
| ◀ 前一天 / 后一天 ▶ | 切换日期 |
| 跳转下拉框 | 直接跳到有记录的历史日期 |
| 开机自启复选框 | 勾选后开机自动启动 |

## 项目结构

```
app_usage_tracker/
├── main.py              # 入口：tkinter 主循环 + pystray 托盘线程
├── tracker.py           # 前台窗口追踪（主线程 root.after 轮询）
├── database.py          # SQLite 数据层（含旧数据自动迁移）
├── gui.py               # tkinter 统计面板
├── tray_icon.py         # pystray 系统托盘
├── config.py            # 配置常量与路径
├── testify2.png         # 托盘图标
├── app.ico              # EXE 图标
├── AppUsageTracker.spec # PyInstaller 构建配置
└── requirements.txt     # Python 依赖
```

## 架构说明

- **系统托盘** — pystray 运行在独立 daemon 线程，托盘回调通过 `root.after(0, ...)` 安全切换到 tkinter 主线程，避免跨线程 GIL 冲突
- **窗口追踪** — `root.after(3000, callback)` 在主线程轮询前台窗口，无独立线程，消除 `PyEval_RestoreThread` 致命错误
- **数据存储** — SQLite，数据库统一存放在 `%USERPROFILE%\.app_usage_tracker\usage.db`，源码运行与 EXE 运行共享同一份数据
- **图标** — 托盘图标与窗口图标均使用 `testify2.png`，EXE 图标使用同图生成的 `app.ico`

## 技术栈

Python 3.12 + tkinter + pystray + Pillow + pywin32 + psutil + SQLite

## 故障排除

### 图标不显示
确保 `testify2.png` 与 `main.py` 在同一目录。

### 程序在 msys2 / Git Bash 中闪退
msys2 运行时与 Python GIL 存在已知冲突。请使用 **cmd** 或 **PowerShell** 启动程序，或直接双击 `AppUsageTracker.exe`。

### 数据找不到
数据库已统一迁移至 `%USERPROFILE%\.app_usage_tracker\usage.db`。首次运行时会自动从旧位置导入历史数据。

## License

MIT
