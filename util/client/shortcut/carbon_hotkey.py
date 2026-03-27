# coding: utf-8
"""
Carbon 恢复热键（macOS 专用）

使用 Carbon RegisterEventHotKey API 注册全局热键，
与 pynput 的 CGEventTap 走完全不同的事件通路。

用途：当 pynput 热键假死时，按 Ctrl+Shift+R 触发 listener 重建。

Phase 1: 只打日志，验证假死时 Carbon 热键是否仍能触发。
Phase 2: 接上 rebuild 回调。
"""

import sys
import ctypes
import ctypes.util
from ctypes import c_uint32, c_void_p, c_int, Structure, CFUNCTYPE, byref

from . import logger

# Carbon modifier 常量
controlKey = 0x1000
shiftKey = 0x0200

# Carbon event 常量
kEventClassKeyboard = 0x6B657962  # 'keyb'
kEventHotKeyPressed = 5

# 回调类型: OSStatus (*)(EventHandlerCallRef, EventRef, void*)
_EventHandlerProcPtr = CFUNCTYPE(c_int, c_void_p, c_void_p, c_void_p)


class EventTypeSpec(Structure):
    _fields_ = [('eventClass', c_uint32), ('eventKind', c_uint32)]


class EventHotKeyID(Structure):
    _fields_ = [('signature', c_uint32), ('id', c_uint32)]


# 持有引用防止 GC
_refs = {}


def register_recovery_hotkey(callback=None):
    """
    注册 Ctrl+Shift+R 为恢复热键（Carbon API）。

    Args:
        callback: 热键触发时的回调。None 则只打日志。

    Returns:
        True 注册成功，False 失败。
    """
    if sys.platform != 'darwin':
        return False

    try:
        carbon_path = ctypes.util.find_library('Carbon')
        if not carbon_path:
            logger.warning("[CarbonHotkey] 找不到 Carbon framework")
            return False

        carbon = ctypes.cdll.LoadLibrary(carbon_path)

        def _handler(next_handler, event, user_data):
            logger.info("[CarbonHotkey] 恢复热键被触发 (Ctrl+Shift+R)")
            if callback:
                try:
                    callback()
                except Exception as e:
                    logger.error(f"[CarbonHotkey] 回调执行失败: {e}", exc_info=True)
            return 0  # noErr

        # 保持引用
        handler_func = _EventHandlerProcPtr(_handler)
        _refs['handler_func'] = handler_func

        # 安装事件处理器
        event_type = EventTypeSpec(kEventClassKeyboard, kEventHotKeyPressed)
        handler_ref = c_void_p()

        status = carbon.InstallApplicationEventHandler(
            handler_func,
            c_uint32(1),
            byref(event_type),
            None,
            byref(handler_ref),
        )
        if status != 0:
            logger.warning(f"[CarbonHotkey] InstallApplicationEventHandler 失败: {status}")
            return False

        _refs['handler_ref'] = handler_ref

        # 注册热键: Ctrl+Shift+R (keycode 15)
        hotkey_id = EventHotKeyID(
            signature=0x43575254,  # 'CWRT'
            id=1,
        )
        hotkey_ref = c_void_p()
        modifiers = controlKey | shiftKey
        keycode = 15  # R

        status = carbon.RegisterEventHotKey(
            c_uint32(keycode),
            c_uint32(modifiers),
            hotkey_id,
            carbon.GetApplicationEventTarget(),
            c_uint32(0),
            byref(hotkey_ref),
        )
        if status != 0:
            logger.warning(f"[CarbonHotkey] RegisterEventHotKey 失败: {status}")
            return False

        _refs['hotkey_ref'] = hotkey_ref

        logger.info("[CarbonHotkey] 恢复热键已注册: Ctrl+Shift+R")
        return True

    except Exception as e:
        logger.error(f"[CarbonHotkey] 注册失败: {e}", exc_info=True)
        return False
