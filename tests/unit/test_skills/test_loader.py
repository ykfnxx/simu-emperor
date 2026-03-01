"""SkillLoader 单元测试"""

import time
from pathlib import Path

from simu_emperor.agents.skills.loader import SkillLoader


class TestSkillLoader:
    """SkillLoader 测试类"""

    def test_load_skill_file_not_found(self, tmp_path: Path):
        """测试加载不存在的 Skill 文件"""
        loader = SkillLoader(skill_dirs=[tmp_path])

        skill = loader.load("nonexistent_skill")

        assert skill is None

    def test_load_skill_success(self, tmp_path: Path):
        """测试成功加载 Skill 文件"""
        # 创建测试 Skill 文件
        skill_file = tmp_path / "test_skill.md"
        skill_file.write_text(
            """---
name: test_skill
description: Test skill
version: 1.0.0
---

This is a test skill content."""
        )

        loader = SkillLoader(skill_dirs=[tmp_path])
        skill = loader.load("test_skill")

        assert skill is not None
        assert skill.metadata.name == "test_skill"
        assert skill.metadata.description == "Test skill"
        assert "This is a test skill content" in skill.content

    def test_load_skill_cached(self, tmp_path: Path):
        """测试内存缓存命中（LRU 缓存）"""
        # 创建测试 Skill 文件
        skill_file = tmp_path / "cached_skill.md"
        skill_file.write_text(
            """---
name: cached_skill
description: Cached skill
version: 1.0.0
---

Cached skill content."""
        )

        loader = SkillLoader(skill_dirs=[tmp_path])

        # 第一次加载
        skill1 = loader.load("cached_skill")
        assert skill1 is not None

        # 第二次加载应该从缓存返回（同一个对象）
        skill2 = loader.load("cached_skill")
        assert skill2 is not None
        assert skill1 is skill2  # 同一个对象实例

    def test_load_skill_cache_lru(self, tmp_path: Path):
        """测试 LRU 缓存淘汰机制"""
        # 创建测试 Skill 文件
        for i in range(3):
            skill_file = tmp_path / f"skill_{i}.md"
            skill_file.write_text(
                f"""---
name: skill_{i}
description: Skill {i}
version: 1.0.0
---

Content for skill {i}."""
            )

        # 创建缓存大小为 2 的 loader
        loader = SkillLoader(skill_dirs=[tmp_path], cache_size=2)

        # 加载 3 个 Skill（超过缓存大小）
        skill_0 = loader.load("skill_0")
        skill_1 = loader.load("skill_1")
        skill_2 = loader.load("skill_2")

        assert skill_0 is not None
        assert skill_1 is not None
        assert skill_2 is not None

        # skill_0 应该被淘汰（LRU）
        # 验证缓存大小
        assert len(loader._memory_cache) == 2
        assert "skill_0" not in loader._memory_cache
        assert "skill_1" in loader._memory_cache
        assert "skill_2" in loader._memory_cache

    def test_find_skill_path(self, tmp_path: Path):
        """测试遍历 skill_dirs 查找 Skill 文件"""
        # 创建多个 skill 目录
        skill_dir1 = tmp_path / "skills1"
        skill_dir2 = tmp_path / "skills2"
        skill_dir1.mkdir()
        skill_dir2.mkdir()

        # 在第二个目录创建 Skill 文件
        skill_file = skill_dir2 / "found_skill.md"
        skill_file.write_text(
            """---
name: found_skill
description: Found in second dir
version: 1.0.0
---

Content."""
        )

        loader = SkillLoader(skill_dirs=[skill_dir1, skill_dir2])

        # 应该在第二个目录找到
        skill_path = loader._find_skill_path("found_skill")

        assert skill_path is not None
        assert skill_path == skill_file

    def test_find_skill_path_not_found(self, tmp_path: Path):
        """测试查找不存在的 Skill 文件"""
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()

        loader = SkillLoader(skill_dirs=[skill_dir])

        skill_path = loader._find_skill_path("nonexistent")

        assert skill_path is None

    def test_mtime_check(self, tmp_path: Path):
        """测试 mtime 变化时重新加载"""
        # 创建测试 Skill 文件
        skill_file = tmp_path / "mtime_skill.md"
        skill_file.write_text(
            """---
name: mtime_skill
description: Mtime test skill
version: 1.0.0
---

Original content."""
        )

        loader = SkillLoader(skill_dirs=[tmp_path], enable_hot_reload=True)

        # 第一次加载
        skill1 = loader.load("mtime_skill")
        assert skill1 is not None
        assert "Original content" in skill1.content

        # 等待以确保 mtime 变化
        time.sleep(0.01)

        # 修改文件内容
        skill_file.write_text(
            """---
name: mtime_skill
description: Mtime test skill
version: 1.0.0
---

Updated content."""
        )

        # 第二次加载应该获取新内容（mtime 变化）
        skill2 = loader.load("mtime_skill")
        assert skill2 is not None
        assert "Updated content" in skill2.content

    def test_load_skill_registers_to_registry(self, tmp_path: Path):
        """测试加载 Skill 后自动注册到 registry"""
        skill_file = tmp_path / "registry_skill.md"
        skill_file.write_text(
            """---
name: registry_skill
description: Registry test skill
version: 1.0.0
---

Content."""
        )

        loader = SkillLoader(skill_dirs=[tmp_path])

        # 加载 Skill
        skill = loader.load("registry_skill")
        assert skill is not None

        # 验证已注册到 registry
        assert loader.registry.has_skill("registry_skill")
        registered_skill = loader.registry.get_skill("registry_skill")
        assert registered_skill is skill

    def test_load_multiple_skill_dirs(self, tmp_path: Path):
        """测试从多个目录加载 Skill"""
        # 创建两个 skill 目录
        skill_dir1 = tmp_path / "skills1"
        skill_dir2 = tmp_path / "skills2"
        skill_dir1.mkdir()
        skill_dir2.mkdir()

        # 在两个目录分别创建 Skill
        (skill_dir1 / "skill_from_dir1.md").write_text(
            """---
name: skill_from_dir1
description: From dir 1
version: 1.0.0
---

Content from dir 1."""
        )

        (skill_dir2 / "skill_from_dir2.md").write_text(
            """---
name: skill_from_dir2
description: From dir 2
version: 1.0.0
---

Content from dir 2."""
        )

        loader = SkillLoader(skill_dirs=[skill_dir1, skill_dir2])

        # 应该能从两个目录加载
        skill1 = loader.load("skill_from_dir1")
        skill2 = loader.load("skill_from_dir2")

        assert skill1 is not None
        assert skill1.metadata.name == "skill_from_dir1"
        assert skill2 is not None
        assert skill2.metadata.name == "skill_from_dir2"

    def test_cache_move_to_end_on_access(self, tmp_path: Path):
        """测试访问缓存项时更新 LRU 顺序"""
        skill_file = tmp_path / "lru_skill.md"
        skill_file.write_text(
            """---
name: lru_skill
description: LRU test skill
version: 1.0.0
---

Content."""
        )

        loader = SkillLoader(skill_dirs=[tmp_path], cache_size=2)

        # 加载同一个 skill 多次
        loader.load("lru_skill")
        loader.load("lru_skill")

        # 验证缓存中只有一个项，且在末尾
        assert len(loader._memory_cache) == 1
        assert list(loader._memory_cache.keys()) == ["lru_skill"]
