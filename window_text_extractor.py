"""
窗口文本提取工具 v1.5.0
功能：拖动按钮到目标窗口，提取该窗口内的所有文本
新增：
1. 结果分区块显示（头部信息+各方法区块）
2. 每个区块独立线框、独立复制按钮
3. Ctrl+A只选中当前区块
4. 底部"复制原始文本"按钮
"""

import tkinter as tk
from tkinter import messagebox, colorchooser
import threading
import ctypes
from ctypes import wintypes
import re

# 加载Windows API
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


class WindowTextExtractor:
    """窗口文本提取器主类"""

    def __init__(self, root):
        """初始化主窗口"""
        self.root = root
        self.root.title("窗口文本提取工具 v1.5.0")
        
        # 窗口尺寸设置
        self.root.geometry("700x600")
        self.root.minsize(500, 400)
        self.root.resizable(True, True)

        # 拖动状态标志
        self.is_dragging = False

        # 完整的原始结果文本
        self.full_result_text = ""
        
        # 解析后的区块数据
        self.sections_data = {
            "header": "",      # 头部信息
            "sections": []     # 各方法区块列表
        }
        
        # 当前提取到的所有标签类型
        self.available_tags = set()
        
        # 当前选中的筛选标签
        self.current_filter = None

        # 默认颜色配置（控件类型 -> 颜色）
        self.color_settings = {
            "Button": "#2196F3",
            "Edit": "#9C27B0",
            "Text": "#9C27B0",
            "TreeItem": "#4CAF50",
            "ComboBox": "#FF9800",
            "List": "#FF9800",
            "Document": "#795548",
            "MenuItem": "#009688",
            "CheckBox": "#E91E63",
            "RadioButton": "#E91E63",
            "Pane": "#607D8B",
            "Window": "#F44336",
            "Dialog": "#F44336",
            "Title": "#F44336",
            "default": "#333333"
        }

        # 尝试导入依赖库
        self.check_dependencies()
        
        # 创建菜单栏
        self.create_menu()
        
        # 创建界面
        self.create_widgets()
        
        # 设置窗口始终置顶
        self.root.attributes('-topmost', True)

    def check_dependencies(self):
        """检查并导入必要的依赖库"""
        self.has_pywinauto = False
        self.has_win32gui = False
        self.has_win32process = False

        try:
            import win32gui
            import win32con
            self.win32gui = win32gui
            self.win32con = win32con
            self.has_win32gui = True
            print("✓ win32gui 已加载")
        except ImportError:
            print("✗ win32gui 未安装")

        try:
            import win32process
            self.win32process = win32process
            self.has_win32process = True
            print("✓ win32process 已加载")
        except ImportError:
            print("✗ win32process 未安装")

        try:
            from pywinauto import Desktop
            self.Desktop = Desktop
            self.has_pywinauto = True
            print("✓ pywinauto 已加载")
        except ImportError:
            print("✗ pywinauto 未安装")

        if not self.has_pywinauto and not self.has_win32gui:
            messagebox.showerror(
                "依赖缺失",
                "请至少安装以下之一：\n"
                "1. pip install pywin32\n"
                "2. pip install pywinauto\n\n"
                "推荐同时安装两者以获得最佳兼容性"
            )

    def create_menu(self):
        """创建菜单栏"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # 设置菜单
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="设置", menu=settings_menu)
        settings_menu.add_command(label="自定义标签颜色...", command=self.open_color_settings)

        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="关于", command=self.show_about)

    def open_color_settings(self):
        """打开颜色设置窗口"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("颜色设置")
        settings_window.geometry("450x500")
        settings_window.resizable(False, False)
        settings_window.transient(self.root)
        settings_window.grab_set()

        # 标题
        title = tk.Label(
            settings_window,
            text="点击颜色块修改对应控件类型的标签颜色",
            font=("微软雅黑", 10),
            pady=10
        )
        title.pack()

        # 创建滚动区域
        canvas = tk.Canvas(settings_window)
        scrollbar = tk.Scrollbar(settings_window, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        canvas.bind("<MouseWheel>", _on_mousewheel)
        
        def _bind_to_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            
        def _unbind_from_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
            
        canvas.bind("<Enter>", _bind_to_mousewheel)
        canvas.bind("<Leave>", _unbind_from_mousewheel)

        color_labels = {}

        for ctrl_type, color in self.color_settings.items():
            if ctrl_type == "default":
                continue

            row_frame = tk.Frame(scrollable_frame, padx=10, pady=5)
            row_frame.pack(fill=tk.X)

            name_label = tk.Label(
                row_frame,
                text=f"[{ctrl_type}]",
                font=("Consolas", 11, "bold"),
                width=18,
                anchor="w"
            )
            name_label.pack(side=tk.LEFT)

            color_label = tk.Label(
                row_frame,
                bg=color,
                width=6,
                height=1,
                relief=tk.RAISED,
                cursor="hand2"
            )
            color_label.pack(side=tk.LEFT, padx=10)
            color_labels[ctrl_type] = color_label

            def make_callback(ctrl_type, label):
                def callback(event):
                    color = colorchooser.askcolor(
                        title=f"选择 [{ctrl_type}] 的颜色",
                        initialcolor=label.cget("bg"),
                        parent=settings_window
                    )
                    if color[1]:
                        label.config(bg=color[1])
                        self.color_settings[ctrl_type] = color[1]
                return callback
            
            color_label.bind("<Button-1>", make_callback(ctrl_type, color_label))

            hex_label = tk.Label(
                row_frame,
                text=color,
                font=("Consolas", 9),
                fg="gray"
            )
            hex_label.pack(side=tk.LEFT)

            def make_hex_updater(label, color_label):
                def updater(event):
                    label.config(text=color_label.cget("bg"))
                return updater
            
            color_label.bind("<ButtonRelease-1>", make_hex_updater(hex_label, color_label))

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        btn_frame = tk.Frame(settings_window)
        btn_frame.pack(fill=tk.X, pady=10)

        def apply_colors():
            self.apply_tag_colors()
            messagebox.showinfo("成功", "颜色设置已应用！", parent=settings_window)

        apply_btn = tk.Button(
            btn_frame,
            text="应用",
            font=("微软雅黑", 9),
            command=apply_colors,
            width=10
        )
        apply_btn.pack(side=tk.RIGHT, padx=10)

        close_btn = tk.Button(
            btn_frame,
            text="关闭",
            font=("微软雅黑", 9),
            command=settings_window.destroy,
            width=10
        )
        close_btn.pack(side=tk.RIGHT)

    def apply_tag_colors(self):
        """应用颜色设置到所有区块的文本标签"""
        for ctrl_type, color in self.color_settings.items():
            tag_name = f"tag_{ctrl_type}"
            # 应用到所有区块的文本框
            for section in self.sections_data["sections"]:
                if "text_widget" in section:
                    section["text_widget"].tag_configure(tag_name, foreground=color)

    def show_about(self):
        """显示关于对话框"""
        messagebox.showinfo(
            "关于",
            "窗口文本提取工具 v1.5.0\n\n"
            "功能：拖动按钮到目标窗口，提取所有文本\n"
            "支持分区块显示、独立复制\n"
            "支持语法高亮显示控件类型标签\n"
            "支持结果筛选过滤\n\n"
            "依赖库：\n"
            "- pywin32\n"
            "- pywinauto\n"
            "- comtypes"
        )

    def create_widgets(self):
        """创建界面组件"""
        # ========== 1. 底部按钮区域 ==========
        bottom_frame = tk.Frame(self.root)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

        clear_button = tk.Button(
            bottom_frame,
            text="清空结果",
            font=("微软雅黑", 9),
            command=self.clear_result,
            width=12
        )
        clear_button.pack(side=tk.LEFT, padx=5)

        # 改为"复制原始文本"
        copy_button = tk.Button(
            bottom_frame,
            text="复制原始文本",
            font=("微软雅黑", 9),
            command=self.copy_original_text,
            width=12
        )
        copy_button.pack(side=tk.LEFT, padx=5)

        self.status_label = tk.Label(
            bottom_frame,
            text="就绪",
            font=("微软雅黑", 9),
            fg='#666666'
        )
        self.status_label.pack(side=tk.RIGHT, padx=5)

        # ========== 2. 标题说明 ==========
        title_frame = tk.Frame(self.root, bg='#4a90e2', height=50)
        title_frame.pack(side=tk.TOP, fill=tk.X)
        title_frame.pack_propagate(False)

        title_label = tk.Label(
            title_frame,
            text="🔍 拖动下方按钮到目标窗口，自动提取所有文本",
            font=("微软雅黑", 11, "bold"),
            bg='#4a90e2',
            fg='white'
        )
        title_label.pack(expand=True)

        # ========== 3. 按钮区域 ==========
        button_frame = tk.Frame(self.root, bg='#f5f5f5')
        button_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        self.drag_button = tk.Button(
            button_frame,
            text="🎯 拖动我到目标窗口",
            font=("微软雅黑", 12, "bold"),
            bg='#ff6b6b',
            fg='white',
            activebackground='#ff5252',
            activeforeground='white',
            cursor='hand2',
            width=25,
            height=2,
            relief=tk.RAISED,
            bd=3
        )
        self.drag_button.pack(pady=10)

        self.drag_button.bind('<Button-1>', self.on_drag_start)
        self.drag_button.bind('<B1-Motion>', self.on_drag_motion)
        self.drag_button.bind('<ButtonRelease-1>', self.on_drag_release)

        hint_label = tk.Label(
            button_frame,
            text="提示：按住鼠标左键拖动此按钮到目标窗口上方，然后释放鼠标",
            font=("微软雅黑", 9),
            bg='#f5f5f5',
            fg='#666666'
        )
        hint_label.pack(pady=5)

        # ========== 4. 结果显示区域（使用Canvas滚动） ==========
        result_container = tk.Frame(self.root)
        result_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 顶部工具栏（筛选按钮）
        toolbar = tk.Frame(result_container, bg='#e0e0e0', height=30)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)

        # 左侧标题
        header_label = tk.Label(
            toolbar,
            text="提取结果",
            font=("微软雅黑", 10, "bold"),
            bg='#e0e0e0',
            fg='#333333'
        )
        header_label.pack(side=tk.LEFT, padx=5)

        # 筛选按钮
        self.filter_mb = tk.Menubutton(
            toolbar,
            text="筛选 ▼",
            font=("微软雅黑", 9),
            bg='#e0e0e0',
            fg='#666666',
            activebackground='#d0d0d0',
            activeforeground='#333333',
            cursor='hand2',
            relief=tk.FLAT,
            indicatoron=False,
            direction='below'
        )
        self.filter_mb.pack(side=tk.RIGHT, padx=5)

        self.filter_menu = tk.Menu(self.filter_mb, tearoff=0, font=("微软雅黑", 9))
        self.filter_mb.config(menu=self.filter_menu)

        def show_menu(event):
            self.filter_mb.after(100, lambda: self.filter_menu.post(
                self.filter_mb.winfo_rootx(),
                self.filter_mb.winfo_rooty() + self.filter_mb.winfo_height()
            ))
        
        self.filter_mb.bind("<Enter>", show_menu)

        # 创建滚动Canvas
        canvas_frame = tk.Frame(result_container)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.result_canvas = tk.Canvas(canvas_frame, bg='#f5f5f5', highlightthickness=0)
        scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=self.result_canvas.yview)
        
        self.scrollable_frame = tk.Frame(self.result_canvas, bg='#f5f5f5')
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.result_canvas.configure(scrollregion=self.result_canvas.bbox("all"))
        )

        self.result_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", width=660)
        self.result_canvas.configure(yscrollcommand=scrollbar.set)

        self.result_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 绑定Canvas宽度变化
        def configure_scroll_region(event):
            self.result_canvas.itemconfig("all", width=event.width)
        
        self.result_canvas.bind("<Configure>", configure_scroll_region)

        # 鼠标滚轮绑定
        def _on_mousewheel(event):
            self.result_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        self.result_canvas.bind("<MouseWheel>", _on_mousewheel)

        # 创建各个区块Frame（初始为空）
        self.create_section_frames()

    def create_section_frames(self):
        """创建各个区块的Frame"""
        # 清空现有区块
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # 1. 头部信息区块
        self.header_frame = self.create_section_frame(
            self.scrollable_frame,
            "📋 窗口信息",
            is_header=True
        )

        # 2. 方法区块列表
        self.method_frames = []
        
        method_titles = [
            "【方法1：pywinauto - UI Automation】",
            "【方法2：win32gui - 枚举子窗口】",
            "【方法3：win32gui - 窗口基本信息】",
            "【方法4：递归枚举所有控件】"
        ]

        for title in method_titles:
            frame = self.create_section_frame(self.scrollable_frame, title)
            self.method_frames.append(frame)

    def create_section_frame(self, parent, title, is_header=False):
        """
        创建单个区块Frame
        
        Args:
            parent: 父容器
            title: 区块标题
            is_header: 是否为头部信息区块
        
        Returns:
            包含区块信息的字典
        """
        # 外层容器（带边框）
        container = tk.Frame(
            parent,
            bg='white',
            relief=tk.GROOVE,
            bd=2,
            padx=0,
            pady=0
        )
        container.pack(fill=tk.X, padx=5, pady=5)

        # 标题栏
        title_bar = tk.Frame(container, bg='#e8e8e8', height=32)
        title_bar.pack(fill=tk.X)
        title_bar.pack_propagate(False)

        # 标题标签
        title_label = tk.Label(
            title_bar,
            text=title,
            font=("微软雅黑", 9, "bold"),
            bg='#e8e8e8',
            fg='#333333'
        )
        title_label.pack(side=tk.LEFT, padx=5)

        # 复制按钮容器（右侧）
        btn_container = tk.Frame(title_bar, bg='#e8e8e8')
        btn_container.pack(side=tk.RIGHT, padx=5)

        # 创建文本框
        text_frame = tk.Frame(container, bg='white')
        text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        text_widget = tk.Text(
            text_frame,
            font=("Consolas", 9),
            wrap=tk.WORD,
            bg='#fafafa',
            height=4,  # 初始高度
            relief=tk.FLAT,
            padx=5,
            pady=5
        )
        text_widget.pack(fill=tk.BOTH, expand=True)

        # 绑定Ctrl+A事件（只选中当前区块）
        text_widget.bind('<Control-a>', self.on_ctrl_a)

        # 创建复制按钮
        copy_with_btn = tk.Button(
            btn_container,
            text="📋含标题",
            font=("微软雅黑", 8),
            relief=tk.FLAT,
            bg='#e8e8e8',
            fg='#666666',
            activebackground='#d0d0d0',
            cursor='hand2'
        )
        copy_with_btn.pack(side=tk.LEFT, padx=2)

        copy_without_btn = tk.Button(
            btn_container,
            text="📄纯内容",
            font=("微软雅黑", 8),
            relief=tk.FLAT,
            bg='#e8e8e8',
            fg='#666666',
            activebackground='#d0d0d0',
            cursor='hand2'
        )
        copy_without_btn.pack(side=tk.LEFT, padx=2)

        # 返回区块信息字典
        section_info = {
            "container": container,
            "title_label": title_label,
            "title": title,
            "text_widget": text_widget,
            "copy_with_btn": copy_with_btn,
            "copy_without_btn": copy_without_btn,
            "is_header": is_header,
            "visible": True
        }

        # 绑定复制按钮事件
        copy_with_btn.config(command=lambda: self.copy_section(section_info, include_title=True))
        copy_without_btn.config(command=lambda: self.copy_section(section_info, include_title=False))

        return section_info

    def on_ctrl_a(self, event):
        """处理Ctrl+A事件，只选中当前区块"""
        text_widget = event.widget
        text_widget.tag_add(tk.SEL, "1.0", tk.END)
        text_widget.mark_set(tk.INSERT, "1.0")
        text_widget.see(tk.INSERT)
        return "break"  # 阻止默认行为

    def parse_result_text(self, text):
        """
        解析提取结果文本，分割为头部信息和各方法区块
        
        Args:
            text: 原始提取结果文本
        
        Returns:
            解析后的数据字典
        """
        result = {
            "header": "",
            "sections": []
        }

        # 分割文本
        parts = re.split(r'(【方法\d+：[^】]+】)', text)
        
        # 提取头部信息（分隔线和窗口句柄等）
        header_match = re.search(r'^=+[\s\S]*?=+\n*', text)
        if header_match:
            result["header"] = header_match.group(0).strip()

        # 提取各方法区块
        for i in range(1, len(parts), 2):
            if i + 1 < len(parts):
                title = parts[i].strip()
                content = parts[i + 1].strip()
                
                # 移除末尾的空行
                content = content.rstrip('\n')
                
                result["sections"].append({
                    "title": title,
                    "content": content,
                    "visible": True
                })

        return result

    def render_section_text(self, text_widget, text):
        """
        渲染带语法高亮的文本
        
        Args:
            text_widget: Text控件
            text: 要渲染的文本
        """
        text_widget.config(state=tk.NORMAL)
        text_widget.delete(1.0, tk.END)

        if not text:
            text_widget.insert(tk.END, "(无内容)")
            text_widget.config(state=tk.DISABLED)
            return

        pattern = re.compile(r'(\[[\w\s]+\])')
        last_end = 0

        for match in pattern.finditer(text):
            start = match.start()
            end = match.end()

            if start > last_end:
                text_widget.insert(tk.END, text[last_end:start])

            tag_content = match.group(1)
            ctrl_type = tag_content[1:-1]
            tag_name = f"tag_{ctrl_type}"

            if ctrl_type not in self.color_settings:
                self.color_settings[ctrl_type] = self.color_settings.get("default", "#333333")
            
            text_widget.tag_configure(tag_name, foreground=self.color_settings[ctrl_type])
            text_widget.insert(tk.END, tag_content, tag_name)
            last_end = end

        if last_end < len(text):
            text_widget.insert(tk.END, text[last_end:])

        text_widget.config(state=tk.DISABLED)

        # 动态调整高度
        line_count = int(text_widget.index(tk.END).split('.')[0])
        text_widget.config(height=max(3, min(line_count, 20)))

    def update_filter_menu(self):
        """更新筛选菜单项"""
        self.filter_menu.delete(0, tk.END)

        self.filter_menu.add_command(
            label="📋 显示全部",
            command=lambda: self.apply_filter(None)
        )
        self.filter_menu.add_separator()

        for tag in sorted(self.available_tags):
            self.filter_menu.add_command(
                label=f"[{tag}]",
                command=lambda t=tag: self.apply_filter(t)
            )

    def apply_filter(self, tag_type):
        """应用筛选过滤"""
        self.current_filter = tag_type
        
        if tag_type is None:
            # 显示全部
            self.filter_mb.config(text="筛选 ▼")
        else:
            self.filter_mb.config(text=f"筛选: [{tag_type}] ▼")

        # 重新渲染所有区块
        self.render_all_sections()

    def render_all_sections(self):
        """渲染所有区块"""
        # 渲染头部信息
        header_text = self.sections_data.get("header", "")
        if self.current_filter:
            # 筛选时也应用过滤
            header_text = self.get_filtered_text(header_text, self.current_filter)
        
        self.render_section_text(self.header_frame["text_widget"], header_text)
        self.header_frame["container"].pack(fill=tk.X, padx=5, pady=5)

        # 渲染各方法区块
        for i, section in enumerate(self.sections_data.get("sections", [])):
            if i >= len(self.method_frames):
                break

            frame = self.method_frames[i]
            content = section.get("content", "")
            
            # 应用筛选
            if self.current_filter:
                filtered_content = self.get_filtered_text(content, self.current_filter)
                # 如果筛选后没有内容，隐藏该区块
                if not filtered_content.strip():
                    frame["container"].pack_forget()
                    continue
                content = filtered_content

            frame["container"].pack(fill=tk.X, padx=5, pady=5)
            self.render_section_text(frame["text_widget"], content)

    def get_filtered_text(self, text, tag_type):
        """获取筛选后的文本"""
        lines = text.split('\n')
        filtered_lines = []

        keep_patterns = [
            r'^=+$',
            r'^窗口句柄:',
            r'^鼠标位置:',
            r'^【方法\d+：',
        ]

        for line in lines:
            should_keep = False
            for pattern in keep_patterns:
                if re.match(pattern, line):
                    should_keep = True
                    break
            
            if f'[{tag_type}]' in line:
                should_keep = True

            if should_keep:
                filtered_lines.append(line)

        return '\n'.join(filtered_lines)

    def copy_section(self, section_info, include_title=True):
        """
        复制单个区块内容
        
        Args:
            section_info: 区块信息字典
            include_title: 是否包含标题
        """
        text_widget = section_info["text_widget"]
        text = text_widget.get(1.0, tk.END).strip()
        
        if include_title:
            title = section_info["title"]
            text = f"{title}\n{text}"
        
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_label.config(text="已复制到剪贴板", fg='#4caf50')

    def copy_original_text(self):
        """复制完整的原始文本（底部按钮功能）"""
        if self.full_result_text:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.full_result_text)
            self.status_label.config(text="已复制原始文本", fg='#4caf50')
        else:
            self.status_label.config(text="无内容可复制", fg='#f44336')

    def on_drag_start(self, event):
        """拖动开始事件"""
        self.is_dragging = True
        self.drag_button.config(bg='#ff5252', text="正在拖动...")
        self.status_label.config(text="拖动中...", fg='#ff6b6b')
        self.drag_button.grab_set_global()

    def on_drag_motion(self, event):
        """拖动过程中事件"""
        pass

    def on_drag_release(self, event):
        """拖动释放事件"""
        if not self.is_dragging:
            return

        self.is_dragging = False
        self.drag_button.config(bg='#ff6b6b', text="🎯 拖动我到目标窗口", state=tk.DISABLED)
        self.drag_button.grab_release()

        self.status_label.config(text="正在提取文本...", fg='#4a90e2')
        self.root.update()

        x = self.root.winfo_pointerx()
        y = self.root.winfo_pointery()

        thread = threading.Thread(target=self.extract_text_at_position, args=(x, y))
        thread.daemon = True
        thread.start()

    def extract_text_at_position(self, x, y):
        """在指定屏幕位置提取窗口文本"""
        try:
            if self.has_win32gui:
                hwnd = self.win32gui.WindowFromPoint((x, y))
            else:
                class POINT(ctypes.Structure):
                    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
                
                user32.WindowFromPoint.argtypes = [POINT]
                user32.WindowFromPoint.restype = wintypes.HWND
                hwnd = user32.WindowFromPoint(POINT(x, y))

            if not hwnd:
                self.safe_update_ui("未找到窗口", "提取失败", "🎯 拖动我到目标窗口")
                return

            root_hwnd = self.get_root_window(hwnd)

            all_texts = []
            all_texts.append(f"{'='*60}")
            all_texts.append(f"窗口句柄: {root_hwnd} (0x{root_hwnd:X})")
            all_texts.append(f"鼠标位置: ({x}, {y})")
            all_texts.append(f"{'='*60}\n")

            if self.has_pywinauto:
                all_texts.append("【方法1：pywinauto - UI Automation】")
                try:
                    texts = self.extract_with_pywinauto(root_hwnd)
                    all_texts.extend(texts if texts else [" (未提取到文本)"])
                except Exception as e:
                    all_texts.append(f" 错误: {str(e)}")
                all_texts.append("")

            if self.has_win32gui:
                all_texts.append("【方法2：win32gui - 枚举子窗口】")
                try:
                    texts = self.extract_with_win32gui(root_hwnd)
                    all_texts.extend(texts if texts else [" (未提取到文本)"])
                except Exception as e:
                    all_texts.append(f" 错误: {str(e)}")
                all_texts.append("")

            if self.has_win32gui:
                all_texts.append("【方法3：win32gui - 窗口基本信息】")
                try:
                    texts = self.extract_window_info(root_hwnd)
                    all_texts.extend(texts)
                except Exception as e:
                    all_texts.append(f" 错误: {str(e)}")
                all_texts.append("")

            if self.has_win32gui:
                all_texts.append("【方法4：递归枚举所有控件】")
                try:
                    texts = self.extract_all_controls(root_hwnd)
                    all_texts.extend(texts if texts else [" (未提取到文本)"])
                except Exception as e:
                    all_texts.append(f" 错误: {str(e)}")
                all_texts.append("")

            result = '\n'.join(all_texts)
            self.safe_update_ui(result, "提取完成", "🎯 拖动我到目标窗口")

        except Exception as e:
            self.safe_update_ui(f"提取失败: {str(e)}", "提取失败", "🎯 拖动我到目标窗口")

    def safe_update_ui(self, result_text, status_text, button_text):
        """线程安全地更新UI"""
        def update():
            self.drag_button.config(state=tk.NORMAL, text=button_text)
            self.status_label.config(text=status_text, fg='#4caf50' if "完成" in status_text else '#f44336')
            self.update_result(result_text)
            
        self.root.after(0, update)

    def get_root_window(self, hwnd):
        """获取顶层父窗口"""
        if not self.has_win32gui:
            return hwnd
        while True:
            parent = self.win32gui.GetParent(hwnd)
            if parent == 0:
                break
            hwnd = parent
        return hwnd

    def extract_with_pywinauto(self, hwnd):
        """使用pywinauto提取文本"""
        texts = []
        try:
            desktop = self.Desktop(backend="uia")
            window = desktop.window(handle=hwnd)
            
            try:
                title = window.window_text()
                if title:
                    texts.append(f" 窗口标题: {title}")
            except:
                pass

            try:
                for control in window.descendants():
                    try:
                        text = control.window_text()
                        if text and text.strip():
                            ctrl_type = control.element_info.control_type
                            texts.append(f" [{ctrl_type}] {text}")
                    except Exception:
                        continue
            except Exception as e:
                texts.append(f" 遍历控件时出错: {str(e)}")
                
        except Exception as e:
            texts.append(f" 连接窗口失败: {str(e)}")
            
        return texts

    def extract_with_win32gui(self, hwnd):
        """使用win32gui枚举子窗口提取文本"""
        texts = []
        control_count = [0]

        def enum_child_proc(child_hwnd, lparam):
            control_count[0] += 1
            text = self.win32gui.GetWindowText(child_hwnd)
            class_name = self.win32gui.GetClassName(child_hwnd)
            
            try:
                length = user32.SendMessageW(child_hwnd, 0x000E, 0, 0)
                if length > 0:
                    buffer = ctypes.create_unicode_buffer(length + 1)
                    user32.SendMessageW(child_hwnd, 0x000D, length + 1, buffer)
                    msg_text = buffer.value
                    if msg_text and msg_text != text:
                        text = msg_text
            except:
                pass

            if text and text.strip():
                texts.append(f" [{class_name}] {text}")
            return True

        self.win32gui.EnumChildWindows(hwnd, enum_child_proc, 0)
        texts.insert(0, f" 找到 {control_count[0]} 个子控件")
        return texts

    def extract_window_info(self, hwnd):
        """提取窗口基本信息"""
        texts = []
        
        title = self.win32gui.GetWindowText(hwnd)
        texts.append(f" 窗口标题: {title if title else '(无)'}")
        
        class_name = self.win32gui.GetClassName(hwnd)
        texts.append(f" 窗口类名: {class_name}")
        
        rect = self.win32gui.GetWindowRect(hwnd)
        texts.append(f" 窗口位置: {rect}")
        
        window_id = self.win32gui.GetDlgCtrlID(hwnd)
        texts.append(f" 控件ID: {window_id}")
        
        if self.has_win32process:
            try:
                thread_id, process_id = self.win32process.GetWindowThreadProcessId(hwnd)
                texts.append(f" 进程ID: {process_id}, 线程ID: {thread_id}")
            except Exception as e:
                texts.append(f" 进程ID/线程ID 获取失败: {str(e)}")
        else:
            texts.append(f" 进程ID/线程ID: 需要 win32process 模块支持")
        
        return texts

    def extract_all_controls(self, hwnd, indent=0):
        """递归提取所有控件信息"""
        texts = []

        def recursive_enum(parent_hwnd, level):
            def enum_proc(hwnd, lparam):
                text = self.win32gui.GetWindowText(hwnd)
                class_name = self.win32gui.GetClassName(hwnd)
                
                try:
                    buffer = ctypes.create_unicode_buffer(1024)
                    user32.SendMessageW(hwnd, 0x000D, 1024, buffer)
                    if buffer.value and buffer.value != text:
                        text = buffer.value
                except:
                    pass

                ind = " " * level
                if text and text.strip():
                    texts.append(f"{ind}[{class_name}] {text}")
                else:
                    texts.append(f"{ind}[{class_name}] (无文本)")
                    
                recursive_enum(hwnd, level + 1)
                return True

            self.win32gui.EnumChildWindows(parent_hwnd, enum_proc, 0)

        recursive_enum(hwnd, 0)
        return texts

    def update_result(self, text):
        """更新结果显示"""
        # 保存完整原始文本
        self.full_result_text = text

        # 解析文本为各个区块
        self.sections_data = self.parse_result_text(text)

        # 提取所有标签类型
        self.available_tags = set()
        pattern = re.compile(r'\[([\w\s]+)\]')
        for match in pattern.finditer(text):
            self.available_tags.add(match.group(1))

        # 更新筛选菜单
        self.update_filter_menu()

        # 渲染所有区块
        self.render_all_sections()

    def clear_result(self):
        """清空结果"""
        self.full_result_text = ""
        self.sections_data = {"header": "", "sections": []}
        self.available_tags = set()
        self.current_filter = None

        # 清空各区块文本
        self.render_section_text(self.header_frame["text_widget"], "")
        for frame in self.method_frames:
            self.render_section_text(frame["text_widget"], "")
            frame["container"].pack(fill=tk.X, padx=5, pady=5)

        self.filter_mb.config(text="筛选 ▼")
        self.status_label.config(text="就绪", fg='#666666')


def main():
    """主函数"""
    try:
        user32.SetProcessDPIAware()
    except:
        pass

    root = tk.Tk()
    try:
        root.iconbitmap('icon.ico')
    except:
        pass
        
    app = WindowTextExtractor(root)
    root.mainloop()


if __name__ == "__main__":
    main()
