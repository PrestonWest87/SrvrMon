# backend/collectors.py

import psutil
import os
import shutil
import time
from datetime import timedelta
import subprocess # For running radeontop
import json       # Not used for current radeontop parsing, but kept for future
import re         # For regular expression parsing of text output
import logging
import docker # For Docker container stats
from dateutil import parser as dateutil_parser # For parsing ISO 8601 dates from Docker
from datetime import timezone # For timezone-aware datetime objects


logger = logging.getLogger(__name__)

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
            logger.warning("Storage path %s not found or not accessible.", path)
        except Exception as e: 
            storage_data.append({
                "path": path,
                "error": f"Error accessing path: {str(e)}"
            })
            logger.exception("Error accessing storage path %s:", path)
    return storage_data

_last_net_io = None
_last_time = None

# Global variables for disk I/O rate calculation
_last_disk_io_counters = {}
_last_disk_io_time = None


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

def get_nvidia_gpu_data():
    """Collects NVIDIA GPU statistics using nvidia-smi."""
    try:
        process = subprocess.run(
            ['nvidia-smi', '--query-gpu=timestamp,name,temperature.gpu,utilization.gpu,utilization.memory,memory.total,memory.used,memory.free', '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            timeout=10  # Added timeout
        )
        if process.returncode != 0:
            # Handle cases where nvidia-smi exists but fails (e.g. no GPU, driver issue)
            error_message = process.stderr.strip() if process.stderr else "Unknown error"
            if "NVIDIA-SMI has failed" in error_message or "No devices were found" in error_message:
                 return {"status": "No NVIDIA GPUs detected or driver issue.", "gpus": []}
            return {"status": f"Error executing NVIDIA SMI: {error_message[:200]}", "gpus": []}

        output = process.stdout.strip()
        if not output:
            return {"status": "No NVIDIA GPUs detected or unexpected output", "gpus": []}

        gpus_data = []
        lines = output.splitlines()
        for line in lines:
            parts = line.split(', ')
            if len(parts) == 8:
                try:
                    gpus_data.append({
                        "timestamp": parts[0],
                        "name": parts[1],
                        "temperature_gpu": float(parts[2]) if parts[2].strip().lower() != '[not supported]' else None,
                        "utilization_gpu_percent": float(parts[3]) if parts[3].strip().lower() != '[not supported]' else None,
                        "utilization_memory_percent": float(parts[4]) if parts[4].strip().lower() != '[not supported]' else None,
                        "memory_total_mb": float(parts[5]) if parts[5].strip().lower() != '[not supported]' else None,
                        "memory_used_mb": float(parts[6]) if parts[6].strip().lower() != '[not supported]' else None,
                        "memory_free_mb": float(parts[7]) if parts[7].strip().lower() != '[not supported]' else None,
                    })
                except ValueError as e:
                    logger.warning("Could not parse NVIDIA GPU data line: %s - Error: %s", line, e)
                    continue # Skip this line
            else:
                logger.warning("Unexpected number of fields in nvidia-smi output line: %s", line)

        if not gpus_data and lines: # If lines were processed but no data was added (e.g. all lines malformed)
            logger.warning("NVIDIA SMI output format not recognized from output: %s", output[:500])
            return {"status": "NVIDIA SMI output format not recognized", "gpus": []}
        
        logger.debug("NVIDIA GPU data collected successfully.")
        return {"status": "NVIDIA GPU data collected.", "gpus": gpus_data}

    except FileNotFoundError:
        logger.warning("NVIDIA SMI command not found.")
        return {"status": "NVIDIA SMI not found. Ensure it's installed and in PATH.", "gpus": []}
    except subprocess.TimeoutExpired:
        logger.warning("NVIDIA SMI command timed out.")
        return {"status": "NVIDIA SMI command timed out.", "gpus": []}
    except Exception as e:
        logger.exception("An unexpected error occurred with NVIDIA SMI:")
        return {"status": f"An unexpected error occurred with NVIDIA SMI: {str(e)}", "gpus": []}

def get_load_average():
    """Gets system load average (1, 5, 15 min)."""
    try:
        load_avg = psutil.getloadavg()
        return {
            "one_min": round(load_avg[0], 2),
            "five_min": round(load_avg[1], 2),
            "fifteen_min": round(load_avg[2], 2)
        }
    except AttributeError: # psutil.getloadavg() not available on all platforms (e.g. Windows)
        logger.info("psutil.getloadavg() not available on this platform.")
        return { "one_min": "N/A", "five_min": "N/A", "fifteen_min": "N/A" }
    except Exception as e: 
        logger.exception("Error getting load average:")
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
            logger.warning("Log path not provided for log config item: %s", log_config.get("name", "Unnamed Log"))
            logs_data.append(log_entry)
            continue

        try:
            if os.path.exists(log_path):
                with open(log_path, 'r', errors='ignore') as f: 
                    all_lines = f.readlines()
                    log_entry["lines"] = [line.strip() for line in all_lines[-lines_count:]]
            else:
                log_entry["lines"] = [f"Log file not found at {log_path}. Ensure it's mounted correctly or path is valid."]
                logger.warning("Log file not found at %s for %s.", log_path, log_config.get("name"))
        except PermissionError:
            log_entry["lines"] = [f"Permission denied reading log file: {log_path}."]
            logger.error("Permission denied reading log file: %s for %s.", log_path, log_config.get("name"))
        except Exception as e:
            log_entry["lines"] = [f"Error reading log {log_path}: {str(e)}"]
            logger.exception("Error reading log %s for %s:", log_path, log_config.get("name"))
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
    if not text_output or not text_output.strip(): # Handle empty output
        return metrics

    for line in text_output.splitlines():
        if re.match(r"^\d+\.\d+:", line): # Example: "1700000000.123: ..."
            data_line = line
            break
    
    if not data_line:
        # Could be that radeontop output "Dumping to -" or similar without actual data lines
        # if "Dumping to -" in text_output or "waiting for client" in text_output.lower():
        #     return {"error": "No data line from radeontop, possibly no activity or header only."}
        return metrics # No data line found, return empty metrics

    # Remove the timestamp part e.g. "1700000000.123: bus 0, ..." -> "bus 0, ..."
    cleaned_data_line = re.sub(r"^\d+\.\d+:\s*", "", data_line).strip()
    
    # Try to extract device name from the full output (often in header lines)
    device_name = "Unknown AMD GPU"
    name_match = re.search(r"for device .* \((.*?)\) on bus", text_output, re.IGNORECASE)
    if name_match:
        device_name = name_match.group(1).strip()
    metrics["device_name"] = device_name

    # GPU Load: "gpu 12.34%"
    gpu_match = re.search(r"gpu\s+([\d.]+?)%", cleaned_data_line)
    if gpu_match: metrics["gpu_load_percent"] = float(gpu_match.group(1))

    # VRAM: "vram 5.67% 123mb" or "vram 5.67% 1.23gb"
    vram_match = re.search(r"vram\s+([\d.]+?)%\s+([\d.]+?)(mb|gb)", cleaned_data_line, re.IGNORECASE)
    if vram_match:
        metrics["vram_usage_percent"] = float(vram_match.group(1))
        vram_val = float(vram_match.group(2))
        vram_unit = vram_match.group(3).lower()
        if vram_unit == "gb":
            metrics["vram_used_mb"] = vram_val * 1024
        else:
            metrics["vram_used_mb"] = vram_val
    
    # MCLK (Memory Clock): "mclk 20.00% 0.300ghz" or "mclk 100.00% 1000mhz"
    mclk_match = re.search(r"mclk\s+([\d.]+?)%\s+([\d.]+?)(mhz|ghz)", cleaned_data_line, re.IGNORECASE)
    if mclk_match:
        metrics["mem_clock_mclk_percent"] = float(mclk_match.group(1))
        mclk_val = float(mclk_match.group(2))
        mclk_unit = mclk_match.group(3).lower()
        if mclk_unit == "ghz":
            metrics["mem_clock_mclk_mhz"] = mclk_val * 1000
        else:
            metrics["mem_clock_mclk_mhz"] = mclk_val
        
    # SCLK (GPU Clock): "sclk 30.00% 0.500ghz" or "sclk 90.00% 900mhz"
    sclk_match = re.search(r"sclk\s+([\d.]+?)%\s+([\d.]+?)(mhz|ghz)", cleaned_data_line, re.IGNORECASE)
    if sclk_match:
        metrics["gpu_clock_sclk_percent"] = float(sclk_match.group(1))
        sclk_val = float(sclk_match.group(2))
        sclk_unit = sclk_match.group(3).lower()
        if sclk_unit == "ghz":
            metrics["gpu_clock_sclk_mhz"] = sclk_val * 1000
        else:
            metrics["gpu_clock_sclk_mhz"] = sclk_val
            
    # Add other engine percentages if needed, e.g.:
    # ee_match = re.search(r"ee\s+([\d.]+?)%", cleaned_data_line)
    # if ee_match: metrics["ee_percent"] = float(ee_match.group(1))

    return metrics


def get_radeontop_data():
    """
    Collects AMD GPU statistics using radeontop, parsing text output.
    Requires radeontop to be installed and accessible GPU devices.
    """
    radeontop_data = {"status": "Radeontop data not available.", "metrics": {}, "raw_output_sample": ""}
    cmd1 = ['radeontop', '-l', '1', '-d', '-']
    cmd2 = ['radeontop', '-l', '1']
    process = None
    
    try:
        # Try with '-d -' first for dumping to stdout
        logger.debug(f"Attempting radeontop with command: {' '.join(cmd1)}")
        process = subprocess.run(
            cmd1,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        # If '-d -' fails, try without it
        if process.returncode != 0:
            stderr_for_debug = process.stderr.strip() if process.stderr else "No stderr."
            logger.warning(f"Radeontop command {' '.join(cmd1)} failed (code {process.returncode}): {stderr_for_debug[:200]}. Trying {' '.join(cmd2)}.")
            process = subprocess.run(
                cmd2,
                capture_output=True,
                text=True,
                timeout=5
            )
        
        # Store raw output for debugging, regardless of success or failure of the command itself
        # This helps diagnose parsing issues or unexpected command output.
        raw_stdout = process.stdout.strip() if process.stdout else "No stdout."
        raw_stderr = process.stderr.strip() if process.stderr else "No stderr."
        radeontop_data["raw_output_sample"] = f"STDOUT: {raw_stdout[:500]}\nSTDERR: {raw_stderr[:500]}"

        if process.returncode == 0:
            logger.debug(f"Radeontop command successful. Output: {raw_stdout[:200]}")
            parsed_metrics = parse_radeontop_single_line_output(process.stdout) # Use full stdout
            if parsed_metrics and "gpu_load_percent" in parsed_metrics:
                radeontop_data["status"] = "Radeontop data collected."
                radeontop_data["metrics"] = parsed_metrics
                logger.debug("Radeontop metrics parsed successfully.")
            elif parsed_metrics:
                radeontop_data["status"] = "Radeontop: Some metrics parsed, but key data (e.g., GPU load) might be missing."
                radeontop_data["metrics"] = parsed_metrics
                logger.info("Radeontop: Some metrics parsed, but key data might be missing.")
            elif not raw_stdout: # Output was empty
                radeontop_data["status"] = "No AMD GPU detected by Radeontop (empty output)."
                logger.info("Radeontop command produced no output.")
            else: # Non-empty output but parsing failed to find expected metrics
                radeontop_data["status"] = "Radeontop: Failed to parse output or no relevant data found."
                logger.warning(f"Radeontop: Failed to parse output or no relevant data found. Raw output sample: {raw_stdout[:500]}")
        else:
            # Radeontop command failed
            logger.warning(f"Radeontop command {' '.join(cmd2 if process.args == cmd2 else cmd1)} failed with code {process.returncode}. Stderr: {raw_stderr[:200]}")
            if "no amd gpu detected" in raw_stderr.lower():
                radeontop_data["status"] = "No AMD GPU detected by Radeontop."
            elif "Could not find VCE Governor" in raw_stderr:
                # This can sometimes be a non-fatal error, try parsing stdout anyway
                logger.info("Radeontop: 'Could not find VCE Governor'. Will attempt to parse other metrics.")
                parsed_metrics = parse_radeontop_single_line_output(process.stdout)
                if parsed_metrics and "gpu_load_percent" in parsed_metrics:
                    radeontop_data["status"] = "Radeontop data collected (VCE Governor not found, this is often okay)."
                    radeontop_data["metrics"] = parsed_metrics
                    logger.debug("Radeontop metrics parsed successfully despite VCE Governor error.")
                else:
                    radeontop_data["status"] = "Radeontop: VCE Governor not found and failed to parse other metrics."
                    logger.warning("Radeontop: VCE Governor not found and failed to parse other metrics.")
            else:
                radeontop_data["status"] = f"Radeontop error: {raw_stderr[:200]}"

    except FileNotFoundError:
        logger.warning("Radeontop command not found. Ensure it's installed.")
        radeontop_data["status"] = "Radeontop command not found. Ensure it's installed."
    except subprocess.TimeoutExpired:
        logger.warning("Radeontop command timed out.")
        radeontop_data["status"] = "Radeontop command timed out."
    except Exception as e:
        logger.exception("An unexpected error occurred with Radeontop:")
        radeontop_data["status"] = f"An unexpected error occurred with Radeontop: {str(e)}"
    
    # Final check to ensure metrics key exists, even if empty
    if "metrics" not in radeontop_data:
        radeontop_data["metrics"] = {}
        
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
        "gpu_nvidia": get_nvidia_gpu_data(),
        "gpu_amd": get_radeontop_data(),
        "docker_containers": get_docker_stats(),
        "disk_io": get_disk_io_stats(),
        "processes": get_process_stats(),
        "temperatures": get_sensor_temperatures()
    }

def get_sensor_temperatures():
    """Collects sensor temperature data."""
    sensor_data = {"status": "Sensor temperature data not available.", "sensors": {}}
    
    if not hasattr(psutil, 'sensors_temperatures'):
        logger.info("psutil.sensors_temperatures() not available on this system.")
        sensor_data["status"] = "Sensor temperature data not available on this system (psutil lacks support)."
        return sensor_data

    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            logger.info("No sensors detected by psutil.sensors_temperatures().")
            sensor_data["status"] = "No temperature sensors detected."
            return sensor_data

        processed_sensors = {}
        for name, entries in temps.items():
            processed_entries = []
            for entry in entries:
                processed_entries.append({
                    "label": entry.label or name, # Use main name if sub-label is empty
                    "current": float(entry.current) if entry.current is not None else None,
                    "high": float(entry.high) if entry.high is not None else None,
                    "critical": float(entry.critical) if entry.critical is not None else None,
                })
            processed_sensors[name] = processed_entries
        
        sensor_data["sensors"] = processed_sensors
        sensor_data["status"] = "OK"
        logger.debug(f"Collected sensor temperatures for {len(processed_sensors)} groups.")

    except AttributeError: # Fallback if sensors_temperatures was dynamically removed or a sub-attribute missing
        logger.warning("psutil.sensors_temperatures() attribute error during execution.")
        sensor_data["status"] = "Sensor temperature data not available on this system (AttributeError)."
    except Exception as e:
        logger.exception("Error collecting sensor temperatures:")
        sensor_data["status"] = f"Error collecting sensor temperatures: {str(e)}"
        
    return sensor_data

def get_process_stats(top_n=10):
    """Collects information about top CPU and Memory consuming processes."""
    processes_data = []
    # Initialize CPU percent calculation for all processes
    # A very small interval or 0.0 means non-blocking and gives CPU % since last call or process start
    try:
        psutil.cpu_percent(interval=0.01) 
    except Exception as e:
        logger.error(f"Initial psutil.cpu_percent call failed: {e}")
        # This might not be fatal, individual process cpu_percent might still work or return 0
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'status', 'create_time']):
            try:
                # cpu_percent(interval=None) gives usage since last call or process start for this specific process
                # For a continuously running monitor, this gives a snapshot of recent CPU usage
                p_cpu_percent = proc.info['cpu_percent'] # Already called by process_iter if fields are cached
                if p_cpu_percent is None: # if first call for this process, it might be None
                    p_cpu_percent = proc.cpu_percent(interval=None) # try one more time

                processes_data.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'] or 'N/A',
                    'username': proc.info['username'] or 'N/A',
                    'cpu_percent': p_cpu_percent if p_cpu_percent is not None else 0.0,
                    'memory_percent': round(proc.info['memory_percent'], 2) if proc.info['memory_percent'] is not None else 0.0,
                    'status': proc.info['status'] or 'N/A'
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logger.debug(f"Skipping process due to {type(e).__name__}: {e}")
                continue
            except Exception as e:
                logger.warning(f"Error collecting data for a process: {e}")
                continue
    except Exception as e:
        logger.error(f"Error iterating through processes: {e}")
        return {"status": f"Error collecting process data: {str(e)}", "top_cpu": [], "top_mem": []}

    # Sort processes
    try:
        # It's possible cpu_percent is None for some processes on first call, handle this in sort
        top_cpu_processes = sorted(
            [p for p in processes_data if p['cpu_percent'] is not None], 
            key=lambda x: x['cpu_percent'], 
            reverse=True
        )[:top_n]
        
        top_mem_processes = sorted(
            [p for p in processes_data if p['memory_percent'] is not None], 
            key=lambda x: x['memory_percent'], 
            reverse=True
        )[:top_n]
    except Exception as e:
        logger.error(f"Error sorting process data: {e}")
        return {"status": f"Error sorting process data: {str(e)}", "top_cpu": [], "top_mem": []}
    
    logger.debug(f"Collected top {top_n} CPU and Memory processes.")
    return {"status": "OK", "top_cpu": top_cpu_processes, "top_mem": top_mem_processes}


def get_disk_io_stats():
    """Collects disk I/O statistics (per disk) including rates."""
    global _last_disk_io_counters, _last_disk_io_time
    disk_io_data = []

    try:
        current_disk_io = psutil.disk_io_counters(perdisk=True)
    except Exception as e:
        logger.error(f"Could not retrieve disk I/O counters: {e}")
        return {"status": f"Error getting disk I/O: {str(e)}", "disks": []}

    current_time = time.time()

    if not current_disk_io:
        logger.info("No disk I/O counters found.")
        return {"status": "No disk I/O counters available.", "disks": []}

    if not _last_disk_io_counters or _last_disk_io_time is None:
        # Store current values and return zero rates for the first call
        for disk_name, stats in current_disk_io.items():
            disk_io_data.append({
                "disk_name": disk_name,
                "read_mb_s": 0.0,
                "write_mb_s": 0.0,
                "read_iops": 0.0,
                "write_iops": 0.0,
                "total_read_gb": round(stats.read_bytes / (1024**3), 2),
                "total_write_gb": round(stats.write_bytes / (1024**3), 2),
                "read_time_ms": stats.read_time, # Time spent reading from disk (ms)
                "write_time_ms": stats.write_time # Time spent writing to disk (ms)
            })
        _last_disk_io_counters = current_disk_io
        _last_disk_io_time = current_time
        return {"status": "OK", "disks": disk_io_data}

    time_delta = current_time - _last_disk_io_time
    if time_delta <= 0: # Avoid division by zero or negative time_delta
        time_delta = 1 # Or handle as an error/stale data

    for disk_name, current_stats in current_disk_io.items():
        last_stats = _last_disk_io_counters.get(disk_name)
        read_mb_s, write_mb_s, read_iops, write_iops = 0.0, 0.0, 0.0, 0.0

        if last_stats:
            delta_read_bytes = current_stats.read_bytes - last_stats.read_bytes
            delta_write_bytes = current_stats.write_bytes - last_stats.write_bytes
            delta_read_count = current_stats.read_count - last_stats.read_count
            delta_write_count = current_stats.write_count - last_stats.write_count

            if delta_read_bytes >= 0: # Ensure non-negative delta (counter wraps are rare but possible)
                read_mb_s = round((delta_read_bytes / time_delta) / (1024**2), 2)
            if delta_write_bytes >= 0:
                write_mb_s = round((delta_write_bytes / time_delta) / (1024**2), 2)
            if delta_read_count >= 0:
                read_iops = round(delta_read_count / time_delta, 2)
            if delta_write_count >= 0:
                write_iops = round(delta_write_count / time_delta, 2)
        
        disk_io_data.append({
            "disk_name": disk_name,
            "read_mb_s": read_mb_s,
            "write_mb_s": write_mb_s,
            "read_iops": read_iops,
            "write_iops": write_iops,
            "total_read_gb": round(current_stats.read_bytes / (1024**3), 2),
            "total_write_gb": round(current_stats.write_bytes / (1024**3), 2),
            "read_time_ms": current_stats.read_time,
            "write_time_ms": current_stats.write_time
        })

    _last_disk_io_counters = current_disk_io
    _last_disk_io_time = current_time
    
    logger.debug(f"Collected disk I/O stats for {len(disk_io_data)} disks.")
    return {"status": "OK", "disks": disk_io_data}


def get_docker_stats():
    """Collects statistics about running and all Docker containers."""
    docker_data = {"status": "Docker data not available", "containers": []}
    try:
        client = docker.from_env()
        # Test if Docker daemon is running
        client.ping() 
        logger.debug("Successfully connected to Docker daemon.")
    except docker.errors.DockerException as e:
        logger.warning(f"Could not connect to Docker daemon. Is it running? Is the socket mounted? Error: {e}")
        docker_data["status"] = f"Docker not available: {str(e)}"
        return docker_data
    except Exception as e: # Catch other potential errors like FileNotFoundError if socket is misconfigured
        logger.error(f"An unexpected error occurred while initializing Docker client: {e}")
        docker_data["status"] = f"Docker client init error: {str(e)}"
        return docker_data

    try:
        containers = client.containers.list(all=True)
        if not containers:
            docker_data["status"] = "No Docker containers found."
            logger.info("No Docker containers found.")
            return docker_data

        container_list = []
        for container in containers:
            attrs = container.attrs
            state = attrs.get('State', {})
            status = state.get('Status', 'unknown')
            image_name = container.image.tags[0] if container.image.tags else 'N/A'
            
            uptime_str = "N/A"
            if status == 'running':
                try:
                    started_at_str = state.get('StartedAt')
                    if started_at_str and not started_at_str.startswith("0001-01-01"): # Check for invalid zero-time
                        # Make started_at timezone-aware if it's not (assume UTC if naive)
                        started_at_dt = dateutil_parser.isoparse(started_at_str)
                        if started_at_dt.tzinfo is None:
                             started_at_dt = started_at_dt.replace(tzinfo=timezone.utc)
                        
                        now_utc = datetime.now(timezone.utc)
                        uptime_delta = now_utc - started_at_dt
                        
                        days = uptime_delta.days
                        hours, remainder = divmod(uptime_delta.seconds, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        
                        if days > 0:
                            uptime_str = f"{days}d {hours}h"
                        elif hours > 0:
                            uptime_str = f"{hours}h {minutes}m"
                        elif minutes > 0:
                            uptime_str = f"{minutes}m {seconds}s"
                        else:
                            uptime_str = f"{seconds}s"
                    else: # Handle cases where StartedAt might be missing or zero
                         uptime_str = "Running (uptime N/A)"

                except Exception as e:
                    logger.warning(f"Could not parse uptime for container {container.short_id}: {e}. StartedAt: {state.get('StartedAt')}")
                    uptime_str = "Running (err)"
            elif status == 'exited':
                try:
                    started_at_str = state.get('StartedAt')
                    finished_at_str = state.get('FinishedAt')
                    if started_at_str and finished_at_str and \
                       not started_at_str.startswith("0001-01-01") and \
                       not finished_at_str.startswith("0001-01-01"):
                        
                        started_at_dt = dateutil_parser.isoparse(started_at_str)
                        if started_at_dt.tzinfo is None: started_at_dt = started_at_dt.replace(tzinfo=timezone.utc)
                        
                        finished_at_dt = dateutil_parser.isoparse(finished_at_str)
                        if finished_at_dt.tzinfo is None: finished_at_dt = finished_at_dt.replace(tzinfo=timezone.utc)
                        
                        duration_delta = finished_at_dt - started_at_dt
                        uptime_str = f"Exited (ran for {str(duration_delta).split('.')[0]})" # Show duration
                    else: # Handle cases where times might be missing or zero
                        uptime_str = f"Exited (duration N/A)"
                except Exception as e:
                    logger.warning(f"Could not parse duration for exited container {container.short_id}: {e}")
                    uptime_str = "Exited (err)"
            else: # created, restarting, paused etc.
                uptime_str = status.capitalize()


            container_list.append({
                "id": container.short_id,
                "name": ", ".join(container.name for container in [container]), # container.name is a string
                "status": status,
                "uptime": uptime_str,
                "image": image_name,
            })
        
        docker_data["status"] = "OK"
        docker_data["containers"] = container_list
        logger.debug(f"Collected data for {len(container_list)} Docker containers.")

    except docker.errors.APIError as e:
        logger.error(f"Docker API error while fetching container list: {e}")
        docker_data["status"] = f"Docker API error: {str(e)}"
    except Exception as e:
        logger.exception("An unexpected error occurred while fetching Docker stats:")
        docker_data["status"] = f"Unexpected error fetching Docker stats: {str(e)}"
        
    return docker_data
