# app.py
from flask import Flask, render_template, jsonify, request, send_file
import plotly
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
import psutil
from db_models import get_latest_announcement, get_db, init_db, insert_log, cleanup_old_logs
from mineru_manager import MinerUManager
from log_processor import LogMonitor
import json
from datetime import datetime, timedelta
import threading
import time
import os
from config import SECRET_KEY, MINERU_LOG_PATH

app = Flask(__name__)
app.secret_key = SECRET_KEY

# 初始化
init_db()
mineru_manager = MinerUManager()
log_monitor = LogMonitor(MINERU_LOG_PATH)
log_monitor.start()


# ========== 网页路由 ==========
@app.route('/')
def index():
    """主仪表盘页面"""
    return render_template('dashboard.html')


@app.route('/logs')
def logs_page():
    """日志查看页面"""
    return render_template('logs.html')


@app.route('/control')
def control_page():
    """服务控制页面"""
    return render_template('control.html')


# ========== API 路由 ==========
@app.route('/api/stats/summary')
def get_summary_stats():
    """获取统计数据摘要"""
    with get_db() as conn:
        # 今日总数
        today = datetime.now().date().isoformat()
        total = conn.execute('''
            SELECT COUNT(*) as count FROM conversion_logs
            WHERE date(timestamp) = ?
        ''', (today,)).fetchone()['count']

        # 成功率
        success = conn.execute('''
            SELECT COUNT(*) as count FROM conversion_logs
            WHERE date(timestamp) = ? AND status = 'success'
        ''', (today,)).fetchone()['count']

        success_rate = (success / total * 100) if total > 0 else 0

        # 平均耗时
        avg_duration = conn.execute('''
            SELECT AVG(duration) as avg FROM conversion_logs
            WHERE date(timestamp) = ? AND status = 'success' AND duration IS NOT NULL
        ''', (today,)).fetchone()['avg'] or 0

        return jsonify({
            'today_total': total,
            'today_success': success,
            'today_success_rate': round(success_rate, 2),
            'avg_duration': round(avg_duration, 2)
        })


@app.route('/api/stats/charts/<int:days>')
def get_chart_data(days=7):
    """获取图表数据"""
    with get_db() as conn:
        # 按天统计
        data = conn.execute('''
            SELECT 
                date(timestamp) as date,
                COUNT(*) as total,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
                AVG(duration) as avg_duration
            FROM conversion_logs
            WHERE timestamp >= datetime('now', ?)
            GROUP BY date(timestamp)
            ORDER BY date(timestamp)
        ''', (f'-{days} days',)).fetchall()

        df = pd.DataFrame([dict(row) for row in data])

        if df.empty:
            return jsonify({})

        # 创建图表
        fig1 = go.Figure()
        fig1.add_trace(go.Bar(
            x=df['date'],
            y=df['total'],
            name='总请求数',
            marker_color='lightblue'
        ))
        fig1.add_trace(go.Bar(
            x=df['date'],
            y=df['success'],
            name='成功数',
            marker_color='lightgreen'
        ))
        fig1.update_layout(
            title='每日请求统计',
            xaxis_title='日期',
            yaxis_title='数量',
            barmode='group'
        )

        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=df['date'],
            y=df['avg_duration'],
            mode='lines+markers',
            name='平均耗时(秒)',
            line=dict(color='orange', width=2)
        ))
        fig2.update_layout(
            title='平均处理耗时趋势',
            xaxis_title='日期',
            yaxis_title='秒'
        )

        return jsonify({
            'daily_chart': json.loads(plotly.utils.PlotlyJSONEncoder().encode(fig1)),
            'duration_chart': json.loads(plotly.utils.PlotlyJSONEncoder().encode(fig2))
        })


@app.route('/api/logs')
def get_logs():
    """获取日志列表（支持分页）"""
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    source = request.args.get('source')
    status = request.args.get('status')

    offset = (page - 1) * per_page

    query = 'SELECT * FROM conversion_logs WHERE 1=1'
    params = []

    if source:
        query += ' AND source = ?'
        params.append(source)
    if status:
        query += ' AND status = ?'
        params.append(status)

    query += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
    params.extend([per_page, offset])

    with get_db() as conn:
        logs = conn.execute(query, params).fetchall()
        total = conn.execute('SELECT COUNT(*) as count FROM conversion_logs').fetchone()['count']

        return jsonify({
            'logs': [dict(log) for log in logs],
            'total': total,
            'page': page,
            'per_page': per_page
        })


@app.route('/api/mineru/status')
def get_mineru_status():
    """获取 MinerU 服务状态"""
    return jsonify(mineru_manager.get_status())


@app.route('/api/mineru/control/<action>', methods=['POST'])
def control_mineru(action):
    """控制 MinerU 服务"""
    if action == 'start':
        result = mineru_manager.start()
    elif action == 'stop':
        result = mineru_manager.stop()
    elif action == 'restart':
        result = mineru_manager.restart()
    else:
        return jsonify({'error': '无效操作'}), 400

    return jsonify(result)


@app.route('/api/system/metrics')
def get_system_metrics():
    """获取系统实时指标"""
    metrics = {
        'cpu': psutil.cpu_percent(interval=1),
        'memory': psutil.virtual_memory().percent,
        'disk': psutil.disk_usage('/').percent,
        'timestamp': datetime.now().isoformat()
    }

    # 尝试获取 GPU 信息
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
        metrics['gpu_util'] = util.gpu
        metrics['gpu_memory'] = memory.used / memory.total * 100
    except:
        metrics['gpu_util'] = None
        metrics['gpu_memory'] = None

    return jsonify(metrics)


# ===== 新增：公告相关 API =====
@app.route('/api/announcement/latest')
def get_latest_announcement_api():
    """前端获取最新公告的接口"""
    announcement = get_latest_announcement()
    if announcement:
        return jsonify(announcement)
    return jsonify({'title': '暂无公告', 'content': '欢迎使用本软件！'})


@app.route('/api/announcement/save', methods=['POST'])
def save_announcement():
    data = request.json
    title = data.get('title')
    content = data.get('content')
    if not title or not content:
        return jsonify({'error': '标题和内容不能为空'}), 400

    with get_db() as conn:
        # 先删除旧公告（简单策略：只保留最新一条）
        conn.execute('DELETE FROM announcements')
        conn.execute('''
            INSERT INTO announcements (title, content, created_at)
            VALUES (?, ?, datetime('now'))
        ''', (title, content))
    return jsonify({'message': '公告已发布'})

@app.route('/announcement')
def announcement_page():
    return render_template('announcement.html')

# ===== 新增结束 =====

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)