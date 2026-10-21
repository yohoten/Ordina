# Ordina / 归序 — 便携版使用说明

开箱即用，无需安装 Python，也不需要联网。解压后即可运行。

## 目录说明

```
Ordina-v3.0.0-win64\
├── Ordina\                 图形界面版
│   └── Ordina.exe          双击启动（无黑色控制台窗口）
│   └── _internal\          运行依赖，勿删、勿改名
├── Ordina-cli\             命令行版
│   └── ordina-cli.exe      在终端里使用
│   └── _internal\          运行依赖
├── README.md               项目完整文档
└── README-PORTABLE.md      本文件
```

> 单文件模式下没有 `_internal` 目录，两个 exe 直接放在根目录：`Ordina.exe` / `ordina-cli.exe`。

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

打开 PowerShell 或 CMD，进入 `Ordina-cli` 目录：

```bat
:: 整理（先预览）
ordina-cli.exe organize --path %USERPROFILE%\Downloads

:: 确认无误后落盘
ordina-cli.exe organize --path %USERPROFILE%\Downloads --execute

:: 按扩展名分类（而非按用途）
ordina-cli.exe organize --path ... --mode extension --execute

:: 按日期分组 + 追加日期后缀
ordina-cli.exe organize --path ... --date-grouping --add-date-suffix --execute

:: 查看命名规则与模板
ordina-cli.exe naming

:: 仅重命名（指定模板）
ordina-cli.exe rename --path ... --template "{date}_{name}" --execute

:: 存储分析 / 诊断 / 清理
ordina-cli.exe analyze --path ... --format markdown
ordina-cli.exe diagnose --path ...
ordina-cli.exe cleanup --path ... --execute

:: 安卓手机（需开启 USB 调试）
ordina-cli.exe phone devices
ordina-cli.exe phone organize --path /sdcard/Download
ordina-cli.exe phone backup --remote /sdcard/DCIM --local D:\backup
```

完整参数用 `ordina-cli.exe --help` 或 `ordina-cli.exe organize --help` 查看。

### 计划任务（每日自动整理）

把 `organize --path ... --execute` 写进 Windows 任务计划程序，
指向本目录下的 `ordina-cli.exe`，即可每天定时整理，全程无需人工干预。

## 常见问题

**首次运行被 Windows 拦下**
exe 未做代码签名，SmartScreen 会提示"未知发布者"，点「更多信息 → 仍要运行」即可。
本程序不联网、不上传任何数据。

**杀毒软件误报**
PyInstaller 打包的程序常被启发式引擎误判。加白名单即可；源码完全开放可自行审查。

**任务管理器里出现多个进程**
正常现象：GUI 用后台线程做文件扫描与哈希计算，避免界面卡死。

**配置文件与日志在哪**
- 界面偏好（主题、最近目录、命名规则）：`%USERPROFILE%\.ordina.json`
- 整理日志：目标文件夹下的 `.ordina_logs\`（隐藏目录）

**可以直接拷到 U 盘用吗**
可以。整个目录是自包含的，换台 Windows 电脑同样能跑。

## 系统要求

- Windows 10 / 11（GUI 与 CLI 均为 64 位）
- 安卓整理功能另需 ADB 环境
