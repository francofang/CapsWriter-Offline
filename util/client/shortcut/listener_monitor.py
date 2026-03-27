# coding: utf-8
"""
pynput 键盘监听器健康监控

纯诊断模块，不修改任何业务逻辑。定期检查：
- 监听器线程是否存活
- CGEventTap 是否仍然启用
- 距离上次收到键盘事件的时间

用于定位"热键假死"的根因：是线程死了、tap 被禁用、还是其他原因。
"""

import sys
import time
import threading

from . import logger

_tap_refs = {}       # name -> tap reference
_listeners = {}      # name -> listener instance
_last_event_time = 0.0
_running = False


def register_listener(name, listener):
    """
    注册一个 pynput listener 进行监控。

    会 monkey-patch listener._create_event_tap 来捕获 tap 引用。
    必须在 listener.start() 之前调用。
    """
    _listeners[name] = listener

    if sys.platform != 'darwin':
        return

    original_create = listener._create_event_tap

    def patched_create():
        tap = original_create()
        _tap_refs[name] = tap
        logger.info(f"[ListenerMonitor] {name}: CGEventTap 已创建, tap={tap}")
        return tap

    listener._create_event_tap = patched_create


def on_event():
    """记录收到键盘事件的时间，在 shortcut 回调中调用"""
    global _last_event_time
    _last_event_time = time.time()


def start(interval=30):
    """启动定期健康检查（守护线程）"""
    global _running, _last_event_time
    _running = True
    _last_event_time = time.time()
    thread = threading.Thread(target=_check_loop, args=(interval,), daemon=True)
    thread.start()
    logger.info(f"[ListenerMonitor] 健康检查已启动，间隔 {interval}s")


def stop():
    global _running
    _running = False


def _check_loop(interval):
    while _running:
        time.sleep(interval)
        _check_health()


def _check_health():
    idle_seconds = time.time() - _last_event_time if _last_event_time > 0 else 0

    for name, listener in _listeners.items():
        # 1. 线程是否存活
        thread_alive = listener.is_alive() if listener else False

        # 2. CGEventTap 是否启用
        tap_enabled = _check_tap_enabled(name)

        # 3. 判断是否需要告警
        is_warning = (
            not thread_alive
            or tap_enabled is False
            or idle_seconds > 120
        )

        msg = (
            f"[ListenerMonitor] {name}: "
            f"thread_alive={thread_alive}, "
            f"tap_enabled={tap_enabled}, "
            f"idle={idle_seconds:.0f}s"
        )

        if is_warning:
            logger.warning(msg)
        else:
            logger.debug(msg)


def _check_tap_enabled(name):
    """检查 CGEventTap 是否仍然启用"""
    if sys.platform != 'darwin':
        return None

    tap = _tap_refs.get(name)
    if tap is None:
        return None

    try:
        from Quartz import CGEventTapIsEnabled
        return bool(CGEventTapIsEnabled(tap))
    except Exception as e:
        return f"error: {e}"
