"""
检测器模块初始化
"""
from .system import SystemDetector
from .domain import DomainManager
from .panel import PanelDetector

__all__ = ['SystemDetector', 'DomainManager', 'PanelDetector']
