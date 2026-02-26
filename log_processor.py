# log_processor.py
import os
import re
import json
from datetime import datetime
import watchdog
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
import time
from db_models import insert_log, cleanup_old_logs
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class MinerULogHandler(FileSystemEventHandler):
    """监控 MinerU 日志目录的处理器"""

    def __init__(self, log_dir):
        self.log_dir = log_dir
        self.processed_files = set()

    def on_created(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith('.log'):
            self.process_log_file(event.src_path)

    def on_modified(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith('.log') and event.src_path not in self.processed_files:
            self.process_log_file(event.src_path)
            self.processed_files.add(event.src_path)

    def process_log_file(self, file_path):
        """解析并处理日志文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 解析日志内容（根据 MinerU 的实际日志格式调整）
            log_data = self.parse_mineru_log(content, file_path)

            if log_data:
                insert_log(log_data)

            # 处理完成后可以删除原始日志（可选）
            # os.remove(file_path)

        except Exception as e:
            print(f"处理日志文件失败 {file_path}: {e}")

    def parse_mineru_log(self, content, file_path):
        """解析 MinerU 日志，提取关键信息"""
        data = {
            'task_id': self.extract_task_id(file_path),
            'source': 'mineru',
            'timestamp': datetime.now().isoformat()
        }

        # 提取文件名
        filename_match = re.search(r'Processing file: (.+?\.pdf)', content)
        if filename_match:
            data['filename'] = filename_match.group(1)

        # 提取状态
        if 'Successfully converted' in content:
            data['status'] = 'success'
        elif 'Error' in content or 'Failed' in content:
            data['status'] = 'failed'
            error_match = re.search(r'Error: (.+?)\n', content)
            if error_match:
                data['error_msg'] = error_match.group(1)
        else:
            data['status'] = 'processing'

        # 提取耗时
        duration_match = re.search(r'Time elapsed: ([\d.]+) seconds', content)
        if duration_match:
            data['duration'] = float(duration_match.group(1))

        # 提取页数
        pages_match = re.search(r'Total pages: (\d+)', content)
        if pages_match:
            data['pages'] = int(pages_match.group(1))

        return data

    def extract_task_id(self, file_path):
        """从文件名提取任务ID"""
        basename = os.path.basename(file_path)
        # 假设格式为: task_id_timestamp_ip.log
        return basename.split('_')[0]


class LogMonitor:
    """日志监控服务"""

    def __init__(self, log_dir):
        self.log_dir = log_dir
        self.observer = Observer()
        self.handler = MinerULogHandler(log_dir)
        self.is_running = False

    def start(self):
        """启动监控"""
        self.observer.schedule(self.handler, self.log_dir, recursive=False)
        self.observer.start()
        self.is_running = True

        # 启动清理线程
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()

    def stop(self):
        """停止监控"""
        if self.is_running:
            self.observer.stop()
            self.observer.join()
            self.is_running = False

    def _cleanup_loop(self):
        """定时清理线程"""
        while self.is_running:
            time.sleep(3600)  # 每小时检查一次
            cleanup_old_logs()