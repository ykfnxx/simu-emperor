"""Skill 加载器"""

import logging
from collections import OrderedDict
from pathlib import Path

from simu_emperor.agents.skills.models import Skill
from simu_emperor.agents.skills.parser import SkillParser
from simu_emperor.agents.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)


class SkillLoader:
    """Skill 加载器 - 三级缓存

    三级缓存架构：
    - L1: 内存缓存（LRU）
    - L2: mtime 缓存（用于快速判断文件是否变化）
    - L3: 文件系统（通过 SkillParser 加载）

    Attributes:
        skill_dirs: Skill 文件搜索目录列表
        enable_hot_reload: 是否启用热重载（mtime 检测）
        cache_size: LRU 缓存大小
        registry: Skill 注册表实例
    """

    def __init__(
        self,
        skill_dirs: list[Path] | None = None,
        enable_hot_reload: bool = True,
        cache_size: int = 50,
    ):
        """初始化 SkillLoader

        Args:
            skill_dirs: Skill 文件搜索目录列表，默认为 [Path("data/skills")]
            enable_hot_reload: 是否启用热重载（检测文件 mtime 变化）
            cache_size: LRU 缓存大小，默认为 50
        """
        self.skill_dirs = skill_dirs or [Path("data/skills")]
        self.enable_hot_reload = enable_hot_reload

        # L1: 内存缓存（LRU）
        self._memory_cache: OrderedDict[str, Skill] = OrderedDict()
        self._cache_size = cache_size

        # L2: mtime 缓存（用于快速判断文件是否变化）
        self._mtime_cache: dict[str, float] = {}

        # 解析器和注册表
        self._parser = SkillParser()
        self.registry = SkillRegistry()

    def load(self, skill_name: str) -> Skill | None:
        """加载 Skill（三级缓存）

        Args:
            skill_name: Skill 名称（不含 .md 扩展名）

        Returns:
            Skill 对象，如果加载失败则返回 None
        """
        # L1: 检查内存缓存
        if skill_name in self._memory_cache:
            # 如果启用热重载，需要检查文件是否变化
            if self.enable_hot_reload:
                skill_path = self._find_skill_path(skill_name)
                if skill_path:
                    current_mtime = skill_path.stat().st_mtime
                    cached_mtime = self._mtime_cache.get(skill_name)
                    # 如果 mtime 变化，需要重新加载
                    if cached_mtime is None or current_mtime != cached_mtime:
                        logger.debug(f"SkillLoader: 检测到 {skill_name} 文件变化，重新加载")
                        # 继续到下面的文件加载逻辑
                    else:
                        # mtime 未变化，返回缓存
                        self._memory_cache.move_to_end(skill_name)
                        logger.debug(f"SkillLoader: 缓存命中 {skill_name} (mtime 未变化)")
                        return self._memory_cache[skill_name]
                else:
                    # 文件不存在，返回缓存
                    self._memory_cache.move_to_end(skill_name)
                    logger.debug(f"SkillLoader: 缓存命中 {skill_name} (文件不存在)")
                    return self._memory_cache[skill_name]
            else:
                # 未启用热重载，直接返回缓存
                self._memory_cache.move_to_end(skill_name)
                logger.debug(f"SkillLoader: 缓存命中 {skill_name}")
                return self._memory_cache[skill_name]

        # 查找 Skill 文件路径
        skill_path = self._find_skill_path(skill_name)
        if not skill_path:
            logger.warning(f"SkillLoader: 未找到 Skill 文件 {skill_name}")
            return None

        # L2: 检查 mtime（如果启用热重载）
        current_mtime = skill_path.stat().st_mtime
        if self.enable_hot_reload:
            # 如果启用热重载，检查 mtime 是否变化
            cached_mtime = self._mtime_cache.get(skill_name)
            if cached_mtime is not None and current_mtime == cached_mtime:
                # mtime 未变化，使用内存缓存（如果存在）
                if skill_name in self._memory_cache:
                    self._memory_cache.move_to_end(skill_name)
                    return self._memory_cache[skill_name]

        # L3: 从文件加载
        try:
            skill = self._parser.parse_file(skill_path)
            self._update_cache(skill_name, skill, current_mtime)
            self.registry.register_skill(skill)
            logger.info(f"SkillLoader: 成功加载 {skill_name} from {skill_path}")
            return skill
        except Exception as e:
            logger.warning(f"SkillLoader: Skill {skill_name} 加载失败: {e}")
            # 如果加载失败，返回缓存中的旧版本（如果有）
            return self._memory_cache.get(skill_name)

    def _find_skill_path(self, skill_name: str) -> Path | None:
        """遍历 skill_dirs 查找 Skill 文件

        Args:
            skill_name: Skill 名称（不含 .md 扩展名）

        Returns:
            Skill 文件路径，如果未找到则返回 None
        """
        for skill_dir in self.skill_dirs:
            skill_path = skill_dir / f"{skill_name}.md"
            if skill_path.exists():
                return skill_path
        return None

    def _update_cache(self, name: str, skill: Skill, mtime: float):
        """更新缓存（LRU 淘汰机制）

        Args:
            name: Skill 名称
            skill: Skill 对象
            mtime: 文件修改时间
        """
        # LRU 淘汰：如果缓存已满，移除最久未使用的项
        if len(self._memory_cache) >= self._cache_size:
            oldest_name, _ = self._memory_cache.popitem(last=False)
            self._mtime_cache.pop(oldest_name, None)
            logger.debug(f"SkillLoader: LRU 淘汰 {oldest_name}")

        # 添加新项到缓存末尾
        self._memory_cache[name] = skill
        self._memory_cache.move_to_end(name)
        self._mtime_cache[name] = mtime

    def clear_cache(self):
        """清空所有缓存"""
        self._memory_cache.clear()
        self._mtime_cache.clear()
        logger.debug("SkillLoader: 缓存已清空")

    def get_cache_size(self) -> int:
        """获取当前缓存大小

        Returns:
            当前缓存中的 Skill 数量
        """
        return len(self._memory_cache)

    def is_cached(self, skill_name: str) -> bool:
        """检查 Skill 是否在缓存中

        Args:
            skill_name: Skill 名称

        Returns:
            如果 Skill 在缓存中返回 True，否则返回 False
        """
        return skill_name in self._memory_cache
