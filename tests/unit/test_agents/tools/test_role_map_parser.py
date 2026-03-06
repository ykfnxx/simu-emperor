"""Tests for RoleMapParser"""

import pytest
from pathlib import Path
from simu_emperor.agents.tools.role_map_parser import RoleMapParser


@pytest.fixture
def temp_role_map(tmp_path):
    """创建临时 role_map.md 文件"""
    content = """
## 户部尚书 (revenue_minister)
- 姓名：张廷玉
- 职责：管理国家财政、税收

## 直隶巡抚 (zhili_governor)
- 姓名：李卫
- 职责：管理直隶省政务
"""
    role_map_path = tmp_path / "role_map.md"
    role_map_path.write_text(content, encoding="utf-8")
    return tmp_path


@pytest.fixture
def parser(temp_role_map):
    """创建 RoleMapParser 实例"""
    return RoleMapParser(temp_role_map)


def test_parse_returns_all_agents(parser):
    """测试解析返回所有官员"""
    agents = parser.parse()
    assert len(agents) == 2
    assert agents[0]["agent_id"] == "revenue_minister"
    assert agents[1]["agent_id"] == "zhili_governor"


def test_get_agent_by_id(parser):
    """测试通过 ID 获取官员"""
    agent = parser.get_agent("revenue_minister")
    assert agent is not None
    assert agent["name"] == "张廷玉"
    assert agent["title"] == "户部尚书"
    assert agent["duty"] == "管理国家财政、税收"


def test_get_agent_returns_none_for_unknown_id(parser):
    """测试查询不存在的官员返回 None"""
    agent = parser.get_agent("unknown_agent")
    assert agent is None


def test_cache_mechanism(parser, temp_role_map):
    """测试缓存机制"""
    # 第一次解析
    agents1 = parser.parse()
    assert len(agents1) == 2

    # 修改文件
    role_map_path = temp_role_map / "role_map.md"
    role_map_path.write_text("## 新官 (new_agent)\n- 姓名：新人\n", encoding="utf-8")

    # 第二次解析（应该使用缓存）
    agents2 = parser.parse()
    assert len(agents2) == 2  # 仍然是2个，因为使用了缓存

    # 清除缓存后再次解析
    parser.clear_cache()
    agents3 = parser.parse()
    assert len(agents3) == 1  # 现在只有1个新官



def test_parse_handles_empty_file(tmp_path):
    """测试处理空文件的情况"""
    empty_file = tmp_path / "role_map.md"
    empty_file.write_text("", encoding="utf-8")

    parser = RoleMapParser(tmp_path)
    agents = parser.parse()
    assert agents == []


def test_parse_handles_malformed_markdown(tmp_path):
    """测试处理缺少agent_id的格式"""
    malformed_content = """
## 不完整的官员信息
- 姓名：只有姓名
"""
    malformed_file = tmp_path / "role_map.md"
    malformed_file.write_text(malformed_content, encoding="utf-8")

    parser = RoleMapParser(tmp_path)
    agents = parser.parse()
    # 没有agent_id的section不会被添加到结果中
    assert len(agents) == 0
