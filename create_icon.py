from PIL import Image, ImageDraw

def create_icon():
    # 1. 创建一个 256x256 的透明画布
    img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # --- 颜色定义 (取自你的程序界面) ---
    bg_color = '#4a90e2'       # 蓝色背景 (标题栏色)
    card_color = '#ffffff'     # 白色卡片
    text_color = '#e0e0e0'     # 文字纹理色
    accent_color = '#ff6b6b'   # 红色强调色 (按钮色)

    # 2. 绘制圆角背景
    # 为了兼容性，使用多个圆角和矩形拼接
    r = 50 # 圆角半径
    w, h = 256, 256
    draw.rectangle([r, 0, w-r, h], fill=bg_color)
    draw.rectangle([0, r, w, h-r], fill=bg_color)
    draw.pieslice([0, 0, r*2, r*2], 180, 270, fill=bg_color)
    draw.pieslice([w-r*2, 0, w, r*2], 270, 360, fill=bg_color)
    draw.pieslice([0, h-r*2, r*2, h], 90, 180, fill=bg_color)
    draw.pieslice([w-r*2, h-r*2, w, h], 0, 90, fill=bg_color)

    # 3. 绘制内部的“文档卡片”
    # 模拟提取结果区域的白色背景
    margin = 50
    card_rect = [margin, margin, w-margin, h-margin]
    draw.rounded_rectangle(card_rect, radius=15, fill=card_color, outline='#d0d0d0', width=2)

    # 4. 绘制文档标题栏
    title_h = 40
    draw.rectangle([margin, margin, w-margin, margin+title_h], fill='#f5f5f5')
    # 标题栏上的小圆点（模拟按钮）
    draw.ellipse([margin+15, margin+15, margin+30, margin+30], fill=accent_color)

    # 5. 绘制文字纹理线条
    line_h = 12
    line_gap = 20
    start_y = margin + title_h + 20
    
    for i in range(3):
        y = start_y + i * line_gap
        length = 100 - i*15 # 长度递减模拟真实文本
        draw.rectangle([margin+20, y, margin+20+length, y+line_h], fill=text_color)

    # 6. 绘制右上角的“靶心准星”
    # 象征“拖动定位”功能
    cx, cy = w - 60, 60 # 位置在右上角
    r_scope = 25
    
    # 外圈
    draw.ellipse([cx-r_scope, cy-r_scope, cx+r_scope, cy+r_scope], 
                 outline=accent_color, width=5)
    
    # 中心点
    draw.ellipse([cx-5, cy-5, cx+5, cy+5], fill=accent_color)
    
    # 十字线
    line_len = 10
    # 上
    draw.line([cx, cy-r_scope-line_len, cx, cy-r_scope+line_len], fill=accent_color, width=5)
    # 下
    draw.line([cx, cy+r_scope-line_len, cx, cy+r_scope+line_len], fill=accent_color, width=5)
    # 左
    draw.line([cx-r_scope-line_len, cy, cx-r_scope+line_len, cy], fill=accent_color, width=5)
    # 右
    draw.line([cx+r_scope-line_len, cy, cx+r_scope+line_len, cy], fill=accent_color, width=5)

    # 7. 保存为 .ico 文件 (包含多种尺寸以适配不同场景)
    icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save('icon.ico', format='ICO', sizes=icon_sizes)
    print("✅ 成功生成图标文件: icon.ico")

if __name__ == "__main__":
    create_icon()
