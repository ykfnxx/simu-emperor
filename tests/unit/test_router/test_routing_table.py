"""
RoutingTable测试 - V5 Router Process

测试 register/unregister/get/has/list_all/clear 方法
"""

import pytest
from simu_emperor.router.routing_table import RoutingTable


class TestRoutingTableInit:
    """RoutingTable初始化测试"""

    def test_init_empty(self):
        """初始化后应为空表"""
        table = RoutingTable()
        assert table.list_all() == []
        assert len(table.list_all()) == 0


class TestRoutingTableRegister:
    """RoutingTable.register()测试"""

    def test_register_single_agent(self):
        """注册单个agent"""
        table = RoutingTable()
        identity = b"worker_identity_001"

        table.register("agent:governor", identity)

        assert table.has("agent:governor")
        assert table.get("agent:governor") == identity

    def test_register_multiple_agents(self):
        """注册多个agent"""
        table = RoutingTable()
        identity1 = b"worker_001"
        identity2 = b"worker_002"
        identity3 = b"worker_003"

        table.register("agent:governor", identity1)
        table.register("agent:minister", identity2)
        table.register("engine:*", identity3)

        assert table.has("agent:governor")
        assert table.has("agent:minister")
        assert table.has("engine:*")
        assert len(table.list_all()) == 3

    def test_register_overwrites_existing(self):
        """注册已存在的agent_id会覆盖"""
        table = RoutingTable()
        old_identity = b"old_identity"
        new_identity = b"new_identity"

        table.register("agent:governor", old_identity)
        table.register("agent:governor", new_identity)

        assert table.get("agent:governor") == new_identity
        assert len(table.list_all()) == 1

    def test_register_empty_agent_id(self):
        """可以注册空字符串agent_id"""
        table = RoutingTable()
        identity = b"worker"

        table.register("", identity)

        assert table.has("")
        assert table.get("") == identity

    def test_register_empty_identity(self):
        """可以注册空identity"""
        table = RoutingTable()

        table.register("agent:test", b"")

        assert table.has("agent:test")
        assert table.get("agent:test") == b""


class TestRoutingTableUnregister:
    """RoutingTable.unregister()测试"""

    def test_unregister_existing_agent(self):
        """注销已注册的agent"""
        table = RoutingTable()
        table.register("agent:governor", b"identity")

        table.unregister("agent:governor")

        assert not table.has("agent:governor")
        assert table.get("agent:governor") is None

    def test_unregister_non_existent_agent(self):
        """注销不存在的agent不会报错"""
        table = RoutingTable()

        # Should not raise
        table.unregister("agent:nonexistent")

        assert len(table.list_all()) == 0

    def test_unregister_from_multiple(self):
        """从多个agent中注销一个"""
        table = RoutingTable()
        table.register("agent:governor", b"id1")
        table.register("agent:minister", b"id2")
        table.register("engine:*", b"id3")

        table.unregister("agent:minister")

        assert table.has("agent:governor")
        assert not table.has("agent:minister")
        assert table.has("engine:*")
        assert len(table.list_all()) == 2


class TestRoutingTableGet:
    """RoutingTable.get()测试"""

    def test_get_existing_agent(self):
        """获取已注册agent的identity"""
        table = RoutingTable()
        identity = b"worker_identity"

        table.register("agent:governor", identity)

        assert table.get("agent:governor") == identity

    def test_get_non_existent_agent(self):
        """获取不存在的agent返回None"""
        table = RoutingTable()

        assert table.get("agent:nonexistent") is None

    def test_get_returns_copy_or_reference(self):
        """get返回的是引用，不是副本"""
        table = RoutingTable()
        identity = b"identity"

        table.register("agent:test", identity)

        # Same object reference
        assert table.get("agent:test") is identity


class TestRoutingTableHas:
    """RoutingTable.has()测试"""

    def test_has_existing_agent(self):
        """检查已注册agent存在"""
        table = RoutingTable()
        table.register("agent:governor", b"identity")

        assert table.has("agent:governor") is True

    def test_has_non_existent_agent(self):
        """检查不存在的agent"""
        table = RoutingTable()

        assert table.has("agent:nonexistent") is False

    def test_has_after_unregister(self):
        """注销后has返回False"""
        table = RoutingTable()
        table.register("agent:test", b"id")
        table.unregister("agent:test")

        assert table.has("agent:test") is False

    def test_has_after_clear(self):
        """clear后has返回False"""
        table = RoutingTable()
        table.register("agent:test", b"id")

        table.clear()

        assert table.has("agent:test") is False


class TestRoutingTableListAll:
    """RoutingTable.list_all()测试"""

    def test_list_all_empty(self):
        """空表返回空列表"""
        table = RoutingTable()

        assert table.list_all() == []

    def test_list_all_single_agent(self):
        """单个agent返回单元素列表"""
        table = RoutingTable()
        table.register("agent:governor", b"id")

        result = table.list_all()

        assert result == ["agent:governor"]

    def test_list_all_multiple_agents(self):
        """多个agent返回所有ID"""
        table = RoutingTable()
        table.register("agent:governor", b"id1")
        table.register("agent:minister", b"id2")
        table.register("engine:*", b"id3")

        result = table.list_all()

        assert len(result) == 3
        assert "agent:governor" in result
        assert "agent:minister" in result
        assert "engine:*" in result

    def test_list_all_returns_copy(self):
        """list_all返回副本，修改不影响内部状态"""
        table = RoutingTable()
        table.register("agent:test", b"id")

        result = table.list_all()
        result.append("fake_agent")

        assert "fake_agent" not in table.list_all()


class TestRoutingTableClear:
    """RoutingTable.clear()测试"""

    def test_clear_empty_table(self):
        """清空空表无副作用"""
        table = RoutingTable()

        table.clear()

        assert table.list_all() == []

    def test_clear_with_agents(self):
        """清空有agent的表"""
        table = RoutingTable()
        table.register("agent:governor", b"id1")
        table.register("agent:minister", b"id2")
        table.register("engine:*", b"id3")

        table.clear()

        assert table.list_all() == []
        assert not table.has("agent:governor")
        assert not table.has("agent:minister")
        assert not table.has("engine:*")

    def test_clear_idempotent(self):
        """多次clear是幂等的"""
        table = RoutingTable()
        table.register("agent:test", b"id")

        table.clear()
        table.clear()

        assert table.list_all() == []


class TestRoutingTableEdgeCases:
    """RoutingTable边界条件测试"""

    def test_unicode_agent_id(self):
        """Unicode agent_id支持"""
        table = RoutingTable()

        table.register("agent:总督", b"identity")

        assert table.has("agent:总督")
        assert table.get("agent:总督") == b"identity"

    def test_large_identity(self):
        """大identity支持"""
        table = RoutingTable()
        large_identity = b"x" * 10000

        table.register("agent:test", large_identity)

        assert table.get("agent:test") == large_identity

    def test_many_agents(self):
        """大量agent注册"""
        table = RoutingTable()

        for i in range(1000):
            table.register(f"agent:{i}", f"id_{i}".encode())

        assert len(table.list_all()) == 1000
        assert table.has("agent:0")
        assert table.has("agent:999")
