"""
录音状态浮动指示器

在录音时显示一个小型浮动窗口，带绿色圆点动画。
"""
import asyncio
from typing import Optional

from . import logger

# 动画帧（模拟 Rich 'point' spinner 的左到右流动效果）
ANIMATION_FRAMES = [
    '∙∙∙  录音中',
    '●∙∙  录音中',
    '∙●∙  录音中',
    '∙∙●  录音中',
]
ANIMATION_INTERVAL = 0.15  # 150ms/帧


class RecordingIndicator:
    """录音状态浮动指示器（单例）

    使用现有的 ToastMessageManager 创建一个小型浮动窗口，
    在录音期间显示动画指示器。

    线程安全：show/hide 可从任何线程调用。
    """

    _instance: Optional['RecordingIndicator'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._msg_id: Optional[str] = None
        self._animation_task: Optional[asyncio.Task] = None

    def show(self, loop: asyncio.AbstractEventLoop) -> None:
        """显示录音指示器（线程安全）"""
        try:
            asyncio.run_coroutine_threadsafe(self._show_async(), loop)
        except Exception as e:
            logger.warning(f"RecordingIndicator show failed: {e}")

    def hide(self, loop: asyncio.AbstractEventLoop) -> None:
        """隐藏录音指示器（线程安全）"""
        try:
            asyncio.run_coroutine_threadsafe(self._hide_async(), loop)
        except Exception as e:
            logger.warning(f"RecordingIndicator hide failed: {e}")

    async def _show_async(self) -> None:
        """创建指示器 toast 并启动动画"""
        if self._msg_id is not None:
            return

        from .toast_manager import ToastMessageManager, ToastMessage

        manager = ToastMessageManager()
        msg = ToastMessage(
            text=ANIMATION_FRAMES[0],
            font_size=11,
            font_family='',
            bg='#1a1a2e',
            fg='#00ff88',
            duration=0,
            initial_width=130,
            initial_height=32,
            streaming=True,
            window_type='label',
            stop_callback=None,
            markdown=False,
        )
        self._msg_id = manager.add_message(msg)

        # 等待窗口创建完成后重定位到右上角
        window = await manager.wait_for_window(self._msg_id, timeout=1.0)
        if window:
            self._reposition_window(window)

        # 启动动画
        self._animation_task = asyncio.get_event_loop().create_task(
            self._animate_loop()
        )

    async def _hide_async(self) -> None:
        """停止动画并关闭指示器"""
        if self._animation_task and not self._animation_task.done():
            self._animation_task.cancel()
            self._animation_task = None

        if self._msg_id:
            from .toast_manager import ToastMessageManager
            ToastMessageManager().close_toast(self._msg_id)
            self._msg_id = None

    async def _animate_loop(self) -> None:
        """动画循环：循环更新帧"""
        from .toast_manager import ToastMessageManager
        manager = ToastMessageManager()
        frame = 0

        try:
            while True:
                await asyncio.sleep(ANIMATION_INTERVAL)
                frame = (frame + 1) % len(ANIMATION_FRAMES)
                if self._msg_id:
                    manager.update_toast(self._msg_id, ANIMATION_FRAMES[frame])
        except asyncio.CancelledError:
            pass

    @staticmethod
    def _reposition_window(window) -> None:
        """将指示器定位到屏幕右上角"""
        try:
            screen_w = window.window.winfo_screenwidth()
            x = screen_w - 170
            y = 45  # 菜单栏下方
            window.window.geometry(f'130x32+{x}+{y}')
        except Exception as e:
            logger.warning(f"RecordingIndicator reposition failed: {e}")
