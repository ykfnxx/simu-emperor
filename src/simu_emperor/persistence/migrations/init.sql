-- V5 初始化脚本

CREATE DATABASE IF NOT EXISTS simu_emperor;
USE simu_emperor;

-- tape_events - 事件流主表
CREATE TABLE IF NOT EXISTS tape_events (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- tape_sessions - 会话元数据 + 滑动窗口状态
CREATE TABLE IF NOT EXISTS tape_sessions (
    session_id VARCHAR(64) PRIMARY KEY,
    agent_id VARCHAR(64) NOT NULL,
    window_offset BIGINT DEFAULT 0,
    summary TEXT,
    title VARCHAR(256),
    tick_start INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_agent (agent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- tape_segments - 向量索引
CREATE TABLE IF NOT EXISTS tape_segments (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    agent_id VARCHAR(64) NOT NULL,
    start_pos BIGINT NOT NULL,
    end_pos BIGINT NOT NULL,
    summary TEXT NOT NULL,
    embedding BLOB,
    tick INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_session_agent (session_id, agent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- agent_config - Agent配置
CREATE TABLE IF NOT EXISTS agent_config (
    agent_id VARCHAR(64) PRIMARY KEY,
    role_name VARCHAR(128) NOT NULL,
    soul_text TEXT NOT NULL,
    skills JSON,
    permissions JSON,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- game_tick - 当前tick
CREATE TABLE IF NOT EXISTS game_tick (
    id INT PRIMARY KEY DEFAULT 1,
    tick INT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- provinces - 省份数据
CREATE TABLE IF NOT EXISTS provinces (
    province_id VARCHAR(32) PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    population BIGINT DEFAULT 0,
    treasury BIGINT DEFAULT 0,
    tax_rate DECIMAL(5, 4) DEFAULT 0.1000,
    stability DECIMAL(3, 2) DEFAULT 0.80,
    production_value BIGINT DEFAULT 0,
    fixed_expenditure BIGINT DEFAULT 0,
    stockpile BIGINT DEFAULT 0,
    base_production_growth DECIMAL(5, 4) DEFAULT 0.0100,
    base_population_growth DECIMAL(5, 4) DEFAULT 0.0050,
    tax_modifier DECIMAL(5, 4) DEFAULT 0.0000,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- national_treasury - 国库数据
CREATE TABLE IF NOT EXISTS national_treasury (
    id INT PRIMARY KEY DEFAULT 1,
    total_silver BIGINT DEFAULT 0,
    monthly_income BIGINT DEFAULT 0,
    monthly_expense BIGINT DEFAULT 0,
    base_tax_rate DECIMAL(5, 4) DEFAULT 0.1000,
    tribute_rate DECIMAL(5, 4) DEFAULT 0.8000,
    fixed_expenditure BIGINT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- incidents - 事件/Incident
CREATE TABLE IF NOT EXISTS incidents (
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
    INDEX idx_status (status),
    UNIQUE KEY uk_incident_id (incident_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- task_sessions - 任务会话
CREATE TABLE IF NOT EXISTS task_sessions (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 初始化数据
INSERT INTO game_tick (id, tick) VALUES (1, 0) ON DUPLICATE KEY UPDATE tick = tick;

INSERT INTO national_treasury (id, total_silver, monthly_income, monthly_expense)
VALUES (1, 0, 0, 0) ON DUPLICATE KEY UPDATE total_silver = total_silver;

INSERT INTO provinces (province_id, name, population, treasury, tax_rate) VALUES
('zhili', '直隶', 5000000, 1000000, 0.1000),
('jiangsu', '江苏', 8000000, 2000000, 0.1200),
('zhejiang', '浙江', 7000000, 1800000, 0.1100),
('guangdong', '广东', 9000000, 2500000, 0.1300),
('sichuan', '四川', 6000000, 1200000, 0.1000)
ON DUPLICATE KEY UPDATE name = VALUES(name);
