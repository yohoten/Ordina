"""
安卓手机文件配置规则
====================
定义手机上的常见目录、文件类型规则、厂商/机型路径差异等。

此配置与现有 config.py 互补，专注手机文件特有的规则。

核心数据结构:
- PHONE_DIRECTORIES: 手机常见系统目录映射
- APP_CATEGORIES: 按 App 来源分类的文件规则
- PHONE_FILE_PATTERNS: 手机产生文件的命名模式
- VENDOR_PATHS: 不同厂商的路径差异
"""

import re
from typing import Dict, List, Optional

# ============================================================
# 手机常见系统目录
# ============================================================
PHONE_DIRECTORIES = {
    "下载目录": {
        "paths": [
            "/sdcard/Download",
            "/storage/emulated/0/Download",
            "/sdcard/download",
        ],
        "description": "浏览器/系统默认下载目录",
        "scan_depth": 1,  # 不递归子目录
    },
    "相册": {
        "paths": [
            "/sdcard/DCIM/Camera",
            "/sdcard/DCIM",
            "/sdcard/Pictures",
            "/sdcard/相册",
            "/storage/emulated/0/DCIM",
        ],
        "description": "手机拍照和录制的照片/视频",
        "scan_depth": 2,
    },
    "截图": {
        "paths": [
            "/sdcard/Pictures/Screenshots",
            "/sdcard/截图",
            "/sdcard/DCIM/Screenshots",
            "/storage/emulated/0/Pictures/Screenshots",
        ],
        "description": "屏幕截图和录屏",
        "scan_depth": 1,
    },
    "微信文件": {
        "paths": [
            "/sdcard/tencent/MicroMsg/Download",
            "/sdcard/Android/data/com.tencent.mm/files/Download",
            "/storage/emulated/0/tencent/MicroMsg/Download",
        ],
        "description": "微信接收的文件（文档、图片、视频等）",
        "scan_depth": 2,
        "note": "部分 Android 11+ 路径被限制访问",
    },
    "微信图片": {
        "paths": [
            "/sdcard/tencent/MicroMsg/WeiXin",
            "/sdcard/Pictures/WeiXin",
            "/storage/emulated/0/tencent/MicroMsg/WeiXin",
        ],
        "description": "微信聊天图片缓存",
        "scan_depth": 3,
    },
    "QQ文件": {
        "paths": [
            "/sdcard/tencent/QQfile_recv",
            "/sdcard/tencent/QQ_images",
            "/storage/emulated/0/tencent/QQfile_recv",
        ],
        "description": "QQ 接收的文件",
        "scan_depth": 2,
    },
    "钉钉文件": {
        "paths": [
            "/sdcard/DingTalk",
            "/storage/emulated/0/DingTalk",
            "/sdcard/Android/data/com.alibaba.android.rimet/files",
        ],
        "description": "钉钉接收的文件",
        "scan_depth": 2,
    },
    "蓝牙接收": {
        "paths": [
            "/sdcard/Bluetooth",
            "/storage/emulated/0/Bluetooth",
        ],
        "description": "通过蓝牙接收的文件",
        "scan_depth": 1,
    },
    "屏幕录制": {
        "paths": [
            "/sdcard/Movies/ScreenRecorder",
            "/sdcard/DCIM/ScreenRecorder",
            "/sdcard/屏幕录制",
            "/storage/emulated/0/Movies/ScreenRecorder",
        ],
        "description": "屏幕录制视频",
        "scan_depth": 1,
    },
    "音乐": {
        "paths": [
            "/sdcard/Music",
            "/sdcard/音乐",
            "/sdcard/MIUI/Music",
            "/storage/emulated/0/Music",
        ],
        "description": "音乐/音频文件",
        "scan_depth": 2,
    },
    "应用安装包": {
        "paths": [
            "/sdcard/Download",
            "/sdcard/备份",
            "/sdcard/Android/apk",
        ],
        "description": "APK/XAPK 安装包",
        "scan_depth": 2,
    },
    "备份文件": {
        "paths": [
            "/sdcard/备份",
            "/sdcard/Backup",
            "/sdcard/TitaniumBackup",
            "/storage/emulated/0/Backup",
        ],
        "description": "手机备份文件",
        "scan_depth": 3,
    },
    "MIUI 特殊": {
        "paths": [
            "/sdcard/MIUI",
            "/sdcard/MIUI/sound_recorder",
            "/sdcard/MIUI/Gallery",
        ],
        "description": "小米 MIUI 系统目录",
        "scan_depth": 2,
        "note": "仅小米手机适用",
    },
    "华为特殊": {
        "paths": [
            "/sdcard/Huawei",
            "/sdcard/Huawei/MagazineUnlock",
        ],
        "description": "华为系统目录",
        "scan_depth": 2,
        "note": "仅华为/荣耀手机适用",
    },
    "OPPO 特殊": {
        "paths": [
            "/sdcard/oppo",
            "/sdcard/Android/data/com.oppo*",
        ],
        "description": "OPPO 系统目录",
        "scan_depth": 2,
        "note": "仅 OPPO/一加手机适用",
    },
}

# ============================================================
# 按 App 来源分类
# ============================================================
APP_CATEGORIES = {
    "微信": {
        "keywords": ["wx_camera", "mmexport", "wxin", "MicroMsg", "WeiXin"],
        "patterns": [
            r"wx_camera_\d+",          # 微信拍摄
            r"mmexport\d+",             # 微信导出的图片
            r"Screenshot_\d+_com\.tencent\.mm",  # 微信截图
        ],
        "priority": 90,
    },
    "QQ": {
        "keywords": ["QQfile_recv", "QQ_images", "mobileQQ"],
        "patterns": [
            r"QQ_\d+",                 # QQ 图片
            r"IMG_\d+_com\.tencent\.mobileqq",
        ],
        "priority": 85,
    },
    "钉钉": {
        "keywords": ["DingTalk", "alibaba"],
        "patterns": [
            r"dt_\d+",                 # 钉钉文件
        ],
        "priority": 80,
    },
    "浏览器下载": {
        "keywords": [],
        "patterns": [
            r".*下载.*",
            r"download.*",
        ],
        "priority": 50,
    },
    "相机拍摄": {
        "keywords": [],
        "patterns": [
            r"IMG_\d{8}_\d{6}",        # 标准相机命名
            r"IMG-\d{8}-WA\d{4}",      # WhatsApp 图片
            r"VID_\d{8}_\d{6}",        # 视频
            r"PANO_\d{8}_\d{6}",       # 全景
            r"P\d{7}",                  # 某些相机的命名
        ],
        "priority": 95,
    },
    "截图": {
        "keywords": ["Screenshots", "截图"],
        "patterns": [
            r"Screenshot_\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}",  # 标准截图
            r"Screenshot_\d{14}",       # 数字时间戳
            r"IMG_\d{8}_\d{6}.*HDR",   # HDR 截图
        ],
        "priority": 80,
    },
    "屏幕录制": {
        "keywords": ["ScreenRecorder", "recording"],
        "patterns": [
            r"screen_recording_\d+",    # 屏幕录制
            r"recording_\d+",
            r"SCR_\d+",
        ],
        "priority": 75,
    },
}

# ============================================================
# 手机文件命名模式（用途分类规则）
# ============================================================
PHONE_FILE_PATTERNS = {
    "手机照片": {
        "patterns": [
            r"^(IMG|VID|PANO)[_-]\d{8}[_-]\d{6}",  # IMG_20240115_103020
            r"^P\d{7,}\.",                           # P20240115.jpg
            r"^DSC[F\d]{4,}\.",                      # DSCF1234.JPG
            r"^DSCN\d+\.",
            r"^SAM_\d+\.",
            r"^\d{8}[_-]",
        ],
        "description": "手机相机直接拍摄的照片",
        "target_category": "05_相册",
    },
    "微信/QQ图片": {
        "patterns": [
            r"^wx_camera_\d+",
            r"^mmexport\d+",
            r"^QQ_\d+",
            r"^IMG_\d+_com\.",
        ],
        "description": "微信/QQ 保存的图片",
        "target_category": "05_相册",
    },
    "截图图片": {
        "patterns": [
            r"^Screenshot",
            r"^Screenshot_\d{14}",
            r"^screen_capture",
        ],
        "description": "手机截图",
        "target_category": "05_相册",
    },
    "手机视频": {
        "patterns": [
            r"^VID[_-]\d{8}[_-]\d{6}",  # VID_20240115_103020
            r"^screen_recording",
            r"^SCR_\d+",
        ],
        "description": "手机拍摄/录制的视频",
        "target_category": "04_视频娱乐",
    },
    "APK安装包": {
        "patterns": [],
        "extensions": [".apk", ".xapk", ".apks"],
        "description": "Android 应用安装包",
        "target_category": "06_软件工具",
    },
    "微信文档": {
        "patterns": [],
        "keywords": ["微信", "WeiXin", "wxin"],
        "description": "微信传输的文档文件",
        "target_category": "03_参考资料",
    },
}

# ============================================================
# 厂商路径映射（不同品牌的差异化路径）
# ============================================================
VENDOR_PATHS = {
    "Xiaomi": {
        "keywords": ["Xiaomi", "Redmi", "MIUI", "POCO"],
        "paths": {
            "录音": "/sdcard/MIUI/sound_recorder",
            "音乐": "/sdcard/MIUI/Music",
            "截图": "/sdcard/DCIM/Screenshots",
            "相册": "/sdcard/DCIM/Camera",
            "主题": "/sdcard/MIUI/theme",
        },
    },
    "Huawei": {
        "keywords": ["HUAWEI", "Honor", "EMUI", "HarmonyOS"],
        "paths": {
            "截图": "/sdcard/Pictures/Screenshots",
            "相册": "/sdcard/DCIM/Camera",
            "锁屏杂志": "/sdcard/Huawei/MagazineUnlock",
        },
    },
    "Samsung": {
        "keywords": ["SAMSUNG", "SM-", "OneUI"],
        "paths": {
            "截图": "/sdcard/DCIM/Screenshots",
            "相册": "/sdcard/DCIM/Camera",
            "通话录音": "/sdcard/Call",
            "笔记": "/sdcard/Samsung Notes",
        },
    },
    "OPPO": {
        "keywords": ["OPPO", "OnePlus", "Realme", "ColorOS"],
        "paths": {
            "截图": "/sdcard/DCIM/Screenshots",
            "相册": "/sdcard/DCIM/Camera",
        },
    },
    "vivo": {
        "keywords": ["vivo", "iQOO", "Funtouch", "OriginOS"],
        "paths": {
            "截图": "/sdcard/Pictures/Screenshots",
            "相册": "/sdcard/DCIM/Camera",
        },
    },
}

# ============================================================
# 应关注的手机文件类型（用于快速扫描推荐）
# ============================================================
PHONE_SCAN_RECOMMENDATIONS = {
    "大文件清理": {
        "description": "占用空间较大的文件，建议审查",
        "min_size_mb": 50,
        "extensions": [".mp4", ".mov", ".zip", ".rar", ".7z", ".iso"],
        "icon": "💾",
    },
    "临时文件清理": {
        "description": "App 缓存和临时文件",
        "patterns": [
            r".*cache.*",
            r".*temp.*",
            r".*tmp.*",
            r".*\.thumbnails.*",
        ],
        "icon": "🗑️",
    },
    "重复照片": {
        "description": "可能存在重复的图片文件",
        "extensions": [".jpg", ".jpeg", ".png", ".gif"],
        "min_count": 2,
        "icon": "🖼️",
    },
    "已安装APK": {
        "description": "已安装应用的安装包，可删除",
        "extensions": [".apk", ".xapk"],
        "icon": "📦",
    },
    "过时备份": {
        "description": "30天前的备份文件",
        "min_age_days": 30,
        "patterns": [
            r".*backup.*",
            r".*备份.*",
            r".*\.bak",
        ],
        "icon": "📋",
    },
}

# ============================================================
# 常用文件大小阈值（Android 系统参考值）
# ============================================================
PHONE_SIZE_THRESHOLDS = {
    "tiny": 10 * 1024,              # < 10KB: 小文件
    "small": 100 * 1024,            # < 100KB: 配置文件/图标
    "medium": 5 * 1024 * 1024,      # < 5MB: 普通文档/图片
    "large": 50 * 1024 * 1024,      # < 50MB: 视频/压缩包
    "huge": 200 * 1024 * 1024,      # < 200MB: 高清视频/大型应用
    "max_recommend": 1024 * 1024 * 1024,  # > 1GB: 建议立即处理
}

# ============================================================
# 手机文件安全删除列表（已知可安全清理的路径）
# ============================================================
SAFE_CLEANUP_PATHS = [
    "/sdcard/Android/data/*/cache",
    "/sdcard/Android/obb/*",        # 注意: 游戏数据包，谨慎
    "/sdcard/DCIM/.thumbnails",
    "/sdcard/Pictures/.thumbnails",
    "/sdcard/tencent/*/Cache",
    "/sdcard/backups/app_backup",
]

# ============================================================
# 工具函数
# ============================================================


def get_recommended_directories() -> Dict[str, Dict]:
    """
    获取推荐扫描的手机目录（排除厂商特定目录）

    Returns:
        通用推荐目录字典
    """
    return {
        name: info
        for name, info in PHONE_DIRECTORIES.items()
        if "note" not in info or "仅" not in info.get("note", "")
    }


def get_directory_by_category(category: str) -> List[str]:
    """
    根据分类名称获取对应的手机目录路径列表

    Args:
        category: 分类名（如 "下载目录", "相册", "微信文件"）

    Returns:
        路径列表
    """
    for name, info in PHONE_DIRECTORIES.items():
        if name == category:
            return info["paths"]
    return []


def get_app_category(filename: str) -> Optional[str]:
    """
    根据文件名判断来自哪个 App

    Args:
        filename: 文件名

    Returns:
        App 分类名或 None
    """
    for app_name, rules in APP_CATEGORIES.items():
        # 关键词匹配
        for kw in rules.get("keywords", []):
            if kw.lower() in filename.lower():
                return app_name

        # 正则模式匹配
        for pattern in rules.get("patterns", []):
            if re.search(pattern, filename, re.IGNORECASE):
                return app_name

    return None


def match_phone_pattern(filename: str) -> Optional[str]:
    """
    匹配手机文件命名模式，返回建议的用途分类

    Args:
        filename: 文件名

    Returns:
        匹配的分类名 (如 "05_相册") 或 None
    """
    for category, rules in PHONE_FILE_PATTERNS.items():
        # 扩展名匹配
        ext = PathSuffix(filename).lower()
        for file_ext in rules.get("extensions", []):
            if ext == file_ext:
                return rules.get("target_category")

        # 正则模式匹配
        for pattern in rules.get("patterns", []):
            if re.search(pattern, filename, re.IGNORECASE):
                return rules.get("target_category")

        # 关键词匹配
        for kw in rules.get("keywords", []):
            if kw.lower() in filename.lower():
                return rules.get("target_category")

    return None


def get_vendor_paths(model_name: str) -> Dict[str, str]:
    """
    根据设备型号获取厂商特定路径

    Args:
        model_name: 设备型号字符串

    Returns:
        路径字典 {目录名: 路径}
    """
    for vendor, info in VENDOR_PATHS.items():
        for keyword in info.get("keywords", []):
            if keyword.lower() in model_name.lower():
                return info.get("paths", {})
    return {}


def classify_phone_size(size_bytes: int) -> str:
    """
    根据手机文件大小分类

    Args:
        size_bytes: 文件大小(bytes)

    Returns:
        大小类别: "tiny" | "small" | "medium" | "large" | "huge" | "max"
    """
    if size_bytes < PHONE_SIZE_THRESHOLDS["tiny"]:
        return "tiny"
    elif size_bytes < PHONE_SIZE_THRESHOLDS["small"]:
        return "small"
    elif size_bytes < PHONE_SIZE_THRESHOLDS["medium"]:
        return "medium"
    elif size_bytes < PHONE_SIZE_THRESHOLDS["large"]:
        return "large"
    elif size_bytes < PHONE_SIZE_THRESHOLDS["huge"]:
        return "huge"
    else:
        return "max"


class PathSuffix:
    """兼容 Path().suffix 的静态方法"""
    import os as _os

    @staticmethod
    def lower(path: str) -> str:
        import os
        _, ext = os.path.splitext(path)
        return ext.lower()

    @staticmethod
    def name(path: str) -> str:
        import os
        return os.path.basename(path)
