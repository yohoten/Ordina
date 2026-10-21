"""
双模式文件分类系统
- ExtensionClassifier: 按扩展名分类（向后兼容）
- PurposeClassifier: 按用途分类（文章推荐）
"""

import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, List, Tuple

from .config import (
    DEFAULT_EXTENSION_CATEGORIES,
    PURPOSE_CATEGORIES,
    KEYWORD_DICTIONARY,
    CATEGORY_PREFIXES,
)


class BaseClassifier(ABC):
    """分类器基类"""

    @abstractmethod
    def classify(self, file_path: Path, **kwargs) -> str:
        """返回分类名称"""
        ...

    @abstractmethod
    def get_all_categories(self) -> List[str]:
        """返回所有分类名"""
        ...


class ExtensionClassifier(BaseClassifier):
    """基于文件扩展名的分类器（向后兼容）"""

    def __init__(self, custom_rules: Optional[Dict[str, List[str]]] = None):
        self.categories = custom_rules or DEFAULT_EXTENSION_CATEGORIES.copy()

    def classify(self, file_path: Path, **kwargs) -> str:
        ext = file_path.suffix.lower()
        for category, extensions in self.categories.items():
            if ext in extensions:
                return category
        return "其他"

    def get_all_categories(self) -> List[str]:
        return list(self.categories.keys())

    def add_extension(self, category: str, extension: str):
        """动态添加扩展名到分类"""
        if category not in self.categories:
            self.categories[category] = []
        ext = extension.lower()
        if not ext.startswith("."):
            ext = "." + ext
        if ext not in self.categories[category]:
            self.categories[category].append(ext)

    def to_dict(self) -> dict:
        return self.categories

    def update_from_dict(self, rules: dict):
        self.categories = rules


class PurposeClassifier(BaseClassifier):
    """
    按用途分类的文件分类器

    识别逻辑：
    1. 文件名关键词匹配（权重: 40%）
    2. 文件名正则模式匹配（权重: 25%）
    3. 扩展名匹配（权重: 20%）
    4. 上下文信息（来源、EXIF等）（权重: 15%）
    """

    # 分类优先级（按编号排列，编号小的优先）
    PRIORITY_ORDER = [
        "07_个人资料",   # 个人资料优先级最高（合同、身份证等关键词明确）
        "05_相册",       # 相册（相机文件名模式明确）
        "04_视频娱乐",   # 视频（文件名模式+SxxExx明确）
        "06_软件工具",   # 软件（扩展名明确）
        "01_工作目录",   # 工作
        "02_学习资料",   # 学习
        "03_参考资料",   # 参考
        "08_存档资料",   # 存档
    ]

    FALLBACK_CATEGORY = "03_参考资料"  # 无法识别时默认归入参考资料

    def __init__(self, custom_keywords: Optional[Dict[str, str]] = None):
        # 构建合并后的关键词索引（KEYWORD_DICTIONARY + PURPOSE_CATEGORIES 内的关键词）
        self.keywords = self._build_keyword_index(custom_keywords)
        # 预编译正则
        self._compiled_patterns: Dict[str, List[re.Pattern]] = {}
        for cat, config in PURPOSE_CATEGORIES.items():
            patterns = config.get("name_patterns", [])
            self._compiled_patterns[cat] = [re.compile(p, re.IGNORECASE) for p in patterns]

    @staticmethod
    def _build_keyword_index(custom_kw: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """构建合并关键词索引，PURPOSE_CATEGORIES 中的关键词优先级更高"""
        merged = {}

        # 先加入 KEYWORD_DICTIONARY（中文为主）
        for kw, cat in KEYWORD_DICTIONARY.items():
            merged[kw.lower()] = cat

        # PURPOSE_CATEGORIES 中的关键词覆盖（英文为主，优先级更高）
        for cat, config in PURPOSE_CATEGORIES.items():
            for kw in config.get("keywords", []):
                merged[kw.lower()] = cat

        # 用户自定义覆盖
        if custom_kw:
            for kw, cat in custom_kw.items():
                merged[kw.lower()] = cat

        return merged

    def classify(self, file_path: Path, **kwargs) -> str:
        """
        分类文件，返回用途分类名

        kwargs 可选:
            exif_info: dict - EXIF 信息 {"has_exif": bool, "camera_make": str, ...}
            source_info: str - 文件来源信息
            context: dict - 额外上下文
        """
        filename = file_path.name
        stem = file_path.stem  # 不含扩展名的文件名主干
        ext = file_path.suffix.lower()
        scores: Dict[str, float] = {}

        # 1. 关键词匹配（权重 40%）— 只匹配文件名主干，避免扩展名污染
        for keyword, category in self.keywords.items():
            kw_lower = keyword.lower()
            # 长度门槛：中文词信息密度高，2 字即足够（报告/合同/周报/发票…）；
            # 拉丁词至少 3 字符，否则容易出现 "os"、"in" 之类的误匹配。
            # 旧实现统一用 len < 3 过滤，导致全部双字中文关键词失效。
            if len(kw_lower) < (2 if self._has_cjk(kw_lower) else 3):
                continue
            if kw_lower in stem.lower():
                scores[category] = scores.get(category, 0) + 0.4
                break  # 命中即停：一个文件只取首个命中的关键词

        # 2. 正则模式匹配（权重 25%）
        for cat, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(filename):
                    scores[cat] = scores.get(cat, 0) + 0.25
                    break

        # 3. 扩展名匹配（权重 20%）
        for cat, config in PURPOSE_CATEGORIES.items():
            cat_exts = config.get("extensions", [])
            if cat_exts and ext in cat_exts:
                scores[cat] = scores.get(cat, 0) + 0.2

        # 4. 上下文信息（权重 15%）
        exif_info = kwargs.get("exif_info")
        if exif_info and exif_info.get("has_exif"):
            scores["05_相册"] = scores.get("05_相册", 0) + 0.15

        source_info = kwargs.get("source_info", "")
        if source_info:
            # 检测来源于工作相关网站
            if any(kw in source_info.lower() for kw in ["work", "company", "corp", "dingtalk", "feishu", "wework"]):
                scores["01_工作目录"] = scores.get("01_工作目录", 0) + 0.1

        # 5. 按优先级+得分选择最终分类
        best_category = self._select_best(scores, filename)

        return best_category

    @staticmethod
    def _has_cjk(text: str) -> bool:
        """判断是否包含中日韩统一表意文字（用于区分中英文关键词的长度门槛）"""
        return any("\u4e00" <= ch <= "\u9fff" for ch in text)

    def _select_best(self, scores: Dict[str, float], filename: str) -> str:
        """根据得分和优先级选择最佳分类"""
        if not scores:
            # 无法分类，尝试从文件名推断
            return self._guess_from_filename(filename)

        # 找到最高分
        max_score = max(scores.values())

        if max_score < 0.3:
            # 得分太低，尝试猜测
            return self._guess_from_filename(filename)

        # 同分时按优先级选择
        top_categories = [cat for cat, s in scores.items() if s >= max_score - 0.05]

        if len(top_categories) == 1:
            return top_categories[0]

        # 多个候选，取优先级最高的
        for priority_cat in self.PRIORITY_ORDER:
            if priority_cat in top_categories:
                return priority_cat

        return top_categories[0]

    def _guess_from_filename(self, filename: str) -> str:
        """从文件名猜测分类"""
        name_lower = filename.lower()

        # 检查相机文件名模式
        if re.match(r'^(IMG[_-]|VID[_-]|PANO[_-]|DSC|DSCN|SAM_|MOV_)', name_lower):
            return "05_相册"

        # .exe/.msi → 软件
        if name_lower.endswith(('.exe', '.msi', '.apk')):
            return "06_软件工具"

        # 视频扩展名 + 常见视频命名
        if re.search(r'(S\d{2}E\d{2}|第[一二三四五六七八九十\d]+[季集]|1080p|720p|bluray)', name_lower):
            return "04_视频娱乐"

        # 默认归入参考资料
        return self.FALLBACK_CATEGORY

    def get_all_categories(self) -> List[str]:
        return list(PURPOSE_CATEGORIES.keys())

    def get_category_info(self, category: str) -> Optional[dict]:
        """获取分类详细信息"""
        return PURPOSE_CATEGORIES.get(category)

    def get_prefix(self, category: str) -> str:
        """获取分类对应的数字前缀"""
        return CATEGORY_PREFIXES.get(category, "00_其他")

    def get_keywords_for_category(self, category: str) -> List[str]:
        """获取某个分类的所有关键词"""
        return [kw for kw, cat in self.keywords.items() if cat == category]

    def add_keyword(self, keyword: str, category: str):
        """添加自定义关键词映射"""
        self.keywords[keyword] = category

    def update_patterns(self, category: str, patterns: List[str]):
        """更新某分类的正则模式"""
        self._compiled_patterns[category] = [re.compile(p, re.IGNORECASE) for p in patterns]

    @staticmethod
    def list_categories_with_info() -> List[Tuple[str, str]]:
        """列出所有用途分类及其说明"""
        return [(cat, info["description"]) for cat, info in PURPOSE_CATEGORIES.items()]


def create_classifier(mode: str = "purpose", **kwargs):
    """
    工厂函数：创建分类器

    Args:
        mode: "extension" | "purpose"
        **kwargs: 传递给分类器构造函数的参数
          - extension 模式: custom_rules
          - purpose 模式: custom_keywords
    """
    if mode == "extension":
        return ExtensionClassifier(**kwargs)
    elif mode == "purpose":
        # PurposeClassifier 接受 custom_keywords 而非 custom_rules
        if "custom_rules" in kwargs:
            kwargs["custom_keywords"] = kwargs.pop("custom_rules")
        return PurposeClassifier(**kwargs)
    else:
        raise ValueError(f"未知分类模式: {mode}，可选: extension, purpose")
