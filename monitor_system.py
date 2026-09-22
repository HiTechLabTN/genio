import psutil
import datetime

def get_system_stats():
    cpu_usage = psutil.cpu_percent(interval=1)
    memory_info = psutil.virtual_memory()
    mem_usage = memory_info.percent
    
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return f"[{now}] CPU: {cpu_usage}% | RAM: {mem_usage}%"

if __name__ == "__main__":
    print(get_system_stats())
