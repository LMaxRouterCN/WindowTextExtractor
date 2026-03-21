"""
窗口文本提取工具 v1.4.2
功能：拖动按钮到目标窗口，提取该窗口内的所有文本
优化：
1. 修复多线程操作UI导致潜在崩溃的问题（线程安全）
2. 结果文本框默认设为只读，防止误操作
3. 移除未使用的代码常量，优化异常捕获逻辑
4. 修复 GetWindowThreadProcessId 调用错误（应在 win32process 模块中）
"""

import tkinter as tk
from tkinter import messagebox, scrolledtext, colorchooser
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
        self.root.title("窗口文本提取工具 v1.4.2")
        
        # 窗口尺寸设置
        self.root.geometry("650x550")
        self.root.minsize(500, 400)
        self.root.resizable(True, True)

        # 拖动状态标志
        self.is_dragging = False
        self.drag_button = None

        # 完整的原始结果文本（用于筛选）
        self.full_result_text = ""
        
        # 当前提取到的所有标签类型
        self.available_tags = set()
        
        # 当前选中的筛选标签 (None 表示显示全部)
        self.current_filter = None

        # 默认颜色配置（控件类型 -> 颜色）
        self.color_settings = {
            "Button": "#2196F3",      # 蓝色
            "Edit": "#9C27B0",        # 紫色
            "Text": "#9C27B0",        # 紫色
            "TreeItem": "#4CAF50",    # 绿色
            "ComboBox": "#FF9800",    # 橙色
            "List": "#FF9800",        # 橙色
            "Document": "#795548",    # 棕色
            "MenuItem": "#009688",    # 青色
            "CheckBox": "#E91E63",    # 粉色
            "RadioButton": "#E91E63", # 粉色
            "Pane": "#607D8B",        # 蓝灰色
            "Window": "#F44336",      # 红色
            "Dialog": "#F44336",      # 红色
            "Title": "#F44336",       # 红色
            "default": "#333333"      # 默认颜色
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

        # 尝试导入 win32gui（窗口操作相关）
        try:
            import win32gui
            import win32con
            self.win32gui = win32gui
            self.win32con = win32con
            self.has_win32gui = True
            print("✓ win32gui 已加载")
        except ImportError:
            print("✗ win32gui 未安装")

        # 尝试导入 win32process（进程/线程相关）
        try:
            import win32process
            self.win32process = win32process
            self.has_win32process = True
            print("✓ win32process 已加载")
        except ImportError:
            print("✗ win32process 未安装")

        # 尝试导入 pywinauto（UI Automation）
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

        # 绑定鼠标滚轮事件
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        canvas.bind("<MouseWheel>", _on_mousewheel)
        
        def _bind_to_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            
        def _unbind_from_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
            
        canvas.bind("<Enter>", _bind_to_mousewheel)
        canvas.bind("<Leave>", _unbind_from_mousewheel)

        # 存储颜色标签引用
        color_labels = {}

        # 创建每种类型的颜色设置行
        for ctrl_type, color in self.color_settings.items():
            if ctrl_type == "default":
                continue

            row_frame = tk.Frame(scrollable_frame, padx=10, pady=5)
            row_frame.pack(fill=tk.X)

            # 类型名称
            name_label = tk.Label(
                row_frame,
                text=f"[{ctrl_type}]",
                font=("Consolas", 11, "bold"),
                width=18,
                anchor="w"
            )
            name_label.pack(side=tk.LEFT)

            # 颜色显示块（可点击）
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

            # 绑定点击事件
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

            # 颜色代码显示
            hex_label = tk.Label(
                row_frame,
                text=color,
                font=("Consolas", 9),
                fg="gray"
            )
            hex_label.pack(side=tk.LEFT)

            # 更新 hex_label 的回调
            def make_hex_updater(label, color_label):
                def updater(event):
                    label.config(text=color_label.cget("bg"))
                return updater
            
            color_label.bind("<ButtonRelease-1>", make_hex_updater(hex_label, color_label))

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 底部按钮
        btn_frame = tk.Frame(settings_window)
        btn_frame.pack(fill=tk.X, pady=10)

        def apply_colors():
            """应用颜色到结果文本"""
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
        """应用颜色设置到文本框的标签"""
        for ctrl_type, color in self.color_settings.items():
            tag_name = f"tag_{ctrl_type}"
            self.result_text.tag_configure(tag_name, foreground=color)

    def show_about(self):
        """显示关于对话框"""
        messagebox.showinfo(
            "关于",
            "窗口文本提取工具 v1.4.2\n\n"
            "功能：拖动按钮到目标窗口，提取所有文本\n"
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

        copy_button = tk.Button(
            bottom_frame,
            text="复制文本",
            font=("微软雅黑", 9),
            command=self.copy_result,
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

        # 绑定鼠标事件
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

        # ========== 4. 结果显示区域 ==========
        result_container = tk.Frame(self.root)
        result_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 标题栏
        result_header = tk.Frame(result_container, bg='#e0e0e0', height=30)
        result_header.pack(fill=tk.X)
        result_header.pack_propagate(False)

        header_label = tk.Label(
            result_header,
            text="提取结果",
            font=("微软雅黑", 10, "bold"),
            bg='#e0e0e0',
            fg='#333333'
        )
        header_label.pack(side=tk.LEFT, padx=5)

        # 筛选按钮
        self.filter_mb = tk.Menubutton(
            result_header,
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

        # 文本框容器
        text_frame = tk.Frame(result_container)
        text_frame.pack(fill=tk.BOTH, expand=True)

        # 创建滚动文本框
        self.result_text = scrolledtext.ScrolledText(
            text_frame,
            font=("Consolas", 10),
            wrap=tk.WORD,
            bg='#fafafa',
            state=tk.DISABLED  # 默认设为禁用（只读），防止误编辑
        )
        self.result_text.pack(fill=tk.BOTH, expand=True)
        
        self.set_result_text("等待拖动操作...\n")
        
        # 初始化颜色标签
        self.apply_tag_colors()

    def update_filter_menu(self):
        """更新筛选菜单项"""
        # 清空旧菜单
        self.filter_menu.delete(0, tk.END)

        # 添加"显示全部"选项
        self.filter_menu.add_command(
            label="📋 显示全部",
            command=lambda: self.apply_filter(None)
        )
        self.filter_menu.add_separator()

        # 添加标签类型选项（按字母排序）
        for tag in sorted(self.available_tags):
            self.filter_menu.add_command(
                label=f"[{tag}]",
                command=lambda t=tag: self.apply_filter(t)
            )

    def apply_filter(self, tag_type):
        """应用筛选过滤"""
        self.current_filter = tag_type
        if not self.full_result_text:
            return

        if tag_type is None:
            # 显示全部
            self.render_text(self.full_result_text)
            self.filter_mb.config(text="筛选 ▼")
        else:
            # 筛选特定标签
            filtered_text = self.get_filtered_text(self.full_result_text, tag_type)
            self.render_text(filtered_text)
            self.filter_mb.config(text=f"筛选: [{tag_type}] ▼")

    def get_filtered_text(self, text, tag_type):
        """获取筛选后的文本"""
        lines = text.split('\n')
        filtered_lines = []

        # 总是保留的行（头部信息）
        keep_patterns = [
            r'^=+$',            # 分隔线
            r'^窗口句柄:',
            r'^鼠标位置:',
            r'^【方法\d+：',    # 方法标题
        ]

        for line in lines:
            should_keep = False
            # 检查是否为保留行
            for pattern in keep_patterns:
                if re.match(pattern, line):
                    should_keep = True
                    break
            
            # 或者包含目标标签
            if f'[{tag_type}]' in line:
                should_keep = True

            if should_keep:
                filtered_lines.append(line)

        return '\n'.join(filtered_lines)

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

        # 获取屏幕坐标
        x = self.root.winfo_pointerx()
        y = self.root.winfo_pointery()

        # 在新线程中提取文本
        thread = threading.Thread(target=self.extract_text_at_position, args=(x, y))
        thread.daemon = True
        thread.start()

    def extract_text_at_position(self, x, y):
        """在指定屏幕位置提取窗口文本 (运行在后台线程)"""
        try:
            # 优先使用 win32gui 获取窗口句柄
            if self.has_win32gui:
                hwnd = self.win32gui.WindowFromPoint((x, y))
            else:
                # 备用方案：使用 ctypes
                class POINT(ctypes.Structure):
                    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
                
                user32.WindowFromPoint.argtypes = [POINT]
                user32.WindowFromPoint.restype = wintypes.HWND
                hwnd = user32.WindowFromPoint(POINT(x, y))

            if not hwnd:
                self.safe_update_ui("未找到窗口", "提取失败", "🎯 拖动我到目标窗口")
                return

            # 获取顶层父窗口
            root_hwnd = self.get_root_window(hwnd)

            # 收集所有文本
            all_texts = []
            all_texts.append(f"{'='*60}")
            all_texts.append(f"窗口句柄: {root_hwnd} (0x{root_hwnd:X})")
            all_texts.append(f"鼠标位置: ({x}, {y})")
            all_texts.append(f"{'='*60}\n")

            # 方法1：使用pywinauto
            if self.has_pywinauto:
                all_texts.append("【方法1：pywinauto - UI Automation】")
                try:
                    texts = self.extract_with_pywinauto(root_hwnd)
                    all_texts.extend(texts if texts else [" (未提取到文本)"])
                except Exception as e:
                    all_texts.append(f" 错误: {str(e)}")
                all_texts.append("")

            # 方法2：使用win32gui枚举子窗口
            if self.has_win32gui:
                all_texts.append("【方法2：win32gui - 枚举子窗口】")
                try:
                    texts = self.extract_with_win32gui(root_hwnd)
                    all_texts.extend(texts if texts else [" (未提取到文本)"])
                except Exception as e:
                    all_texts.append(f" 错误: {str(e)}")
                all_texts.append("")

            # 方法3：使用win32gui获取窗口标题和类名
            if self.has_win32gui:
                all_texts.append("【方法3：win32gui - 窗口基本信息】")
                try:
                    texts = self.extract_window_info(root_hwnd)
                    all_texts.extend(texts)
                except Exception as e:
                    all_texts.append(f" 错误: {str(e)}")
                all_texts.append("")

            # 方法4：递归枚举所有子窗口控件
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
        """
        线程安全地更新UI
        使用 root.after 将更新操作调度到主线程
        """
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
                # 增加异常捕获，防止个别控件导致遍历中断
                for control in window.descendants():
                    try:
                        text = control.window_text()
                        if text and text.strip():
                            ctrl_type = control.element_info.control_type
                            texts.append(f" [{ctrl_type}] {text}")
                    except Exception:
                        # 忽略无法访问的控件
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
                length = user32.SendMessageW(child_hwnd, 0x000E, 0, 0) # WM_GETTEXTLENGTH
                if length > 0:
                    buffer = ctypes.create_unicode_buffer(length + 1)
                    user32.SendMessageW(child_hwnd, 0x000D, length + 1, buffer) # WM_GETTEXT
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
        
        # 窗口标题
        title = self.win32gui.GetWindowText(hwnd)
        texts.append(f" 窗口标题: {title if title else '(无)'}")
        
        # 窗口类名
        class_name = self.win32gui.GetClassName(hwnd)
        texts.append(f" 窗口类名: {class_name}")
        
        # 窗口位置
        rect = self.win32gui.GetWindowRect(hwnd)
        texts.append(f" 窗口位置: {rect}")
        
        # 控件ID
        window_id = self.win32gui.GetDlgCtrlID(hwnd)
        texts.append(f" 控件ID: {window_id}")
        
        # 进程ID和线程ID（使用 win32process 模块）
        # 修复：GetWindowThreadProcessId 在 win32process 模块中，而非 win32gui
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

    def set_result_text(self, text):
        """设置结果文本（处理只读状态）"""
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, text)
        self.result_text.config(state=tk.DISABLED)

    def update_result(self, text):
        """更新结果显示（带语法高亮）"""
        # 保存完整文本
        self.full_result_text = text

        # 提取所有标签类型
        self.available_tags = set()
        pattern = re.compile(r'\[([\w\s]+)\]')
        for match in pattern.finditer(text):
            self.available_tags.add(match.group(1))

        # 更新筛选菜单
        self.update_filter_menu()

        # 检查并应用当前筛选状态
        if self.current_filter and self.current_filter in self.available_tags:
            filtered_text = self.get_filtered_text(text, self.current_filter)
            self.render_text(filtered_text)
            self.filter_mb.config(text=f"筛选: [{self.current_filter}] ▼")
        else:
            if self.current_filter:
                self.current_filter = None
                self.filter_mb.config(text="筛选 ▼")
            self.render_text(text)

    def render_text(self, text):
        """渲染文本（带语法高亮）"""
        # 解锁文本框
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)

        pattern = re.compile(r'(\[[\w\s]+\])')
        last_end = 0

        for match in pattern.finditer(text):
            start = match.start()
            end = match.end()

            # 插入匹配前的普通文本
            if start > last_end:
                self.result_text.insert(tk.END, text[last_end:start])

            tag_content = match.group(1)
            ctrl_type = tag_content[1:-1]

            # 确定使用的颜色标签
            tag_name = f"tag_{ctrl_type}"

            if ctrl_type not in self.color_settings:
                self.color_settings[ctrl_type] = self.color_settings.get("default", "#333333")
                self.result_text.tag_configure(tag_name, foreground=self.color_settings[ctrl_type])

            self.result_text.insert(tk.END, tag_content, tag_name)
            last_end = end

        # 插入剩余的普通文本
        if last_end < len(text):
            self.result_text.insert(tk.END, text[last_end:])

        self.result_text.see(tk.END)
        # 锁定文本框
        self.result_text.config(state=tk.DISABLED)

    def clear_result(self):
        """清空结果"""
        self.full_result_text = ""
        self.available_tags = set()
        self.current_filter = None
        self.set_result_text("等待拖动操作...\n")
        self.filter_mb.config(text="筛选 ▼")
        self.status_label.config(text="就绪", fg='#666666')

    def copy_result(self):
        """复制结果到剪贴板"""
        # 获取实际显示的文本（包括筛选后的）
        text = self.result_text.get(1.0, tk.END)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_label.config(text="已复制到剪贴板", fg='#4caf50')

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
