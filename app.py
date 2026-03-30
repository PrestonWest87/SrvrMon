import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
from backend.collectors import get_all_stats

# --- Page Configuration ---
# 'wide' layout is crucial for the compact 3-column view
st.set_page_config(page_title="Live Server Monitor", page_icon="🖥️", layout="wide")

# --- Configuration & Env Vars ---
POLLING_INTERVAL = int(os.environ.get('POLLING_INTERVAL_MS', 5000)) / 1000.0
STORAGE_PATHS = os.environ.get('STORAGE_PATHS', '/').split(',')
MAX_HISTORY = 60 

# --- Session State for Historical Data (Charts) ---
if 'history' not in st.session_state:
    st.session_state.history = {
        'timestamp': [], 'cpu': [], 'ram': [],
        'net_sent': [], 'net_recv': [],
        'disk_read': [], 'disk_write': [],
        'avg_core_temp': []
    }

def update_history(stats):
    now = datetime.now()
    st.session_state.history['timestamp'].append(now)
    st.session_state.history['cpu'].append(stats['cpu']['overall'])
    st.session_state.history['ram'].append(stats['ram']['percent'])
    
    net_sent = sum(n['bytes_sent_rate_kbps'] for n in stats['network'] if n['interface'] != 'lo')
    net_recv = sum(n['bytes_recv_rate_kbps'] for n in stats['network'] if n['interface'] != 'lo')
    st.session_state.history['net_sent'].append(net_sent)
    st.session_state.history['net_recv'].append(net_recv)

    if stats['disk_io']['status'] == 'OK':
        st.session_state.history['disk_read'].append(sum(d['read_mb_s'] for d in stats['disk_io']['disks']))
        st.session_state.history['disk_write'].append(sum(d['write_mb_s'] for d in stats['disk_io']['disks']))
    else:
        st.session_state.history['disk_read'].append(0)
        st.session_state.history['disk_write'].append(0)

    core_temps = []
    if stats['temperatures']['status'] == 'OK':
        for group, sensors in stats['temperatures']['sensors'].items():
            for s in sensors:
                lbl = s.get('label', '').lower()
                if 'core' in lbl or 'tctl' in lbl or 'die' in lbl or 'cpu' in lbl:
                    if s['current'] is not None:
                        core_temps.append(s['current'])
                        
    avg_temp = sum(core_temps) / len(core_temps) if core_temps else 0.0
    st.session_state.history['avg_core_temp'].append(avg_temp)

    for key in st.session_state.history:
        st.session_state.history[key] = st.session_state.history[key][-MAX_HISTORY:]

LOG_CONFIG_ENV = os.environ.get('LOG_CONFIG', '')
LOG_FILES = [{'name': n.strip(), 'path': p.strip()} for n, p in (item.split(':', 1) for item in LOG_CONFIG_ENV.split(',') if ':' in item)]

# --- Top Header (Outside Fragment) ---
st.markdown(f"### 📊 Live Server Monitor")

@st.fragment(run_every=timedelta(seconds=POLLING_INTERVAL))
def live_dashboard():
    stats = get_all_stats(log_files_to_monitor=LOG_FILES, storage_paths_to_monitor=STORAGE_PATHS)
    update_history(stats)

    # Server status banner
    st.caption(f"**Updated:** {stats['timestamp']} | **Uptime:** {stats['uptime']} | **Load (1/5m):** {stats['load_average']['one_min']}, {stats['load_average']['five_min']}")

    # --- 3-Column Compact Layout ---
    col1, col2, col3 = st.columns(3)

    # COLUMN 1: System Core (CPU, RAM, Temps)
    with col1:
        st.markdown("**CPU & Memory**")
        c1_a, c1_b = st.columns(2)
        c1_a.metric("CPU", f"{stats['cpu']['overall']}%")
        c1_b.metric("RAM", f"{stats['ram']['percent']}%", f"{stats['ram']['used_gb']}GB used")
        
        st.line_chart(pd.DataFrame({'Time': st.session_state.history['timestamp'], 'CPU %': st.session_state.history['cpu']}).set_index('Time'), color="#10b981", height=130)
        st.line_chart(pd.DataFrame({'Time': st.session_state.history['timestamp'], 'RAM %': st.session_state.history['ram']}).set_index('Time'), color="#8b5cf6", height=130)

        if st.session_state.history['avg_core_temp'][-1] > 0:
            st.metric("Avg CPU Temp", f"{round(st.session_state.history['avg_core_temp'][-1], 1)} °C")
            st.line_chart(pd.DataFrame({'Time': st.session_state.history['timestamp'], 'Temp (°C)': st.session_state.history['avg_core_temp']}).set_index('Time'), color="#ef4444", height=130)

    # COLUMN 2: Network, Storage, GPUs
    with col2:
        st.markdown("**Network & Storage**")
        st.line_chart(pd.DataFrame({
            'Time': st.session_state.history['timestamp'],
            'Send': st.session_state.history['net_sent'],
            'Recv': st.session_state.history['net_recv']
        }).set_index('Time'), color=["#f97316", "#3b82f6"], height=130)

        # Storage (Compact bars)
        for s in stats['storage']:
            if 'error' not in s:
                st.progress(s['percent'] / 100.0, text=f"{s['path']} ({s['percent']}%) - {s['used_gb']} / {s['total_gb']} GB")
        
        # GPUs
        has_nv = "collected" in stats['gpu_nvidia']['status'].lower() and stats['gpu_nvidia']['gpus']
        has_amd = "collected" in stats['gpu_amd']['status'].lower() and stats['gpu_amd']['metrics']
        
        if has_nv or has_amd:
            st.markdown("**GPUs**")
            if has_nv:
                for gpu in stats['gpu_nvidia']['gpus']:
                    st.progress(gpu['utilization_gpu_percent'] / 100.0, text=f"NVIDIA: {gpu['name']} Core ({gpu['temperature_gpu']}°C)")
                    st.progress(gpu['utilization_memory_percent'] / 100.0, text=f"NVIDIA VRAM: {gpu['memory_used_mb']}MB")
            if has_amd:
                m = stats['gpu_amd']['metrics']
                st.progress(m.get('gpu_load_percent', 0.0) / 100.0, text=f"AMD Core Load")
                st.progress(m.get('vram_usage_percent', 0.0) / 100.0, text=f"AMD VRAM Load")

    # COLUMN 3: Tables (Docker & Processes)
    with col3:
        st.markdown("**Docker Containers**")
        if stats['docker_containers']['status'] == 'OK' and stats['docker_containers']['containers']:
            df_docker = pd.DataFrame(stats['docker_containers']['containers'])
            st.dataframe(df_docker[['name', 'status', 'uptime']], hide_index=True, height=200)
        else:
            st.caption("No containers running.")

        st.markdown("**Top Processes**")
        if stats['processes']['status'] == 'OK':
            tab_cpu, tab_mem = st.tabs(["CPU", "Memory"])
            with tab_cpu:
                st.dataframe(pd.DataFrame(stats['processes']['top_cpu'])[['name', 'cpu_percent', 'username']], hide_index=True, height=200)
            with tab_mem:
                st.dataframe(pd.DataFrame(stats['processes']['top_mem'])[['name', 'memory_percent', 'username']], hide_index=True, height=200)

    # --- Full Width Bottom: System Logs ---
    st.markdown("**System Logs**")
    if stats['logs']:
        # Create columns if there are multiple logs to keep it compact vertically
        log_cols = st.columns(len(stats['logs']))
        for i, log in enumerate(stats['logs']):
            with log_cols[i]:
                st.caption(f"{log['name']} `({log['path']})`")
                with st.container(height=250):
                    st.code("\n".join(log['lines']), language="bash")
    else:
        st.info("No logs configured. Use the LOG_CONFIG env var.")

live_dashboard()
