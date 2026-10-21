"""
Ordina / 归序 — 按用途分类的双端文件整理工具
=============================================

融合知乎文章《如何高效整理和分类电脑上的文件》的管理理念：
- 按用途分类（而非仅扩展名）
- 数字前缀固定排序
- 日期后缀追溯版本
- 扁平结构减少嵌套
- 8 大分类覆盖全盘

版本: 3.0（结构重构 + 命名规则引擎 + GUI 组件化）
"""

__version__ = "3.0.0"
__app_name__ = "Ordina"
__app_name_cn__ = "归序"
__author__ = "yohoten"

from .core import (
    # 配置
    DEFAULT_EXTENSION_CATEGORIES,
    PURPOSE_CATEGORIES,
    KEYWORD_DICTIONARY,
    CATEGORY_PREFIXES,
    TEMP_FILE_EXTENSIONS,
    DATE_SUFFIX_FORMAT,
    # 分类 / 识别
    BaseClassifier,
    ExtensionClassifier,
    PurposeClassifier,
    create_classifier,
    SmartRecognizer,
    # 命名
    NameNormalizer,
    NamingRules,
    DateSource,
    TEMPLATE_PRESETS,
    # 归档 / 报告 / 整理
    ArchiveManager,
    Reporter,
    FileOrganizer,
)

__all__ = [
    "__version__",
    "__app_name__",
    "__app_name_cn__",
    "DEFAULT_EXTENSION_CATEGORIES",
    "PURPOSE_CATEGORIES",
    "KEYWORD_DICTIONARY",
    "CATEGORY_PREFIXES",
    "TEMP_FILE_EXTENSIONS",
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
