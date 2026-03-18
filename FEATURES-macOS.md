# CapsWriter-Offline 功能清单 (macOS 移植版)

本文档梳理了 CapsWriter-Offline v2.5-alpha 的所有功能模块，标注了 macOS 上的可用状态。


## 功能总览

| 功能 | 简介 | 配置位置 | macOS 可用 |
|------|------|---------|-----------|
| 语音输入 | 按快捷键说话，识别结果自动上屏 | `config_client.py` shortcuts | ✅ 可用 |
| 模型切换 | 4 种 ASR 模型可选 | `config_server.py` model_type | ✅ 可用 |
| Metal GPU 加速 | Apple Silicon 自动启用 Metal 加速 | 自动，无需配置 | ✅ 可用 |
| 录音模式切换 | 按住模式 / 单击切换模式 | `config_client.py` hold_mode | ✅ 可用 |
| 热词替换 | 音素模糊匹配，强制替换偏僻词 | `hot.txt` + `config_client.py` | ✅ 可用 |
| 服务端热词语境 | Fun-ASR-Nano 语境增强识别 | `hot-server.txt` | ✅ 可用 |
| 正则替换 | 基于正则表达式的强制替换 | `hot-rule.txt` | ✅ 可用 |
| 纠错历史 | 记录纠错对，辅助 LLM 润色 | `hot-rectify.txt` | ✅ 可用 |
| 热词自动重载 | 修改热词文件后自动生效，无需重启 | 自动（watchdog 监控） | ✅ 可用 |
| LLM 角色系统 | 润色、翻译、助手等多角色 | `LLM/*.py` | ✅ 可用 |
| LLM 角色热重载 | 修改角色文件后自动重载 | 自动（watchdog 监控） | ✅ 可用 |
| Toast 弹窗输出 | LLM 结果在浮窗中显示 | `LLM/*.py` output_mode | ✅ 可用 |
| 文件转录 | 音视频文件转为字幕/文本 | `config_client.py` file_save_* | ✅ 可用（需 FFmpeg） |
| 日记归档 | 按日期保存语音识别结果 | 自动保存到 `YYYY/MM/DD.md` | ✅ 可用 |
| 录音保存 | 每次语音保存为本地音频文件 | `config_client.py` save_audio | ✅ 可用 |
| 数字 ITN | 中文数字自动转为阿拉伯数字 | `config_server.py` format_num | ✅ 可用 |
| 中英空格调整 | 中英文之间自动加空格 | `config_server.py` format_spell | ✅ 可用 |
| 繁体中文转换 | 识别结果转为繁体 | `config_client.py` traditional_convert | ✅ 可用 |
| UDP 广播 | 将识别结果广播给其他程序 | `config_client.py` udp_broadcast | ✅ 可用 |
| UDP 控制 | 外部程序发送 START/STOP 控制录音 | `config_client.py` udp_control | ✅ 可用 |
| 托盘图标 | 系统托盘图标 + 右键菜单 | `config_client.py` enable_tray | ❌ 仅 Windows |
| 鼠标侧键 | X1/X2 鼠标按键触发录音 | `config_client.py` shortcuts | ❌ pynput 不支持 |
| 流式打字输出 | keyboard.write() 逐字输出 | `config_client.py` paste | ❌ 自动降级为粘贴 |
| 按键阻塞 (suppress) | 阻塞快捷键不传递给系统 | `config_client.py` suppress | ❌ pynput 不支持 |


---


## 功能详解


### 一、LLM 角色系统

#### 内置角色

| 角色 | 触发词 | 功能 | 输出方式 |
|------|--------|------|---------|
| default（默认） | 无需触发词，自动生效 | 热词替换、去语气词（默认不调用 LLM） | 直接打字 |
| 翻译 | 说「翻译，……」 | 翻译为英文 | Toast 弹窗 |
| 小助理 | 说「小助理，……」 | 通用问答助手，可读取选中文字 | Toast 弹窗 |

#### 怎么用

录音时在开头说角色名就触发。例如：
- 说「翻译，今天天气真好」→ 翻译角色接管，弹窗显示英文翻译
- 说「小助理，帮我总结一下」→ 先用鼠标选中一段文字，再说这句，助手会读取选中内容
- 直接说话（不说角色名）→ 默认角色处理，仅做热词替换和去标点

#### 配置方法

每个角色是 `LLM/` 目录下的一个 `.py` 文件，核心配置项：

```python
# === 基本设置 ===
match = True               # 是否启用角色匹配
process = True             # 是否调用 LLM（False = 仅做热词替换）
prefix = '翻译'            # 触发词（空字符串 = 默认角色）

# === LLM 后端 ===
provider = 'ollama'        # 'ollama', 'openai', 'deepseek', 'claude', 'gemini' 等
model = 'gemma3:4b'        # 模型名称
api_key = ''               # 在线 API 的密钥
base_url = ''              # 自定义 API 地址

# === 输出方式 ===
output_mode = 'typing'     # 'typing' = 直接打字/粘贴, 'toast' = 弹窗显示

# === 高级功能 ===
enable_read_selection = True   # 是否读取鼠标选中的文字
enable_history = True          # 是否保留对话历史
enable_hotwords = True         # 是否启用热词替换
enable_rectify = True          # 是否使用纠错历史
```

#### 本地 vs 在线

- **本地**：安装 [Ollama](https://ollama.com)，设置 `provider = 'ollama'`，`model = 'gemma3:4b'`（或其他模型）
- **在线 API**：设置 `provider = 'deepseek'`（或 `'claude'`、`'gemini'` 等），填写 `api_key`
- macOS 上两种方式都完全可用

#### 添加新角色

复制 `LLM/翻译.py` 或 `LLM/小助理.py`，改文件名和 `prefix`，保存后**自动生效**（watchdog 热重载，无需重启）。


---


### 二、热词系统

#### 各文件作用

| 文件 | 用途 | 匹配方式 | 效果 |
|------|------|---------|------|
| `hot.txt` | 客户端强制替换词 | 音素 RAG 模糊匹配 | 相似度 > 0.85 则强制替换 |
| `hot-server.txt` | 服务端语境增强 | 提供给 Fun-ASR-Nano 的 LLM Decoder | 建议性，帮助模型更好识别 |
| `hot-rule.txt` | 正则/等号替换规则 | 正则表达式或 `A = B` 等号语法 | 精确强制替换 |
| `hot-rectify.txt` | 纠错历史记录 | RAG 相似度匹配 | 提供给 LLM 角色作为参考 |

> 注意：没有 `hot-zh.txt` 和 `hot-en.txt`，客户端热词统一写在 `hot.txt` 中。

#### 怎么添加和修改

**hot.txt**（一行一个热词）：
```
CapsWriter
Claude Code
Apple Silicon
我家鸽鸽
```

**hot-rule.txt**（等号或正则语法）：
```
毫安时 = mAh
(艾特)\s*(\w+)\s*(点)\s*(\w+) = @\2.\4
```

**hot-rectify.txt**（纠错对，用 `---` 分隔）：
```
Do you know cloud code?
Do you know Claude Code?
---
他在用science voice模型
他在用SenseVoice模型
```

#### 修改后是否需要重启

**不需要！** 所有热词文件都有 watchdog 文件监控，保存后 **3 秒内自动重载**，控制台会打印更新确认：
```
热词库 hot.txt 已更新 42 条
```

LLM 角色文件（`LLM/*.py`）也有热重载，保存后 **1 秒内自动生效**。

#### 纠错检索是什么

「纠错检索」是指：你可以在 `hot-rectify.txt` 中记录过去的识别错误和正确结果。当启用 LLM 润色时，系统会用 RAG 在纠错历史中检索相似的错误，将匹配到的纠错对作为上下文提供给 LLM，帮助它更准确地修正类似错误。

例如：如果你之前纠正过「cloud code → Claude Code」，下次再说到类似发音时，LLM 角色就会参考这条纠错记录。


---


### 三、日记归档 & 录音保存

#### 目录结构

```
CapsWriter-Offline/
├── 2026/
│   └── 03/
│       ├── 18.md                    # 日记文件（按日期）
│       └── assets/
│           ├── (20260318-143025)今天天气真好.mp3
│           └── (20260318-143210)帮我翻译一下.mp3
```

#### 日记文件格式

每条记录自动追加到当天的 `.md` 文件中：
```markdown
[14:30:25](assets/(20260318-143025)今天天气真好.mp3) 今天天气真好
[14:32:10](assets/(20260318-143210)帮我翻译一下.mp3) 帮我翻译一下
```

#### 相关配置

```python
# config_client.py
save_audio = True           # 是否保存录音文件
audio_name_len = 20         # 文件名中包含识别文字的字数
```


---


### 四、文件转录

#### 使用方法

将音视频文件（mp3、wav、mp4、mkv 等）拖到**客户端窗口**中即可开始转录。

> 前提：需要安装 FFmpeg（`brew install ffmpeg`，安装指南中已包含）。

#### 输出格式

转录完成后，在原文件同目录生成：

| 输出文件 | 配置项 | 说明 |
|---------|--------|------|
| `文件名.srt` | `file_save_srt = True` | SRT 字幕（带时间戳） |
| `文件名.txt` | `file_save_txt = True` | 纯文本（按标点智能分行） |
| `文件名.json` | `file_save_json = True` | JSON 结果（含原始时间戳） |
| `文件名.merge.txt` | `file_save_merge = False` | 未分行的完整段落文本 |

#### macOS 兼容性

✅ 完全可用。底层使用 FFmpeg 提取音频 + WebSocket 流式发送，均为跨平台实现。


---


### 五、UDP 广播与控制

#### UDP 广播（默认开启）

识别结果自动通过 UDP 广播发送，其他程序可以监听接收。

```python
# config_client.py
udp_broadcast = True
udp_broadcast_targets = [
    ('127.255.255.255', 6017),      # 本地广播
    # ('192.168.1.255', 6017),      # 局域网广播
]
```

用途举例：自制弹幕工具、OBS 字幕插件、自动化工作流等。

#### UDP 控制（默认关闭）

外部程序可以通过 UDP 发送 `START` / `STOP` 命令来控制录音。

```python
# config_client.py
udp_control = False                # 改为 True 启用
udp_control_addr = '127.0.0.1'
udp_control_port = 6018
```

用途举例：用 Stream Deck、快捷指令、脚本等外部触发录音。


---


### 六、其他实用功能

#### 繁体中文转换

```python
# config_client.py
traditional_convert = False        # 改为 True 启用
traditional_locale = 'zh-hant'     # 'zh-hant' / 'zh-tw' / 'zh-hk'
```

#### 数字格式化（服务端自动处理）

```python
# config_server.py
format_num = True       # 中文数字 → 阿拉伯数字（如「十五个」→「15个」）
format_spell = True     # 中英文之间自动加空格
```

#### 末尾标点去除

```python
# config_client.py
trash_punc = '，。,.'   # 语音输入时自动去掉末尾的逗号和句号
```

#### 提示词上下文

```python
# config_client.py
context = ''            # 可填入人名、地名、专业术语，辅助 ASR 模型识别
```

#### LLM 中断

录音识别后如果 LLM 正在流式输出，按 **ESC** 可以立即中断。

```python
# config_client.py
llm_stop_key = 'esc'
```
