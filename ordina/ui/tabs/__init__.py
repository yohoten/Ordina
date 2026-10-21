"""标签页集合"""

from .base import BaseTab
from .organize import OrganizeTab
from .duplicate import DuplicateTab
from .analyze import AnalyzeTab
from .rules import RulesTab
from .logs import LogsTab

TAB_CLASSES = (
    OrganizeTab,
    DuplicateTab,
    AnalyzeTab,
    RulesTab,
    LogsTab,
)

__all__ = [
    "BaseTab",
    "OrganizeTab",
    "DuplicateTab",
    "AnalyzeTab",
    "RulesTab",
    "LogsTab",
    "TAB_CLASSES",
]
