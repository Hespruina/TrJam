#!/usr/bin/env python3
# check_parallel_pro_status.py
# 用于检查 Parallel Pro 模式的状态和诊断问题

import asyncio
import yaml
import sys
from pathlib import Path

def load_config():
    """加载配置文件"""
    config_path = Path(__file__).parent / 'config.yml'
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def check_accounts_config(config):
    """检查账号配置"""
    print("\n=== 账号配置检查 ===")
    accounts = config.get('accounts', [])
    mode = config.get('mode', 'fallback')
    
    print(f"当前运行模式：{mode}")
    print(f"配置账号数量：{len(accounts)}")
    
    if mode != 'parallel-pro':
        print(f"⚠️  警告：当前不是 parallel-pro 模式，而是 {mode}")
        if mode == 'parallel':
            print("💡 建议：如果需要优先级控制，请切换到 parallel-pro 模式")
        return
    
    print("\n账号详情:")
    for i, account in enumerate(accounts, 1):
        account_id = account.get('id', f'未知_{i}')
        priority = account.get('priority', 999)
        bot_qq = account.get('bot_qq', '未知')
        ws_uri = account.get('ws_uri', '未知')
        is_connected = account.get('connected', '未知')
        
        print(f"\n  账号 {i}:")
        print(f"    ID: {account_id}")
        print(f"    优先级：{priority}")
        print(f"    机器人 QQ: {bot_qq}")
        print(f"    WebSocket URI: {ws_uri}")
    
    # 检查优先级配置
    priorities = [acc.get('priority', 999) for acc in accounts]
    if len(priorities) != len(set(priorities)):
        print("\n⚠️  警告：存在重复的优先级配置！")
        print("💡 建议：为每个账号设置不同的优先级")
    
    # 按优先级排序
    sorted_accounts = sorted(accounts, key=lambda x: x.get('priority', 999))
    print("\n账号优先级排序（数字越小优先级越高）:")
    for i, account in enumerate(sorted_accounts, 1):
        print(f"  {i}. 账号 ID {account.get('id')} (QQ: {account.get('bot_qq')}) - 优先级：{account.get('priority')}")

def check_common_issues():
    """检查常见问题"""
    print("\n=== 常见问题检查 ===")
    
    issues = []
    
    # 检查配置文件是否存在
    config_path = Path(__file__).parent / 'config.yml'
    if not config_path.exists():
        issues.append("配置文件不存在！")
    else:
        print("✓ 配置文件存在")
    
    # 检查日志文件
    log_path = Path(__file__).parent / 'logs'
    if log_path.exists():
        print("✓ 日志目录存在")
        log_files = list(log_path.glob('*.log'))
        if log_files:
            print(f"  找到 {len(log_files)} 个日志文件")
        else:
            print("  ⚠️  未找到日志文件")
    else:
        print("⚠️  日志目录不存在")
    
    if issues:
        print("\n发现的问题:")
        for issue in issues:
            print(f"  ❌ {issue}")
    else:
        print("\n✓ 未发现明显问题")

async def diagnose():
    """诊断函数"""
    print("=" * 60)
    print("Parallel Pro 模式诊断工具")
    print("=" * 60)
    
    try:
        config = load_config()
        check_accounts_config(config)
        check_common_issues()
        
        print("\n" + "=" * 60)
        print("诊断完成")
        print("=" * 60)
        print("\n💡 建议:")
        print("1. 如果群列表缓存不完整，检查各账号的 WebSocket 连接状态")
        print("2. 查看日志中是否有连接失败或心跳超时的记录")
        print("3. 确保所有账号都能正常获取群列表")
        print("4. 如果问题持续，可以临时切换到 parallel 模式")
        
    except Exception as e:
        print(f"\n❌ 诊断过程发生错误：{e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(diagnose())
