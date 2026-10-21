"""
命名规则引擎 (Ordina / 归序)
=============================

把「文件该怎么起名」这件事收敛成一套可配置的规则，而不是散落在各处的字符串拼接。

规则维度:
    1. 命名模板     — {name} / {date} / {category} / {index}，自由组合
    2. 日期来源     — 文件名 > EXIF > 修改时间 > 创建时间 > 当前时间，可指定
    3. 安全清洗     — Windows 非法字符、保留设备名、结尾点/空格、超长名、全角字符
    4. 冲突消解     — 语义化的 _v2 / _v3（插在日期后缀之前），而非随机时间戳
    5. 数字前缀     — 目录固定排序，宽度一致（最小 2 位）

设计要点:
    - `NamingRules` 是纯数据类，可 JSON 序列化，GUI「规则」页与 CLI 共用
    - `NameNormalizer` 保持旧版公开 API，调用方（organizer / phone_organizer / cli）无需改动
    - 日期识别采用「数字边界 + 合法范围 + 合理年份」三重校验，避免把订单号、流水号误判成日期
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, asdict, replace
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .config import DATE_SUFFIX_FORMAT

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════

class DateSource:
    """日期来源"""

    AUTO = "auto"        # 文件名 → EXIF → 修改时间 → 创建时间 → 当前
    FILENAME = "filename"
    EXIF = "exif"
    MODIFIED = "modified"
    CREATED = "created"
    NOW = "now"

    CHOICES = (AUTO, FILENAME, EXIF, MODIFIED, CREATED, NOW)

    LABELS = {
        AUTO: "自动（文件名 > EXIF > 修改时间）",
        FILENAME: "仅文件名中的日期",
        EXIF: "照片 EXIF 拍摄时间",
        MODIFIED: "文件修改时间",
        CREATED: "文件创建时间",
        NOW: "当前日期",
    }


#: 命名模板预设（GUI / CLI 下拉用）
TEMPLATE_PRESETS: Dict[str, str] = {
    "{name}_{date}": "名称_日期（推荐）",
    "{date}_{name}": "日期_名称（按时间排序）",
    "{category}_{name}_{date}": "分类_名称_日期",
    "{name}_{date}_{category}": "名称_日期_分类",
    "{name}": "仅安全清洗，不加日期",
}

#: Windows 文件名非法字符
ILLEGAL_CHARS_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

#: Windows 保留设备名（不带扩展名时亦不可作为文件名）
RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

#: 文件名中的日期模式（带数字边界，避免误匹配流水号）
#: 每项为 (正则, 是否两位年)
_DATE_PATTERNS: Sequence[Tuple[re.Pattern, bool]] = (
    (re.compile(r"(?<!\d)(\d{4})[-_.](\d{1,2})[-_.](\d{1,2})(?!\d)"), False),
    (re.compile(r"(?<!\d)(\d{4})年(\d{1,2})月(\d{1,2})日"), False),
    (re.compile(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)"), False),
    (re.compile(r"(?<!\d)(\d{2})(\d{2})(\d{2})(?!\d)"), True),
)

_MIN_YEAR = 1970
_MAX_YEAR = 2099


# ═══════════════════════════════════════════════════════════════
# 规则数据类
# ═══════════════════════════════════════════════════════════════

@dataclass
class NamingRules:
    """命名规则配置（可 JSON 序列化）"""

    # ── 文件命名 ──
    file_template: str = "{name}_{date}"
    date_format: str = DATE_SUFFIX_FORMAT          # %Y%m%d / %Y-%m-%d / %Y%m
    date_source: str = DateSource.AUTO
    skip_if_has_date: bool = True                  # 已有日期则不再追加

    # ── 清洗 ──
    sanitize: bool = True
    normalize_unicode: bool = True                 # 全角 → 半角（NFKC）
    replace_illegal_with: str = "_"
    collapse_separators: bool = True
    lowercase_extension: bool = False
    max_name_length: int = 120                     # 不含扩展名的主干上限

    # ── 冲突 ──
    conflict_pattern: str = "_v{n}"                # _v2 / _v3 ...
    max_conflict_attempts: int = 999

    # ── 目录数字前缀 ──
    prefix_separator: str = "_"
    prefix_width: int = 2                          # 最小 2 位：01_ 而非 1_

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "NamingRules":
        """从字典构建，未知键忽略"""
        if not data:
            return cls()
        valid = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in valid})

    def summary(self) -> str:
        """人类可读的规则摘要（状态栏 / CLI 输出）"""
        return (
            f"模板 {self.file_template} | 日期 {self.date_format}"
            f"（{DateSource.LABELS.get(self.date_source, self.date_source)}）"
            f" | 前缀 {self.prefix_width} 位 + '{self.prefix_separator}'"
            f" | 冲突 {self.conflict_pattern}"
        )


# ═══════════════════════════════════════════════════════════════
# 规范化器
# ═══════════════════════════════════════════════════════════════

class NameNormalizer:
    """
    命名规范化器

    遵循「按用途分类」文件管理哲学：
        1. 文件按模板命名，默认 `名称_YYYYMMDD`
        2. 文件夹加数字前缀 `01_`、`02_` 固定排序
        3. 避免深层嵌套
    """

    def __init__(self,
                 prefix_separator: str = "_",
                 date_format: str = DATE_SUFFIX_FORMAT,
                 rules: Optional[NamingRules] = None):
        if rules is None:
            rules = NamingRules(
                prefix_separator=prefix_separator,
                date_format=date_format,
            )
        self.rules = rules

    # ── 兼容旧 API 的属性 ──────────────────────────────────────

    @property
    def prefix_separator(self) -> str:
        return self.rules.prefix_separator

    @property
    def date_format(self) -> str:
        return self.rules.date_format

    # ═══════════════════════════════════════════════════════
    # 安全清洗
    # ═══════════════════════════════════════════════════════

    def sanitize_component(self, text: str) -> str:
        """把任意文本清洗成合法的 Windows 文件名片段（不含分隔符）"""
        if not text:
            return ""

        rules = self.rules
        result = text

        # 1. Unicode 规范化：全角 → 半角
        if rules.normalize_unicode:
            result = unicodedata.normalize("NFKC", result)

        # 2. MSYS/Git Bash 会把 Windows 非法字符映射进私用区 U+F0xx，先还原再清洗
        if any("\ue000" <= ch <= "\uf0ff" for ch in result):
            result = "".join(chr(ord(ch) - 0xF000) if "\uf000" <= ch <= "\uf0ff" else ch
                             for ch in result)

        # 3. 非法字符替换
        if rules.sanitize:
            result = ILLEGAL_CHARS_PATTERN.sub(rules.replace_illegal_with, result)

        # 4. 连续空白压缩
        result = re.sub(r"\s+", " ", result).strip()

        # 5. 结尾的点与空格（Windows 会静默丢弃，必须显式剥离）
        result = result.rstrip(". ")

        # 6. 连续分隔符压缩 + 首尾剥离
        if rules.collapse_separators:
            result = re.sub(r"[_\-]{2,}", "_", result)
            result = result.strip("_- ")

        # 7. 保留设备名规避（CON / PRN / NUL / COM1 ...）
        if result.split(".")[0].upper() in RESERVED_NAMES:
            result = "_" + result

        # 8. 长度截断
        limit = max(16, rules.max_name_length)
        if len(result) > limit:
            result = result[:limit].rstrip("_- .")

        return result or "unnamed"

    def sanitize_filename(self, name: str) -> str:
        """清洗完整文件名（保留扩展名）"""
        path = Path(name)
        stem = self.sanitize_component(path.stem)
        ext = path.suffix
        if self.rules.lowercase_extension:
            ext = ext.lower()
        return f"{stem}{ext}"

    # ═══════════════════════════════════════════════════════
    # 日期提取
    # ═══════════════════════════════════════════════════════

    @staticmethod
    def _valid_date(year: int, month: int, day: int) -> Optional[datetime]:
        """范围校验：年 1970-2099，月 1-12，日必须真实存在"""
        if not (_MIN_YEAR <= year <= _MAX_YEAR):
            return None
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return None
        try:
            return datetime(year, month, day)
        except ValueError:
            return None

    def extract_date_from_filename(self, filename: str) -> Optional[datetime]:
        """
        从文件名中严格提取日期

        与旧版的区别：
            - 增加数字边界 `(?<!\\d)` / `(?!\\d)`，避免匹配订单号、流水号中的片段
            - 增加年/月/日范围校验，`20241345` 这类不可能的日期直接判否
            - 两位年（YYMMDD）按 2000+ 解释，同样做边界校验
        """
        for pattern, two_digit_year in _DATE_PATTERNS:
            for match in pattern.finditer(filename):
                try:
                    parts = [int(g) for g in match.groups()]
                except (TypeError, ValueError):
                    continue

                if two_digit_year:
                    year, month, day = 2000 + parts[0], parts[1], parts[2]
                else:
                    year, month, day = parts[0], parts[1], parts[2]

                parsed = self._valid_date(year, month, day)
                if parsed:
                    return parsed
        return None

    def has_date_in_name(self, filename: str) -> bool:
        """文件名中是否已含日期"""
        return self.extract_date_from_filename(Path(filename).stem) is not None

    @staticmethod
    def _date_from_exif(file_path: Path) -> Optional[datetime]:
        """EXIF 拍摄时间（Pillow 缺失或读取失败时静默降级）"""
        try:
            from .recognizer import SmartRecognizer
            exif = SmartRecognizer().detect_exif(file_path)
            value = exif.get("date_taken") if isinstance(exif, dict) else None
            if isinstance(value, datetime):
                return value
        except Exception:
            pass
        return None

    def extract_date_from_file(self,
                               file_path: Path,
                               source: Optional[str] = None) -> Optional[datetime]:
        """
        提取文件的最佳日期

        auto 优先级: 文件名日期 > EXIF > 修改时间 > 创建时间 > 当前时间
        """
        source = source or self.rules.date_source

        if source == DateSource.FILENAME:
            return self.extract_date_from_filename(file_path.stem)
        if source == DateSource.EXIF:
            return self._date_from_exif(file_path)
        if source == DateSource.MODIFIED:
            return self._stat_date(file_path, "st_mtime")
        if source == DateSource.CREATED:
            return self._stat_date(file_path, "st_ctime")
        if source == DateSource.NOW:
            return datetime.now()

        return (
            self.extract_date_from_filename(file_path.stem)
            or self._date_from_exif(file_path)
            or self._stat_date(file_path, "st_mtime")
            or self._stat_date(file_path, "st_ctime")
            or datetime.now()
        )

    @staticmethod
    def _stat_date(file_path: Path, attr: str) -> Optional[datetime]:
        try:
            return datetime.fromtimestamp(getattr(file_path.stat(), attr))
        except (OSError, ValueError, OverflowError):
            return None

    # ═══════════════════════════════════════════════════════
    # 模板渲染
    # ═══════════════════════════════════════════════════════

    @staticmethod
    def _clean_rendered(text: str) -> str:
        """渲染后清理：空占位留下的悬空分隔符"""
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"([_\-])\s*([_\-])", r"\1", text)
        text = re.sub(r"[_\-]{2,}", "_", text)
        return text.strip("_- .")

    def render(self, template: str, values: Dict[str, str]) -> str:
        """渲染命名模板，未提供 / 未知的占位符会被移除"""
        rendered = template
        for key, value in values.items():
            rendered = rendered.replace("{" + key + "}", value or "")
        rendered = re.sub(r"\{(\w+)\}", "", rendered)
        return self._clean_rendered(rendered)

    def build_name(self,
                   stem: str,
                   ext: str = "",
                   date: Optional[datetime] = None,
                   category: Optional[str] = None,
                   index: Optional[int] = None) -> str:
        """按模板生成完整文件名"""
        date_str = date.strftime(self.rules.date_format) if date else ""
        rendered = self.render(self.rules.file_template, {
            "name": self.sanitize_component(stem),
            "date": date_str,
            "category": self.sanitize_component(category) if category else "",
            "index": f"{index:02d}" if index is not None else "",
        })
        rendered = self.sanitize_component(rendered) or "unnamed"
        suffix = ext.lower() if self.rules.lowercase_extension else ext
        return f"{rendered}{suffix}"

    # ═══════════════════════════════════════════════════════
    # 日期后缀
    # ═══════════════════════════════════════════════════════

    def add_date_suffix(self, file_path: Path,
                        date: Optional[datetime] = None,
                        category: Optional[str] = None) -> str:
        """
        按模板生成新文件名（默认 `名称_YYYYMMDD.ext`）

        Example:
            "报告.pdf"            → "报告_20220523.pdf"
            "报告_20220501.pdf"   → "报告_20220501.pdf"（已有日期，不重复添加）
            "订单20240512001.pdf" → 数字超长不判为日期，按修改时间正常追加
        """
        stem = file_path.stem
        ext = file_path.suffix

        if self.rules.skip_if_has_date and self.has_date_in_name(stem):
            # 已有日期：仅做安全清洗，不重复追加
            return self.build_name(stem, ext, date=None, category=category)

        if date is None:
            date = self.extract_date_from_file(file_path)

        return self.build_name(stem, ext, date=date, category=category)

    def should_add_date_suffix(self, file_path: Path) -> bool:
        """判断是否需要按模板改写文件名"""
        if "{date}" not in self.rules.file_template:
            return False
        if self.rules.skip_if_has_date and self.has_date_in_name(file_path.stem):
            return False
        return True

    # ═══════════════════════════════════════════════════════
    # 数字前缀（文件夹）
    # ═══════════════════════════════════════════════════════

    def add_number_prefix(self, name: str, number: int, total: int = 8) -> str:
        """
        给文件夹名添加数字前缀

        修复旧版 bug：宽度不再取 `len(str(total))`（total=8 时为 1，会产出 `1_工作目录`），
        改为 `max(prefix_width, len(str(total)))`，保证 `01_工作目录` 且同批宽度一致。

        Example:
            add_number_prefix("工作目录", 1, 8) → "01_工作目录"
        """
        width = max(int(self.rules.prefix_width), len(str(max(total, 1))))
        prefix = f"{number:0{width}d}{self.rules.prefix_separator}"
        return f"{prefix}{name}"

    @staticmethod
    def remove_number_prefix(name: str) -> str:
        """移除数字前缀"""
        match = re.match(r"^\d+[_\-\s.]?(.+)", name)
        return match.group(1) if match else name

    @staticmethod
    def has_number_prefix(name: str) -> bool:
        """检查是否已有数字前缀"""
        return bool(re.match(r"^\d+[_\-\s.]", name))

    @staticmethod
    def strip_prefix(name: str) -> str:
        """去除已有的数字前缀（分类目录名 → 纯分类名）"""
        return re.sub(r"^\d{2,}[_\-\s.]", "", name)

    # ═══════════════════════════════════════════════════════
    # 冲突消解
    # ═══════════════════════════════════════════════════════

    def resolve_conflict(self, target_path: Path) -> Path:
        """
        目标已存在时的语义化重命名：`_v2` / `_v3` ...

        冲突标记插在日期后缀之前，读起来是「第 2 版的 20240512」，
        而不是旧版那种 `名称_20251021_143207` 的时间戳噪音。
        """
        if not target_path.exists():
            return target_path

        parent = target_path.parent
        stem = target_path.stem
        ext = target_path.suffix

        # 若主干尾部是日期 token，把冲突标记插到日期之前
        date_token = ""
        match = re.search(r"[_\-](?:\d{4}[-_.]?\d{2}[-_.]?\d{2}|\d{6,8})$", stem)
        if match:
            date_token = match.group(0)
            stem = stem[: match.start()]

        for n in range(2, self.rules.max_conflict_attempts + 2):
            marker = self.rules.conflict_pattern.format(n=n)
            candidate = parent / f"{stem}{marker}{date_token}{ext}"
            if not candidate.exists():
                return candidate

        # 兜底：时间戳
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return parent / f"{stem}_{stamp}{date_token}{ext}"

    # ═══════════════════════════════════════════════════════
    # 批量重命名
    # ═══════════════════════════════════════════════════════

    def preview_rename(self,
                       file_paths: List[Path],
                       add_date: bool = True,
                       date: Optional[datetime] = None,
                       category: Optional[str] = None) -> List[Tuple[Path, str]]:
        """预览重命名结果（不实际执行）"""
        preview: List[Tuple[Path, str]] = []
        for fp in file_paths:
            if not fp.is_file():
                continue
            if add_date and self.should_add_date_suffix(fp):
                preview.append((fp, self.add_date_suffix(fp, date, category=category)))
        return preview

    def execute_rename(self,
                       file_paths: List[Path],
                       add_date: bool = True,
                       date: Optional[datetime] = None,
                       dry_run: bool = True,
                       category: Optional[str] = None) -> List[Tuple[Path, Path]]:
        """执行重命名，返回 [(原路径, 新路径), ...]"""
        results: List[Tuple[Path, Path]] = []
        for fp in file_paths:
            if not fp.is_file() or not fp.exists():
                continue

            if add_date and self.should_add_date_suffix(fp):
                new_name = self.add_date_suffix(fp, date, category=category)
            else:
                new_name = self.sanitize_filename(fp.name)

            new_path = self.resolve_conflict(fp.parent / new_name)
            if new_path == fp:
                continue

            if not dry_run:
                try:
                    fp.rename(new_path)
                    logger.info("重命名: %s → %s", fp.name, new_path.name)
                    results.append((fp, new_path))
                except OSError as exc:
                    logger.error("重命名失败: %s - %s", fp.name, exc)
            else:
                results.append((fp, new_path))

        return results

    # ═══════════════════════════════════════════════════════
    # 诊断
    # ═══════════════════════════════════════════════════════

    def diagnose(self, directory: Path) -> Dict[str, List[Path]]:
        """
        诊断目录命名规范问题

        Returns:
            needs_date_suffix / needs_prefix / has_duplicate_names /
            too_deep_nested / irregular_names
        """
        diagnosis: Dict[str, List[Path]] = {
            "needs_date_suffix": [],
            "needs_prefix": [],
            "has_duplicate_names": [],
            "too_deep_nested": [],
            "irregular_names": [],
        }

        try:
            all_items = list(directory.rglob("*"))
        except OSError:
            return diagnosis

        name_map: Dict[str, List[Path]] = {}

        for item in all_items:
            if item.is_file():
                depth = len(item.relative_to(directory).parts)
                if depth > 3:
                    diagnosis["too_deep_nested"].append(item)

                if self.should_add_date_suffix(item):
                    diagnosis["needs_date_suffix"].append(item)

                # 命名是否合规（非法字符 / 全角 / 结尾点空格 / 超长）
                if self.sanitize_filename(item.name) != item.name:
                    diagnosis["irregular_names"].append(item)

                name_map.setdefault(item.name, []).append(item)

            elif item.is_dir():
                if not self.has_number_prefix(item.name):
                    diagnosis["needs_prefix"].append(item)

        for paths in name_map.values():
            if len(paths) > 1:
                diagnosis["has_duplicate_names"].extend(paths)

        return diagnosis

    # ═══════════════════════════════════════════════════════
    # 目录前缀批处理
    # ═══════════════════════════════════════════════════════

    def add_prefixes_to_folders(self,
                                directory: Path,
                                prefix_map: Dict[str, int],
                                dry_run: bool = True) -> List[Tuple[Path, Path]]:
        """给文件夹批量添加数字前缀（宽度按总数统一）"""
        results: List[Tuple[Path, Path]] = []
        total = max(prefix_map.values()) if prefix_map else 0

        for item in sorted(directory.iterdir()):
            if not item.is_dir():
                continue
            if item.name in prefix_map and not self.has_number_prefix(item.name):
                new_name = self.add_number_prefix(item.name, prefix_map[item.name], total)
                new_path = item.parent / new_name

                if not dry_run:
                    try:
                        item.rename(new_path)
                        logger.info("文件夹前缀: %s → %s", item.name, new_name)
                        results.append((item, new_path))
                    except OSError as exc:
                        logger.error("重命名失败: %s - %s", item.name, exc)
                else:
                    results.append((item, new_path))

        return results

    def with_rules(self, **overrides) -> "NameNormalizer":
        """返回套用了新规则的规范化器副本"""
        return NameNormalizer(rules=replace(self.rules, **overrides))
