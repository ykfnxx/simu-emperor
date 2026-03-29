# V5 持久化与存取 SPEC

> 可执行规格文档 — 2026-03-29

---

## 1. 概述

### 1.1 目标

将 V4 的多层存储（SQLite + JSONL + ChromaDB + 文件系统）统一到 SeekDB，实现：
- 单一数据源
- 结构化查询
- 向量搜索
- 权限隔离

### 1.2 设计原则

- **不过度设计**：表结构满足当前需求即可
- **完全重构**：不考虑与 V4 的数据迁移
- **V5 暂不实现 Schema 迁移框架**：后续迭代再加

---

## 2. 存储架构

### 2.1 技术选型

| 组件 | 技术 | 说明 |
|------|------|------|
| 数据库 | SeekDB (MySQL 兼容) | 支持 VECTOR、FULLTEXT |
| 连接池 | aiomysql.Pool | 异步连接池 |
| 部署 | Docker Compose | 开发和生产统一 |

### 2.2 表清单

| 表 | 用途 | 替代 V4 |
|----|------|--------|
| `tape_events` | 事件流 | tape.jsonl |
| `tape_sessions` | 会话元数据 + 滑动窗口状态 | tape_meta.jsonl |
| `tape_segments` | 向量索引 | ChromaDB |
| `agent_config` | Agent 配置 | soul.md + data_scope.yaml |
| `game_tick` | 当前 tick | SQLite game_state |
| `provinces` | 省份数据 | SQLite game_state JSON |
| `national_treasury` | 国库数据 | SQLite game_state JSON |
| `incidents` | 事件/Incident | SQLite incidents |
| `task_sessions` | 任务会话 | 内存 TaskMonitor |

---

## 3. 表结构设计

### 3.1 tape_events

事件流主表，记录所有事件。

```sql
CREATE TABLE tape_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    agent_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(32) NOT NULL,
    event_id VARCHAR(64) NOT NULL,
    src VARCHAR(128),
    dst JSON,
    payload JSON NOT NULL,
    tick INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_session_agent (session_id, agent_id),
    INDEX idx_session_created (session_id, created_at),
    INDEX idx_event_type (event_type)
);
```

**查询模式：**

```sql
-- 加载滑动窗口（从 window_offset 开始）
SELECT * FROM tape_events
WHERE session_id = ? AND agent_id = ? AND id > ?
ORDER BY id ASC;

-- 插入新事件
INSERT INTO tape_events 
(session_id, agent_id, event_type, event_id, src, dst, payload, tick)
VALUES (?, ?, ?, ?, ?, ?, ?, ?);
```

### 3.2 tape_sessions

会话元数据，包含滑动窗口状态。

```sql
CREATE TABLE tape_sessions (
    session_id VARCHAR(64) PRIMARY KEY,
    agent_id VARCHAR(64) NOT NULL,
    window_offset BIGINT DEFAULT 0,
    summary TEXT,
    title VARCHAR(256),
    tick_start INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_agent (agent_id)
);
```

**字段说明：**
- `window_offset`: 已压缩的事件 ID，下次加载从此 ID 之后开始
- `summary`: 累积摘要（LLM 生成）
- `title`: 会话标题（首条消息生成）

### 3.3 tape_segments

向量索引，用于语义搜索。

```sql
CREATE TABLE tape_segments (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    agent_id VARCHAR(64) NOT NULL,
    start_pos BIGINT NOT NULL,
    end_pos BIGINT NOT NULL,
    summary TEXT NOT NULL,
    embedding VECTOR(384),
    tick INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_session_agent (session_id, agent_id)
);
```

**向量搜索查询：**

```sql
SELECT session_id, agent_id, summary, start_pos, end_pos,
       embedding <=> :query_embedding AS distance
FROM tape_segments
WHERE agent_id = ?
ORDER BY distance ASC
LIMIT 10;
```

### 3.4 agent_config

Agent 配置，替代 soul.md 和 data_scope.yaml。

```sql
CREATE TABLE agent_config (
    agent_id VARCHAR(64) PRIMARY KEY,
    role_name VARCHAR(128) NOT NULL,
    soul_text TEXT NOT NULL,
    skills JSON,
    permissions JSON,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

**permissions 格式：**

```json
{
    "provinces": ["zhili", "jiangsu"],
    "tables": {
        "provinces": ["SELECT"],
        "national_treasury": ["SELECT"]
    },
    "tools": {
        "query_province_data": ["zhili", "jiangsu"],
        "query_national_data": true
    }
}
```

### 3.5 游戏状态表

**game_tick:**

```sql
CREATE TABLE game_tick (
    id INT PRIMARY KEY DEFAULT 1,
    tick INT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

**provinces（支持行级权限隔离）：**

```sql
CREATE TABLE provinces (
    province_id VARCHAR(32) PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    population INT DEFAULT 0,
    treasury BIGINT DEFAULT 0,
    tax_rate DECIMAL(5, 4) DEFAULT 0.1000,
    stability DECIMAL(3, 2) DEFAULT 0.80,
    -- 其他字段...
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

**national_treasury:**

```sql
CREATE TABLE national_treasury (
    id INT PRIMARY KEY DEFAULT 1,
    total_silver BIGINT DEFAULT 0,
    monthly_income BIGINT DEFAULT 0,
    monthly_expense BIGINT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### 3.6 incidents

```sql
CREATE TABLE incidents (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    incident_id VARCHAR(64) NOT NULL,
    session_id VARCHAR(64) NOT NULL,
    agent_id VARCHAR(64) NOT NULL,
    incident_type VARCHAR(32) NOT NULL,
    title VARCHAR(256) NOT NULL,
    description TEXT,
    severity ENUM('low', 'medium', 'high') DEFAULT 'medium',
    status ENUM('active', 'expired', 'resolved') DEFAULT 'active',
    tick_created INT NOT NULL,
    tick_expire INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_session (session_id),
    INDEX idx_status (status)
);
```

### 3.7 task_sessions

```sql
CREATE TABLE task_sessions (
    task_id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    creator_id VARCHAR(64) NOT NULL,
    task_type VARCHAR(32),
    status ENUM('pending', 'running', 'completed', 'failed') DEFAULT 'pending',
    timeout_seconds INT DEFAULT 300,
    result JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    
    INDEX idx_session (session_id),
    INDEX idx_status (status)
);
```

---

## 4. Repository 层

### 4.1 SeekDBClient

统一的数据库客户端。

```python
class SeekDBClient:
    def __init__(self, pool: aiomysql.Pool):
        self._pool = pool
    
    async def execute(self, sql: str, *args) -> int:
        """执行 SQL，返回 affected rows。"""
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, args)
                return cur.rowcount
    
    async def fetch_one(self, sql: str, *args) -> dict | None:
        """查询单行。"""
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, args)
                return await cur.fetchone()
    
    async def fetch_all(self, sql: str, *args) -> list[dict]:
        """查询多行。"""
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, args)
                return await cur.fetchall()
```

### 4.2 TapeRepository

事件流读写。

```python
class TapeRepository:
    def __init__(self, client: SeekDBClient):
        self._client = client
    
    async def append_event(self, event: Event) -> int:
        """追加事件，返回 event_id (auto_increment)。"""
        return await self._client.execute("""
            INSERT INTO tape_events 
            (session_id, agent_id, event_type, event_id, src, dst, payload, tick)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, event.session_id, event.agent_id, event.event_type, 
            event.event_id, event.src, json.dumps(event.dst), 
            json.dumps(event.payload), event.tick)
    
    async def load_events(
        self, session_id: str, agent_id: str, offset: int = 0
    ) -> list[dict]:
        """加载事件（从 offset 开始）。"""
        return await self._client.fetch_all("""
            SELECT * FROM tape_events
            WHERE session_id = ? AND agent_id = ? AND id > ?
            ORDER BY id ASC
        """, session_id, agent_id, offset)
    
    async def get_session(self, session_id: str) -> dict | None:
        """获取会话元数据。"""
        return await self._client.fetch_one(
            "SELECT * FROM tape_sessions WHERE session_id = ?", session_id
        )
    
    async def update_window_offset(
        self, session_id: str, offset: int, summary: str
    ) -> None:
        """更新滑动窗口偏移和摘要。"""
        await self._client.execute("""
            UPDATE tape_sessions 
            SET window_offset = ?, summary = ?
            WHERE session_id = ?
        """, offset, summary, session_id)
```

### 4.3 SegmentRepository

向量索引管理。

```python
class SegmentRepository:
    async def add_segment(
        self, 
        session_id: str,
        agent_id: str,
        start_pos: int,
        end_pos: int,
        summary: str,
        embedding: list[float],
        tick: int
    ) -> None:
        """添加向量段。"""
        await self._client.execute("""
            INSERT INTO tape_segments
            (session_id, agent_id, start_pos, end_pos, summary, embedding, tick)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, session_id, agent_id, start_pos, end_pos, summary, 
            self._encode_vector(embedding), tick)
    
    async def search_similar(
        self, 
        query_embedding: list[float],
        agent_id: str | None = None,
        limit: int = 10
    ) -> list[dict]:
        """向量搜索。"""
        sql = """
            SELECT session_id, agent_id, summary, start_pos, end_pos,
                   embedding <=> ? AS distance
            FROM tape_segments
        """
        args = [self._encode_vector(query_embedding)]
        
        if agent_id:
            sql += " WHERE agent_id = ?"
            args.append(agent_id)
        
        sql += " ORDER BY distance ASC LIMIT ?"
        args.append(limit)
        
        return await self._client.fetch_all(sql, *args)
    
    def _encode_vector(self, embedding: list[float]) -> str:
        """编码向量为 MySQL 格式。"""
        return f"[{','.join(str(x) for x in embedding)}]"
```

### 4.4 AgentConfigRepository

Agent 配置管理。

```python
class AgentConfigRepository:
    async def get(self, agent_id: str) -> dict | None:
        """获取 Agent 配置。"""
        return await self._client.fetch_one(
            "SELECT * FROM agent_config WHERE agent_id = ?", agent_id
        )
    
    async def create(self, config: AgentConfig) -> None:
        """创建 Agent 配置。"""
        await self._client.execute("""
            INSERT INTO agent_config 
            (agent_id, role_name, soul_text, skills, permissions, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        """, config.agent_id, config.role_name, config.soul_text,
            json.dumps(config.skills), json.dumps(config.permissions), 
            config.is_active)
    
    async def update(self, agent_id: str, **fields) -> None:
        """更新 Agent 配置。"""
        set_clauses = []
        args = []
        for key, value in fields.items():
            if key in ('skills', 'permissions'):
                value = json.dumps(value)
            set_clauses.append(f"{key} = ?")
            args.append(value)
        args.append(agent_id)
        
        await self._client.execute(
            f"UPDATE agent_config SET {', '.join(set_clauses)} WHERE agent_id = ?",
            *args
        )
    
    async def list_active(self) -> list[dict]:
        """列出所有活跃 Agent。"""
        return await self._client.fetch_all(
            "SELECT * FROM agent_config WHERE is_active = TRUE"
        )
```

### 4.5 GameStateRepository

游戏状态管理。

```python
class GameStateRepository:
    async def get_tick(self) -> int:
        """获取当前 tick。"""
        row = await self._client.fetch_one(
            "SELECT tick FROM game_tick WHERE id = 1"
        )
        return row["tick"] if row else 0
    
    async def increment_tick(self) -> int:
        """Tick +1，返回新值。"""
        await self._client.execute(
            "UPDATE game_tick SET tick = tick + 1 WHERE id = 1"
        )
        return await self.get_tick()
    
    async def get_province(self, province_id: str) -> dict | None:
        """获取省份数据。"""
        return await self._client.fetch_one(
            "SELECT * FROM provinces WHERE province_id = ?", province_id
        )
    
    async def get_all_provinces(self) -> list[dict]:
        """获取所有省份数据。"""
        return await self._client.fetch_all("SELECT * FROM provinces")
    
    async def update_province(self, province_id: str, **fields) -> None:
        """更新省份数据。"""
        set_clauses = [f"{k} = ?" for k in fields.keys()]
        args = list(fields.values()) + [province_id]
        await self._client.execute(
            f"UPDATE provinces SET {', '.join(set_clauses)} WHERE province_id = ?",
            *args
        )
    
    async def get_national_treasury(self) -> dict:
        """获取国库数据。"""
        return await self._client.fetch_one(
            "SELECT * FROM national_treasury WHERE id = 1"
        )
```

---

## 5. 向量索引更新

### 5.1 触发时机

**滑动窗口压缩时异步写入：**

```python
class ContextManager:
    async def slide_window(self) -> None:
        # 1. 丢弃旧事件
        dropped_events = self._drop_old_events()
        if not dropped_events:
            return
        
        # 2. 生成段摘要
        summary = await self._summarize_events(dropped_events)
        
        # 3. 异步计算 embedding 并写入
        asyncio.create_task(self._index_segment(
            dropped_events[0].id,
            dropped_events[-1].id,
            summary
        ))
        
        # 4. 更新 window_offset
        await self._tape_repo.update_window_offset(
            self.session_id,
            dropped_events[-1].id,
            self._cumulative_summary
        )
    
    async def _index_segment(
        self, start_pos: int, end_pos: int, summary: str
    ) -> None:
        """异步索引段。"""
        embedding = await self._embedding_service.embed(summary)
        await self._segment_repo.add_segment(
            self.session_id,
            self.agent_id,
            start_pos,
            end_pos,
            summary,
            embedding,
            self._current_tick
        )
```

### 5.2 Embedding 服务

```python
class EmbeddingService:
    async def embed(self, text: str) -> list[float]:
        """计算文本 embedding。"""
        # 使用 SeekDB 内置的 embedding 函数
        # 或调用外部 API（如 OpenAI）
        pass
```

---

## 6. 权限管理

### 6.1 权限检查

```python
class PermissionChecker:
    def __init__(self, permissions: dict):
        self._permissions = permissions
    
    def has_tool_permission(
        self, tool_name: str, resource: str = "*"
    ) -> bool:
        """检查工具权限。"""
        tool_perms = self._permissions.get("tools", {})
        if tool_name not in tool_perms:
            return False
        
        perm = tool_perms[tool_name]
        if perm is True:
            return True
        if isinstance(perm, list):
            return resource in perm or "*" in perm
        return False
    
    def get_allowed_provinces(self) -> list[str]:
        """获取允许访问的省份列表。"""
        return self._permissions.get("provinces", [])
```

### 6.2 集成到工具

```python
async def query_province_data(ctx: AgentContext, province_id: str) -> str:
    # 权限检查
    if not ctx.permissions.has_tool_permission("query_province_data", province_id):
        return f"无权限查询省份 {province_id}"
    
    # 查询数据
    data = await ctx.seekdb.get_province(province_id)
    if not data:
        return f"省份 {province_id} 不存在"
    
    return format_province_data(data)
```

---

## 7. 部署配置

### 7.1 Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  seekdb:
    image: seekdb/seekdb:latest
    ports:
      - "3306:3306"
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: simu_emperor
    volumes:
      - seekdb_data:/var/lib/mysql
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql

volumes:
  seekdb_data:
```

### 7.2 初始化脚本

```sql
-- init.sql
CREATE DATABASE IF NOT EXISTS simu_emperor;
USE simu_emperor;

-- 创建所有表（见第 3 节）
-- ...

-- 初始化游戏状态
INSERT INTO game_tick (id, tick) VALUES (1, 0) ON DUPLICATE KEY UPDATE tick = tick;

-- 初始化省份
INSERT INTO provinces (province_id, name, population, treasury, tax_rate) VALUES
('zhili', '直隶', 5000000, 1000000, 0.1000),
('jiangsu', '江苏', 8000000, 2000000, 0.1200),
-- ...
```

### 7.3 连接池配置

```python
# config.py
DB_POOL_SIZE = 10
DB_POOL_RECYCLE = 3600
DB_POOL_TIMEOUT = 30

async def create_db_pool() -> aiomysql.Pool:
    return await aiomysql.create_pool(
        host="localhost",
        port=3306,
        user="root",
        password="root",
        db="simu_emperor",
        minsize=1,
        maxsize=DB_POOL_SIZE,
        pool_recycle=DB_POOL_RECYCLE,
        autocommit=True
    )
```

---

## 8. 实现清单

### 8.1 文件结构

```
src/simu_emperor/persistence/
├── __init__.py
├── client.py              # SeekDBClient
├── repositories/
│   ├── __init__.py
│   ├── tape.py            # TapeRepository
│   ├── segment.py         # SegmentRepository
│   ├── agent_config.py    # AgentConfigRepository
│   ├── game_state.py      # GameStateRepository
│   └── task_session.py    # TaskSessionRepository
├── models.py              # 数据模型
└── migrations/            # 预留，V5 暂不实现
    └── init.sql
```

### 8.2 实现顺序

1. **Phase 1**: 基础设施
   - client.py
   - init.sql
   - Docker Compose

2. **Phase 2**: Repository 层
   - tape.py
   - agent_config.py
   - game_state.py

3. **Phase 3**: 向量索引
   - segment.py
   - EmbeddingService

4. **Phase 4**: 权限管理
   - PermissionChecker
   - 集成到工具

---

## 9. 测试清单

- [ ] 连接池创建和回收
- [ ] tape_events 读写
- [ ] 滑动窗口 offset 更新
- [ ] 向量索引写入和搜索
- [ ] agent_config CRUD
- [ ] 游戏状态读写
- [ ] 权限检查
- [ ] 并发访问
