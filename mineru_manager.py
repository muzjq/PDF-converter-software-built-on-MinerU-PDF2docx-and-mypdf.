# mineru_manager.py
import subprocess
import os
import signal
import psutil
from datetime import datetime
import logging
import psutil

logger = logging.getLogger(__name__)


class MinerUManager:
    """MinerU 服务管理器"""

    def __init__(self, api_port=8000, webui_port=7860):
        self.api_port = api_port
        self.webui_port = webui_port
        self.process = None

    def start(self):
        """启动 MinerU 服务（通过 Docker）"""
        try:
            # 检查是否已在运行
            if self.is_running():
                return {'status': 'already_running', 'message': 'MinerU 服务已在运行'}

            # 启动 Docker 容器
            cmd = [
                'docker', 'run', '-d',
                '--gpus', 'all',
                '--name', 'mineru-api',
                '-p', f'{self.api_port}:8000',
                '-p', f'{self.webui_port}:7860',
                '--restart', 'unless-stopped',
                'mineru-sglang:latest'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                # 记录启动日志
                self._log_event('start', 'success')
                return {'status': 'success', 'container_id': result.stdout.strip()}
            else:
                self._log_event('start', 'failed', result.stderr)
                return {'status': 'failed', 'error': result.stderr}

        except Exception as e:
            self._log_event('start', 'error', str(e))
            return {'status': 'error', 'error': str(e)}

    def stop(self):
        """停止 MinerU 服务"""
        try:
            cmd = ['docker', 'stop', 'mineru-api']
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                # 可选：删除容器
                subprocess.run(['docker', 'rm', 'mineru-api'], capture_output=True)
                self._log_event('stop', 'success')
                return {'status': 'success'}
            else:
                self._log_event('stop', 'failed', result.stderr)
                return {'status': 'failed', 'error': result.stderr}

        except Exception as e:
            self._log_event('stop', 'error', str(e))
            return {'status': 'error', 'error': str(e)}

    def restart(self):
        """重启服务"""
        self.stop()
        return self.start()

    def is_running(self):
        """检查服务是否运行"""
        try:
            cmd = ['docker', 'ps', '--filter', 'name=mineru-api', '--format', '{{.Names}}']
            result = subprocess.run(cmd, capture_output=True, text=True)
            return 'mineru-api' in result.stdout
        except:
            return False

    def get_status(self):
        """获取详细状态"""
        status = {
            'running': self.is_running(),
            'api_port': self.api_port,
            'webui_port': self.webui_port,
            'container_id': None,
            'uptime': None,
            'cpu_usage': None,
            'memory_usage': None
        }

        if status['running']:
            # 获取容器详情
            cmd = ['docker', 'inspect', 'mineru-api']
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)[0]
                status['container_id'] = data['Id'][:12]
                # 计算运行时间
                started = data['State']['StartedAt']
                # 获取资源使用
                stats = subprocess.run(
                    ['docker', 'stats', '--no-stream', '--format', '{{.CPUPerc}}|{{.MemUsage}}', 'mineru-api'],
                    capture_output=True, text=True
                )
                if stats.returncode == 0:
                    parts = stats.stdout.strip().split('|')
                    if len(parts) == 2:
                        status['cpu_usage'] = parts[0]
                        status['memory_usage'] = parts[1]

        return status

    def _log_event(self, action, result, error=None):
        """记录管理事件到日志"""
        logger.info(f"MinerU {action}: {result}" + (f" - {error}" if error else ""))
        # 也可以写入数据库
        with get_db() as conn:
            conn.execute('''
                INSERT INTO system_metrics (event_type, event_result, event_detail)
                VALUES (?, ?, ?)
            ''', (f'mineru_{action}', result, error))