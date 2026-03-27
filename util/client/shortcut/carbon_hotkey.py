# coding: utf-8
"""
恢复热键（macOS 专用）

使用独立的 CGEventTap 监听 Ctrl+Shift+R，跑在自己的线程和 RunLoop 上，
完全独立于 pynput 的 CGEventTap。

用途：当 pynput 热键假死时，按 Ctrl+Shift+R 触发 listener 重建。
同时也是诊断工具——如果假死时这个 tap 也收不到事件，说明是 macOS 层面的问题。

Phase 1: 只打日志，验证假死时是否仍能触发。
Phase 2: 接上 rebuild 回调。
"""

import sys
import threading

from . import logger

_refs = {}


def register_recovery_hotkey(callback=None):
    """
    注册 Ctrl+Shift+R 为恢复热键（独立 CGEventTap）。

    Args:
        callback: 热键触发时的回调。None 则只打日志。

    Returns:
        True 启动成功，False 失败。
    """
    if sys.platform != 'darwin':
        return False

    try:
        from Quartz import (
            CGEventTapCreate, CGEventTapEnable,
            CGEventMaskBit, kCGEventKeyDown, kCGEventFlagsChanged,
            kCGSessionEventTap, kCGHeadInsertEventTap, kCGEventTapOptionListenOnly,
            CGEventGetFlags, CGEventGetIntegerValueField,
            kCGKeyboardEventKeycode,
            kCGEventFlagMaskShift, kCGEventFlagMaskControl,
            kCGEventFlagMaskCommand, kCGEventFlagMaskAlternate,
            CFMachPortCreateRunLoopSource,
            CFRunLoopGetCurrent, CFRunLoopAddSource, CFRunLoopRun,
            kCFRunLoopDefaultMode,
        )
    except ImportError:
        logger.warning("[RecoveryHotkey] PyObjC Quartz 未安装")
        return False

    target_modifiers = kCGEventFlagMaskControl | kCGEventFlagMaskShift
    exclude_modifiers = kCGEventFlagMaskCommand | kCGEventFlagMaskAlternate

    def _tap_callback(proxy, event_type, event, refcon):
        try:
            keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
            if keycode != 15:  # R 键
                return event

            flags = CGEventGetFlags(event)
            # 必须有 Ctrl+Shift，不能有 Cmd/Option
            if (flags & target_modifiers) == target_modifiers and not (flags & exclude_modifiers):
                logger.info("[RecoveryHotkey] 恢复热键被触发 (Ctrl+Shift+R)")
                if callback:
                    try:
                        callback()
                    except Exception as e:
                        logger.error(f"[RecoveryHotkey] 回调执行失败: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"[RecoveryHotkey] tap 回调异常: {e}", exc_info=True)

        return event

    def _run_tap():
        tap = CGEventTapCreate(
            kCGSessionEventTap,
            kCGHeadInsertEventTap,
            kCGEventTapOptionListenOnly,
            CGEventMaskBit(kCGEventKeyDown),
            _tap_callback,
            None,
        )
        if tap is None:
            logger.warning("[RecoveryHotkey] CGEventTap 创建失败（检查辅助功能权限）")
            return

        source = CFMachPortCreateRunLoopSource(None, tap, 0)
        loop = CFRunLoopGetCurrent()
        CFRunLoopAddSource(loop, source, kCFRunLoopDefaultMode)
        CGEventTapEnable(tap, True)

        # 保存引用
        _refs['tap'] = tap
        _refs['source'] = source
        _refs['callback'] = _tap_callback

        logger.info("[RecoveryHotkey] 恢复热键已注册: Ctrl+Shift+R (独立 CGEventTap)")

        # 阻塞本线程，持续运行 RunLoop
        CFRunLoopRun()

    try:
        thread = threading.Thread(target=_run_tap, daemon=True, name='RecoveryHotkey')
        thread.start()
        _refs['thread'] = thread
        return True
    except Exception as e:
        logger.error(f"[RecoveryHotkey] 启动失败: {e}", exc_info=True)
        return False
