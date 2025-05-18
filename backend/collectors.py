# backend/collectors.py

import psutil
import os
import shutil
import time
from datetime import timedelta
import subprocess # For running radeontop
import json       # Not used for current radeontop parsing, but kept for future
import re         # For regular expression parsing of text output

def get_cpu_usage():
    """Gets overall and per-CPU usage."""
    return {
        "overall": psutil.cpu_percent(interval=0.1, percpu=False),
        "per_core": psutil.cpu_percent(interval=0.1, percpu=True)
    }

def get_ram_usage():
    """Gets RAM usage statistics."""
    mem = psutil.virtual_memory()
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
    if not paths: 
        paths = ['/'] 

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
        except Exception as e: 
            storage_data.append({
                "path": path,
                "error": f"Error accessing path: {str(e)}"
            })
    return storage_data

_last_net_io = None
_last_time = None

def get_network_traffic():
    """
    Gets network I/O statistics per interface, including send/receive rates.
    Rates are calculated by comparing current and previous stats over a time delta.
    """
    global _last_net_io, _last_time 

    current_net_io = psutil.net_io_counters(pernic=True)
    current_time = time.time()
    traffic = []

    if _last_net_io is None or _last_time is None:
        _last_net_io = current_net_io
        _last_time = current_time
        for interface, stats in current_net_io.items():
            traffic.append({
                "interface": interface,
                "bytes_sent_mb": round(stats.bytes_sent / (1024**2), 2),
                "bytes_recv_mb": round(stats.bytes_recv / (1024**2), 2),
                "packets_sent": stats.packets_sent,
                "packets_recv": stats.packets_recv,
                "bytes_sent_rate_kbps": 0.0, 
                "bytes_recv_rate_kbps": 0.0,
                "errin": stats.errin,
                "errout": stats.errout,
                "dropin": stats.dropin,
                "dropout": stats.dropout
            })
        return traffic

    time_delta = current_time - _last_time
    if time_delta <= 0: 
        time_delta = 1 

    for interface, current_stats in current_net_io.items():
        last_stats = _last_net_io.get(interface)
        bytes_sent_rate_kbps = 0.0
        bytes_recv_rate_kbps = 0.0

        if last_stats:
            bytes_sent_delta = current_stats.bytes_sent - last_stats.bytes_sent
            bytes_recv_delta = current_stats.bytes_recv - last_stats.bytes_recv

            if bytes_sent_delta >= 0:
                 bytes_sent_rate_kbps = round((bytes_sent_delta * 8) / time_delta / 1000, 2)
            if bytes_recv_delta >= 0:
                bytes_recv_rate_kbps = round((bytes_recv_delta * 8) / time_delta / 1000, 2)
        
        traffic.append({
            "interface": interface,
            "bytes_sent_mb": round(current_stats.bytes_sent / (1024**2), 2), 
            "bytes_recv_mb": round(current_stats.bytes_recv / (1024**2), 2), 
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
    return str(timedelta(seconds=int(uptime_seconds)))

def get_load_average():
    """Gets system load average (1, 5, 15 min)."""
    try:
        load_avg = psutil.getloadavg()
        return {
            "one_min": round(load_avg[0], 2),
            "five_min": round(load_avg[1], 2),
            "fifteen_min": round(load_avg[2], 2)
        }
    except AttributeError: 
        return { "one_min": "N/A", "five_min": "N/A", "fifteen_min": "N/A" }
    except Exception: 
        return { "one_min": "Error", "five_min": "Error", "fifteen_min": "Error" }


def get_system_logs(log_files_config, lines_count=20):
    """Reads the last N lines from configured log files."""
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
                with open(log_path, 'r', errors='ignore') as f: 
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

def parse_radeontop_single_line_output(text_output):
    """
    Parses the single-line, comma-separated output from some radeontop versions.
    Example line: 17...: bus 81, gpu 0.00%, ..., vram 0.14% 5.69mb, ...
    """
    metrics = {}
    # Find the line that starts with a timestamp and colon (data line)
    data_line = None
    for line in text_output.splitlines():
        if re.match(r"^\d+\.\d+:", line):
            data_line = line
            break
    
    if not data_line:
        return metrics # No data line found

    # Remove the timestamp part
    data_line = re.sub(r"^\d+\.\d+:\s*bus\s*\d+,\s*", "", data_line).strip()

    # Split by comma and parse key-value pairs
    # This is a simplified parser; more robust would be to use regex for each expected metric.
    parts = [p.strip() for p in data_line.split(',')]
    
    # Generic pattern to find "name value% value_unit" or "name value%"
    # Example: "gpu 0.00%", "vram 0.14% 5.69mb", "mclk 20.00% 0.300ghz"
    
    # GPU Load
    gpu_match = re.search(r"gpu\s+([\d.]+?)%", data_line)
    if gpu_match: metrics["gpu_load_percent"] = float(gpu_match.group(1))

    # VRAM
    vram_match = re.search(r"vram\s+([\d.]+?)%\s+([\d.]+?)mb", data_line)
    if vram_match:
        metrics["vram_usage_percent"] = float(vram_match.group(1))
        metrics["vram_used_mb"] = float(vram_match.group(2))
    
    # MCLK (Memory Clock)
    mclk_match = re.search(r"mclk\s+([\d.]+?)%\s+([\d.]+?)ghz", data_line)
    if mclk_match:
        metrics["mem_clock_mclk_percent"] = float(mclk_match.group(1))
        metrics["mem_clock_mclk_mhz"] = float(mclk_match.group(2)) * 1000 # Convert GHz to MHz
        
    # SCLK (GPU Clock)
    sclk_match = re.search(r"sclk\s+([\d.]+?)%\s+([\d.]+?)ghz", data_line)
    if sclk_match:
        metrics["gpu_clock_sclk_percent"] = float(sclk_match.group(1))
        metrics["gpu_clock_sclk_mhz"] = float(sclk_match.group(2)) * 1000 # Convert GHz to MHz

    # Try to get device name (often first line or near it from the full output)
    # This is very heuristic and might not be available in the single data line.
    # We'll rely on the `get_radeontop_data` to try and find it in the full output.
    first_line_of_output = text_output.splitlines()[0] if text_output.splitlines() else ""
    device_name_match = re.search(r"for device.*?\((.*?)\)", first_line_of_output)
    if device_name_match:
        metrics["device_name"] = device_name_match.group(1).strip()
    else:
        # Fallback if not found in the first line (e.g. if first line is "Dumping to...")
        second_line_of_output = text_output.splitlines()[1] if len(text_output.splitlines()) > 1 else ""
        device_name_match_alt = re.search(r"for device.*?\((.*?)\)", second_line_of_output)
        if device_name_match_alt:
             metrics["device_name"] = device_name_match_alt.group(1).strip()
        else:
            metrics["device_name"] = "Unknown AMD GPU (text parse)"
            
    # Add other engine percentages if needed, e.g.:
    # ee_match = re.search(r"ee\s+([\d.]+?)%", data_line)
    # if ee_match: metrics["ee_percent"] = float(ee_match.group(1))

    return metrics


def get_radeontop_data():
    """
    Collects AMD GPU statistics using radeontop, parsing text output.
    Requires radeontop to be installed and accessible GPU devices.
    """
    radeontop_data = {"status": "Radeontop data not available.", "metrics": {}}
    try:
        process = subprocess.run(
            ['radeontop', '-l', '1', '-d', '-'], 
            capture_output=True,
            text=True,
            timeout=5 
        )

        radeontop_data["raw_output_sample"] = process.stdout[:1000] # Store raw output for debugging

        if process.returncode == 0:
            try:
                # Use the new parser for single-line format
                parsed_metrics = parse_radeontop_single_line_output(process.stdout) 
                
                if parsed_metrics and "gpu_load_percent" in parsed_metrics: # Check if essential metric is present
                    radeontop_data["status"] = "Radeontop data collected (text parsed)."
                    radeontop_data["metrics"] = parsed_metrics
                elif parsed_metrics: # Some metrics parsed, but maybe not all expected
                    radeontop_data["status"] = "Radeontop: Some metrics parsed, check details."
                    radeontop_data["metrics"] = parsed_metrics
                else: # No metrics parsed from the data line
                    radeontop_data["status"] = "Radeontop: Parsed output, but no expected metrics found in data line."

            except Exception as e:
                radeontop_data["status"] = f"Radeontop: Error parsing text data - {str(e)}"
        
        elif process.stderr:
            if "invalid option" in process.stderr.lower():
                 radeontop_data["status"] = f"Radeontop error: {process.stderr.strip()[:200]}. (Consider checking radeontop version/flags)"
            else:
                radeontop_data["status"] = f"Radeontop error: {process.stderr.strip()[:200]}"
        else:
            radeontop_data["status"] = f"Radeontop exited with code {process.returncode} but no stderr."

    except FileNotFoundError:
        radeontop_data["status"] = "Radeontop command not found. Ensure it's installed in the container and in PATH."
    except subprocess.TimeoutExpired:
        radeontop_data["status"] = "Radeontop command timed out."
    except Exception as e:
        radeontop_data["status"] = f"An unexpected error occurred with Radeontop: {str(e)}"
    
    return radeontop_data


# --- Main function to gather all stats ---
def get_all_stats(log_files_to_monitor, storage_paths_to_monitor):
    """Gathers all system statistics by calling individual collector functions."""
    if not isinstance(log_files_to_monitor, list):
        log_files_to_monitor = []
    if not isinstance(storage_paths_to_monitor, list) or not storage_paths_to_monitor:
        storage_paths_to_monitor = ['/'] 

    return {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cpu": get_cpu_usage(),
        "ram": get_ram_usage(),
        "storage": get_storage_usage(paths=storage_paths_to_monitor),
        "network": get_network_traffic(),
        "uptime": get_system_uptime(),
        "load_average": get_load_average(),
        "logs": get_system_logs(log_files_config=log_files_to_monitor, lines_count=25), 
        "gpu_amd": get_radeontop_data() 
    }
