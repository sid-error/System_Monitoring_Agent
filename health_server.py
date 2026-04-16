import os
import psutil
import time
import json
from fastmcp import FastMCP

mcp = FastMCP("System Health Monitor")

@mcp.tool()
def get_cpu_usage() -> str:
    """Returns the current CPU usage percentage as a JSON table and chart."""
    usage = psutil.cpu_percent(interval=1)
    data = {
        "type": "table_and_chart",
        "chart_type": "bar",
        "x_axis": "Metric",
        "y_axis": "Percentage",
        "columns": ["Metric", "Percentage"],
        "data": [
            {"Metric": "CPU Usage", "Percentage": usage},
            {"Metric": "Idle", "Percentage": 100 - usage}
        ]
    }
    return json.dumps(data)

@mcp.tool()
def convert_to_diagram(metric_name: str, value: float, chart_type: str = "bar") -> str:
    """Explicitly converts a metric value into a diagrammatic JSON structure. 
    Use this to format any textual metric into a chart.
    """
    data = {
        "type": "table_and_chart",
        "chart_type": chart_type,
        "x_axis": "Metric",
        "y_axis": "Value",
        "columns": ["Metric", "Value"],
        "data": [
            {"Metric": metric_name, "Value": value}
        ]
    }
    if chart_type == "pie" and value <= 100:
         data["data"].append({"Metric": "Other", "Value": 100 - value})
    
    return json.dumps(data)

@mcp.tool()
def get_ram_usage() -> str:
    """Returns the current RAM usage including total, used, free and percentage. MUST be maintained precisely as the JSON output."""
    mem = psutil.virtual_memory()
    data = {
        "type": "table_and_chart",
        "chart_type": "pie",
        "x_axis": "Category",
        "y_axis": "Gigabytes",
        "columns": ["Category", "Gigabytes"],
        "data": [
            {"Category": "Used", "Gigabytes": round(mem.used / (1024**3), 2)},
            {"Category": "Free", "Gigabytes": round(mem.free / (1024**3), 2)}
        ]
    }
    return json.dumps(data)

@mcp.tool()
def get_disk_usage(path: str = "/") -> str:
    """Returns disk usage for a given path (e.g., 'C:' on Windows, '/' on Linux). MUST output exactly as JSON!"""
    if os.name == 'nt':
        if len(path) == 2 and path[1] == ':':
            path = path + "\\"
        if path.endswith(':'):
            path = path + "\\"
    try:
        usage = psutil.disk_usage(path)
        data = {
            "type": "table_and_chart",
            "chart_type": "pie",
            "x_axis": "Partition",
            "y_axis": "Gigabytes",
            "columns": ["Partition", "Gigabytes"],
            "data": [
                {"Partition": "Used", "Gigabytes": round(usage.used / (1024**3), 2)},
                {"Partition": "Free", "Gigabytes": round(usage.free / (1024**3), 2)}
            ]
        }
        return json.dumps(data)
    except FileNotFoundError:
        return f"Error: Drive or path '{path}' not found."
    except PermissionError:
        return f"Error: Permission denied for path '{path}'."
    except Exception as e:
        return f"Error checking disk usage: {str(e)}"

@mcp.tool()
def get_top_processes(n: int = 5) -> str:
    """Returns the top n processes by CPU usage as a JSON UI Schema. MUST NOT be modified from JSON string format!"""
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
                'PID': str(proc.info['pid']),
                'Process Name': proc.info['name'] or 'Unknown',
                'CPU Usage': float(round(cpu_percent, 1))
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
            
    proc_data.sort(key=lambda x: x['CPU Usage'], reverse=True)
    top_n = proc_data[:n]
    
    data = {
        "type": "table_and_chart",
        "chart_type": "bar",
        "x_axis": "Process Name",
        "y_axis": "CPU Usage",
        "columns": ["PID", "Process Name", "CPU Usage"],
        "data": top_n
    }
    
    return json.dumps(data)

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
                f"CPU: {cpu}%, Memory: {mem:.1f} MB, User: {user}")
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
        except:
            continue
    time.sleep(0.1)
    if not matching_procs: return f"No processes found matching name '{name}'."
        
    result = f"Found {len(matching_procs)} processes matching '{name}':\n"
    for proc in matching_procs:
        try:
            cpu = proc.cpu_percent(interval=0)
            mem = proc.memory_info().rss / (1024**2)
            user = proc.info.get('username') or "Unknown"
            result += (f"- PID {proc.info['pid']} ({proc.info['name']}): "
                       f"Status: {proc.info['status']}, CPU: {cpu}%, "
                       f"Mem: {mem:.1f} MB, User: {user}\n")
        except:
            continue
    return result

if __name__ == "__main__":
    mcp.run()
