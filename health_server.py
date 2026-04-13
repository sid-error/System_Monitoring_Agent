import os
import psutil
import time
from fastmcp import FastMCP

mcp = FastMCP("System Health Monitor")

@mcp.tool()
def get_cpu_usage() -> str:
    """Returns the current CPU usage percentage."""
    return f"CPU usage: {psutil.cpu_percent(interval=1)}%"

@mcp.tool()
def get_ram_usage() -> str:
    """Returns the current RAM usage including total, used, free and percentage."""
    mem = psutil.virtual_memory()
    return (f"RAM - Total: {mem.total // (1024**3)} GB, "
            f"Used: {mem.used // (1024**3)} GB, "
            f"Free: {mem.free // (1024**3)} GB, "
            f"Usage: {mem.percent}%")

@mcp.tool()
def get_disk_usage(path: str = "/") -> str:
    """Returns disk usage for a given path (e.g., 'C:' on Windows, '/' on Linux).
    Args:
        path: Drive or mount point (e.g., 'C:' or '/')
    """
    if os.name == 'nt':
        if len(path) == 2 and path[1] == ':':
            path = path + "\\"
        if path.endswith(':'):
            path = path + "\\"
    try:
        usage = psutil.disk_usage(path)
        return (f"Disk {path}: Total: {usage.total // (1024**3)} GB, "
                f"Used: {usage.used // (1024**3)} GB, "
                f"Free: {usage.free // (1024**3)} GB, "
                f"Usage: {usage.percent}%")
    except FileNotFoundError:
        return f"Error: Drive or path '{path}' not found. Please specify an existing drive (e.g., 'C:' on Windows)."
    except PermissionError:
        return f"Error: Permission denied for path '{path}'."
    except Exception as e:
        return f"Error checking disk usage: {str(e)}"

@mcp.tool()
def get_top_processes(n: int = 5) -> str:
    """Returns the top n processes by CPU usage."""
    processes = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            proc.cpu_percent(interval=0)
            processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    time.sleep(0.5)
    proc_data = []
    for proc in processes:
        try:
            if proc.info['name'] == "System Idle Process":
                continue
            cpu_percent = proc.cpu_percent(interval=0)
            proc_data.append({
                'pid': proc.info['pid'],
                'name': proc.info['name'] or 'Unknown',
                'cpu_percent': cpu_percent
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    proc_data.sort(key=lambda x: x['cpu_percent'], reverse=True)
    top_n = proc_data[:n]
    result = f"Top {n} processes by CPU usage (over 0.5s):\n"
    for p in top_n:
        result += f"PID {p['pid']}: {p['name']} - {p['cpu_percent']:.1f}%\n"
    return result

@mcp.tool()
def get_process_details_by_id(pid: int) -> str:
    """Returns details for a specific process given its Process ID (PID)."""
    try:
        proc = psutil.Process(pid)
        cpu = proc.cpu_percent(interval=0.1)
        mem = proc.memory_info().rss / (1024**2)
        try:
            user = proc.username()
        except:
            user = "Unknown"
        return (f"PID {pid} ({proc.name()}): Status: {proc.status()}, "
                f"CPU: {cpu}%, Memory: {mem:.1f} MB, "
                f"User: {user}")
    except psutil.NoSuchProcess:
        return f"Error: No process with PID {pid} found."
    except psutil.AccessDenied:
        return f"Error: Access denied to process {pid}."
    except Exception as e:
        return f"Error getting details for PID {pid}: {str(e)}"

@mcp.tool()
def get_process_details_by_name(name: str) -> str:
    """Returns details for processes matching the given name."""
    matching_procs = []
    for proc in psutil.process_iter(['pid', 'name', 'status', 'username']):
        try:
            if proc.info['name'] and name.lower() in proc.info['name'].lower():
                proc.cpu_percent(interval=0)
                matching_procs.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    time.sleep(0.1)
    
    if not matching_procs:
        return f"No processes found matching name '{name}'."
        
    result = f"Found {len(matching_procs)} processes matching '{name}':\n"
    for proc in matching_procs:
        try:
            cpu = proc.cpu_percent(interval=0)
            mem = proc.memory_info().rss / (1024**2)
            user = proc.info.get('username') or "Unknown"
            result += (f"- PID {proc.info['pid']} ({proc.info['name']}): "
                       f"Status: {proc.info['status']}, CPU: {cpu}%, "
                       f"Mem: {mem:.1f} MB, User: {user}\n")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return result

if __name__ == "__main__":
    mcp.run()
