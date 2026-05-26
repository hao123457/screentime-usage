# ScreenTime Usage

Windows 桌面应用使用时间追踪器。后台记录每天各应用的使用时长和电脑总使用时间，图形化界面查看统计，系统托盘常驻。

## 特性

- **后台静默追踪** -- 每 3 秒检测前台窗口，自动记录应用使用时长
- **空闲检测** -- 超过 5 分钟无键鼠操作自动暂停计时，不会虚增数据
- **系统托盘常驻** -- 最小化到托盘，不影响日常工作
- **日报统计** -- 按日期查看各应用使用时长排名 + 当日总使用时间
- **历史记录** -- 可切换查看任意历史日期的统计
- **开机自启** -- 勾选即生效，写入 Windows Startup 文件夹

## 启动方式

### 方式一：Python 源码运行

```bash
pip install -r requirements.txt
python main.py
```

### 方式二：直接运行 exe

下载 `dist/AppUsageTracker.exe`（19MB，单文件），双击运行。

或自行构建：

```bash
pip install pyinstaller
pyinstaller AppUsageTracker.spec
```

## 使用方法

| 操作 | 说明 |
|------|------|
| 启动程序 | 系统托盘出现图标，后台开始记录 |
| 左键点击托盘图标 | 打开统计面板 |
| 右键 -> 打开统计面板 | 同上 |
| 右键 -> 退出 | 停止追踪并退出程序 |
| 关闭窗口 | 隐藏到托盘，不退出 |
| < 前一天 / 后一天 > | 切换统计日期 |
| 跳转下拉框 | 直接跳转到有记录的历史日期 |
| 开机自启复选框 | 勾选后下次开机自动启动 |

## 统计面板

```
+----------------------------------+
|  应用使用时间统计                  |
|  < 前一天  [2026-05-25]  后一天 > |
+----------------------------------+
|  应用名称         使用时长         |
|  ------------------------------- |
|  Code.exe        2h 35m          |
|  chrome.exe      1h 12m          |
|  ...             ...             |
+----------------------------------+
|  当日总使用时间: 4h 32m           |
|  [x] 开机自启                    |
+----------------------------------+
```

## 项目结构

```
app_usage_tracker/
+-- main.py          # 入口：启动 tkinter 主循环 + pystray 托盘线程
+-- tracker.py       # 前台窗口追踪（主线程 root.after 轮询，无独立线程）
+-- database.py      # SQLite 数据层（含窗口标题字段）
+-- gui.py           # tkinter 统计面板
+-- tray_icon.py     # pystray 系统托盘（独立 daemon 线程）
+-- config.py        # 配置常量
+-- testify.png      # 托盘图标
+-- requirements.txt # 依赖
```

## 架构说明

- **托盘图标**：pystray 运行在独立 daemon 线程，通过 `root.after(0, callback)` 与 tkinter 主线程通信，避免跨线程直接调用导致的 GIL 冲突。
- **前台窗口追踪**：使用 `root.after(3000, callback)` 在主线程定时轮询，不使用 daemon 线程。消除了 `time.sleep()` / `Event.wait()` 释放 GIL 导致的 `PyEval_RestoreThread` 致命错误。
- **数据存储**：SQLite + 线程本地连接，WAL 模式保证读写并发安全。

## 技术栈

Python 3.12 + tkinter + pystray + pywin32 + psutil + Pillow + SQLite

## 故障排除

### 程序闪退 / PyEval_RestoreThread 错误

使用 **cmd 或 PowerShell** 启动程序，避免从 msys2 / Git Bash 直接运行 Python：

```bash
pythonw main.py
```

msys2 的运行时与 Python GIL 管理机制存在已知不兼容，会导致 daemon 线程崩溃。本程序已最大限度减少线程使用，但 pystray 仍需要一个托盘线程。

### 图标不显示

确保 `testify.png` 与 `main.py` 在同一目录下。

## License

MIT
