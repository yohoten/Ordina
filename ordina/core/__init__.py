"""
核心引擎包 (Ordina / 归序)
=========================

模块职责:
    config.py      全局配置与默认规则（分类体系 / 关键词 / 阈值）
    classifiers.py 双模式分类器（扩展名 / 用途）
    recognizer.py  智能识别（魔数 / EXIF / 下载来源）
    naming.py      命名规则引擎（模板 / 日期 / 清洗 / 冲突）
    archiver.py    归档与清理（时效 / 大文件 / 空目录 / 临时文件）
    reporter.py    报告生成（JSON / CSV / Markdown）
    organizer.py   整理主引擎，串联以上能力
"""

from .config import (
    DEFAULT_EXTENSION_CATEGORIES,
    ANDROID_EXTENSION_CATEGORIES,
    PURPOSE_CATEGORIES,
    KEYWORD_DICTIONARY,
    CATEGORY_PREFIXES,
    TEMP_FILE_EXTENSIONS,
    TEMP_FILE_PATTERNS,
    ARCHIVE_DAYS_THRESHOLD,
    LARGE_FILE_SIZE_MB,
    DATE_SUFFIX_FORMAT,
)
from .classifiers import (
    BaseClassifier,
    ExtensionClassifier,
    PurposeClassifier,
    create_classifier,
)
from .recognizer import SmartRecognizer
from .naming import (
    NameNormalizer,
    NamingRules,
    DateSource,
    TEMPLATE_PRESETS,
)
from .archiver import ArchiveManager
from .reporter import Reporter
from .organizer import FileOrganizer

__all__ = [
    "DEFAULT_EXTENSION_CATEGORIES",
    "ANDROID_EXTENSION_CATEGORIES",
    "PURPOSE_CATEGORIES",
    "KEYWORD_DICTIONARY",
    "CATEGORY_PREFIXES",
    "TEMP_FILE_EXTENSIONS",
    "TEMP_FILE_PATTERNS",
    "ARCHIVE_DAYS_THRESHOLD",
    "LARGE_FILE_SIZE_MB",
    "DATE_SUFFIX_FORMAT",
    "BaseClassifier",
    "ExtensionClassifier",
    "PurposeClassifier",
    "create_classifier",
    "SmartRecognizer",
    "NameNormalizer",
    "NamingRules",
    "DateSource",
    "TEMPLATE_PRESETS",
    "ArchiveManager",
    "Reporter",
    "FileOrganizer",
]
