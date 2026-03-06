"""Tests for FileOperationsHelper"""

import json
import pytest
from pathlib import Path

from simu_emperor.common import FileOperationsHelper, JSONParseError, FileOperationError


@pytest.mark.asyncio
async def test_read_write_json_file(tmp_path):
    """测试JSON文件读写"""
    test_file = tmp_path / "test.json"
    data = {"key": "value", "number": 42}

    # 写入
    await FileOperationsHelper.write_json_file(test_file, data)
    assert test_file.exists()

    # 读取
    result = await FileOperationsHelper.read_json_file(test_file)
    assert result == data


@pytest.mark.asyncio
async def test_read_json_file_handles_empty(tmp_path):
    """测试读取空JSON文件"""
    test_file = tmp_path / "empty.json"
    test_file.write_text("", encoding="utf-8")

    result = await FileOperationsHelper.read_json_file(test_file)
    assert result == {}


@pytest.mark.asyncio
async def test_read_json_file_handles_invalid(tmp_path):
    """测试读取无效JSON文件"""
    test_file = tmp_path / "invalid.json"
    test_file.write_text("{invalid json}", encoding="utf-8")

    result = await FileOperationsHelper.read_json_file(test_file)
    assert result is None


@pytest.mark.asyncio
async def test_read_write_text_file(tmp_path):
    """测试文本文件读写"""
    test_file = tmp_path / "test.txt"
    content = "Hello, World!"

    # 写入
    await FileOperationsHelper.write_text_file(test_file, content)
    assert test_file.exists()

    # 读取
    result = await FileOperationsHelper.read_text_file(test_file)
    assert result == content


@pytest.mark.asyncio
async def test_read_text_file_default(tmp_path):
    """测试读取不存在的文本文件返回默认值"""
    test_file = tmp_path / "nonexistent.txt"
    result = await FileOperationsHelper.read_text_file(test_file, default="default")
    assert result == "default"


@pytest.mark.asyncio
async def test_read_write_jsonl_file(tmp_path):
    """测试JSONL文件读写"""
    test_file = tmp_path / "test.jsonl"
    data = [
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
    ]

    # 写入
    await FileOperationsHelper.write_jsonl_file(test_file, data)
    assert test_file.exists()

    # 读取
    result = await FileOperationsHelper.read_jsonl_file(test_file)
    assert result == data


@pytest.mark.asyncio
async def test_read_jsonl_file_handles_invalid_lines(tmp_path):
    """测试JSONL文件忽略无效行"""
    test_file = tmp_path / "mixed.jsonl"
    test_file.write_text('{"id": 1}\ninvalid line\n{"id": 2}\n', encoding="utf-8")

    result = await FileOperationsHelper.read_jsonl_file(test_file)
    assert len(result) == 2
    assert result[0]["id"] == 1
    assert result[1]["id"] == 2


@pytest.mark.asyncio
async def test_write_creates_parent_directories(tmp_path):
    """测试写入时自动创建父目录"""
    test_file = tmp_path / "nested" / "dir" / "test.json"
    data = {"key": "value"}

    await FileOperationsHelper.write_json_file(test_file, data)
    assert test_file.exists()
    assert test_file.parent.is_dir()
