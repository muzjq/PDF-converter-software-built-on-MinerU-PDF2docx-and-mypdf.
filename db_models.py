# db_models.py
import sqlite3
import json
from datetime import datetime, timedelta
from contextlib import contextmanager
from config import DB_PATH, LOG_RETENTION_DAYS
from contextlib import contextmanager

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """初始化数据库表"""
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS conversion_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                task_id TEXT UNIQUE,
                filename TEXT,
                source TEXT,  -- 'mineru' 或 'frontend'
                status TEXT,  -- 'success', 'failed', 'processing'
                duration REAL,  -- 处理耗时(秒)
                file_size INTEGER,
                pages INTEGER,
                error_msg TEXT,
                details TEXT  -- JSON格式存储额外信息
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS system_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                cpu_percent REAL,
                memory_percent REAL,
                gpu_utilization REAL,
                gpu_memory_used REAL,
                disk_usage REAL
            )
        ''')

        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON conversion_logs(timestamp)
        ''')
 # ===== 新增：创建公告表 =====
        conn.execute('''
            CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_published BOOLEAN DEFAULT 1
            )
        ''')
        # ===== 新增结束 =====


def cleanup_old_logs():
    """删除60天前的日志"""
    cutoff = datetime.now() - timedelta(days=LOG_RETENTION_DAYS)
    with get_db() as conn:
        conn.execute(
            'DELETE FROM conversion_logs WHERE timestamp < ?',
            (cutoff.isoformat(),)
        )
        conn.execute(
            'DELETE FROM system_metrics WHERE timestamp < ?',
            (cutoff.isoformat(),)
        )


def insert_log(data):
    """插入转换日志"""
    with get_db() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO conversion_logs
            (task_id, filename, source, status, duration, 
             file_size, pages, error_msg, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('task_id'),
            data.get('filename'),
            data.get('source', 'mineru'),
            data.get('status'),
            data.get('duration'),
            data.get('file_size'),
            data.get('pages'),
            data.get('error_msg'),
            json.dumps(data.get('details', {}))
        ))


def get_latest_announcement():
    """获取最新的已发布公告"""
    with get_db() as conn:
        row = conn.execute('''
             SELECT title, content, created_at FROM announcements
             WHERE is_published = 1
             ORDER BY created_at DESC LIMIT 1
         ''').fetchone()
        return dict(row) if row else None