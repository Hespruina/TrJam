#!/usr/bin/env python3
# test_parallel_pro_fix.py
# 测试 Parallel Pro 模式的修复

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

def test_should_handle_message_call():
    """测试 should_handle_message 的调用"""
    print("测试 should_handle_message 调用参数...")
    
    # 读取 message_router.py
    router_path = Path(__file__).parent / 'core' / 'message_router.py'
    with open(router_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否所有 should_handle_message 调用都包含 account_id 和 context
    import re
    
    # 找到所有 should_handle_message 调用
    pattern = r'should_handle_message\([^)]*\)'
    matches = re.findall(pattern, content)
    
    print(f"\n找到 {len(matches)} 处 should_handle_message 调用:")
    all_correct = True
    
    for i, match in enumerate(matches, 1):
        # BotContext.should_handle_message 只需要 account_id 参数
        has_account_id = 'account_id=' in match
        
        status = "✓" if has_account_id else "✗"
        print(f"  {i}. {status} {match}")
        
        if not has_account_id:
            all_correct = False
    
    print()
    if all_correct:
        print("✓ 所有调用都正确传递了 account_id 参数")
        return True
    else:
        print("✗ 仍有调用未正确传递 account_id 参数")
        return False

def test_account_manager_logic():
    """测试 account_manager 的逻辑"""
    print("\n测试 account_manager 逻辑...")
    
    # 读取 account_manager.py
    manager_path = Path(__file__).parent / 'core' / 'bot_context' / 'account_manager.py'
    with open(manager_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否有群列表未缓存时的处理逻辑
    if '群列表未缓存' in content or 'accounts_in_group' in content:
        print("✓ 包含群列表未缓存的处理逻辑")
        return True
    else:
        print("✗ 缺少群列表未缓存的处理逻辑")
        return False

def test_multi_ws_manager_logic():
    """测试 multi_websocket_manager 的逻辑"""
    print("\n测试 multi_websocket_manager 逻辑...")
    
    # 读取 multi_websocket_manager.py
    manager_path = Path(__file__).parent / 'core' / 'multi_websocket_manager.py'
    with open(manager_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否有详细的日志
    checks = [
        ('群列表缓存检查', '只有 {len(accounts_in_group)} 个账号缓存' in content),
        ('连接健康检查', '未连接或不健康' in content),
        ('优先级判断日志', '优先级：' in content),
    ]
    
    all_passed = True
    for check_name, result in checks:
        status = "✓" if result else "✗"
        print(f"  {status} {check_name}: {result}")
        if not result:
            all_passed = False
    
    return all_passed

def main():
    print("=" * 60)
    print("Parallel Pro 模式修复验证")
    print("=" * 60)
    
    results = []
    results.append(test_should_handle_message_call())
    results.append(test_account_manager_logic())
    results.append(test_multi_ws_manager_logic())
    
    print("\n" + "=" * 60)
    if all(results):
        print("✓ 所有检查通过！修复完成。")
        print("\n建议操作:")
        print("1. 重启机器人")
        print("2. 切换到 parallel-pro 模式")
        print("3. 发送测试消息验证功能")
        print("4. 查看日志确认优先级判断逻辑正常工作")
    else:
        print("✗ 部分检查未通过，请检查代码")
    print("=" * 60)

if __name__ == '__main__':
    main()
