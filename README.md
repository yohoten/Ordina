# 📂 Download Organizer

下载文件夹整理工具 v2.0 — **PC 端 + 安卓手机双端**，基于"按用途分类"的文件管理哲学，一键整理杂乱的下载目录。

融合知乎文章《如何高效整理和分类电脑上的文件》的管理理念：
- **按用途分类**（而非仅扩展名）
- **数字前缀**固定排序
- **日期后缀**追溯版本
- **扁平结构**减少嵌套
- **8 大分类**覆盖全盘

---

## ✨ 功能特性

### 🖥 PC 端文件整理

**双模式智能分类**
- **扩展名模式**：按扩展名归类（文档 / 图片 / 视频 / 音频 / 压缩包 / 代码 / 安装包 / 字体 / 其他）
- **用途模式**：8 大用途分类体系（工作目录 / 学习资料 / 参考资料 / 视频娱乐 / 相册 / 软件工具 / 个人资料 / 存档资料），综合**文件名关键词（40%）+ 正则模式（25%）+ 扩展名（20%）+ 上下文（15%）**加权评分

**智能识别引擎**
- 文件头部魔数检测（Magic Bytes）识别真实类型
- EXIF 检测（区分手机拍摄 vs 网图 / 截图）
- Windows Zone.Identifier 读取下载来源
- 来源推测与处置建议（保留 / 归档 / 清理 / 审查）

**整理与维护**
- **整理**：按分类移动 + 可选日期分组子目录 + 日期后缀 + 冲突自动解决
- **查重**：文件大小 + MD5 双重校验，显示可释放空间
- **清理**：临时文件（.tmp / ~$ / .crdownload 等）+ 空目录
- **分析**：存储占用 / 扩展名分布 / 过期文件 / 大文件 / 临时文件统计
- **诊断**：命名规范问题（缺日期后缀 / 缺数字前缀 / 嵌套过深 / 同名冲突）+ 归档建议 + 预计释放空间
- **命名规范化**：文件加 `_YYYYMMDD` 日期后缀、文件夹加 `01_` 数字前缀、批量重命名

**报告导出**
- JSON / CSV / Markdown 三种格式
- 整理报告、存储分析报告、诊断报告

### 📱 安卓手机文件管理（ADB）

通过 Android Debug Bridge 连接手机，无需 root：

| 命令 | 功能 |
| --- | --- |
| `phone devices` | 检测连接的安卓设备（型号 / 状态 / 授权） |
| `phone info` | 设备信息 + 存储概况 + 电量 + 存储告警 |
| `phone organize` | 整理手机目录（预览 / 执行） |
| `phone cleanup` | 清理手机临时文件与空目录 |
| `phone backup` | 备份手机文件到电脑（可自动整理、按扩展名过滤） |
| `phone scan` | 扫描手机文件（扩展名过滤 / 大文件查找 / Top10 统计） |
| `phone diagnose` | 全面诊断手机存储（主要目录占用 / 大文件 / 建议） |
| `phone reconnect` | 重新连接 USB 设备 / 重启 ADB 服务 |

内置手机常见目录映射（下载 / 相册 / 截图 / 微信文件等）与厂商路径差异配置。

### 🖥 GUI 多标签界面

| 标签页 | 功能 |
| --- | --- |
| **整理** | Treeview 可排序预览 + 批量选择 + 进度条 |
| **查重** | 树形展开/折叠 + 全选重复项 + 双击预览 |
| **分析** | Canvas 可视化图表 + Treeview 统计表 |
| **规则** | JSON 实时校验 + 规则导入/导出 + 搜索过滤 |
| **日志** | 级别过滤 + 自动刷新 + 关键词搜索 |

全局 **暗色 / 亮色主题一键切换**，支持快捷键。

---

## 📁 目录结构

```
Download_Organizer/
├── __main__.py            # 入口路由（GUI / CLI）
├── __init__.py            # 包初始化、版本、公共导出
├── gui.py                 # 多标签图形界面（5 Tab，双主题）
├── cli.py                 # 命令行接口（PC + 手机全部命令）
├── organizer.py           # 文件整理核心引擎
├── classifiers.py         # 双模式分类器（扩展名 / 用途）
├── recognizer.py          # 智能识别引擎（魔数 / EXIF / Zone.Identifier）
├── normalizer.py          # 命名规范化（数字前缀 / 日期后缀）
├── archiver.py            # 归档与清理管理器
├── reporter.py            # 报告生成器（JSON / CSV / Markdown）
├── config.py              # 全局配置与默认规则
│
├── android/               # 安卓手机文件管理（ADB）
│   ├── adb_bridge.py      #   ADB 连接 / 设备检测 / 文件操作
│   ├── phone_config.py    #   手机目录映射 / 厂商路径配置
│   ├── phone_organizer.py #   手机整理引擎
│   └── phone_scanner.py   #   手机文件扫描
│
├── launcher.bat           # 双击启动脚本（调 gui.py）
├── launcher.exe           # 编译版启动器（由 launcher.bat 用 Bat To Exe 生成）
├── download_organizer.ico # 程序图标
├── README.md
└── requirements.txt
```

---

## ⚙️ 环境要求

| 项目 | 要求 |
| --- | --- |
| Python | 3.8+（GUI 需 tkinter，官方安装包默认自带） |
| 核心依赖 | 仅标准库，无需 pip 安装 |
| 可选：Pillow | 图片 EXIF 检测（未安装时自动降级跳过） |
| 可选：ADB Platform Tools | 安卓手机功能（需 `adb.exe` 在系统 PATH 中） |

---

## 🚀 使用方法

### 启动 GUI

```bat
:: 方式一：双击 launcher.bat（或 launcher.exe）
:: 方式二：
python -m download_organizer
:: 方式三：
python gui.py
```

### CLI 使用

```bash
# ── PC 端 ──
python -m download_organizer cli organize --path ~/Downloads
                          # 预览整理（默认 dry-run 预览，安全）
python -m download_organizer cli organize --path ~/Downloads --execute
                          # 实际执行
python -m download_organizer cli organize --path ~/Downloads --mode extension
                          # 切换为扩展名分类模式
python -m download_organizer cli organize --path ~/Downloads --date-grouping --add-date-suffix
                          # 日期分组 + 日期后缀
python -m download_organizer cli analyze --path ~/Downloads --format markdown -o report.md
                          # 生成 Markdown 分析报告
python -m download_organizer cli cleanup --path ~/Downloads --execute
                          # 清理临时文件 + 空目录
python -m download_organizer cli rename --path ~/Downloads --add-date-suffix --execute
                          # 批量添加日期后缀重命名
python -m download_organizer cli diagnose --path ~/Downloads -o report.json
                          # 全面诊断
python -m download_organizer cli categories
                          # 查看 8 大用途分类体系
python -m download_organizer cli version
                          # 版本信息

# ── 安卓手机（需已连接 USB 并开启 USB 调试）──
python -m download_organizer cli phone devices                  # 检测设备
python -m download_organizer cli phone info                     # 手机信息
python -m download_organizer cli phone organize --path /sdcard/Download --execute
python -m download_organizer cli phone cleanup --path /sdcard/Download --execute
python -m download_organizer cli phone backup --remote /sdcard/DCIM/Camera --local D:/backup --organize
                          # 备份相册到电脑并自动整理
python -m download_organizer cli phone scan --path /sdcard --ext .apk
python -m download_organizer cli phone diagnose
python -m download_organizer cli phone reconnect
```

> 💡 **安全设计**：所有 `organize / cleanup / backup / rename` 命令默认**预览模式（dry-run）**，只显示将要执行的操作，确认无误后加 `--execute` 才实际执行。

---

## 🧩 技术要点

- **纯标准库核心**：分类、整理、查重、归档全部基于 Python 内置模块
- **多端统一引擎**：PC 与手机共用相同的整理设计模式（分类器 / 规范化 / 查重）
- **加权分类评分**：关键词 40% + 正则 25% + 扩展名 20% + 上下文 15%，按优先级裁决同分
- **双重查重**：先按大小分组，再算 MD5，兼顾速度与准确率
- **智能降级**：Pillow 缺失时自动跳过 EXIF 检测，不影响其他功能
- **异步 ADB**：`adb_bridge` 使用 asyncio 封装，支持设备选择与错误重试
- **报告可追踪**：整理日志落盘 `目标目录/.organizer_logs/`，操作全记录

---

## ⚠️ 注意事项

1. **整理前务必预览**：首次使用请先运行默认的 dry-run 模式，确认分类结果符合预期后再 `--execute`。
2. **用途分类可调**：`config.py` 中的关键词 / 正则 / 扩展名规则均可自定义；GUI「规则」页支持导入导出。
3. **安卓功能依赖 ADB**：需要安装 [Platform Tools](https://developer.android.com/studio/releases/platform-tools) 并开启手机「开发者模式 + USB 调试」；Android 11+ 部分目录（如 `Android/data/`）受系统访问限制。
4. **备份操作安全**：手机 `backup` 默认只读拉取到电脑，不会删除手机文件。
5. `launcher.exe` 是编译产物，由 `launcher.bat` 重新生成即可。

---

## 📦 版本历史

- **v2.0**：引入 8 大用途分类体系（按用途分类）；新增 GUI 多标签界面（整理/查重/分析/规则/日志，双主题）；新增安卓手机文件管理（ADB）；CLI 全面命令化
- **v1.x**：基础扩展名分类整理 + 查重 + 清理
