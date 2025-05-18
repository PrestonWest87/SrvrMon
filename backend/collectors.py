# backend/collectors.py

import psutil
import os
import shutil
import time
from datetime import timedelta

def get_cpu_usage():
    """Gets overall and per-CPU usage."""
    # interval=0.1 means it's a non-blocking call that compares CPU times over the last 0.1s
    # Using a small interval helps in getting more real-time data.
    return {
        "overall": psutil.cpu_percent(interval=0.1, percpu=False),
        "per_core": psutil.cpu_percent(interval=0.1, percpu=True)
    }

def get_ram_usage():
    """Gets RAM usage statistics."""
    mem = psutil.virtual_memory()
    # Convert bytes to gigabytes (GB) for easier readability
    return {
        "total_gb": round(mem.total / (1024**3), 2),
        "available_gb": round(mem.available / (1024**3), 2),
        "used_gb": round(mem.used / (1024**3), 2),
        "percent": mem.percent
    }

def get_storage_usage(paths=['/']):
    """
    Gets storage usage for specified mount paths.
    'paths' should be a list of strings, e.g., ['/', '/mnt/data']
    These paths are from the container's perspective.
    """
    storage_data = []
    if not paths: # Ensure paths is not None or empty
        paths = ['/'] # Default to root if no paths are provided

    for path in paths:
        try:
            usage = shutil.disk_usage(path)
            storage_data.append({
                "path": path,
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
                "percent": round((usage.used / usage.total) * 100, 2)
            })
        except FileNotFoundError:
            storage_data.append({
                "path": path,
                "error": "Path not found or not accessible"
            })
        except Exception as e: # Catch other potential errors like permission issues
            storage_data.append({
                "path": path,
                "error": f"Error accessing path: {str(e)}"
            })
    return storage_data

# Static variables for network rate calculation
# These will persist across calls to get_network_traffic within the same process
_last_net_io = None
_last_time = None

def get_network_traffic():
    """
    Gets network I/O statistics per interface, including send/receive rates.
    Rates are calculated by comparing current and previous stats over a time delta.
    """
    global _last_net_io, _last_time # Use global to maintain state between calls

    current_net_io = psutil.net_io_counters(pernic=True)
    current_time = time.time()
    traffic = []

    if _last_net_io is None or _last_time is None:
        # First call, initialize and return current totals with zero rates
        _last_net_io = current_net_io
        _last_time = current_time
        for interface, stats in current_net_io.items():
            traffic.append({
                "interface": interface,
                "bytes_sent_mb": round(stats.bytes_sent / (1024**2), 2),
                "bytes_recv_mb": round(stats.bytes_recv / (1024**2), 2),
                "packets_sent": stats.packets_sent,
                "packets_recv": stats.packets_recv,
                "bytes_sent_rate_kbps": 0.0, # Kilobits per second
                "bytes_recv_rate_kbps": 0.0,
                "errin": stats.errin,
                "errout": stats.errout,
                "dropin": stats.dropin,
                "dropout": stats.dropout
            })
        return traffic

    time_delta = current_time - _last_time
    if time_delta <= 0: # Avoid division by zero or negative time delta
        time_delta = 1 # Assume 1 second if delta is too small or negative

    for interface, current_stats in current_net_io.items():
        last_stats = _last_net_io.get(interface)
        bytes_sent_rate_kbps = 0.0
        bytes_recv_rate_kbps = 0.0

        if last_stats:
            bytes_sent_delta = current_stats.bytes_sent - last_stats.bytes_sent
            bytes_recv_delta = current_stats.bytes_recv - last_stats.bytes_recv

            # Calculate rate in Kilobits per second (Kbps)
            # (bytes_delta * 8 bits/byte) / time_delta seconds / 1000 bits/Kb
            # Ensure deltas are not negative (e.g., counter reset, though psutil handles this for some OS)
            if bytes_sent_delta >= 0:
                 bytes_sent_rate_kbps = round((bytes_sent_delta * 8) / time_delta / 1000, 2)
            if bytes_recv_delta >= 0:
                bytes_recv_rate_kbps = round((bytes_recv_delta * 8) / time_delta / 1000, 2)
        
        traffic.append({
            "interface": interface,
            "bytes_sent_mb": round(current_stats.bytes_sent / (1024**2), 2), # Total MB
            "bytes_recv_mb": round(current_stats.bytes_recv / (1024**2), 2), # Total MB
            "packets_sent": current_stats.packets_sent,
            "packets_recv": current_stats.packets_recv,
            "bytes_sent_rate_kbps": bytes_sent_rate_kbps,
            "bytes_recv_rate_kbps": bytes_recv_rate_kbps,
            "errin": current_stats.errin,
            "errout": current_stats.errout,
            "dropin": current_stats.dropin,
            "dropout": current_stats.dropout
        })

    _last_net_io = current_net_io
    _last_time = current_time
    return traffic

def get_system_uptime():
    """Gets system uptime."""
    boot_time_timestamp = psutil.boot_time()
    current_time_timestamp = time.time()
    uptime_seconds = current_time_timestamp - boot_time_timestamp
    # Format as string like HH:MM:SS
    return str(timedelta(seconds=int(uptime_seconds)))

def get_load_average():
    """Gets system load average (1, 5, 15 min)."""
    try:
        # psutil.getloadavg() returns a tuple of 3 floats (1, 5, 15 min average)
        # This is typically only available on POSIX systems.
        load_avg = psutil.getloadavg()
        return {
            "one_min": round(load_avg[0], 2),
            "five_min": round(load_avg[1], 2),
            "fifteen_min": round(load_avg[2], 2)
        }
    except AttributeError: # Not available on Windows or some other OS
        return {
            "one_min": "N/A",
            "five_min": "N/A",
            "fifteen_min": "N/A"
        }
    except Exception: # Catch any other potential errors
        return {
            "one_min": "Error",
            "five_min": "Error",
            "fifteen_min": "Error"
        }


def get_system_logs(log_files_config, lines_count=20):
    """
    Reads the last N lines from configured log files.
    log_files_config is a list of dicts: [{'name': 'Syslog', 'path': '/var/log/syslog_mounted/syslog'}, ...]
    These paths are from the container's perspective.
    """
    logs_data = []
    if not log_files_config:
        return logs_data

    for log_config in log_files_config:
        log_entry = {"name": log_config.get("name", "Unnamed Log"), 
                     "path": log_config.get("path", ""), 
                     "lines": []}
        
        log_path = log_config.get("path")
        if not log_path:
            log_entry["lines"] = ["Error: Log path not provided in configuration."]
            logs_data.append(log_entry)
            continue

        try:
            if os.path.exists(log_path):
                with open(log_path, 'r', errors='ignore') as f: # 'errors=ignore' to skip decoding errors
                    # Read all lines and take the last N. This can be memory intensive for huge files.
                    # For very large files, more optimized methods might be needed (e.g., seek from end).
                    all_lines = f.readlines()
                    log_entry["lines"] = [line.strip() for line in all_lines[-lines_count:]]
            else:
                log_entry["lines"] = [f"Log file not found at {log_path}. Ensure it's mounted correctly or path is valid."]
        except PermissionError:
            log_entry["lines"] = [f"Permission denied reading log file: {log_path}."]
        except Exception as e:
            log_entry["lines"] = [f"Error reading log {log_path}: {str(e)}"]
        logs_data.append(log_entry)
    return logs_data

def get_radeontop_data():
    """
    Placeholder for Radeontop data collection.
    Integrating radeontop effectively requires:
    1. radeontop installed in the container.
    2. Access to AMD GPU devices (e.g., /dev/dri/card*) mounted into the container.
    3. Potentially elevated privileges for the container.
    4. A method to run radeontop in a non-interactive mode and parse its output.
       Example: `radeontop -d - -l 1` might output to stdout once.
    This is complex and OS/hardware dependent.
    """
    # Example (conceptual, would need subprocess and parsing):
    # try:
    #     result = subprocess.run(['radeontop', '-d', '-', '-l', '1'], capture_output=True, text=True, timeout=2)
    #     if result.returncode == 0:
    #         # Parse result.stdout here
    #         return {"status": "Data from radeontop (parsed)", "raw_output": result.stdout[:200]} # Truncate for example
    #     else:
    #         return {"status": f"Radeontop error: {result.stderr[:200]}"}
    # except FileNotFoundError:
    #     return {"status": "Radeontop command not found in container."}
    # except Exception as e:
    #     return {"status": f"Error running radeontop: {str(e)}"}
    return {"status": "Radeontop monitoring not actively implemented in this example."}

# --- Main function to gather all stats ---
def get_all_stats(log_files_to_monitor, storage_paths_to_monitor):
    """Gathers all system statistics by calling individual collector functions."""
    # Ensure parameters are lists, even if None or empty string was passed from env var parsing
    if not isinstance(log_files_to_monitor, list):
        log_files_to_monitor = []
    if not isinstance(storage_paths_to_monitor, list) or not storage_paths_to_monitor:
        storage_paths_to_monitor = ['/'] # Default to root if empty or not a list

    return {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cpu": get_cpu_usage(),
        "ram": get_ram_usage(),
        "storage": get_storage_usage(paths=storage_paths_to_monitor),
        "network": get_network_traffic(),
        "uptime": get_system_uptime(),
        "load_average": get_load_average(),
        "logs": get_system_logs(log_files_config=log_files_to_monitor, lines_count=25), # Increased default lines
        "gpu_amd": get_radeontop_data() # Placeholder for AMD GPU stats
    }
