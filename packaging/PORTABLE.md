# Ordina / 归序 — 便携版使用说明

开箱即用，无需安装 Python，也不需要联网。解压后即可运行。

> 便携包只含图形界面版。命令行功能仍在，但需回到源码运行（见文末）。

## 目录说明

```
Ordina-v3.0.0-win64\
├── Ordina\              图形界面版
│   ├── Ordina.exe       双击启动（无黑色控制台窗口）
│   └── _internal\       运行依赖，勿删、勿改名
├── README.md            项目完整文档
└── README-PORTABLE.md   本文件
```

> 单文件模式下没有 `_internal` 目录，`Ordina.exe` 直接放在根目录。

## 图形界面

双击 `Ordina.exe`。

| 快捷键 | 作用 |
| --- | --- |
| `Ctrl+O` | 选择要整理的文件夹 |
| `Ctrl+P` | 预览整理效果（不改动磁盘） |
| `Ctrl+Enter` | 执行整理 |
| `F5` | 刷新文件列表 |
| `Ctrl+T` | 切换深色 / 浅色主题 |

五个标签页：整理、查重、分析、规则、日志。
先预览、确认无误后再执行——预览阶段不会碰任何文件。

## 命令行

便携包不再附带 `ordina-cli.exe`。请用源码运行（需要本机装有 Python ≥ 3.9）：

```bat
:: 整理（先预览）
python -m ordina cli organize --path %USERPROFILE%\Downloads

:: 确认无误后落盘
python -m ordina cli organize --path %USERPROFILE%\Downloads --execute

:: 按扩展名分类（而非按用途）
python -m ordina cli organize --path ... --mode extension --execute

:: 查看命名规则与模板
python -m ordina cli naming

:: 存储分析 / 诊断 / 清理
python -m ordina cli analyze --path ... --format markdown
python -m ordina cli diagnose --path ...
python -m ordina cli cleanup --path ... --execute

:: 安卓手机（需开启 USB 调试 + ADB）
python -m ordina cli phone devices
python -m ordina cli phone organize --path /sdcard/Download
```

完整参数用 `python -m ordina cli --help` 查看。

### 计划任务（每日自动整理）

在 Windows 任务计划程序里新建任务：
程序填 `pythonw.exe` 的完整路径，参数填 `-m ordina cli organize --path "..." --execute`，
起始位置填 Ordina 源码目录。即可每天定时整理，全程无需人工干预。

## 常见问题

**首次运行被 Windows 拦下**
exe 未做代码签名，SmartScreen 会提示"未知发布者"，点「更多信息 → 仍要运行」即可。
本程序不联网、不上传任何数据。

**杀毒软件误报**
PyInstaller 打包的程序常被启发式引擎误判；UPX 压缩会进一步提高误报概率。
加白名单即可，源码完全开放可自行审查。不放心可用 `.\build.ps1 -NoUpx` 重打一份不压缩的版本。

**启动很慢 / 卡在空白窗口**
单文件模式（onefile）每次启动都要把依赖解压到临时目录，属正常现象；
改用单目录模式（默认）会快很多。

**任务管理器里出现多个进程**
正常现象：GUI 用后台线程做文件扫描与哈希计算，避免界面卡死。

**配置文件与日志在哪**
- 界面偏好（主题、最近目录、命名规则）：`%USERPROFILE%\.ordina.json`
- 整理日志：目标文件夹下的 `.ordina_logs\`（隐藏目录）

**可以直接拷到 U 盘用吗**
可以。整个目录是自包含的，换台 Windows 电脑同样能跑。

## 系统要求

- Windows 10 / 11（64 位）
- 安卓整理功能另需 ADB 环境
- EXIF 日期识别需要 Pillow（便携包未内置；未安装时自动回退到文件修改时间）
