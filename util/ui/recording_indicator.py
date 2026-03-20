"""
录音状态浮动指示器（macOS NSPanel 方案）

使用 NSPanel + NSWindowStyleMaskNonactivatingPanel 创建不抢焦点的浮动窗口。
这是 macOS 原生语音输入法使用的技术。
"""
import asyncio
import sys
from typing import Optional

from . import logger

# 动画帧
ANIMATION_FRAMES = [
    '∙∙∙  录音中',
    '●∙∙  录音中',
    '∙●∙  录音中',
    '∙∙●  录音中',
]
ANIMATION_INTERVAL = 0.15  # 150ms/帧


class RecordingIndicator:
    """录音状态浮动指示器（单例）

    使用 macOS NSPanel 创建不抢焦点的浮动窗口。
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
        self._panel = None
        self._label = None
        self._animation_task: Optional[asyncio.Task] = None

    def show(self, loop: asyncio.AbstractEventLoop) -> None:
        """显示录音指示器（线程安全）"""
        if sys.platform != 'darwin':
            return
        try:
            asyncio.run_coroutine_threadsafe(self._show_async(), loop)
        except Exception as e:
            logger.warning(f"RecordingIndicator show failed: {e}")

    def hide(self, loop: asyncio.AbstractEventLoop) -> None:
        """隐藏录音指示器（线程安全）"""
        if sys.platform != 'darwin':
            return
        try:
            asyncio.run_coroutine_threadsafe(self._hide_async(), loop)
        except Exception as e:
            logger.warning(f"RecordingIndicator hide failed: {e}")

    async def _show_async(self) -> None:
        """创建 NSPanel 并启动动画"""
        if self._panel is not None:
            return

        try:
            from AppKit import (
                NSApplication, NSApplicationActivationPolicyAccessory,
                NSPanel, NSFloatingWindowLevel,
                NSWindowStyleMaskNonactivatingPanel, NSWindowStyleMaskBorderless,
                NSBackingStoreBuffered,
                NSTextField, NSFont, NSColor, NSMakeRect,
                NSView, NSScreen,
            )
            from Quartz import CGEventGetLocation, CGEventCreate

            # 防止 Python 出现在 Dock
            app = NSApplication.sharedApplication()
            app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

            # 获取鼠标位置（Quartz 坐标系：左上角为原点）
            event = CGEventCreate(None)
            mouse = CGEventGetLocation(event)

            # 转换为 AppKit 坐标系（左下角为原点）
            screen_h = NSScreen.mainScreen().frame().size.height

            w, h = 105, 22
            x = mouse.x - w / 2
            y = screen_h - mouse.y + 5  # 鼠标上方一行距离

            # 创建不抢焦点的浮动面板
            panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                NSMakeRect(x, y, w, h),
                NSWindowStyleMaskNonactivatingPanel | NSWindowStyleMaskBorderless,
                NSBackingStoreBuffered,
                False,
            )
            panel.setLevel_(NSFloatingWindowLevel)
            panel.setOpaque_(False)
            panel.setHasShadow_(True)

            # 圆角 + 半透明深色背景
            panel.setBackgroundColor_(NSColor.clearColor())
            content = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, h))
            content.setWantsLayer_(True)
            content.layer().setCornerRadius_(6)
            content.layer().setBackgroundColor_(
                NSColor.colorWithRed_green_blue_alpha_(0.15, 0.15, 0.15, 0.75).CGColor()
            )
            panel.setContentView_(content)

            # 文字标签
            label = NSTextField.labelWithString_(ANIMATION_FRAMES[0])
            label.setFont_(NSFont.monospacedSystemFontOfSize_weight_(11, 0.0))
            label.setTextColor_(NSColor.colorWithRed_green_blue_alpha_(0.3, 1, 0.55, 1))
            label.setFrame_(NSMakeRect(8, 2, w - 16, 18))
            label.setDrawsBackground_(False)
            label.setBezeled_(False)
            label.setEditable_(False)
            label.setSelectable_(False)
            content.addSubview_(label)

            # 确保面板可见（sleep/wake 后可能需要重新激活）
            panel.setIsVisible_(True)
            panel.display()
            panel.orderFrontRegardless()

            # 刷新 AppKit 事件循环让面板渲染
            from Foundation import NSRunLoop, NSDate
            NSRunLoop.currentRunLoop().runUntilDate_(
                NSDate.dateWithTimeIntervalSinceNow_(0.05)
            )

            self._panel = panel
            self._label = label

            logger.info(f"RecordingIndicator 已显示: x={x:.0f}, y={y:.0f}, mouse=({mouse.x:.0f},{mouse.y:.0f}), screen_h={screen_h:.0f}")

            # 启动动画
            self._animation_task = asyncio.get_event_loop().create_task(
                self._animate_loop()
            )

        except Exception as e:
            logger.error(f"RecordingIndicator create failed: {e}", exc_info=True)

    async def _hide_async(self) -> None:
        """停止动画并关闭面板"""
        if self._animation_task and not self._animation_task.done():
            self._animation_task.cancel()
            self._animation_task = None

        if self._panel:
            try:
                self._panel.close()
                # 刷新 AppKit 事件循环让面板消失
                from Foundation import NSRunLoop, NSDate
                NSRunLoop.currentRunLoop().runUntilDate_(
                    NSDate.dateWithTimeIntervalSinceNow_(0.05)
                )
            except Exception:
                pass
            self._panel = None
            self._label = None

    async def _animate_loop(self) -> None:
        """动画循环"""
        from Foundation import NSRunLoop, NSDate
        frame = 0
        try:
            while True:
                await asyncio.sleep(ANIMATION_INTERVAL)
                frame = (frame + 1) % len(ANIMATION_FRAMES)
                if self._label:
                    self._label.setStringValue_(ANIMATION_FRAMES[frame])
                    # 刷新 AppKit 事件循环让面板更新
                    NSRunLoop.currentRunLoop().runUntilDate_(
                        NSDate.dateWithTimeIntervalSinceNow_(0.001)
                    )
        except asyncio.CancelledError:
            pass
