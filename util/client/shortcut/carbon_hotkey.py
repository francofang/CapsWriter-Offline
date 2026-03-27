# coding: utf-8
"""
恢复热键（macOS 专用）

使用 NSEvent.addGlobalMonitorForEventsMatchingMask 注册全局键盘监控，
监听 Ctrl+Shift+R 组合键。这走的是 Cocoa 事件通路，与 pynput 的
CGEventTap 是不同的机制。

用途：当 pynput 热键假死时，按 Ctrl+Shift+R 触发 listener 重建。

Phase 1: 只打日志，验证假死时是否仍能触发。
Phase 2: 接上 rebuild 回调。
"""

import sys

from . import logger

# 持有引用防止 GC
_refs = {}


def register_recovery_hotkey(callback=None):
    """
    注册 Ctrl+Shift+R 为恢复热键（NSEvent 全局监控）。

    Args:
        callback: 热键触发时的回调。None 则只打日志。

    Returns:
        True 注册成功，False 失败。
    """
    if sys.platform != 'darwin':
        return False

    try:
        from AppKit import NSEvent, NSKeyDownMask, NSControlKeyMask, NSShiftKeyMask

        target_modifiers = NSControlKeyMask | NSShiftKeyMask
        # 排除其他修饰键（Cmd, Option）
        modifier_mask = NSControlKeyMask | NSShiftKeyMask | 0x100108  # Cmd | Option

        def _handler(event):
            # 检查是否是 R 键 (keycode 15)
            if event.keyCode() != 15:
                return
            # 检查修饰键：必须有 Ctrl+Shift，不能有 Cmd/Option
            flags = event.modifierFlags()
            if (flags & modifier_mask) != target_modifiers:
                return

            logger.info("[RecoveryHotkey] 恢复热键被触发 (Ctrl+Shift+R)")
            if callback:
                try:
                    callback()
                except Exception as e:
                    logger.error(f"[RecoveryHotkey] 回调执行失败: {e}", exc_info=True)

        monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            NSKeyDownMask, _handler
        )

        if monitor is None:
            logger.warning("[RecoveryHotkey] NSEvent 全局监控注册失败")
            return False

        # 持有引用
        _refs['monitor'] = monitor
        _refs['handler'] = _handler

        logger.info("[RecoveryHotkey] 恢复热键已注册: Ctrl+Shift+R (NSEvent)")
        return True

    except ImportError:
        logger.warning("[RecoveryHotkey] PyObjC 未安装，无法注册恢复热键")
        return False
    except Exception as e:
        logger.error(f"[RecoveryHotkey] 注册失败: {e}", exc_info=True)
        return False
