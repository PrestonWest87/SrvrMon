import streamlit as st
import pandas as pd
import os
import time
import re
from datetime import datetime
from backend.collectors import get_all_stats

# --- Page Configuration ---
st.set_page_config(page_title="Live Server Monitor", page_icon="🖥️", layout="wide")

# --- Configuration & Env Vars ---
POLLING_INTERVAL = int(os.environ.get('POLLING_INTERVAL_MS', 5000)) / 1000.0
STORAGE_PATHS = os.environ.get('STORAGE_PATHS', '/').split(',')
MAX_HISTORY = 60 

# --- Local History Tracking (No session state needed in a while loop!) ---
history = {
    'timestamp': [], 'cpu': [], 'ram': [],
    'net_sent': [], 'net_recv': [], 'avg_core_temp': []
}

def update_history(stats, hist):
    now = datetime.now()
    hist['timestamp'].append(now)
    hist['cpu'].append(stats['cpu']['overall'])
    hist['ram'].append(stats['ram']['percent'])
    
    hist['net_sent'].append(sum(n['bytes_sent_rate_kbps'] for n in stats['network'] if n['interface'] != 'lo'))
    hist['net_recv'].append(sum(n['bytes_recv_rate_kbps'] for n in stats['network'] if n['interface'] != 'lo'))

    core_temps = []
    if stats['temperatures']['status'] == 'OK':
        for group, sensors in stats['temperatures']['sensors'].items():
            for s in sensors:
                lbl = s.get('label', '').lower()
                if 'core' in lbl or 'tctl' in lbl or 'die' in lbl or 'cpu' in lbl:
                    if s['current'] is not None:
                        core_temps.append(s['current'])
                        
    hist['avg_core_temp'].append(sum(core_temps) / len(core_temps) if core_temps else 0.0)

    for key in hist:
        hist[key] = hist[key][-MAX_HISTORY:]

LOG_CONFIG_ENV = os.environ.get('LOG_CONFIG', '')
LOG_FILES = [{'name': n.strip(), 'path': p.strip()} for n, p in (item.split(':', 1) for item in LOG_CONFIG_ENV.split(',') if ':' in item)]


# ==========================================
# 1. BUILD THE STATIC UI SKELETON ONCE
# ==========================================
st.markdown(f"### 📊 Live Server Monitor")
status_ph = st.empty()

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**CPU & Memory**")
    c1_a, c1_b = st.columns(2)
    cpu_metric_ph = c1_a.empty()
    ram_metric_ph = c1_b.empty()
    
    cpu_chart_ph = st.empty()
    ram_chart_ph = st.empty()
    
    temp_metric_ph = st.empty()
    temp_chart_ph = st.empty()

with col2:
    st.markdown("**Network & Storage**")
    net_chart_ph = st.empty()
    storage_ph = st.empty()
    gpu_ph = st.empty()

with col3:
    st.markdown("**Docker Containers**")
    docker_ph = st.empty()
    
    st.markdown("**Top Processes**")
    tab_cpu, tab_mem = st.tabs(["CPU", "Memory"])
    with tab_cpu:
        proc_cpu_ph = st.empty()
    with tab_mem:
        proc_mem_ph = st.empty()

st.markdown("**System Logs**")
logs_ph = st.empty()


# ==========================================
# 2. THE INFINITE UPDATE LOOP
# ==========================================
while True:
    stats = get_all_stats(log_files_to_monitor=LOG_FILES, storage_paths_to_monitor=STORAGE_PATHS)
    update_history(stats, history)

    # -- Status Banner --
    status_ph.caption(f"**Updated:** {stats['timestamp']} | **Uptime:** {stats['uptime']} | **Load (1/5m):** {stats['load_average']['one_min']}, {stats['load_average']['five_min']}")

    # -- Column 1: Core Systems --
    cpu_metric_ph.metric("CPU", f"{stats['cpu']['overall']}%")
    ram_metric_ph.metric("RAM", f"{stats['ram']['percent']}%", f"{stats['ram']['used_gb']}GB used")
    
    cpu_chart_ph.line_chart(pd.DataFrame({'Time': history['timestamp'], 'CPU %': history['cpu']}).set_index('Time'), color="#10b981", height=130)
    ram_chart_ph.line_chart(pd.DataFrame({'Time': history['timestamp'], 'RAM %': history['ram']}).set_index('Time'), color="#8b5cf6", height=130)

    if history['avg_core_temp'][-1] > 0:
        temp_metric_ph.metric("Avg CPU Temp", f"{round(history['avg_core_temp'][-1], 1)} °C")
        temp_chart_ph.line_chart(pd.DataFrame({'Time': history['timestamp'], 'Temp (°C)': history['avg_core_temp']}).set_index('Time'), color="#ef4444", height=130)

    # -- Column 2: Network, Storage, GPUs --
    net_chart_ph.line_chart(pd.DataFrame({
        'Time': history['timestamp'], 'Send': history['net_sent'], 'Recv': history['net_recv']
    }).set_index('Time'), color=["#f97316", "#3b82f6"], height=130)

    with storage_ph.container():
        for s in stats['storage']:
            if 'error' not in s:
                st.progress(s['percent'] / 100.0, text=f"{s['path']} ({s['percent']}%) - {s['used_gb']} / {s['total_gb']} GB")

    has_nv = "collected" in stats['gpu_nvidia']['status'].lower() and stats['gpu_nvidia']['gpus']
    has_amd = "collected" in stats['gpu_amd']['status'].lower() and stats['gpu_amd']['metrics']
    
    if has_nv or has_amd:
        with gpu_ph.container():
            st.markdown("**GPUs**")
            if has_nv:
                for gpu in stats['gpu_nvidia']['gpus']:
                    st.progress(gpu['utilization_gpu_percent'] / 100.0, text=f"NVIDIA: {gpu['name']} Core ({gpu['temperature_gpu']}°C)")
                    st.progress(gpu['utilization_memory_percent'] / 100.0, text=f"NVIDIA VRAM: {gpu['memory_used_mb']}MB")
            if has_amd:
                m = stats['gpu_amd']['metrics']
                st.progress(m.get('gpu_load_percent', 0.0) / 100.0, text=f"AMD Core Load")
                st.progress(m.get('vram_usage_percent', 0.0) / 100.0, text=f"AMD VRAM Load")

    # -- Column 3: Tables --
    if stats['docker_containers']['status'] == 'OK' and stats['docker_containers']['containers']:
        df_docker = pd.DataFrame(stats['docker_containers']['containers'])
        docker_ph.dataframe(df_docker[['name', 'status', 'uptime']], hide_index=True, height=200, width=500)
    else:
        docker_ph.caption("No containers running.")

    if stats['processes']['status'] == 'OK':
        proc_cpu_ph.dataframe(pd.DataFrame(stats['processes']['top_cpu'])[['name', 'cpu_percent', 'username']], hide_index=True, height=200, width=500)
        proc_mem_ph.dataframe(pd.DataFrame(stats['processes']['top_mem'])[['name', 'memory_percent', 'username']], hide_index=True, height=200, width=500)

    # -- Bottom: System Logs --
    if stats['logs']:
        with logs_ph.container():
            log_cols = st.columns(len(stats['logs']))
            for i, log in enumerate(stats['logs']):
                with log_cols[i]:
                    st.caption(f"{log['name']} `({log['path']})`")
                    with st.container(height=250):
                        formatted_lines = []
                        for line in reversed(log['lines']):
                            # Strip long ISO formats
                            clean_line = re.sub(r'^\d{4}-\d{2}-\d{2}T(\d{2}:\d{2}:\d{2})[^\s]*\s+(?:\S+\s+)?', r'[\1] ', line)
                            # Strip standard syslog formats
                            clean_line = re.sub(r'^[A-Z][a-z]{2}\s+\d{1,2}\s+(\d{2}:\d{2}:\d{2})\s+(?:\S+\s+)?', r'[\1] ', clean_line)
                            formatted_lines.append(clean_line)
                        st.code("\n".join(formatted_lines), language="bash")
    else:
        logs_ph.info("No logs configured. Use the LOG_CONFIG env var.")

    # Pause before next update
    time.sleep(POLLING_INTERVAL)
