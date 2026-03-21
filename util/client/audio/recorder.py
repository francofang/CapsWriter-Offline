# coding: utf-8
"""
音频录制模块

提供 AudioRecorder 类用于管理录音会话，包括开始录音、
发送音频数据到服务端、结束录音等功能。
"""

from __future__ import annotations

import asyncio
import base64
import json
import uuid
from typing import TYPE_CHECKING, Optional

import numpy as np
import websockets

from config_client import ClientConfig as Config
from util.client.state import console
from util.client.audio.file_manager import AudioFileManager
from . import logger

if TYPE_CHECKING:
    from util.client.state import ClientState

# 日志记录器


class AudioRecorder:
    """
    音频录制器
    
    管理一次完整的录音会话，包括：
    - 从音频流接收数据
    - 可选地保存到本地文件
    - 将音频数据发送到识别服务端
    """
    
    def __init__(self, state: 'ClientState'):
        """
        初始化录制器
        
        Args:
            state: 客户端状态实例
        """
        self.state = state
        self.task_id: Optional[str] = None
        self._file_manager: Optional[AudioFileManager] = None
        self._start_time: float = 0.0
        self._duration: float = 0.0
        self._cache: list = []
    
    async def _send_message(self, message: dict) -> None:
        """发送消息到服务端，连接断开时自动重连"""
        websocket = self.state.websocket

        # 连接不存在或已关闭 → 尝试自动重连
        if websocket is None or (hasattr(websocket, 'closed') and websocket.closed):
            self.state.websocket = None
            from util.client.websocket_manager import WebSocketManager
            ws_manager = WebSocketManager(self.state)
            logger.info("音频发送前检测到连接断开，尝试自动重连...")
            if await ws_manager.connect():
                logger.info("自动重连成功")
                websocket = self.state.websocket
            else:
                if message['is_final']:
                    self.state.pop_audio_file(message['task_id'])
                    console.print('    服务端未连接，无法发送\n')
                    logger.warning("服务端未连接且重连失败，无法发送音频数据")
                return

        try:
            await websocket.send(json.dumps(message))

        except (websockets.ConnectionClosedError, websockets.ConnectionClosedOK) as e:
            code = getattr(e, 'code', 'unknown')
            reason = getattr(e, 'reason', 'none')
            logger.warning(f"发送时连接断开: code={code}, reason={reason}")
            self.state.websocket = None
            if message['is_final']:
                self.state.pop_audio_file(message['task_id'])
                console.print(f'[red]连接中断 (code={code})')
                logger.info("WebSocket 连接已正常关闭")
        except Exception as e:
            logger.error(f"发送音频数据时发生错误: {e}", exc_info=True)
    
    async def record_and_send(self) -> None:
        """
        录音并发送数据
        
        从队列中读取音频数据，保存到文件（如果启用），
        并发送到服务端进行识别。
        """
        try:
            # 生成唯一任务 ID
            self.task_id = str(uuid.uuid1())
            logger.debug(f"创建录音任务，任务ID: {self.task_id}")
            
            self._start_time = 0.0
            self._duration = 0.0
            self._cache = []
            
            # 音频文件管理
            file_path = None
            if Config.save_audio:
                self._file_manager = AudioFileManager()
            
            # 从队列读取数据
            while task := await self.state.queue_in.get():
                self.state.queue_in.task_done()
                
                if task['type'] == 'begin':
                    self._start_time = task['time']
                    logger.debug(f"录音开始，时间戳: {self._start_time}")
                    
                elif task['type'] == 'data':
                    # 在阈值之前积攒音频数据
                    if task['time'] - self._start_time < Config.threshold:
                        self._cache.append(task['data'])
                        continue
                    
                    # 创建音频文件
                    if Config.save_audio and self._file_manager and file_path is None:
                        file_path, _ = self._file_manager.create(
                            task['data'].shape[1],
                            self._start_time
                        )
                        self.state.register_audio_file(self.task_id, file_path)
                        logger.debug(f"创建音频文件: {file_path}")
                    
                    # 获取音频数据
                    if self._cache:
                        data = np.concatenate(self._cache)
                        self._cache.clear()
                    else:
                        data = task['data']
                    
                    # 保存音频至本地文件
                    self._duration += len(data) / 48000
                    if Config.save_audio and self._file_manager:
                        self._file_manager.write(data)
                    
                    # 发送音频数据用于识别
                    message = {
                        'task_id': self.task_id,
                        'seg_duration': Config.mic_seg_duration,
                        'seg_overlap': Config.mic_seg_overlap,
                        'is_final': False,
                        'time_start': self._start_time,
                        'time_frame': task['time'],
                        'source': 'mic',
                        'data': base64.b64encode(
                            np.mean(data[::3], axis=1).tobytes()
                        ).decode('utf-8'),
                        'context': Config.context,
                    }
                    asyncio.create_task(self._send_message(message))
                    
                elif task['type'] == 'finish':
                    # 如果有缓存的数据未发送，先发送缓存
                    if self._cache:
                        data = np.concatenate(self._cache)
                        self._cache.clear()
                        
                        self._duration += len(data) / 48000
                        if Config.save_audio and self._file_manager:
                            self._file_manager.write(data)

                        message = {
                            'task_id': self.task_id,
                            'seg_duration': Config.mic_seg_duration,
                            'seg_overlap': Config.mic_seg_overlap,
                            'is_final': False,
                            'time_start': self._start_time,
                            'time_frame': task['time'],
                            'source': 'mic',
                            'data': base64.b64encode(
                                np.mean(data[::3], axis=1).tobytes()
                            ).decode('utf-8'),
                            'context': Config.context,
                        }
                        asyncio.create_task(self._send_message(message))

                    # 完成写入本地文件
                    if Config.save_audio and self._file_manager:
                        self._file_manager.finish()
                        logger.debug("完成音频文件写入")
                    
                    console.print(f'任务标识：{self.task_id}')
                    console.print(f'    录音时长：{self._duration:.2f}s')
                    logger.info(f"录音任务完成，任务ID: {self.task_id}, 时长: {self._duration:.2f}s")
                    
                    # 告诉服务端音频片段结束了
                    message = {
                        'task_id': self.task_id,
                        'seg_duration': 15,
                        'seg_overlap': 2,
                        'is_final': True,
                        'time_start': self._start_time,
                        'time_frame': task['time'],
                        'source': 'mic',
                        'data': '',
                        'context': Config.context,
                    }
                    asyncio.create_task(self._send_message(message))
                    break
                    
        except Exception as e:
            logger.error(f"录音任务错误: {e}", exc_info=True)
    
    def get_file_manager(self) -> Optional[AudioFileManager]:
        """获取当前的文件管理器"""
        return self._file_manager
