# config.py
import os

# 基础路径配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data', 'logs.db')
LOG_DIR = os.path.join(BASE_DIR, 'logs')

# 确保目录存在
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# MinerU 相关配置
MINERU_API_SERVICE = 'mineru-api'  # systemd 服务名称
MINERU_LOG_PATH = '/var/log/mineru'  # MinerU 原始日志目录

# 应用配置
LOG_RETENTION_DAYS = 60  # 日志保留天数
SECRET_KEY = 'your-secret-key-here-change-in-production'