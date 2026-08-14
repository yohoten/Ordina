"""
下载文件夹整理工具 v2.0
=======================
融合知乎文章《如何高效整理和分类电脑上的文件》的文件管理哲学：
- 按用途分类（非仅扩展名）
- 数字前缀固定排序
- 日期后缀追溯版本
- 扁平结构减少嵌套
- 8大分类覆盖全盘
"""

import os
import sys

__version__ = "2.0.0"
__author__ = "Proma Agent"

# 确保当前目录在 Python 路径中
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from organizer import FileOrganizer
from classifiers import ExtensionClassifier, PurposeClassifier
from recognizer import SmartRecognizer
from normalizer import NameNormalizer
from archiver import ArchiveManager
from reporter import Reporter
from config import (
    DEFAULT_EXTENSION_CATEGORIES,
    PURPOSE_CATEGORIES,
    KEYWORD_DICTIONARY,
    CATEGORY_PREFIXES,
    TEMP_FILE_EXTENSIONS,
)
