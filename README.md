

# 🚧 开发阶段提示 🚧

**本项目仍处于内部开发阶段，暂不提供部署方法和详细文档，本仓库暂时为不定期更新的预览发布渠道。如需了解更多信息，欢迎添加我们的QQ群：1077732596**

## 项目概览

ZHRrobot 是一个基于 WebSocket 的 QQ 机器人项目，采用模块化设计，支持多账号、插件系统、命令系统等高级功能。项目使用 Python 异步编程，提供高效、可扩展的机器人框架。

本项目（TrJam）是基于ZHRrobot底层框架开发的，继承了其核心功能和模块，并延展了大量功能。

## 核心功能

### 1. 多账号支持
- 通过 MultiWebSocketManager 管理多个账号的 WebSocket 连接
- 基于优先级的故障转移机制
- 心跳监控和自动重连

### 2. 消息处理管道
- 多阶段、可扩展的消息处理架构
- 支持命令检测、预处理、后处理等多个阶段
- 模块化设计，易于扩展

### 3. 命令系统
- 丰富的内置命令（音乐、聊天、名言等）
- 支持中文命令别名
- 基于配置的权限管理
- 命令禁用机制

### 4. 插件系统
- 基于事件驱动的插件架构
- 支持插件的动态加载、卸载和重载
- 插件间通信通过事件总线和服务注册表
- 完整的插件生命周期管理

### 5. 子机器人系统
- 独立进程的子机器人
- 通过 WebSocket 与主机器人通信
- 自动发现和启动子机器人
- 进程监控和自动重启

### 6. 安全机制
- 敏感词检测和处理
- 黑名单机制
- 权限控制
- 输入验证和参数过滤

### 7. 多媒体功能
- 音乐搜索和播放（支持网易云、QQ音乐、歌曲宝）
- 图像处理和识别
- 名言图片生成
- 腿照识别和精华设置

### 8. 配置管理
- YAML 格式的配置文件
- 配置热更新和监控
- 分层配置（全局、服务器、群组）
- 配置验证机制

## 技术栈

- **Python 3.8+**：主要开发语言
- **异步编程**：使用 asyncio 实现异步操作
- **WebSocket**：与 OneBot 协议通信
- **YAML**：配置文件格式
- **Playwright**：浏览器自动化
- **插件架构**：基于事件总线的插件系统

## 快速开始
项目仍在内部开发阶段，暂无快速部署方法

## 命令系统

### 命令格式
- 命令以 `/` 开头
- 支持参数传递
- 部分命令支持子命令

## 插件开发

### 插件结构
```
plugins/
└── your_plugin/
    ├── plugin.yml        # 插件元信息
    ├── main.py           # 插件主模块
    └── ...               # 其他文件
```

### 插件元信息示例
```yaml
name: Your Plugin
version: 1.0.0
description: A sample plugin
author: Your Name
entry_point: main:YourPlugin
dependencies:
  python:
    - requests
  plugins:
    - base_plugin
commands:
  - name: yourcommand
    description: Your command description
    usage: /yourcommand [args]
    permission: user
events:
  - type: message.group
    priority: 10
    handler: on_group_message
```

### 插件开发示例
```python
from plugin_system import PluginBase, PluginContext

class YourPlugin(PluginBase):
    def on_load(self, context: PluginContext):
        # 插件加载时调用
        pass
    
    def on_enable(self, context: PluginContext):
        # 插件启用时调用
        pass
    
    def on_disable(self, context: PluginContext):
        # 插件禁用时调用
        pass
    
    def on_unload(self, context: PluginContext):
        # 插件卸载时调用
        pass
    
    async def on_group_message(self, context: PluginContext, message):
        # 处理群消息事件
        pass
```

## 子机器人开发

### 子机器人结构
```
subbot/
└── your_subbot/
    ├── subbot.yml        # 子机器人元信息
    ├── __init__.py        # 子机器人入口
    └── ...                # 其他文件
```

### 子机器人元信息示例
```yaml
name: Your SubBot
version: 1.0.0
description: A sample subbot
author: Your Name
entry_point: __init__.py:main
startup: true
requirements:
  - requests
supported_features:
  - message_processing
  - group_message
permissions:
  - send_message
  - receive_message
config:
  option1: value1
metadata:
  created_at: 2023-01-01
  updated_at: 2023-01-01
  compatible_version: ">=3.5.0"
```

## 配置说明

### 主配置文件 (config.yml)
- **accounts**：账号配置列表
- **servers**：服务器配置列表
- **plugin_system**：插件系统配置
- **subbot**：子机器人配置
- **sensitive_words**：敏感词配置
- **commands**：命令配置
- ....

### 命令配置文件 (commands.yml)
- **command_mappings**：命令映射和别名
- **command_categories**：命令分类
- **permission_levels**：权限级别配置
- ....

### 浏览器配置文件 (browser_config.yml)
- **browser_type**：浏览器类型
- **executable_path**：浏览器可执行文件路径
- **args**：浏览器启动参数
- **headless**：是否无头模式
- ....

## 故障排查

### 日志系统
- 日志文件位于 `logs` 目录
- 支持不同级别的日志（DEBUG, INFO, WARNING, ERROR, CRITICAL）
- 插件有独立的日志器

## 许可证

本项目采用 GPL-3 许可证，详见 LICENSE 文件。

## 更新日志

### 最新版本
- 支持多账号故障转移
- 完善的插件系统
- 丰富的内置命令
- 子机器人系统
- 多媒体处理功能

## 联系方式

- 项目地址：[ZHRrobot GitHub](https://github.com/Hespruina/TrJam)
- 开发者邮箱：admin@zhrhello.topadmin@zhrhello.top