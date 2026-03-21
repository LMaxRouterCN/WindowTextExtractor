"""
窗口文本提取工具 v1.5.4
功能：拖动按钮到目标窗口，提取该窗口内的所有文本
修复：
1. 彻底重构滚轮事件处理逻辑，使用全局拦截解决 Windows 下焦点与悬停不一致问题。
2. 修复标题栏滚动失效问题。
3. 实现精确的焦点控制：点击文本框滚动内部，其余任何情况滚动整体。
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
        self.root.title("窗口文本提取工具 v1.5.4")
        
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

        # 区块高度限制开关 (默认关闭)
        self.limit_height = False
        
        # 限制模式下的最大行数
        self.max_display_lines = 15

        # 默认颜色配置
        self.color_settings = {
            "Button": "#2196F3", "Edit": "#9C27B0", "Text": "#9C27B0",
            "TreeItem": "#4CAF50", "ComboBox": "#FF9800", "List": "#FF9800",
            "Document": "#795548", "MenuItem": "#009688", "CheckBox": "#E91E63",
            "RadioButton": "#E91E63", "Pane": "#607D8B", "Window": "#F44336",
            "Dialog": "#F44336", "Title": "#F44336", "default": "#333333"
        }

        self.check_dependencies()
        self.create_menu()
        self.create_widgets()
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

        # 快捷按钮 - 限制区块高度
        self.limit_height_var = tk.BooleanVar(value=self.limit_height)
        menubar.add_checkbutton(
            label="限制区块高度",
            variable=self.limit_height_var,
            command=self.toggle_height_limit
        )

    def toggle_height_limit(self):
        """切换高度限制模式"""
        self.limit_height = self.limit_height_var.get()
        self.render_all_sections()

    def open_color_settings(self):
        """打开颜色设置窗口"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("颜色设置")
        settings_window.geometry("450x500")
        settings_window.resizable(False, False)
        settings_window.transient(self.root)
        settings_window.grab_set()

        title = tk.Label(settings_window, text="点击颜色块修改对应控件类型的标签颜色", font=("微软雅黑", 10), pady=10)
        title.pack()

        canvas = tk.Canvas(settings_window)
        scrollbar = tk.Scrollbar(settings_window, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # 这里的绑定不受全局影响，因为设置了 grab_set
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        canvas.bind("<MouseWheel>", _on_mousewheel)

        color_labels = {}
        for ctrl_type, color in self.color_settings.items():
            if ctrl_type == "default":
                continue

            row_frame = tk.Frame(scrollable_frame, padx=10, pady=5)
            row_frame.pack(fill=tk.X)

            name_label = tk.Label(row_frame, text=f"[{ctrl_type}]", font=("Consolas", 11, "bold"), width=18, anchor="w")
            name_label.pack(side=tk.LEFT)

            color_label = tk.Label(row_frame, bg=color, width=6, height=1, relief=tk.RAISED, cursor="hand2")
            color_label.pack(side=tk.LEFT, padx=10)
            color_labels[ctrl_type] = color_label

            def make_callback(ctrl_type, label):
                def callback(event):
                    color = colorchooser.askcolor(title=f"选择 [{ctrl_type}] 的颜色", initialcolor=label.cget("bg"), parent=settings_window)
                    if color[1]:
                        label.config(bg=color[1])
                        self.color_settings[ctrl_type] = color[1]
                return callback
            
            color_label.bind("<Button-1>", make_callback(ctrl_type, color_label))

            hex_label = tk.Label(row_frame, text=color, font=("Consolas", 9), fg="gray")
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

        apply_btn = tk.Button(btn_frame, text="应用", font=("微软雅黑", 9), command=apply_colors, width=10)
        apply_btn.pack(side=tk.RIGHT, padx=10)
        close_btn = tk.Button(btn_frame, text="关闭", font=("微软雅黑", 9), command=settings_window.destroy, width=10)
        close_btn.pack(side=tk.RIGHT)

    def apply_tag_colors(self):
        """应用颜色设置"""
        for ctrl_type, color in self.color_settings.items():
            tag_name = f"tag_{ctrl_type}"
            for section in self.sections_data["sections"]:
                if "text_widget" in section:
                    section["text_widget"].tag_configure(tag_name, foreground=color)

    def show_about(self):
        """显示关于对话框"""
        messagebox.showinfo("关于", "窗口文本提取工具 v1.5.4\n\n功能：拖动按钮到目标窗口，提取所有文本\n支持分区块显示、独立复制\n优化焦点与滚动交互逻辑\n\n依赖库：\n- pywin32\n- pywinauto\n- comtypes")

    def create_widgets(self):
        """创建界面组件"""
        # 1. 底部按钮区域
        bottom_frame = tk.Frame(self.root)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

        clear_button = tk.Button(bottom_frame, text="清空结果", font=("微软雅黑", 9), command=self.clear_result, width=12)
        clear_button.pack(side=tk.LEFT, padx=5)

        copy_button = tk.Button(bottom_frame, text="复制原始文本", font=("微软雅黑", 9), command=self.copy_original_text, width=12)
        copy_button.pack(side=tk.LEFT, padx=5)

        self.status_label = tk.Label(bottom_frame, text="就绪", font=("微软雅黑", 9), fg='#666666')
        self.status_label.pack(side=tk.RIGHT, padx=5)

        # 2. 标题说明
        title_frame = tk.Frame(self.root, bg='#4a90e2', height=50)
        title_frame.pack(side=tk.TOP, fill=tk.X)
        title_frame.pack_propagate(False)

        title_label = tk.Label(title_frame, text="🔍 拖动下方按钮到目标窗口，自动提取所有文本", font=("微软雅黑", 11, "bold"), bg='#4a90e2', fg='white')
        title_label.pack(expand=True)

        # 3. 按钮区域
        button_frame = tk.Frame(self.root, bg='#f5f5f5')
        button_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        self.drag_button = tk.Button(button_frame, text="🎯 拖动我到目标窗口", font=("微软雅黑", 12, "bold"), bg='#ff6b6b', fg='white', activebackground='#ff5252', activeforeground='white', cursor='hand2', width=25, height=2, relief=tk.RAISED, bd=3)
        self.drag_button.pack(pady=10)

        self.drag_button.bind('<Button-1>', self.on_drag_start)
        self.drag_button.bind('<B1-Motion>', self.on_drag_motion)
        self.drag_button.bind('<ButtonRelease-1>', self.on_drag_release)

        hint_label = tk.Label(button_frame, text="提示：按住鼠标左键拖动此按钮到目标窗口上方，然后释放鼠标", font=("微软雅黑", 9), bg='#f5f5f5', fg='#666666')
        hint_label.pack(pady=5)

        # 4. 结果显示区域
        result_container = tk.Frame(self.root)
        result_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 顶部工具栏
        toolbar = tk.Frame(result_container, bg='#e0e0e0', height=30)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)

        header_label = tk.Label(toolbar, text="提取结果", font=("微软雅黑", 10, "bold"), bg='#e0e0e0', fg='#333333')
        header_label.pack(side=tk.LEFT, padx=5)

        self.filter_mb = tk.Menubutton(toolbar, text="筛选 ▼", font=("微软雅黑", 9), bg='#e0e0e0', fg='#666666', activebackground='#d0d0d0', activeforeground='#333333', cursor='hand2', relief=tk.FLAT, indicatoron=False, direction='below')
        self.filter_mb.pack(side=tk.RIGHT, padx=5)

        self.filter_menu = tk.Menu(self.filter_mb, tearoff=0, font=("微软雅黑", 9))
        self.filter_mb.config(menu=self.filter_menu)

        def show_menu(event):
            self.filter_mb.after(100, lambda: self.filter_menu.post(self.filter_mb.winfo_rootx(), self.filter_mb.winfo_rooty() + self.filter_mb.winfo_height()))
        
        self.filter_mb.bind("<Enter>", show_menu)

        # 创建滚动Canvas
        canvas_frame = tk.Frame(result_container)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.result_canvas = tk.Canvas(canvas_frame, bg='#f5f5f5', highlightthickness=0)
        scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=self.result_canvas.yview)
        
        self.scrollable_frame = tk.Frame(self.result_canvas, bg='#f5f5f5')
        
        self.scrollable_frame.bind("<Configure>", lambda e: self.result_canvas.configure(scrollregion=self.result_canvas.bbox("all")))
        self.result_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", width=660)
        self.result_canvas.configure(yscrollcommand=scrollbar.set)

        self.result_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def configure_scroll_region(event):
            self.result_canvas.itemconfig("all", width=event.width)
        
        self.result_canvas.bind("<Configure>", configure_scroll_region)

        # === 核心：全局滚轮事件拦截 ===
        # 在应用级别绑定滚轮事件，优先于控件自身的处理
        self.root.bind_all("<MouseWheel>", self._on_global_mousewheel, add="+")

        self.create_section_frames()

    def _on_global_mousewheel(self, event):
        """
        全局滚轮事件处理中心
        解决 Windows 下滚轮事件只发送给焦点控件的问题
        """
        # 1. 检查事件发生时，鼠标是否在主窗口内
        # winfo_containing 返回鼠标下的控件，如果为 None 或不属于主窗口，则忽略
        x, y = event.x_root, event.y_root
        target_widget = self.root.winfo_containing(x, y)
        
        # 如果鼠标不在任何控件上，或者不在主窗口内（比如在设置窗口，设置窗口有grab_set，通常轮不到这里处理）
        if not target_widget:
            return

        # 检查是否在主窗口体系内
        try:
            # 递归检查父级，确保是在 self.root 内
            w = target_widget
            in_main_window = False
            while w:
                if w == self.root:
                    in_main_window = True
                    break
                w = w.master
            if not in_main_window:
                return
        except:
            return

        # 2. 获取当前键盘焦点控件
        focused_widget = self.root.focus_get()

        # 3. 逻辑判断
        # 情况A：限制模式关闭 -> 始终滚动整体
        if not self.limit_height:
            self.result_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break" # 阻止事件继续传播

        # 情况B：限制模式开启 -> 焦点优先逻辑
        # 只有当：1. 鼠标悬停在Text控件上 且 2. 该Text控件正好是当前焦点控件
        # 才滚动文本框内部，否则滚动整体
        
        if isinstance(target_widget, tk.Text) and target_widget == focused_widget:
            # 滚动文本框内部
            target_widget.yview_scroll(int(-1 * (event.delta / 120)), "units")
        else:
            # 滚动整体
            self.result_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        return "break" # 阻止事件继续传播，防止双重滚动

    def create_section_frames(self):
        """创建各个区块的Frame"""
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        self.header_frame = self.create_section_frame(self.scrollable_frame, "📋 窗口信息", is_header=True)

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
        """创建单个区块Frame"""
        # 外层容器
        container = tk.Frame(parent, bg='white', relief=tk.GROOVE, bd=2, padx=0, pady=0)
        container.pack(fill=tk.X, padx=5, pady=5)

        # 标题栏
        title_bar = tk.Frame(container, bg='#e8e8e8', height=32)
        title_bar.pack(fill=tk.X)
        title_bar.pack_propagate(False)

        title_label = tk.Label(title_bar, text=title, font=("微软雅黑", 9, "bold"), bg='#e8e8e8', fg='#333333')
        title_label.pack(side=tk.LEFT, padx=5)

        # 复制按钮容器
        btn_container = tk.Frame(title_bar, bg='#e8e8e8')
        btn_container.pack(side=tk.RIGHT, padx=5)

        # 文本框容器
        text_frame = tk.Frame(container, bg='white')
        text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        text_widget = tk.Text(text_frame, font=("Consolas", 9), wrap=tk.WORD, bg='#fafafa', height=4, relief=tk.FLAT, padx=5, pady=5)
        text_scrollbar = tk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.config(yscrollcommand=text_scrollbar.set)
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # --- 焦点管理逻辑 ---
        
        # 1. 点击标题栏/容器 -> 将焦点移回主窗口 root，确保任何文本框失去焦点
        def clear_focus(event):
            self.root.focus_set()
            
        title_bar.bind('<Button-1>', clear_focus)
        container.bind('<Button-1>', clear_focus)

        # 2. 点击文本框 -> 自动获取焦点（Text默认行为，无需额外代码）
        # 但我们需要确保焦点样式更新，或者不需要，因为我们使用全局事件
        
        # --- 结束修改 ---

        # Ctrl+A 全选
        text_widget.bind('<Control-a>', self.on_ctrl_a)

        copy_with_btn = tk.Button(btn_container, text="📋含标题", font=("微软雅黑", 8), relief=tk.FLAT, bg='#e8e8e8', fg='#666666', activebackground='#d0d0d0', cursor='hand2')
        copy_with_btn.pack(side=tk.LEFT, padx=2)

        copy_without_btn = tk.Button(btn_container, text="📄纯内容", font=("微软雅黑", 8), relief=tk.FLAT, bg='#e8e8e8', fg='#666666', activebackground='#d0d0d0', cursor='hand2')
        copy_without_btn.pack(side=tk.LEFT, padx=2)

        section_info = {
            "container": container, "title_label": title_label, "title": title,
            "text_widget": text_widget, "text_scrollbar": text_scrollbar,
            "copy_with_btn": copy_with_btn, "copy_without_btn": copy_without_btn,
            "is_header": is_header, "visible": True
        }

        copy_with_btn.config(command=lambda: self.copy_section(section_info, include_title=True))
        copy_without_btn.config(command=lambda: self.copy_section(section_info, include_title=False))

        return section_info

    def on_ctrl_a(self, event):
        """处理Ctrl+A事件"""
        text_widget = event.widget
        text_widget.tag_add(tk.SEL, "1.0", tk.END)
        text_widget.mark_set(tk.INSERT, "1.0")
        text_widget.see(tk.INSERT)
        return "break"

    def parse_result_text(self, text):
        """解析提取结果文本"""
        result = {"header": "", "sections": []}
        parts = re.split(r'(【方法\d+：[^】]+】)', text)
        header_match = re.search(r'^=+[\s\S]*?=+\n*', text)
        if header_match:
            result["header"] = header_match.group(0).strip()

        for i in range(1, len(parts), 2):
            if i + 1 < len(parts):
                title = parts[i].strip()
                content = parts[i + 1].strip().rstrip('\n')
                result["sections"].append({"title": title, "content": content, "visible": True})
        return result

    def render_section_text(self, section_info, text):
        """渲染文本，并根据模式控制高度和滚动条"""
        text_widget = section_info["text_widget"]
        scrollbar = section_info["text_scrollbar"]
        
        text_widget.config(state=tk.NORMAL)
        text_widget.delete(1.0, tk.END)

        if not text:
            text_widget.insert(tk.END, "(无内容)")
            text_widget.config(state=tk.DISABLED)
            scrollbar.pack_forget()
            text_widget.config(height=1)
            return

        # 渲染高亮
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

        line_count = int(text_widget.index(tk.END).split('.')[0])
        
        if self.limit_height:
            display_height = min(line_count, self.max_display_lines)
            text_widget.config(height=display_height)
            if line_count > self.max_display_lines:
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            else:
                scrollbar.pack_forget()
        else:
            text_widget.config(height=line_count)
            scrollbar.pack_forget()

    def update_filter_menu(self):
        """更新筛选菜单项"""
        self.filter_menu.delete(0, tk.END)
        self.filter_menu.add_command(label="📋 显示全部", command=lambda: self.apply_filter(None))
        self.filter_menu.add_separator()
        for tag in sorted(self.available_tags):
            self.filter_menu.add_command(label=f"[{tag}]", command=lambda t=tag: self.apply_filter(t))

    def apply_filter(self, tag_type):
        """应用筛选过滤"""
        self.current_filter = tag_type
        if tag_type is None:
            self.filter_mb.config(text="筛选 ▼")
        else:
            self.filter_mb.config(text=f"筛选: [{tag_type}] ▼")
        self.render_all_sections()

    def render_all_sections(self):
        """渲染所有区块"""
        header_text = self.sections_data.get("header", "")
        if self.current_filter:
            header_text = self.get_filtered_text(header_text, self.current_filter)
        
        self.render_section_text(self.header_frame, header_text)
        self.header_frame["container"].pack(fill=tk.X, padx=5, pady=5)

        for i, section in enumerate(self.sections_data.get("sections", [])):
            if i >= len(self.method_frames):
                break

            frame = self.method_frames[i]
            content = section.get("content", "")
            
            if self.current_filter:
                filtered_content = self.get_filtered_text(content, self.current_filter)
                if not filtered_content.strip():
                    frame["container"].pack_forget()
                    continue
                content = filtered_content

            frame["container"].pack(fill=tk.X, padx=5, pady=5)
            self.render_section_text(frame, content)

    def get_filtered_text(self, text, tag_type):
        """获取筛选后的文本"""
        lines = text.split('\n')
        filtered_lines = []
        keep_patterns = [r'^=+$', r'^窗口句柄:', r'^鼠标位置:', r'^【方法\d+：']
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
        """复制单个区块内容"""
        text_widget = section_info["text_widget"]
        text = text_widget.get(1.0, tk.END).strip()
        if include_title:
            title = section_info["title"]
            text = f"{title}\n{text}"
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_label.config(text="已复制到剪贴板", fg='#4caf50')

    def copy_original_text(self):
        """复制完整的原始文本"""
        if self.full_result_text:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.full_result_text)
            self.status_label.config(text="已复制原始文本", fg='#4caf50')
        else:
            self.status_label.config(text="无内容可复制", fg='#f44336')

    def on_drag_start(self, event):
        self.is_dragging = True
        self.drag_button.config(bg='#ff5252', text="正在拖动...")
        self.status_label.config(text="拖动中...", fg='#ff6b6b')
        self.drag_button.grab_set_global()

    def on_drag_motion(self, event):
        pass

    def on_drag_release(self, event):
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
        def update():
            self.drag_button.config(state=tk.NORMAL, text=button_text)
            self.status_label.config(text=status_text, fg='#4caf50' if "完成" in status_text else '#f44336')
            self.update_result(result_text)
        self.root.after(0, update)

    def get_root_window(self, hwnd):
        if not self.has_win32gui:
            return hwnd
        while True:
            parent = self.win32gui.GetParent(hwnd)
            if parent == 0:
                break
            hwnd = parent
        return hwnd

    def extract_with_pywinauto(self, hwnd):
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
        self.full_result_text = text
        self.sections_data = self.parse_result_text(text)
        self.available_tags = set()
        pattern = re.compile(r'\[([\w\s]+)\]')
        for match in pattern.finditer(text):
            self.available_tags.add(match.group(1))
        self.update_filter_menu()
        self.render_all_sections()

    def clear_result(self):
        self.full_result_text = ""
        self.sections_data = {"header": "", "sections": []}
        self.available_tags = set()
        self.current_filter = None
        self.render_section_text(self.header_frame, "")
        for frame in self.method_frames:
            self.render_section_text(frame, "")
            frame["container"].pack(fill=tk.X, padx=5, pady=5)
        self.filter_mb.config(text="筛选 ▼")
        self.status_label.config(text="就绪", fg='#666666')


def main():
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
