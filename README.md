# 🗂 Ordina · 归序

> 按用途分类的双端文件整理工具 — PC + 安卓手机，一键把杂乱的下载目录归位成有序结构。

`Ordina` 取自拉丁语 **ordinare**（使有序），中文名 **归序** —— 归并 + 秩序。
融合知乎文章《如何高效整理和分类电脑上的文件》的管理理念：

- **按用途分类**（而非仅看扩展名）
- **数字前缀**固定目录排序
- **日期后缀**追溯版本
- **扁平结构**减少嵌套
- **8 大分类**覆盖全盘

---

## ✨ 功能特性

### 🖥 PC 端

| 能力 | 说明 |
| --- | --- |
| 双模式分类 | **用途模式**（8 大用途，关键词 40% + 正则 25% + 扩展名 20% + 上下文 15% 加权）；**扩展名模式**（文档/图片/视频/音频/压缩包/代码/安装包/字体） |
| 智能识别 | 文件头魔数检测、EXIF 检测（手机拍摄 vs 网图/截图）、Windows Zone.Identifier 下载来源 |
| 整理 | 按分类移动 + 可选月份分组 + 命名规则改写 + 冲突自动消解 |
| 查重 | 文件大小 + MD5 双重校验，显示可释放空间 |
| 清理 | 临时文件（`.tmp` / `~$` / `.crdownload` 等）+ 空目录 |
| 分析 | 存储占用 / 扩展名分布 / 过期文件 / 大文件 / 临时文件统计 |
| 诊断 | 命名规范问题（缺日期 / 缺前缀 / 不合规 / 嵌套过深）+ 归档建议 |
| 报告 | JSON / CSV / Markdown 三种格式导出 |

### 📱 安卓手机（ADB，无需 root）

| 命令 | 功能 |
| --- | --- |
| `phone devices` | 检测设备（型号 / 状态 / 授权） |
| `phone info` | 设备信息 + 存储概况 + 电量 + 存储告警 |
| `phone organize` | 整理手机目录（预览 / 执行） |
| `phone cleanup` | 清理临时文件与空目录 |
| `phone backup` | 备份到电脑（可自动整理、按扩展名过滤） |
| `phone scan` | 扫描文件（扩展名过滤 / 大文件 / Top10） |
| `phone diagnose` | 全面诊断手机存储 |
| `phone reconnect` | 重连 USB / 重启 ADB 服务 |

### 🖼 图形界面

工具栏（品牌 / 目标文件夹 / 分类模式 / 主题开关）+ 五个标签页：

| 标签页 | 内容 |
| --- | --- |
| **整理** | 命名规则面板 + 可勾选可排序的预览表（勾选真正决定执行范围）+ 进度条 |
| **查重** | 树形分组、⭐ 标记保留项、批量选择、双击打开 |
| **分析** | Canvas 柱状图 + 关键指标卡 + 统计表 + 三种格式导出 |
| **规则** | 扩展名 JSON（实时校验/搜索/导入导出）+ 关键词映射 + 命名规则 JSON |
| **日志** | 级别过滤 + 关键词搜索 + 5 秒自动刷新 |

全局 **暗色 / 亮色主题一键切换（Ctrl+T）**，主题切换会重绘包括卡片、工具栏、状态栏在内的全部控件。

---

## 🧾 命名规则（v3.0 重点重写）

规则收敛在 `ordina/core/naming.py`，由 `NamingRules` 数据类描述，可 JSON 序列化、GUI 与 CLI 共用。

| 维度 | 说明 | 默认值 |
| --- | --- | --- |
| 命名模板 | 占位符 `{name}` `{date}` `{category}` `{index}` 自由组合 | `{name}_{date}` |
| 日期来源 | `auto`（文件名 > EXIF > 修改时间 > 创建时间 > 当前）/ filename / exif / modified / created / now | `auto` |
| 日期格式 | 任意 `strftime` 格式 | `%Y%m%d` |
| 安全清洗 | 非法字符 `<>:"/\|?*`、MSYS 私用区字符还原、结尾点与空格、保留设备名（CON/PRN/NUL/COM1）、全角转半角、超长截断 | 开启 |
| 冲突消解 | 语义化 `_v2` / `_v3`，插在日期后缀之前 | `_v{n}` |
| 数字前缀 | 分类目录前缀宽度（修复了旧版 `1_工作目录` 的宽度 bug） | 2 位 |

可用模板预设：

```
{name}_{date}              名称_日期（推荐）      报告.pdf → 报告_20240512.pdf
{date}_{name}              日期_名称              报告.pdf → 20240512_报告.pdf
{category}_{name}_{date}   分类_名称_日期         报告.pdf → 01_工作目录_报告_20240512.pdf
{name}_{date}_{category}   名称_日期_分类
{name}                     仅安全清洗，不加日期
```

日期识别的三重校验（避免订单号误判）：**数字边界**（`(?<!\d)` / `(?!\d)`）+ **合法范围**（月 1-12、日真实存在）+ **合理年份**（1970-2099）。因此 `订单20240512001.xlsx` 不会被当成 5 月 12 日的文件。

---

## 📁 目录结构

```
Ordina/
├── ordina/                      # 主包
│   ├── __init__.py              #   版本与公共导出
│   ├── __main__.py              #   入口路由（gui / cli）
│   ├── core/                    #   核心引擎
│   │   ├── config.py            #     全局配置与默认规则
│   │   ├── classifiers.py       #     双模式分类器
│   │   ├── recognizer.py        #     智能识别（魔数 / EXIF / 来源）
│   │   ├── naming.py            #     命名规则引擎（v3.0 重写）
│   │   ├── archiver.py          #     归档与清理
│   │   ├── reporter.py          #     报告生成（JSON / CSV / Markdown）
│   │   └── organizer.py         #     整理主引擎
│   ├── ui/                      #   图形界面
│   │   ├── theme.py             #     调色板 + 控件注册表 + ttk 样式
│   │   ├── widgets.py           #     卡片 / 按钮 / 分段控件 / 可排序表格
│   │   ├── app.py               #     主窗口（工具栏 + 标签页 + 状态栏）
│   │   └── tabs/                #     整理 / 查重 / 分析 / 规则 / 日志
│   ├── cli/                     #   命令行接口
│   │   └── main.py
│   └── android/                 #   手机端（ADB）
│       ├── adb_bridge.py
│       ├── phone_config.py
│       ├── phone_scanner.py
│       └── phone_organizer.py
├── assets/
│   └── icon.ico
├── launcher.bat                 # 双击启动（launcher.exe 由其生成）
├── README.md
└── requirements.txt
```

**v3.0 结构变化**：模块间不再使用 `sys.path.insert` 硬拼路径，全部改为显式相对导入；1784 行的 `gui.py` 拆分为 `theme / widgets / app / tabs` 五层。

---

## ⚙️ 环境要求

| 项目 | 要求 |
| --- | --- |
| Python | 3.9+（GUI 需 tkinter，python.org 官方安装包默认自带） |
| 核心依赖 | 仅标准库 |
| 可选 | Pillow（图片 EXIF 检测，缺失时自动降级） |
| 可选 | ADB Platform Tools（安卓功能，需 `adb.exe` 在 PATH 中） |

---

## 🚀 使用

### 图形界面

```bat
launcher.bat            :: 双击即可
python -m ordina gui    :: 或命令行启动
```

快捷键：`Ctrl+O` 打开目录 · `Ctrl+P` 预览 · `Ctrl+Enter` 执行 · `F5` 刷新 · `Ctrl+T` 切换主题 · `Ctrl+1~5` 切换标签页

### 命令行

```bash
# ── PC 端 ──
python -m ordina cli organize --path ~/Downloads                # 预览（默认 dry-run）
python -m ordina cli organize --path ~/Downloads --execute      # 实际执行
python -m ordina cli organize --path ~/Downloads --mode extension
python -m ordina cli organize --path ~/Downloads --template "{date}_{name}" \
                              --date-source modified --date-format "%Y-%m-%d"
python -m ordina cli rename  --path ~/Downloads --execute       # 仅重命名
python -m ordina cli analyze --path ~/Downloads --format markdown -o report.md
python -m ordina cli cleanup --path ~/Downloads --execute
python -m ordina cli diagnose --path ~/Downloads -o report.json
python -m ordina cli categories                                 # 查看 8 大分类
python -m ordina cli naming                                     # 查看命名规则与预设

# ── 安卓手机（USB 调试已开启）──
python -m ordina cli phone devices
python -m ordina cli phone organize --path /sdcard/Download --execute
python -m ordina cli phone backup --remote /sdcard/DCIM/Camera --local D:/backup --organize
```

> **安全设计**：`organize / cleanup / backup / rename` 默认预览（dry-run），加 `--execute` 才真正落盘。

---

## 🧩 技术要点

- **命名规则引擎化**：规则是数据（`NamingRules`），可被 CLI 参数、GUI 控件、JSON 文件三处驱动
- **主题注册表**：tk 原生控件登记到 `ThemeManager`，切换主题时整体重绘，解决旧版「只换一半」的问题
- **加权分类评分**：关键词 40% + 正则 25% + 扩展名 20% + 上下文 15%，同分按优先级裁决
- **双重查重**：先按大小分组，再算 MD5，兼顾速度与准确率
- **勾选即范围**：GUI 预览表的勾选状态会作为 `only_names` 传入整理引擎，旧版勾选是装饰性的
- **异步 ADB**：`adb_bridge` 使用 asyncio 封装，支持设备选择与错误重试
- **报告可追踪**：整理日志落盘 `目标目录/.ordina_logs/`

---

## ⚠️ 注意事项

1. **先预览再执行**：首次使用请确认 dry-run 结果符合预期。
2. **规则可调**：`config.py` 的关键词 / 正则 / 扩展名，以及 GUI「规则」页均可自定义并导入导出。
3. **安卓功能依赖 ADB**：Android 11+ 部分目录（如 `Android/data/`）受系统访问限制。
4. **备份操作安全**：手机 `backup` 只拉取到电脑，不会删除手机文件。
5. `launcher.exe` 是编译产物，可由 `launcher.bat` 用 Bat To Exe Converter 重新生成。

---

## 📦 版本历史

- **v3.0**（当前）：项目更名 Ordina / 归序；结构重构为 `core / ui / cli / android` 分包并去除 `sys.path` 黑魔法；GUI 拆分为主题层 + 组件层 + 标签页层；命名规则引擎重写（模板 / 日期来源 / Windows 安全清洗 / 语义化冲突 / 前缀宽度修复）；新增 `cli naming` 命令
- **v2.0**：8 大用途分类体系、GUI 多标签界面、安卓手机文件管理、CLI 全面命令化
- **v1.x**：基础扩展名分类整理 + 查重 + 清理
