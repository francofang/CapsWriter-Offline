# coding: utf-8
"""
录音状态悬浮提示窗

macOS 上按住快捷键录音时，显示一个小的悬浮窗口作为视觉反馈。
使用 subprocess + Tkinter，避免与主线程的 asyncio 事件循环冲突。

架构：
- RecordingOverlay（父进程）：管理子进程，提供 show/hide 接口
- _run_overlay（子进程）：运行 Tkinter 窗口，读取 stdin 命令
"""

import os
import subprocess
import sys
from threading import Lock

# 仅在作为包模块导入时加载 logger（子进程模式不需要）
if __name__ != '__main__':
    from . import logger


class RecordingOverlay:
    """
    录音悬浮提示窗管理器（macOS 专用）

    通过子进程运行 Tkinter 悬浮窗，在录音开始时显示，结束时隐藏。
    子进程在客户端启动时创建，保持后台运行，避免每次录音的启动延迟。
    """

    def __init__(self):
        self._process = None
        self._lock = Lock()

    def start(self):
        """启动悬浮窗子进程"""
        if sys.platform != 'darwin':
            return

        try:
            self._process = subprocess.Popen(
                [sys.executable, '-u', os.path.abspath(__file__)],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("录音悬浮提示窗子进程已启动")
        except Exception as e:
            logger.warning(f"录音悬浮提示窗启动失败: {e}")
            self._process = None

    def show(self):
        """显示悬浮窗"""
        self._send('show')

    def hide(self):
        """隐藏悬浮窗"""
        self._send('hide')

    def cleanup(self):
        """关闭子进程"""
        self._send('quit')
        with self._lock:
            if self._process:
                try:
                    self._process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                self._process = None

    def _send(self, cmd: str):
        """向子进程发送命令"""
        with self._lock:
            if self._process and self._process.poll() is None:
                try:
                    self._process.stdin.write(f'{cmd}\n'.encode())
                    self._process.stdin.flush()
                except (BrokenPipeError, OSError):
                    pass


# ==================== 以下是子进程代码 ====================


def _set_macos_accessory_app():
    """
    通过 ObjC 运行时将进程设置为辅助应用，不在 Dock 显示、不抢焦点。
    """
    import ctypes
    import ctypes.util

    try:
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library('objc'))

        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        objc.objc_msgSend.restype = ctypes.c_void_p
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        NSApplication = objc.objc_getClass(b'NSApplication')
        app = objc.objc_msgSend(NSApplication,
                                objc.sel_registerName(b'sharedApplication'))

        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                      ctypes.c_long]
        # NSApplicationActivationPolicyAccessory = 1
        objc.objc_msgSend(app, objc.sel_registerName(b'setActivationPolicy:'), 1)
    except Exception:
        pass


def _draw_rounded_rect(canvas, x1, y1, x2, y2, radius, **kwargs):
    """在 Canvas 上绘制圆角矩形（使用 smooth polygon 近似）"""
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def _run_overlay():
    """子进程主函数：运行 Tkinter 悬浮窗"""
    import queue
    import threading
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()  # 初始隐藏

    # 设置为辅助应用（不在 Dock 显示）—— 必须在 Tk() 之后调用
    _set_macos_accessory_app()
    root.overrideredirect(True)
    root.attributes('-topmost', True)

    # macOS 透明背景（Tk 8.6+ on macOS 支持）
    use_transparent = False
    try:
        root.attributes('-transparent', True)
        root.config(bg='systemTransparent')
        use_transparent = True
    except tk.TclError:
        root.attributes('-alpha', 0.88)
        root.config(bg='#2D2D2D')

    # 窗口尺寸
    W, H = 160, 50
    PAD = 4

    canvas = tk.Canvas(root, width=W, height=H, highlightthickness=0, bd=0)
    canvas.config(bg='systemTransparent' if use_transparent else '#2D2D2D')
    canvas.pack()

    # 背景圆角矩形（仅透明模式需要手动绘制）
    if use_transparent:
        _draw_rounded_rect(canvas, PAD, PAD, W - PAD, H - PAD, 14,
                           fill='#2D2D2D', outline='')

    # 红色录音指示点
    dot_r = 6
    dot_cx, dot_cy = 30, H // 2
    dot_id = canvas.create_oval(
        dot_cx - dot_r, dot_cy - dot_r,
        dot_cx + dot_r, dot_cy + dot_r,
        fill='#FF3B30', outline='',
    )

    # "录音中" 文字
    canvas.create_text(
        95, H // 2,
        text='录音中',
        fill='white',
        font=('PingFang SC', 16, 'bold'),
    )

    # 窗口位置：屏幕底部居中
    root.update_idletasks()
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    x = (screen_w - W) // 2
    y = screen_h - H - 120
    root.geometry(f'{W}x{H}+{x}+{y}')

    # 红点呼吸动画
    dot_bright = True

    def pulse_dot():
        nonlocal dot_bright
        dot_bright = not dot_bright
        canvas.itemconfig(dot_id, fill='#FF3B30' if dot_bright else '#991F18')
        root.after(600, pulse_dot)

    pulse_dot()

    # stdin 命令读取（后台线程 → 队列 → Tk 主线程处理）
    cmd_queue = queue.Queue()

    def stdin_reader():
        try:
            for line in sys.stdin:
                cmd = line.strip()
                if cmd:
                    cmd_queue.put(cmd)
                if cmd == 'quit':
                    break
        except (EOFError, ValueError):
            cmd_queue.put('quit')

    threading.Thread(target=stdin_reader, daemon=True).start()

    def process_commands():
        try:
            while True:
                cmd = cmd_queue.get_nowait()
                if cmd == 'show':
                    root.deiconify()
                elif cmd == 'hide':
                    root.withdraw()
                elif cmd == 'quit':
                    root.quit()
                    return
        except queue.Empty:
            pass
        root.after(16, process_commands)

    root.after(16, process_commands)
    root.mainloop()


if __name__ == '__main__':
    _run_overlay()
