# Parallel Pro 模式问题修复总结

## 问题描述

当切换到 `parallel-pro` 模式后，机器人完全不处理任何消息，但切换回 `parallel` 模式就正常。

## 根本原因

在 `core/message_router.py` 中，调用 `should_handle_message()` 方法时**没有传递 `account_id` 参数**。

在 Parallel Pro 模式下，`should_handle_message()` 需要 `account_id` 来判断该账号是否是群内优先级最高的活跃账号。如果 `account_id` 为 `None`，方法会直接返回 `False`，导致所有消息都被忽略。

## 修复内容

### 1. 修复消息路由器调用 (core/message_router.py)

在所有调用 `should_handle_message()` 的地方添加 `account_id` 参数：

- 第 111 行：消息事件处理
- 第 201 行：请求事件处理
- 第 212 行：通知事件处理

**修改前：**
```python
if not self.context.should_handle_message(event):
    continue
```

**修改后：**
```python
if not self.context.should_handle_message(event, account_id=account_id):
    continue
```

### 2. 优化 Parallel Pro 模式逻辑 (core/bot_context/account_manager.py)

添加群列表未缓存时的容错处理：

```python
# 检查群列表是否已缓存
accounts_in_group = ws_manager.get_accounts_in_group(str(group_id))
if not accounts_in_group:
    # 群列表未缓存或该群不在缓存中，允许处理并记录警告
    logger.warning(f"Parallel Pro 模式：群 {group_id} 的群列表未缓存，允许账号 {account_id} 处理消息")
    return True
```

### 3. 增强连接状态检查 (core/multi_websocket_manager.py)

- 改进 `is_highest_priority_in_group()` 方法，添加连接健康状态检查
- 优化 `_fetch_all_group_lists()` 方法，即使账号不健康也尝试获取群列表
- 添加详细的日志输出，便于调试

### 4. 修复 account 命令 (commands/account_command.py)

将直接访问 `context._config` 改为使用 `context.config` 属性：

- 第 103 行：`_handle_list_command`
- 第 127 行：`_handle_mode_query`
- 第 166 行：`_handle_mode_switch`
- 第 173 行：`_handle_mode_switch`

**修改前：**
```python
current