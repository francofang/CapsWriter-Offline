# coding: utf-8
"""
快捷键管理器（重构版）

统一管理多个快捷键，处理键盘和鼠标事件，支持：
1. 多快捷键并发处理
2. 防止不同按键互相干扰
3. restore 功能的防自捕获逻辑
4. hold_mode 和 click_mode 支持

Windows: 使用 win32_event_filter 回调处理原始消息
macOS:   使用 on_press / on_release 回调处理 pynput Key 对象
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Dict, List, Optional

from pynput import keyboard, mouse

from . import logger
from util.client.shortcut.key_mapper import (
    KeyMapper, RESTORABLE_KEYS, pynput_key_to_name,
)
from util.client.shortcut.emulator import ShortcutEmulator
from util.client.shortcut.event_handler import ShortcutEventHandler
from util.client.shortcut.task import ShortcutTask

if sys.platform == 'win32':
    from util.client.shortcut.key_mapper import (
        KEYBOARD_MESSAGES, KEY_DOWN_MESSAGES, KEY_UP_MESSAGES,
        MOUSE_MESSAGES, WM_KEYUP, WM_SYSKEYUP,
        WM_XBUTTONDOWN, WM_XBUTTONUP, XBUTTON1,
    )

if TYPE_CHECKING:
    from util.client.shortcut.shortcut_config import Shortcut
    from util.client.state import ClientState


class ShortcutManager:
    """
    快捷键管理器

    统一管理多个快捷键，使用 pynput 监听键盘和鼠标事件。
    Windows: 使用 win32_event_filter 直接处理原始消息
    macOS:   使用 on_press / on_release 回调
    """

    def __init__(self, state: 'ClientState', shortcuts: List['Shortcut']):
        self.state = state
        self.shortcuts = shortcuts

        # 监听器
        self.keyboard_listener: Optional[keyboard.Listener] = None
        self.mouse_listener: Optional[mouse.Listener] = None

        # 快捷键任务映射（key -> ShortcutTask）
        self.tasks: Dict[str, ShortcutTask] = {}

        # 线程池
        self._pool = ThreadPoolExecutor(max_workers=4)

        # 按键模拟器
        self._emulator = ShortcutEmulator()

        # 按键恢复状态追踪
        self._restoring_keys = set()

        # 事件处理器
        self._event_handler = ShortcutEventHandler(self.tasks, self._pool, self._emulator)

        # macOS: 防自捕获用的 pressed 集合
        self._emulating_pressed = set()

        # 初始化快捷键任务
        self._init_tasks()

    def _init_tasks(self) -> None:
        """初始化所有快捷键任务"""
        from config_client import ClientConfig as Config

        for shortcut in self.shortcuts:
            if not shortcut.enabled:
                continue

            task = ShortcutTask(shortcut, self.state)
            task._manager_ref = lambda: self  # 弱引用，用于回调
            task.pool = self._pool
            task.threshold = shortcut.get_threshold(Config.threshold)
            self.tasks[shortcut.key] = task

    # ========== macOS: on_press / on_release 回调 ==========

    def _on_key_press(self, key):
        """macOS 键盘按下回调"""
        try:
            key_name = pynput_key_to_name(key)
            if not key_name:
                return

            # 防自捕获
            if key_name in self._emulating_pressed:
                return
            if key_name in self._restoring_keys:
                return

            if key_name not in self.tasks:
                return

            task = self.tasks[key_name]
            self._event_handler.handle_keydown(key_name, task)
        except Exception as e:
            logger.error(f"键盘按下回调异常: {e}", exc_info=True)

    def _on_key_release(self, key):
        """macOS 键盘释放回调"""
        try:
            key_name = pynput_key_to_name(key)
            if not key_name:
                return

            # 防自捕获 —— 释放时清除标志
            if key_name in self._emulating_pressed:
                self._emulating_pressed.discard(key_name)
                return
            if key_name in self._restoring_keys:
                self._restoring_keys.discard(key_name)
                return

            if key_name not in self.tasks:
                return

            task = self.tasks[key_name]
            self._event_handler.handle_keyup(key_name, task)
        except Exception as e:
            logger.error(f"键盘释放回调异常: {e}", exc_info=True)

    # ========== Windows: win32_event_filter 回调 ==========

    def create_keyboard_filter(self):
        """创建键盘事件过滤器（Windows 专用）"""
        def win32_event_filter(msg, data):
            if msg not in KEYBOARD_MESSAGES:
                return True

            key_name = KeyMapper.vk_to_name(data.vkCode)

            # 防自捕获检查
            if self._check_emulating(key_name, msg):
                return True
            if self._check_restoring(key_name, msg):
                return True

            if key_name not in self.tasks:
                return True

            task = self.tasks[key_name]

            if msg in KEY_DOWN_MESSAGES:
                self._event_handler.handle_keydown(key_name, task)
            elif msg in KEY_UP_MESSAGES:
                self._event_handler.handle_keyup(key_name, task)

            # 阻塞事件
            if task.shortcut.suppress and self.keyboard_listener:
                self.keyboard_listener.suppress_event()

            return True

        return win32_event_filter

    def create_mouse_filter(self):
        """创建鼠标事件过滤器（Windows 专用）"""
        def win32_event_filter(msg, data):
            if msg not in MOUSE_MESSAGES:
                return True

            xbutton = (data.mouseData >> 16) & 0xFFFF
            button_name = 'x1' if xbutton == XBUTTON1 else 'x2'

            if self._check_emulating(button_name, msg, is_mouse=True):
                return True

            if button_name not in self.tasks:
                return True

            task = self.tasks[button_name]

            if msg == WM_XBUTTONDOWN:
                self._event_handler.handle_keydown(button_name, task)
            elif msg == WM_XBUTTONUP:
                self._handle_mouse_keyup(button_name, task)

            if task.shortcut.suppress and self.mouse_listener:
                self.mouse_listener.suppress_event()

            return True

        return win32_event_filter

    def _handle_mouse_keyup(self, button_name: str, task) -> None:
        """处理鼠标按键释放事件"""
        if not task.shortcut.hold_mode:
            if task.pressed:
                task.pressed = False
                task.released = True
                task.event.set()
            return

        if not task.is_recording:
            return

        duration = time.time() - task.recording_start_time
        logger.debug(f"[{button_name}] 松开按键，持续时间: {duration:.3f}s")

        if duration < task.threshold:
            task.cancel()
            if task.shortcut.suppress:
                logger.debug(f"[{button_name}] 安排异步补发鼠标按键")
                self._pool.submit(self._emulator.emulate_mouse_click, button_name)
        else:
            task.finish()

    # ========== 按键恢复管理 ==========

    def schedule_restore(self, key: str) -> None:
        """安排按键恢复（延迟执行）"""
        from pynput import keyboard as kb

        self._restoring_keys.add(key)

        def do_restore():
            import time
            time.sleep(0.05)
            try:
                if key == 'caps_lock':
                    controller = kb.Controller()
                    controller.press(kb.Key.caps_lock)
                    controller.release(kb.Key.caps_lock)
            finally:
                # 确保 restoring flag 被清除，否则该按键会被永久屏蔽
                self._restoring_keys.discard(key)

        self._pool.submit(do_restore)

    def is_restoring(self, key: str) -> bool:
        return key in self._restoring_keys

    def clear_restoring_flag(self, key: str) -> None:
        self._restoring_keys.discard(key)

    # ========== 防自捕获检查（Windows） ==========

    def _check_emulating(self, key_name: str, msg: int, is_mouse: bool = False) -> bool:
        """检查是否正在模拟按键（Windows 专用）"""
        if not self._emulator.is_emulating(key_name):
            return False

        if is_mouse:
            if msg == WM_XBUTTONUP:
                self._emulator.clear_emulating_flag(key_name)
        else:
            if msg in (WM_KEYUP, WM_SYSKEYUP):
                self._emulator.clear_emulating_flag(key_name)

        return True

    def _check_restoring(self, key_name: str, msg: int) -> bool:
        """检查是否正在恢复按键（Windows 专用）"""
        if not self.is_restoring(key_name):
            return False

        if msg in (WM_KEYUP, WM_SYSKEYUP):
            self.clear_restoring_flag(key_name)

        return True

    # ========== 公共接口 ==========

    def start(self) -> None:
        """启动所有监听器"""
        has_keyboard = any(s.type == 'keyboard' for s in self.shortcuts if s.enabled)
        has_mouse = any(s.type == 'mouse' for s in self.shortcuts if s.enabled)

        if has_keyboard:
            if sys.platform == 'win32':
                self.keyboard_listener = keyboard.Listener(
                    win32_event_filter=self.create_keyboard_filter()
                )
            else:
                # macOS / Linux: 使用 on_press / on_release
                self.keyboard_listener = keyboard.Listener(
                    on_press=self._on_key_press,
                    on_release=self._on_key_release,
                )
            self.keyboard_listener.start()
            logger.info("键盘监听器已启动")

        if has_mouse:
            if sys.platform == 'win32':
                self.mouse_listener = mouse.Listener(
                    win32_event_filter=self.create_mouse_filter()
                )
                self.mouse_listener.start()
                logger.info("鼠标监听器已启动")
            else:
                # macOS: 鼠标侧键监听暂不支持（pynput macOS 不支持 x1/x2）
                logger.info("macOS 上暂不支持鼠标侧键监听，已跳过")

        # 打印所有启用的快捷键
        for shortcut in self.shortcuts:
            if shortcut.enabled:
                mode = "长按" if shortcut.hold_mode else "单击"
                toggle = "可恢复" if shortcut.is_toggle_key() else "普通键"
                logger.info(f"  [{shortcut.key}] {mode}模式, 阻塞:{shortcut.suppress}, {toggle}")

    def stop(self) -> None:
        """停止所有监听器和清理资源"""
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            logger.debug("键盘监听器已停止")

        if self.mouse_listener:
            self.mouse_listener.stop()
            logger.debug("鼠标监听器已停止")

        for task in self.tasks.values():
            if task.is_recording:
                task.cancel()

        self._pool.shutdown(wait=False)
        logger.debug("快捷键管理器线程池已关闭")
