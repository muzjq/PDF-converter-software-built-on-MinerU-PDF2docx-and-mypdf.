#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
木子的PDF转换器 4.0 (MinerU云端增强版)
功能：PDF转Word/Txt + 加密PDF处理 + 公文/试卷优化
      自动调用内部MinerU服务器，用户无感知
      制作团队：木子工作室、deepseek R1
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import threading
import queue
import subprocess
from pathlib import Path
from datetime import datetime
import traceback
import urllib.request
import urllib.parse
import json
import time

# ==================== MinerU 生产配置（打包前修改）====================
MINERU_SERVER = "http://192.168.1.100:8000"  #  todo:此处记得改

# ==================== 库导入检查 ====================
HAS_PDF2DOCX = False
HAS_PYPDF2 = False

try:
    from pdf2docx import Converter
    HAS_PDF2DOCX = True
except ImportError:
    print("[错误] 请安装 pdf2docx: pip install pdf2docx")

try:
    from PyPDF2 import PdfReader, PdfWriter
    HAS_PYPDF2 = True
except ImportError:
    print("[错误] 请安装 PyPDF2: pip install PyPDF2")
    HAS_PYPDF2 = False


class PDFConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("✨ 木子的PDF转换器 4.0")

        # 窗口居中
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        ww, wh = 800, 500
        x = (sw - ww) // 2
        y = (sh - wh) // 2
        self.root.geometry(f"{ww}x{wh}+{x}+{y}")
        self.root.resizable(False, False)

        self.set_window_icon()

        # ========== 核心变量 ==========
        self.pdf_path = tk.StringVar()
        self.output_dir = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Desktop"))
        self.format_var = tk.StringVar(value="docx")
        self.page_range_var = tk.StringVar()
        self.dpi_var = tk.IntVar(value=300)
        self.lang_var = tk.StringVar(value="中英文")

        self.gov_optimize_var = tk.BooleanVar(value=False)
        self.exam_optimize_var = tk.BooleanVar(value=False)

        self.password_cache = {}
        self.current_password = None
        self.processing = False

        self.setup_ui()
        self.root.after(100, self.show_user_guide)

    def set_window_icon(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(current_dir, "my_icon.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except:
                pass

    def setup_ui(self):
        """界面与3.8.1完全相同，略"""
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 15))
        tk.Label(title_frame, text="📚 木子 PDF 转换器", font=("微软雅黑", 18, "bold"),
                 fg="#0A192F").pack(side=tk.LEFT)
        tk.Button(title_frame, text="❓ 帮助", command=self.show_user_guide,
                  bg="#87CEFA", fg="white", relief="flat", padx=15,
                  font=("微软雅黑", 10)).pack(side=tk.RIGHT)

        file_frame = ttk.LabelFrame(main_frame, text="📁 选择文件", padding="15")
        file_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(file_frame, text="PDF文件:").grid(row=0, column=0, sticky=tk.W, pady=8)
        ttk.Entry(file_frame, textvariable=self.pdf_path, width=50).grid(row=0, column=1, padx=10)
        ttk.Button(file_frame, text="浏览...", command=self.browse_pdf).grid(row=0, column=2)

        ttk.Label(file_frame, text="输出目录:").grid(row=1, column=0, sticky=tk.W, pady=8)
        ttk.Entry(file_frame, textvariable=self.output_dir, width=50).grid(row=1, column=1, padx=10)
        ttk.Button(file_frame, text="浏览...", command=self.browse_output).grid(row=1, column=2)

        opt_frame = ttk.LabelFrame(main_frame, text="⚙️ 转换选项", padding="15")
        opt_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(opt_frame, text="输出格式:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Radiobutton(opt_frame, text="Word文档 (.docx)", variable=self.format_var, value="docx").grid(row=0, column=1, sticky=tk.W, padx=20)
        ttk.Radiobutton(opt_frame, text="纯文本 (.txt)", variable=self.format_var, value="txt").grid(row=0, column=2, sticky=tk.W)

        ttk.Label(opt_frame, text="页面范围:").grid(row=1, column=0, sticky=tk.W, pady=8)
        ttk.Entry(opt_frame, textvariable=self.page_range_var, width=15).grid(row=1, column=1, sticky=tk.W, padx=20)
        ttk.Label(opt_frame, text="例: 1-5, 10").grid(row=1, column=2, sticky=tk.W)

        ttk.Checkbutton(opt_frame, text="📄 公文优化", variable=self.gov_optimize_var).grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Checkbutton(opt_frame, text="📝 试卷优化", variable=self.exam_optimize_var).grid(row=2, column=1, sticky=tk.W)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        self.convert_btn = tk.Button(btn_frame, text="🚀 开始转换", font=("微软雅黑", 14, "bold"),
                                     bg="#32CD32", fg="white", padx=40, pady=10,
                                     command=self.start_conversion, relief="flat")
        self.convert_btn.pack()

        self.progress = ttk.Progressbar(main_frame, mode='indeterminate', length=600)
        self.progress.pack(pady=(5, 0))

        self.hint_label = tk.Label(main_frame, text="就绪", font=("微软雅黑", 9), fg="#888888")
        self.hint_label.pack(pady=(5, 0))

    # ==================== 文件操作 ====================
    def browse_pdf(self):
        path = filedialog.askopenfilename(title="选择PDF文件", filetypes=[("PDF文件", "*.pdf")])
        if path:
            self.pdf_path.set(path)

    def browse_output(self):
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            self.output_dir.set(path)

    # ==================== 加密处理（新版 PyPDF2）====================
    def check_pdf_encryption(self, pdf_path):
        if not HAS_PYPDF2:
            return False, False, None
        try:
            with open(pdf_path, 'rb') as f:
                reader = PdfReader(f)
                is_encrypted = reader.is_encrypted
                if is_encrypted:
                    cached = self.password_cache.get(pdf_path)
                    if cached:
                        try:
                            reader.decrypt(cached)
                            return True, True, cached
                        except:
                            del self.password_cache[pdf_path]
                    return True, False, None
                return False, True, None
        except:
            return False, False, None

    def ask_for_password(self, pdf_path, max_attempts=3):
        for attempt in range(max_attempts):
            password = simpledialog.askstring("PDF密码输入",
                                              f"文件 '{Path(pdf_path).name}' 已加密\n请输入密码 (尝试 {attempt+1}/{max_attempts}):",
                                              parent=self.root, show='*')
            if password is None:
                return None
            if not password:
                messagebox.showwarning("警告", "密码不能为空")
                continue
            try:
                with open(pdf_path, 'rb') as f:
                    reader = PdfReader(f)
                    if reader.decrypt(password):
                        self.password_cache[pdf_path] = password
                        return password
                messagebox.showerror("密码错误", f"密码错误，还剩 {max_attempts-attempt-1} 次")
            except Exception:
                pass
        messagebox.showerror("错误", "密码错误次数过多")
        return None

    # ==================== 页面范围解析 ====================
    def parse_page_range(self, range_str, total):
        if not range_str.strip():
            return list(range(1, total+1))
        pages = []
        for part in range_str.split(','):
            part = part.strip()
            if '-' in part:
                try:
                    s, e = map(int, part.split('-'))
                    s, e = max(1, s), min(total, e)
                    if s <= e:
                        pages.extend(range(s, e+1))
                except:
                    pass
            else:
                try:
                    p = int(part)
                    if 1 <= p <= total:
                        pages.append(p)
                except:
                    pass
        return sorted(set(pages))

    # ==================== 转换主流程 ====================
    def start_conversion(self):
        if self.processing:
            return
        pdf_path = self.pdf_path.get()
        if not pdf_path or not os.path.exists(pdf_path):
            messagebox.showerror("错误", "请选择有效的PDF文件")
            return

        is_encrypted, is_decrypted, cached_pw = self.check_pdf_encryption(pdf_path)
        if is_encrypted and not is_decrypted:
            password = self.ask_for_password(pdf_path)
            if password is None:
                return
            self.current_password = password
        else:
            self.current_password = cached_pw if is_decrypted else None

        out_dir = self.output_dir.get()
        os.makedirs(out_dir, exist_ok=True)
        pdf_name = Path(pdf_path).stem
        ext = "docx" if self.format_var.get() == "docx" else "txt"
        output_path = os.path.join(out_dir, f"{pdf_name}_转换结果.{ext}")

        self.processing = True
        self.convert_btn.config(state='disabled', text="转换中...")
        self.progress.start()
        self.hint_label.config(text="正在调用云端 MinerU...", fg="#FF69B4")

        threading.Thread(target=self.perform_conversion,
                         args=(pdf_path, output_path, self.current_password),
                         daemon=True).start()

    def perform_conversion(self, pdf_path, output_path, password):
        try:
            total_pages = 0
            if HAS_PYPDF2:
                with open(pdf_path, 'rb') as f:
                    reader = PdfReader(f)
                    if password:
                        reader.decrypt(password)
                    total_pages = len(reader.pages)
            pages_to_convert = self.parse_page_range(self.page_range_var.get(), total_pages)

            self.root.after(0, lambda: self.hint_label.config(text="⏳ MinerU 解析中...", fg="#FF69B4"))
            mineru_success = self.mineru_api_call(pdf_path, output_path, pages_to_convert)

            if mineru_success:
                self.root.after(0, lambda: self.hint_label.config(text="✅ 转换完成！", fg="#27ae60"))
                self.root.after(0, self.ask_open_file, output_path.replace('.docx', '.md').replace('.txt', '.md'))
            else:
                self.root.after(0, lambda: self.hint_label.config(text="⚠️ MinerU 失败，降级本地转换...", fg="#e74c3c"))
                if self.format_var.get() == "docx":
                    if not HAS_PDF2DOCX:
                        self.root.after(0, lambda: self.hint_label.config(text="❌ pdf2docx 未安装", fg="red"))
                        success = False
                    else:
                        success = self.convert_to_docx(pdf_path, output_path, password, pages_to_convert)
                else:
                    if not HAS_PYPDF2:
                        self.root.after(0, lambda: self.hint_label.config(text="❌ PyPDF2 未安装", fg="red"))
                        success = False
                    else:
                        success = self.convert_to_txt(pdf_path, output_path, password, pages_to_convert)
                if success:
                    self.root.after(0, lambda: self.hint_label.config(text="✅ 本地转换完成", fg="#27ae60"))
                    self.root.after(0, self.ask_open_file, output_path)
                else:
                    self.root.after(0, lambda: self.hint_label.config(text="❌ 转换失败", fg="red"))
        except Exception as e:
            self.root.after(0, lambda: self.hint_label.config(text=f"❌ 出错: {str(e)[:30]}", fg="red"))
            traceback.print_exc()
        finally:
            self.root.after(0, self.conversion_finished)

            def fetch_announcement(self):
                """从后端获取最新公告，返回 (title, content) 元组"""
                server = MINERU_SERVER  # 注意：MINERU_SERVER 已经在文件顶部定义
                # 公告API路径
                url = f"{server}/api/announcement/latest"
                try:
                    req = urllib.request.Request(url, method='GET', headers={'Accept': 'application/json'})
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        data = json.loads(resp.read().decode())
                        title = data.get('title', '暂无公告')
                        content = data.get('content', '欢迎使用本软件！')
                        return title, content
                except Exception as e:
                    print(f"获取公告失败: {e}")
                    return "公告", "（无法连接到服务器，请检查网络）"

    # ==================== MinerU API 调用 ====================
    def mineru_api_call(self, pdf_path, output_path, pages):
        """调用 MinerU 云端 API，返回解析后的 Markdown 文件"""
        server = MINERU_SERVER

        try:
            boundary = '----WebKitFormBoundary' + os.urandom(16).hex()
            headers = {
                'Content-Type': f'multipart/form-data; boundary={boundary}',
                'Accept': 'application/json'
            }

            with open(pdf_path, 'rb') as f:
                pdf_data = f.read()

            body_parts = []
            body_parts.append(f'--{boundary}'.encode())
            body_parts.append(f'Content-Disposition: form-data; name="file"; filename="{os.path.basename(pdf_path)}"'.encode())
            body_parts.append('Content-Type: application/pdf'.encode())
            body_parts.append(b'')
            body_parts.append(pdf_data)

            body_parts.append(f'--{boundary}'.encode())
            body_parts.append('Content-Disposition: form-data; name="dpi"'.encode())
            body_parts.append(b'')
            body_parts.append(str(self.dpi_var.get()).encode())

            body_parts.append(f'--{boundary}'.encode())
            body_parts.append('Content-Disposition: form-data; name="language"'.encode())
            body_parts.append(b'')
            lang_map = {"中英文": "ch", "中文": "ch", "英文": "en"}
            lang = lang_map.get(self.lang_var.get(), "ch")
            body_parts.append(lang.encode())

            if self.page_range_var.get().strip():
                body_parts.append(f'--{boundary}'.encode())
                body_parts.append('Content-Disposition: form-data; name="page_ranges"'.encode())
                body_parts.append(b'')
                body_parts.append(self.page_range_var.get().strip().encode())

            body_parts.append(f'--{boundary}--'.encode())
            body_parts.append(b'')
            body = b'\r\n'.join(body_parts)

            req = urllib.request.Request(f"{server}/file/parse", data=body, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode())
                task_id = result.get('task_id')
                if not task_id:
                    return False

            for _ in range(120):
                time.sleep(2)
                req = urllib.request.Request(f"{server}/file/result/{task_id}", method='GET')
                try:
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        if resp.status == 200:
                            data = json.loads(resp.read().decode())
                            md_path = output_path.replace('.docx', '.md').replace('.txt', '.md')
                            with open(md_path, 'w', encoding='utf-8') as f:
                                f.write(data.get('markdown', ''))
                            json_path = output_path.replace('.docx', '.json').replace('.txt', '.json')
                            with open(json_path, 'w', encoding='utf-8') as f:
                                json.dump(data, f, ensure_ascii=False, indent=2)
                            return True
                        elif resp.status == 202:
                            continue
                        else:
                            return False
                except urllib.error.HTTPError as e:
                    if e.code == 202:
                        continue
                    else:
                        return False
            return False
        except Exception:
            return False

    # ==================== 本地转换引擎 ====================
    def convert_to_docx(self, pdf_path, output_path, password, pages):
        try:
            flow_layout = self.exam_optimize_var.get()
            margin = 0.5 if self.gov_optimize_var.get() else 1.0
            cv = Converter(pdf_path, password=password)
            page_list = [p-1 for p in pages]
            cv.convert(output_path, pages=page_list, flow_layout=flow_layout, margin=margin)
            cv.close()
            return True
        except Exception:
            return False

    def convert_to_txt(self, pdf_path, output_path, password, pages):
        if not HAS_PYPDF2:
            return False
        try:
            with open(pdf_path, 'rb') as f:
                reader = PdfReader(f)
                if password:
                    reader.decrypt(password)
                with open(output_path, 'w', encoding='utf-8') as out:
                    out.write(f"文本提取自: {Path(pdf_path).name}\n")
                    out.write("="*50 + "\n\n")
                    for page_num in pages:
                        page = reader.pages[page_num-1]
                        text = page.extract_text() or ""
                        out.write(f"【第 {page_num} 页】\n")
                        out.write(text + "\n\n")
            return True
        except Exception:
            return False

    def ask_open_file(self, file_path):
        if os.path.exists(file_path):
            if messagebox.askyesno("转换完成", f"文件已保存到:\n{file_path}\n\n是否打开？"):
                try:
                    if sys.platform == "win32":
                        os.startfile(file_path)
                    else:
                        subprocess.run(['open' if sys.platform=='darwin' else 'xdg-open', file_path])
                except:
                    pass

    def conversion_finished(self):
        self.processing = False
        self.convert_btn.config(state='normal', text="🚀 开始转换")
        self.progress.stop()

    def show_user_guide(self):
        guide = tk.Toplevel(self.root)
        guide.title("📖 使用说明 & 公告")
        guide.geometry("700x600")
        guide.transient(self.root)
        guide.grab_set()

        # 创建主框架
        main_frame = ttk.Frame(guide, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 创建 PanedWindow 实现上下分栏，并分配权重
        paned = ttk.PanedWindow(main_frame, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # 上半部分：固定帮助文本（权重3，占3/4高度）
        help_frame = ttk.LabelFrame(paned, text="📌 使用说明")
        paned.add(help_frame, weight=1)

        help_text = tk.Text(help_frame, wrap=tk.WORD, font=("微软雅黑", 10), padx=10, pady=10)
        help_text.pack(fill=tk.BOTH, expand=True)
        scroll_help = ttk.Scrollbar(help_text, command=help_text.yview)
        help_text.configure(yscrollcommand=scroll_help.set)

        # 固定的帮助内容（您可自定义）      todo：此处记得改
        fixed_help = """【木子 PDF 转换器 使用说明】

    ▸ 本软件基于 AGPL 3.0 协议开源
    ▸ 集成 MinerU 云端解析引擎（感谢上海人工智能实验室 OpenDataLab）

    ————————— 核心功能 —————————
    ✓ 加密PDF自动处理（需输入密码）
    ✓ 页面范围选择（如 1-5,10）
    ✓ 公文/试卷优化（本地转换生效）

    ————————— 云端特性 —————————
    • 自动使用 MinerU 解析扫描件、公式、表格
    • 返回 Markdown 和 JSON 文件
    • 若云端不可用，自动降级本地转换
    """
        help_text.insert("1.0", fixed_help)
        help_text.config(state="disabled")

        # 下半部分：公告区域（权重1，占1/4高度）
        announce_frame = ttk.LabelFrame(paned, text="📢 最新公告")
        paned.add(announce_frame, weight=4)

        # 创建公告文本框，初始为只读
        announce_text = tk.Text(announce_frame, wrap=tk.WORD, font=("微软雅黑", 10), padx=10, pady=10, fg="#e67e22")
        announce_text.pack(fill=tk.BOTH, expand=True)
        scroll_ann = ttk.Scrollbar(announce_text, command=announce_text.yview)
        announce_text.configure(yscrollcommand=scroll_ann.set)
        announce_text.config(state="disabled")  # 锁定，禁止编辑

        # 异步获取公告并显示
        def update_announce():
            try:
                title, content = self.fetch_announcement()
                # 判断是否为有效公告（可根据实际情况调整）
                if "无法连接" in content or title == "暂无公告":
                    display_content = "✨ 暂时没有新的公告"
                else:
                    display_content = f"【{title}】\n\n{content}"
            except Exception:
                display_content = "✨ 暂时没有新的公告"

            # 临时启用，更新内容，再锁定
            announce_text.config(state="normal")
            announce_text.delete("1.0", tk.END)
            announce_text.insert("1.0", display_content)
            announce_text.config(state="disabled")

        # 启动线程获取公告，用 after 确保线程安全
        threading.Thread(target=lambda: self.root.after(0, update_announce), daemon=True).start()

        # 底部关闭按钮
        btn_frame = ttk.Frame(guide)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="关闭", command=guide.destroy).pack()


def main():
    root = tk.Tk()
    app = PDFConverterApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()