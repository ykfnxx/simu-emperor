"""文件操作工具类"""

import aiofiles
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class FileOperationsHelper:
    """统一的文件操作工具类"""

    @staticmethod
    async def read_json_file(file_path: Path) -> dict[str, Any] | None:
        """读取 JSON 文件"""
        try:
            async with aiofiles.open(file_path, mode="r", encoding="utf-8") as f:
                content = await f.read()
                if not content.strip():
                    return {}
                return json.loads(content)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to read JSON {file_path}: {e}")
            return None

    @staticmethod
    async def write_json_file(file_path: Path, data: dict[str, Any], indent: int = 2) -> None:
        """写入 JSON 文件"""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(file_path, mode="w", encoding="utf-8") as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=indent))

    @staticmethod
    async def read_text_file(file_path: Path, default: str = "") -> str:
        """读取文本文件"""
        try:
            async with aiofiles.open(file_path, mode="r", encoding="utf-8") as f:
                return await f.read()
        except (IOError, OSError) as e:
            logger.warning(f"Failed to read {file_path}: {e}")
            return default

    @staticmethod
    async def write_text_file(file_path: Path, content: str) -> None:
        """写入文本文件"""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(file_path, mode="w", encoding="utf-8") as f:
            await f.write(content)

    @staticmethod
    async def read_jsonl_file(file_path: Path) -> list[dict[str, Any]]:
        """读取 JSONL 文件"""
        events = []
        try:
            async with aiofiles.open(file_path, mode="r", encoding="utf-8") as f:
                async for line in f:
                    if line.strip():
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to read JSONL {file_path}: {e}")
        return events

    @staticmethod
    async def write_jsonl_file(file_path: Path, data: list[dict[str, Any]]) -> None:
        """写入 JSONL 文件"""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(file_path, mode="w", encoding="utf-8") as f:
            for item in data:
                await f.write(json.dumps(item, ensure_ascii=False) + "\n")
