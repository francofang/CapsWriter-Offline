"""
录音状态浮动指示器（macOS NSPanel 波形方案）

使用 NSPanel + NSView 绘制实时音量波形条。
圆角胶囊形状，内部竖线随说话音量变化。
"""
import asyncio
import sys
from collections import deque
from typing import Optional

from . import logger

# 波形参数
BAR_COUNT = 24         # 竖线数量
BAR_WIDTH = 3          # 竖线宽度
BAR_GAP = 2            # 竖线间距
BAR_MIN_H = 4          # 最小高度（静音时）
BAR_MAX_H = 24         # 最大高度
PANEL_PADDING = 8      # 内边距
PANEL_H = 32           # 面板高度
PANEL_W = PANEL_PADDING * 2 + BAR_COUNT * (BAR_WIDTH + BAR_GAP) - BAR_GAP
CORNER_RADIUS = PANEL_H / 2  # 胶囊形
UPDATE_INTERVAL = 0.05  # 50ms 刷新


class RecordingIndicator:
    """录音状态浮动指示器（单例）

    使用 macOS NSPanel 创建不抢焦点的浮动窗口，显示实时音量波形。
    线程安全：show/hide/update_level 可从任何线程调用。
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
        self._bar_views = []
        self._levels = deque([0.0] * BAR_COUNT, maxlen=BAR_COUNT)
        self._animation_task: Optional[asyncio.Task] = None

    def update_level(self, rms: float) -> None:
        """更新音量级别（从音频回调线程调用，线程安全）

        Args:
            rms: 音频 RMS 值（0.0 ~ 1.0 范围，通常 0 ~ 0.3）
        """
        normalized = min(1.0, rms * 12.0)
        self._levels.append(normalized)

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
        """创建 NSPanel 并启动波形动画"""
        if self._panel is not None:
            return

        try:
            try:
                from AppKit import (
                    NSApplication, NSApplicationActivationPolicyAccessory,
                    NSPanel, NSFloatingWindowLevel,
                    NSWindowStyleMaskNonactivatingPanel, NSWindowStyleMaskBorderless,
                    NSBackingStoreBuffered,
                    NSColor, NSMakeRect, NSView, NSScreen,
                )
                from Quartz import CGEventGetLocation, CGEventCreate
            except ImportError:
                logger.warning("录音指示器需要 PyObjC，请运行: pip install pyobjc-framework-Cocoa pyobjc-framework-Quartz")
                return

            # 防止 Python 出现在 Dock
            app = NSApplication.sharedApplication()
            app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

            # 放在鼠标光标（输入焦点）正上方
            screen_h = NSScreen.mainScreen().frame().size.height

            event = CGEventCreate(None)
            mouse = CGEventGetLocation(event)

            x = mouse.x - PANEL_W / 2
            y = screen_h - mouse.y + 5  # 鼠标上方 5px（AppKit 坐标系）

            # 创建面板
            panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                NSMakeRect(x, y, PANEL_W, PANEL_H),
                NSWindowStyleMaskNonactivatingPanel | NSWindowStyleMaskBorderless,
                NSBackingStoreBuffered,
                False,
            )
            panel.setLevel_(NSFloatingWindowLevel)
            panel.setOpaque_(False)
            panel.setHasShadow_(True)

            # 圆角胶囊 + 半透明深色背景
            panel.setBackgroundColor_(NSColor.clearColor())
            content = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, PANEL_W, PANEL_H))
            content.setWantsLayer_(True)
            content.layer().setCornerRadius_(CORNER_RADIUS)
            content.layer().setBackgroundColor_(
                NSColor.colorWithRed_green_blue_alpha_(0.1, 0.1, 0.1, 0.85).CGColor()
            )
            panel.setContentView_(content)

            # 创建竖线（用 NSView + layer 背景色）
            bar_color = NSColor.colorWithRed_green_blue_alpha_(1.0, 0.6, 0.0, 0.9)
            bar_views = []
            for i in range(BAR_COUNT):
                bx = PANEL_PADDING + i * (BAR_WIDTH + BAR_GAP)
                by = (PANEL_H - BAR_MIN_H) / 2
                bar = NSView.alloc().initWithFrame_(NSMakeRect(bx, by, BAR_WIDTH, BAR_MIN_H))
                bar.setWantsLayer_(True)
                bar.layer().setCornerRadius_(BAR_WIDTH / 2)
                bar.layer().setBackgroundColor_(bar_color.CGColor())
                content.addSubview_(bar)
                bar_views.append(bar)

            # 显示面板
            panel.setIsVisible_(True)
            panel.display()
            panel.orderFrontRegardless()

            from Foundation import NSRunLoop, NSDate
            NSRunLoop.currentRunLoop().runUntilDate_(
                NSDate.dateWithTimeIntervalSinceNow_(0.05)
            )

            self._panel = panel
            self._bar_views = bar_views
            self._levels = deque([0.0] * BAR_COUNT, maxlen=BAR_COUNT)

            logger.info(
                f"RecordingIndicator 已显示: x={x:.0f}, y={y:.0f}, "
                f"mouse=({mouse.x:.0f},{mouse.y:.0f}), screen_h={screen_h:.0f}"
            )

            # 启动波形更新
            self._animation_task = asyncio.get_event_loop().create_task(
                self._update_loop()
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
                from Foundation import NSRunLoop, NSDate
                NSRunLoop.currentRunLoop().runUntilDate_(
                    NSDate.dateWithTimeIntervalSinceNow_(0.05)
                )
            except Exception:
                pass
            self._panel = None
            self._bar_views = []

    async def _update_loop(self) -> None:
        """波形更新循环"""
        from Foundation import NSRunLoop, NSDate
        from AppKit import NSMakeRect

        try:
            while True:
                await asyncio.sleep(UPDATE_INTERVAL)
                if not self._bar_views:
                    break

                levels = list(self._levels)
                for i, bar in enumerate(self._bar_views):
                    level = levels[i] if i < len(levels) else 0.0
                    h = BAR_MIN_H + level * (BAR_MAX_H - BAR_MIN_H)
                    bx = PANEL_PADDING + i * (BAR_WIDTH + BAR_GAP)
                    by = (PANEL_H - h) / 2
                    bar.setFrame_(NSMakeRect(bx, by, BAR_WIDTH, h))

                # 刷新渲染
                NSRunLoop.currentRunLoop().runUntilDate_(
                    NSDate.dateWithTimeIntervalSinceNow_(0.001)
                )

        except asyncio.CancelledError:
            pass
