import streamlit as st
import pandas as pd
import time
import os
from datetime import datetime
from backend.collectors import get_all_stats

# --- Page Configuration ---
st.set_page_config(page_title="Live Server Monitor", page_icon="🖥️", layout="wide")

# --- Configuration & Env Vars ---
POLLING_INTERVAL = int(os.environ.get('POLLING_INTERVAL_MS', 2000)) / 1000.0
STORAGE_PATHS = os.environ.get('STORAGE_PATHS', '/').split(',')
MAX_HISTORY = 60 

# --- Session State for Historical Data (Charts) ---
if 'history' not in st.session_state:
    st.session_state.history = {
        'timestamp': [], 'cpu': [], 'ram': [],
        'net_sent': [], 'net_recv': [],
        'disk_read': [], 'disk_write': []
    }

def update_history(stats):
    """Appends new stats to session state and trims to MAX_HISTORY."""
    now = datetime.now()
    st.session_state.history['timestamp'].append(now)
    st.session_state.history['cpu'].append(stats['cpu']['overall'])
    st.session_state.history['ram'].append(stats['ram']['percent'])
    
    # Aggregate network
    net_sent = sum(n['bytes_sent_rate_kbps'] for n in stats['network'] if n['interface'] != 'lo')
    net_recv = sum(n['bytes_recv_rate_kbps'] for n in stats['network'] if n['interface'] != 'lo')
    st.session_state.history['net_sent'].append(net_sent)
    st.session_state.history['net_recv'].append(net_recv)

    # Aggregate Disk I/O
    if stats['disk_io']['status'] == 'OK':
        disk_read = sum(d['read_mb_s'] for d in stats['disk_io']['disks'])
        disk_write = sum(d['write_mb_s'] for d in stats['disk_io']['disks'])
    else:
        disk_read, disk_write = 0, 0
    st.session_state.history['disk_read'].append(disk_read)
    st.session_state.history['disk_write'].append(disk_write)

    # Trim history
    for key in st.session_state.history:
        st.session_state.history[key] = st.session_state.history[key][-MAX_HISTORY:]

# --- Fetch Data ---
stats = get_all_stats(log_files_to_monitor=[], storage_paths_to_monitor=STORAGE_PATHS)
update_history(stats)

# --- Top Header ---
col1, col2 = st.columns([3, 1])
with col1:
    st.title("Live Server Monitor 📊")
with col2:
    st.caption(f"Last Update: {stats['timestamp']}")
    st.caption(f"Uptime: {stats['uptime']} | Load Avg: {stats['load_average']['one_min']}, {stats['load_average']['five_min']}, {stats['load_average']['fifteen_min']}")

st.divider()

# --- Core Metrics (CPU & RAM) ---
col_cpu, col_ram = st.columns(2)

with col_cpu:
    st.subheader("⚙️ CPU Usage")
    st.metric("Overall CPU", f"{stats['cpu']['overall']}%")
    df_cpu = pd.DataFrame({'Time': st.session_state.history['timestamp'], 'CPU %': st.session_state.history['cpu']})
    st.line_chart(df_cpu.set_index('Time'), color="#10b981")
    
    with st.expander("Per-Core Usage"):
        cores = stats['cpu']['per_core']
        core_cols = st.columns(4)
        for i, core_val in enumerate(cores):
            core_cols[i % 4].write(f"**C{i}:** {core_val}%")

with col_ram:
    st.subheader("🧠 RAM Usage")
    ram = stats['ram']
    st.metric("Memory Used", f"{ram['used_gb']} GB / {ram['total_gb']} GB", f"{ram['percent']}%")
    df_ram = pd.DataFrame({'Time': st.session_state.history['timestamp'], 'RAM %': st.session_state.history['ram']})
    st.line_chart(df_ram.set_index('Time'), color="#8b5cf6")

st.divider()

# --- GPUs (NVIDIA & AMD) ---
st.subheader("🎮 GPU Status")
col_nv, col_amd = st.columns(2)

with col_nv:
    st.markdown("#### NVIDIA GPUs")
    if stats['gpu_nvidia']['status'] == "NVIDIA GPU data collected." and stats['gpu_nvidia']['gpus']:
        for gpu in stats['gpu_nvidia']['gpus']:
            st.write(f"**{gpu['name']}** | {gpu['temperature_gpu']}°C")
            st.progress(gpu['utilization_gpu_percent'] / 100.0, text=f"Core Load: {gpu['utilization_gpu_percent']}%")
            st.progress(gpu['utilization_memory_percent'] / 100.0, text=f"VRAM: {gpu['memory_used_mb']}MB / {gpu['memory_total_mb']}MB")
    else:
        st.info(stats['gpu_nvidia']['status'])

with col_amd:
    st.markdown("#### AMD GPUs (Radeontop)")
    amd_stats = stats['gpu_amd']
    if "collected" in amd_stats['status'].lower() and amd_stats['metrics']:
        m = amd_stats['metrics']
        st.write(f"**{m.get('device_name', 'AMD Device')}**")
        
        load = m.get('gpu_load_percent', 0.0)
        vram = m.get('vram_usage_percent', 0.0)
        
        st.progress(load / 100.0, text=f"Core Load: {load}%")
        st.progress(vram / 100.0, text=f"VRAM Load: {vram}%")
    else:
        st.info(amd_stats['status'])

st.divider()

# --- Network & Storage ---
col_stor, col_net = st.columns(2)

with col_stor:
    st.subheader("💾 Storage & Disk I/O")
    for s in stats['storage']:
        if 'error' in s:
            st.error(f"{s['path']}: {s['error']}")
        else:
            st.write(f"**{s['path']}** - {s['used_gb']} GB / {s['total_gb']} GB ({s['percent']}%)")
            st.progress(s['percent'] / 100.0)
    
    if stats['disk_io']['status'] == 'OK':
        with st.expander("Detailed Disk I/O"):
            st.dataframe(pd.DataFrame(stats['disk_io']['disks']), hide_index=True, use_container_width=True)

with col_net:
    st.subheader("🌐 Network Traffic")
    df_net = pd.DataFrame({
        'Time': st.session_state.history['timestamp'],
        'Send (Kbps)': st.session_state.history['net_sent'],
        'Receive (Kbps)': st.session_state.history['net_recv']
    }).set_index('Time')
    st.line_chart(df_net, color=["#f97316", "#3b82f6"])

st.divider()

# --- Hardware Temps & Docker ---
col_temp, col_dock = st.columns(2)

with col_temp:
    st.subheader("🌡️ Hardware Temperatures")
    if stats['temperatures']['status'] == 'OK' and stats['temperatures']['sensors']:
        for group, sensors in stats['temperatures']['sensors'].items():
            st.markdown(f"**{group}**")
            for s in sensors:
                st.write(f"- {s['label']}: `{s['current']} °C`")
    else:
        st.info(stats['temperatures']['status'])

with col_dock:
    st.subheader("🐳 Docker Containers")
    if stats['docker_containers']['status'] == 'OK':
        df_docker = pd.DataFrame(stats['docker_containers']['containers'])
        if not df_docker.empty:
            st.dataframe(df_docker[['name', 'status', 'uptime', 'image']], use_container_width=True, hide_index=True)
        else:
            st.info("No running containers found.")
    else:
        st.error(stats['docker_containers']['status'])

st.divider()

# --- Processes & Logs ---
col_proc, col_logs = st.columns(2)

with col_proc:
    st.subheader("🚦 Top Processes")
    tab_cpu, tab_mem = st.tabs(["Top CPU", "Top Memory"])
    
    if stats['processes']['status'] == 'OK':
        with tab_cpu:
            st.dataframe(pd.DataFrame(stats['processes']['top_cpu']), use_container_width=True, hide_index=True)
        with tab_mem:
            st.dataframe(pd.DataFrame(stats['processes']['top_mem']), use_container_width=True, hide_index=True)
    else:
        st.error(stats['processes']['status'])

with col_logs:
    st.subheader("📜 System Logs")
    if stats['logs']:
        for log in stats['logs']:
            with st.expander(f"📄 {log['name']} ({log['path']})"):
                st.code("\n".join(log['lines']), language="bash")
    else:
        st.info("No logs configured or found.")

# --- Auto Refresh Logic ---
time.sleep(POLLING_INTERVAL)
st.rerun()
