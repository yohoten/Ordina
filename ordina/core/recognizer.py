"""
智能文件识别引擎
- 关键词词典匹配
- EXIF 检测（区分手机照片 vs 网图）
- Windows Zone.Identifier 读取
- 文件内容类型检测（magic bytes）
- 置信度评分系统
"""

import re
import struct
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# ── 文件类型魔数签名 ──────────────────────────────────────────
MAGIC_SIGNATURES = {
    # (offset, bytes) → 类型描述
    (0, b'\xff\xd8\xff'): ("JPEG 图片", "图片"),
    (0, b'\x89PNG\r\n\x1a\n'): ("PNG 图片", "图片"),
    (0, b'GIF87a'): ("GIF87 图片", "图片"),
    (0, b'GIF89a'): ("GIF89 图片", "图片"),
    (0, b'RIFF'): ("RIFF 容器（可能为 WEBP/AVI/WAV）", "未知"),
    (0, b'BM'): ("BMP 图片", "图片"),
    (0, b'%PDF'): ("PDF 文档", "文档"),
    (0, b'PK\x03\x04'): ("ZIP/DOCX/XLSX/PPTX 压缩文档", "文档"),
    (0, b'\xd0\xcf\x11\xe0'): ("OLE2 文档 (旧 Office 格式)", "文档"),
    (0, b'\x1f\x8b\x08'): ("GZip 压缩文件", "压缩包"),
    (0, b'\x42\x5a\x68'): ("BZip2 压缩文件", "压缩包"),
    (0, b'Rar!\x1a\x07'): ("RAR 压缩文件 (v1.5+)", "压缩包"),
    (0, b'Rar!\x1a\x07\x01\x00'): ("RAR 压缩文件 (v5.0+)", "压缩包"),
    (0, b'7z\xbc\xaf\x27\x1c'): ("7-Zip 压缩文件", "压缩包"),
    (0, b'MZ'): ("PE 可执行文件 (EXE/DLL)", "安装包"),
    (0, b'\x00\x00\x01\xba'): ("MPEG 视频", "视频"),
    (0, b'\x00\x00\x01\xb3'): ("MPEG 视频", "视频"),
    (0, b'\x1a\x45\xdf\xa3'): ("MKV/WebM 容器", "视频"),
    (0, b'ID3'): ("MP3 音频 (ID3v2)", "音频"),
    (0, b'\xff\xfb'): ("MP3 音频", "音频"),
    (0, b'\xff\xf3'): ("MP3 音频", "音频"),
    (0, b'fLaC'): ("FLAC 无损音频", "音频"),
    (0, b'OggS'): ("OGG 音频/视频", "音频"),
    (0, b'\x00\x00\x01\x00'): ("ICO 图标", "图片"),
    (4, b'ftyp'): ("MP4/M4A/M4V 媒体", "视频"),
    (8, b'WEBP'): ("WEBP 图片", "图片"),
}


class SmartRecognizer:
    """
    智能文件识别器

    综合多种信号判断文件真实类型和用途
    """

    def __init__(self):
        self._pil_available = self._check_pillow()

    @staticmethod
    def _check_pillow() -> bool:
        """检测 Pillow 库是否可用"""
        try:
            import PIL.Image  # noqa: F401
            return True
        except ImportError:
            return False

    # ── 内容类型检测 ──────────────────────────────────────────

    def detect_by_magic(self, file_path: Path) -> Optional[Tuple[str, str]]:
        """
        通过文件头部魔数检测类型

        Returns:
            (类型描述, 大类) 或 None
        """
        try:
            with open(file_path, 'rb') as f:
                header = f.read(16)
        except (OSError, PermissionError) as e:
            logger.warning(f"无法读取文件头部: {file_path} - {e}")
            return None

        for (offset, magic), (desc, category) in MAGIC_SIGNATURES.items():
            if len(header) >= offset + len(magic):
                if header[offset:offset + len(magic)] == magic:
                    return (desc, category)

        # 纯文本检测
        if self._looks_like_text(header):
            return ("纯文本文件", "文档")

        return None

    @staticmethod
    def _looks_like_text(data: bytes) -> bool:
        """快速判断是否为文本文件"""
        try:
            data.decode('utf-8')
            return True
        except UnicodeDecodeError:
            pass
        try:
            data.decode('ascii')
            # ASCII 成功，且不是全零
            if data.strip(b'\x00').strip():
                return True
        except UnicodeDecodeError:
            pass
        return False

    # ── EXIF 检测 ──────────────────────────────────────────────

    def detect_exif(self, file_path: Path) -> Dict[str, Any]:
        """
        检测图片 EXIF 信息

        Returns:
            {
                "has_exif": bool,
                "camera_make": str | None,
                "camera_model": str | None,
                "date_taken": datetime | None,
                "is_screenshot": bool,
                "software": str | None,
            }
        """
        result = {
            "has_exif": False,
            "camera_make": None,
            "camera_model": None,
            "date_taken": None,
            "is_screenshot": False,
            "software": None,
        }

        ext = file_path.suffix.lower()
        # 常见图片扩展名
        image_exts = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.webp', '.heic'}
        if ext not in image_exts:
            return result

        if not self._pil_available:
            return result

        try:
            from PIL import Image
            from PIL.ExifTags import TAGS

            img = Image.open(file_path)
            exif_data = img._getexif()

            if exif_data:
                result["has_exif"] = True
                for tag_id, value in exif_data.items():
                    tag_name = TAGS.get(tag_id, tag_id)
                    if tag_name == "Make":
                        result["camera_make"] = str(value).strip('\x00')
                    elif tag_name == "Model":
                        result["camera_model"] = str(value).strip('\x00')
                    elif tag_name == "DateTimeOriginal":
                        try:
                            result["date_taken"] = datetime.strptime(
                                str(value), "%Y:%m:%d %H:%M:%S"
                            )
                        except ValueError:
                            pass
                    elif tag_name == "Software":
                        sw = str(value).strip('\x00')
                        result["software"] = sw
                        # 截图软件检测
                        screenshot_keywords = ["screenshot", "screen", "capture", "snip"]
                        if any(kw in sw.lower() for kw in screenshot_keywords):
                            result["is_screenshot"] = True
        except Exception as e:
            logger.debug(f"EXIF 读取失败: {file_path} - {e}")

        return result

    # ── Windows Zone.Identifier 读取 ────────────────────────────

    def detect_download_source(self, file_path: Path) -> Optional[str]:
        """
        读取 Windows Zone.Identifier 流（下载来源标记）

        Returns:
            来源 URL 或 None
        """
        zone_path = Path(str(file_path) + ":Zone.Identifier")
        try:
            if zone_path.exists():
                content = zone_path.read_text(encoding='utf-8', errors='ignore')
                # 解析 ReferrerUrl / HostUrl
                for line in content.split('\n'):
                    if line.startswith('ReferrerUrl='):
                        return line.split('=', 1)[1].strip()
                    if line.startswith('HostUrl='):
                        return line.split('=', 1)[1].strip()
        except (OSError, PermissionError, UnicodeDecodeError):
            pass
        return None

    # ── 文件来源推测 ──────────────────────────────────────────

    def detect_origin(self, file_path: Path) -> str:
        """
        推测文件来源

        Returns:
            "camera" | "download" | "created" | "unknown"
        """
        filename = file_path.name.lower()

        # 相机文件名模式
        if re.match(r'^(img_|vid_|pano_|dsc|dscn|sam_|mov_|p\d{5,})', filename):
            return "camera"

        # 下载文件特征
        if re.search(r'(download|下载|\bcopy\b|\(\d+\)\.)', filename):
            return "download"

        # Zone.Identifier 检查
        source = self.detect_download_source(file_path)
        if source:
            return "download"

        # EXIF 检测
        exif = self.detect_exif(file_path)
        if exif["has_exif"] and exif["camera_make"]:
            return "camera"

        return "unknown"

    # ── 综合识别 ──────────────────────────────────────────────

    def recognize(self, file_path: Path) -> Dict[str, Any]:
        """
        综合识别文件信息

        Returns:
            {
                "filename": str,
                "extension": str,
                "size_bytes": int,
                "magic_type": (desc, category) | None,
                "exif": dict,
                "origin": str,
                "download_source": str | None,
                "is_temp_file": bool,
                "suggested_action": str,  # "keep" | "archive" | "clean" | "review"
            }
        """
        result = {
            "filename": file_path.name,
            "extension": file_path.suffix.lower(),
            "size_bytes": 0,
            "magic_type": None,
            "exif": {},
            "origin": "unknown",
            "download_source": None,
            "is_temp_file": False,
            "suggested_action": "keep",
        }

        # 文件大小
        try:
            result["size_bytes"] = file_path.stat().st_size
        except OSError:
            pass

        # 魔数检测
        result["magic_type"] = self.detect_by_magic(file_path)

        # EXIF（仅图片）
        result["exif"] = self.detect_exif(file_path)

        # 下载来源
        result["download_source"] = self.detect_download_source(file_path)

        # 来源推测
        result["origin"] = self.detect_origin(file_path)

        # 临时文件检测
        result["is_temp_file"] = self._is_temp_file(file_path)

        # 建议操作
        result["suggested_action"] = self._suggest_action(file_path, result)

        return result

    @staticmethod
    def _is_temp_file(file_path: Path) -> bool:
        """检测是否为临时文件"""
        name = file_path.name
        ext = file_path.suffix.lower()

        temp_exts = {'.tmp', '.temp', '.crdownload', '.part', '.partial'}
        if ext in temp_exts:
            return True

        # Office 临时文件 (~$xxx.docx)
        if name.startswith('~$'):
            return True

        # 备份文件
        if ext in {'.bak', '.old'} or name.endswith('~'):
            return True

        return False

    @staticmethod
    def _suggest_action(file_path: Path, info: Dict[str, Any]) -> str:
        """建议操作"""
        if info["is_temp_file"]:
            return "clean"

        # 大文件建议审查
        if info["size_bytes"] > 100 * 1024 * 1024:  # >100MB
            return "review"

        # 检查最后访问时间
        try:
            stat = file_path.stat()
            age_days = (datetime.now() - datetime.fromtimestamp(stat.st_atime)).days
            if age_days > 90:
                return "archive"
        except OSError:
            pass

        return "keep"

    # ── 批量识别 ──────────────────────────────────────────────

    def recognize_batch(self, file_paths: list) -> Dict[str, Dict[str, Any]]:
        """批量识别多个文件"""
        results = {}
        for fp in file_paths:
            results[str(fp)] = self.recognize(fp)
        return results

    # ── 文件大小可读化 ─────────────────────────────────────────

    @staticmethod
    def format_size(size_bytes: int) -> str:
        """将字节数格式化为人类可读的字符串"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"
