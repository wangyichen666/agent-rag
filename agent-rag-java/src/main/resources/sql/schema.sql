-- agent-rag 业务库 schema（MySQL 8），对应《04-数据库与存储设计》
CREATE DATABASE IF NOT EXISTS agent_rag DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE agent_rag;

CREATE TABLE IF NOT EXISTS sys_user (
    id            BIGINT PRIMARY KEY AUTO_INCREMENT,
    username      VARCHAR(64)  NOT NULL UNIQUE,
    password_hash VARCHAR(128) NOT NULL,
    nickname      VARCHAR(64),
    role          VARCHAR(32)  NOT NULL DEFAULT 'user',
    status        TINYINT      NOT NULL DEFAULT 1,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kb (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    kb_code         VARCHAR(64) NOT NULL UNIQUE,
    name            VARCHAR(128) NOT NULL,
    description     VARCHAR(512),
    embedding_model VARCHAR(64) NOT NULL DEFAULT 'bge-m3',
    chunk_config    JSON,
    owner_id        BIGINT      NOT NULL,
    status          TINYINT     NOT NULL DEFAULT 1,
    created_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kb_permission (
    id           BIGINT PRIMARY KEY AUTO_INCREMENT,
    kb_id        BIGINT      NOT NULL,
    subject_type VARCHAR(16) NOT NULL,
    subject_id   BIGINT      NOT NULL,
    perm         VARCHAR(16) NOT NULL,
    UNIQUE KEY uk_kb_subject (kb_id, subject_type, subject_id)
);

CREATE TABLE IF NOT EXISTS kb_document (
    id           BIGINT PRIMARY KEY AUTO_INCREMENT,
    doc_code     VARCHAR(64)  NOT NULL UNIQUE,
    kb_id        BIGINT       NOT NULL,
    file_name    VARCHAR(255) NOT NULL,
    file_type    VARCHAR(16)  NOT NULL,
    file_size    BIGINT,
    file_hash    CHAR(64),
    minio_path   VARCHAR(512) NOT NULL,
    parse_status VARCHAR(16)  NOT NULL DEFAULT 'pending',
    chunk_count  INT          NOT NULL DEFAULT 0,
    error_msg    TEXT,
    version      INT          NOT NULL DEFAULT 1,
    created_by   BIGINT,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_kb_status (kb_id, parse_status),
    KEY idx_hash (file_hash)
);

CREATE TABLE IF NOT EXISTS conversation (
    id         BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id    BIGINT       NOT NULL,
    kb_ids     JSON         NOT NULL,
    title      VARCHAR(255),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_user (user_id, updated_at)
);

CREATE TABLE IF NOT EXISTS message (
    id                BIGINT PRIMARY KEY AUTO_INCREMENT,
    trace_id          VARCHAR(64),
    conversation_id   BIGINT       NOT NULL,
    role              VARCHAR(16)  NOT NULL,
    content           MEDIUMTEXT   NOT NULL,
    rewritten_query   VARCHAR(1024),
    citations         JSON,
    retrieval_debug   JSON,
    prompt_tokens     INT,
    completion_tokens INT,
    latency_ms        INT,
    feedback          TINYINT,
    feedback_note     VARCHAR(512),
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_conv (conversation_id, id)
);
