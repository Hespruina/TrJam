
import sys
import time
print("模拟适配器启动")
sys.stdout.flush()
time.sleep(1)  # 给父进程足够的时间读取输出
print("准备接收配置数据")
sys.stdout.flush()

# 循环等待接收数据，这更符合真实适配器的行为
while True:
    try:
        data = sys.stdin.readline()
        if data:
            print(f"接收到输入: {data.strip()[:20]}...")
            sys.stdout.flush()
            break  # 收到数据后退出
        time.sleep(0.1)
    except Exception as e:
        print(f"读取错误: {e}")
        break

print("模拟适配器正常退出")
sys.stdout.flush()
