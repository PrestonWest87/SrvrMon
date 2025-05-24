# Live Server Monitor Dashboard 📊💻

[](https://www.python.org/)
[](https://flask.palletsprojects.com/)
[](https://socket.io/)
[](https://www.docker.com/)
[](https://www.gnu.org/licenses/gpl-3.0)

A real-time, web-based dashboard to monitor your server's vital statistics. Built with Python, Flask, Socket.IO, psutil, and Docker for easy deployment. The frontend uses HTML, Tailwind CSS, and Chart.js for a modern, responsive, and themeable interface.

![Dashboard Screenchot goes here](https://github.com/PrestonWest87/SrvrMon/blob/main/Screenshot%202025-05-18%20121642.png "Dashboard Screenshot")

## ✨ Features

  * **🖥️ Live CPU Usage:** Overall and per-core CPU utilization percentages, updated in real-time.
  * **🧠 Live RAM Usage:** Total, used, and available memory (GB), along with usage percentage.
  * **💾 Live Storage Usage:** Disk space utilization (total, used, free in GB, and percentage) for configurable mount points.
  * **🌐 Live Network Traffic:**
      * Total bytes sent/received per network interface (MB).
      * Live send/receive rates per interface (Kbps).
      * Packet counts and error/drop statistics.
  * **⏱️ System Uptime & Load Average:** Displays current server uptime and 1, 5, and 15-minute load averages.
  * **📜 Live System Log Tailing:** Tails and displays the latest lines from configured log files (defaults to dummy logs if none are specified).
  * **🎮 AMD GPU Monitoring (Basic):** Placeholder for `radeontop` integration. Shows status message; can be extended to parse output from `radeontop`.
  * **🌐 Web-Based UI:** Accessible from any modern web browser.
  * **⚡ Real-time Updates:** Uses WebSockets (Socket.IO) for instant data updates without page reloads.
  * **🎨 Themeable Interface:**
      * Defaults to a sleek **Dark Mode**.
      * **Toggleable Light Mode** available.
      * Theme preference is saved in browser `localStorage`.
  * **📱 Responsive Design:** Adapts to different screen sizes (desktop, tablet, mobile).
  * **⚙️ Configurable Polling Interval:** Adjust data refresh rate via an environment variable (`POLLING_INTERVAL_MS`). Default is 2000ms.
  * **🐳 Dockerized:** Easy to build and deploy as a Docker container.
  * **🚢 Docker Container Monitoring:** Lists running and exited Docker containers with their status, uptime, and image. (Requires Docker socket access).
  * **📈 Live Disk I/O:** Per-disk read/write rates (MB/s and IOPS) and total data read/written (GB). Includes charts for total read and write rates across all disks.
  * **🚦 Process Monitoring:** Displays lists of top CPU and Memory consuming processes, including PID, Name, User, CPU %, Memory %, and Status.
  * **🌡️ Sensor Temperatures:** Displays available hardware temperatures (e.g., CPU core temps, mainboard) as reported by `psutil`. (Highly OS and hardware dependent).

-----

## 🛠️ Tech Stack

  * **Backend:**
      * Python 3.10+
      * Flask (Web framework)
      * Flask-SocketIO (WebSocket communication)
      * psutil (System information gathering)
      * eventlet (Asynchronous server for Socket.IO)
  * **Frontend:**
      * HTML5
      * Tailwind CSS (Utility-first CSS framework)
      * Chart.js (JavaScript charting library)
      * Socket.IO Client (JavaScript library for WebSockets)
  * **Deployment:**
      * Docker

-----

## 📂 Project Structure

```
server-monitor-docker/
├── Dockerfile                # Defines the Docker image
├── requirements.txt          # Python dependencies
├── run.py                    # Entrypoint script for Docker to start the Flask-SocketIO app
├── backend/
│   ├── app.py                # Flask application, Socket.IO handling, routes
│   └── collectors.py         # Data collection logic using psutil
└── frontend/
    └── index.html            # Main HTML page with CSS and JavaScript
```

-----

## 🚀 Getting Started

### Prerequisites

  * **Docker:** Ensure Docker is installed and running on your system. [Get Docker](https://docs.docker.com/get-docker/)
  * **Git (Optional):** For cloning if this project is in a Git repository.

### Installation & Setup

1.  **Create Project Directory:**
    If you haven't cloned a repository, create the project directory structure as shown above.

    ```bash
    mkdir -p server-monitor-docker/backend
    mkdir -p server-monitor-docker/frontend
    cd server-monitor-docker
    ```

2.  **Populate Files:**
    Place the code files (`Dockerfile`, `requirements.txt`, `run.py`, `backend/app.py`, `backend/collectors.py`, `frontend/index.html`) into their respective directories as outlined in the "Project Structure" section.

    *(Ensure you have the correct versions of these files.)*

-----

## 🐳 Docker Instructions

### Building the Docker Image

Navigate to the root of the project directory (`server-monitor-docker/`) in your terminal and run:

```bash
docker build -t server-monitor-app .
```

This command builds a Docker image tagged as `server-monitor-app` using the `Dockerfile` in the current directory.

### Running the Docker Container

#### Basic Run

To run the container with default settings (2-second polling, monitoring container's root filesystem, and dummy logs generated by the application):

```bash
docker run -d -p 5000:5000 --name live-server-monitor --init server-monitor-app
```

  * `-d`: Run in detached mode (background).
  * `-p 5000:5000`: Map port 5000 of the host to port 5000 of the container (Flask app default port).
  * `--name live-server-monitor`: Assign a name to the container for easier management.
  * `--init`: Runs an init process as PID 1 in the container, which helps manage signals and zombie processes. Recommended for applications like this.

#### Running with Custom Configurations

You can customize the monitor's behavior using environment variables and Docker volume mounts:

**Environment Variables:**

  * `POLLING_INTERVAL_MS`: Data refresh interval in milliseconds (e.g., `1000` for 1 second, `5000` for 5 seconds). Default: `2000`. Minimum effective interval is around `500ms`.
  * `STORAGE_PATHS`: Comma-separated list of absolute paths *inside the container* to monitor for storage usage. Example: `STORAGE_PATHS="/,/mnt/data,/mnt/backups"`. If not set, defaults to `/host_root` if it exists, otherwise `/`.
  * `LOG_CONFIG`: Comma-separated list of `Name:Path` pairs for log files to monitor. `Name` is the display name in the UI, `Path` is the absolute path *inside the container*. Example: `LOG_CONFIG="Syslog:/var/log/syslog_host,App Log:/app/my_app_host.log"`. If not set, defaults to dummy logs created by the application.
  * `FLASK_DEBUG`: Set to `1` for Flask debug mode, `0` for production. Default is `0` as set in the `Dockerfile`. `run.py` uses this to toggle debug mode for `socketio.run`.
  * `FLASK_RUN_HOST`: Host for the Flask app. Default is `0.0.0.0` as set in `Dockerfile`.
  * `FLASK_RUN_PORT`: Port for the Flask app. Default is `5000` as set in `Dockerfile`.
  * `LOG_LEVEL`: Sets the logging level for the application. Defaults to `INFO`. Options: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.

**Volume Mounts (for monitoring host system resources):**

  * To monitor host storage, mount host directories into the container and specify the *container paths* in `STORAGE_PATHS`.
  * To monitor host log files, mount them into the container and specify the *container paths* in `LOG_CONFIG`.
  * **To monitor Docker containers:** The Docker socket must be mounted into the container. Add `-v /var/run/docker.sock:/var/run/docker.sock:ro` to your `docker run` command. Make this read-only (`:ro`) for security.

**Example: Advanced Run Command**

This example runs the monitor with:

  * 3-second polling.
  * Monitors the host's root (`/`) and `/mnt/important_data` directories for storage.
  * Tails the host's `/var/log/syslog` and `/var/log/auth.log`.

<!-- end list -->

```bash
docker run -d \
    -p 5000:5000 \
    --name live-server-monitor \
    --init \
    -e POLLING_INTERVAL_MS=3000 \
    -e STORAGE_PATHS="/host_root,/host_data" \
    -e LOG_CONFIG="Host Syslog:/mnt/logs/syslog,Host Auth Log:/mnt/logs/auth.log" \
    -v /:/host_root:ro \
    -v /mnt/important_data:/host_data:ro \
    -v /var/log/syslog:/mnt/logs/syslog:ro \
    -v /var/log/auth.log:/mnt/logs/auth.log:ro \
    -v /var/run/docker.sock:/var/run/docker.sock:ro \
    server-monitor-app
```

  * `:ro` makes the mounted volumes read-only from the container's perspective, which is recommended for monitoring to prevent accidental changes to host files.
  * **Note on Docker Socket:** Mounting `/var/run/docker.sock` allows the container to interact with the Docker daemon on the host. This is necessary for the "Docker Containers" feature. Ensure you understand the security implications of this, though read-only (`:ro`) mitigates some risks.

### Accessing the Monitor

Once the container is running, open your web browser and navigate to:

`http://localhost:5000`

(If running Docker on a remote machine or VM, replace `localhost` with the machine's IP address).

-----

## 🔧 Customization & Modification

### Configuration File (`config.yaml`)

For more persistent and structured configuration, you can create a `config.yaml` file in the root of your project directory (the same directory as the `Dockerfile` and `run.py`). This file allows you to define settings for polling interval, storage paths, and log files.

**Order of Precedence for Configuration:**

1.  **Environment Variables:** (Highest) If set, these will always override settings from `config.yaml` or default values.
2.  **`config.yaml` File:** If environment variables are not set, values from this file will be used.
3.  **Hardcoded Defaults:** (Lowest) If neither environment variables nor a `config.yaml` file provide a setting, the application's internal defaults are used.

**Example `config.yaml`:**

Place this file in the root of your project (`server-monitor-docker/config.yaml`):

```yaml
# Server Monitor Configuration
# Environment variables will override these settings if set.

polling_interval_ms: 3000 # Data refresh interval in milliseconds

storage_paths: # List of paths to monitor for storage usage
  - /
  - /mnt/data_volume # Example: a mounted volume
  - /media/backup    # Another example

log_config: # List of log files to monitor (Name:Path pairs)
  - name: "System Log"
    path: "/var/log/syslog" # Example: host syslog mounted into container
  - name: "My App Log"
    path: "/app/logs/my_application.log"
  - name: "Kern Log"
    path: "/var/log/kern.log"
```

**Using `config.yaml` with Docker:**

To use the `config.yaml` file with your Docker container, you need to mount it into the container at the expected location (`/app/config.yaml` because the working directory in the container is `/app`).

```bash
docker run -d \
    -p 5000:5000 \
    --name live-server-monitor \
    --init \
    -v "$(pwd)/config.yaml:/app/config.yaml:ro" \ # Mount your local config.yaml
    # Add other volume mounts for storage and logs as needed
    # -v /:/host_root:ro \
    # -v /var/log/syslog:/mnt/logs/syslog:ro \
    # -v /var/run/docker.sock:/var/run/docker.sock:ro \ # If also using config.yaml for other settings
    server-monitor-app
```

If you also set environment variables (e.g., `-e POLLING_INTERVAL_MS=1000`), they will take precedence over the values in the mounted `config.yaml`.

### Polling Interval

Configurable via `polling_interval_ms` in `config.yaml` or the `POLLING_INTERVAL_MS` environment variable.
Example: `-e POLLING_INTERVAL_MS=1000` for 1-second updates. Minimum effective interval is 500ms.

### Monitored Storage

Configurable via `storage_paths` (list) in `config.yaml` or the `STORAGE_PATHS` environment variable (comma-separated string).
1.  To monitor host paths, mount them into the container using Docker's `-v` option.
2.  Specify the *container paths* in `config.yaml` or the environment variable.
    Example in `config.yaml`:
    ```yaml
    storage_paths:
      - /  # Container's root
      - /mnt/drive1_data # Path inside container
    ```
    Example using env var: `-v /data/drive1:/mnt/drive1_data:ro -e STORAGE_PATHS="/,/mnt/drive1_data"`

### Monitored Logs

Configurable via `log_config` (list of name/path dicts) in `config.yaml` or the `LOG_CONFIG` environment variable (comma-separated `Name:Path` strings).
1.  To monitor host log files, mount them into the container using Docker's `-v` option.
2.  Specify the *container paths* and desired display names in `config.yaml` or the environment variable.
    Example in `config.yaml`:
    ```yaml
    log_config:
      - name: "Host System Log"
        path: "/applogs/syslog_host"
    ```
    Example using env var: `-v /var/log/syslog:/applogs/syslog_host:ro -e LOG_CONFIG="Host System Log:/applogs/syslog_host"`


### Frontend Styling & Appearance

  * **Tailwind CSS:** Styles are primarily managed using Tailwind CSS classes directly in `frontend/index.html`. You can modify these classes to change the appearance.
  * **Theme Colors:** Dark and light mode colors are defined using CSS custom properties (variables) in the `<style>` section of `frontend/index.html`. Adjust these variables (e.g., `--bg-color-primary`, `--text-color-accent`) to change the theme.
  * **Charts:** Chart appearance (colors, types) can be modified in the JavaScript section of `frontend/index.html`, specifically in the `createTimeSeriesChart` function and where charts are initialized.

### Backend Logic

  * **Data Collection (`backend/collectors.py`):** If you need to add new metrics or change how existing ones are collected, this is the primary file to modify. It uses the `psutil` library extensively.
  * **Application & WebSocket Handling (`backend/app.py`):** This file handles the Flask routes, Socket.IO events, and manages the background thread for emitting stats. Modifications here would be for changing API behavior or WebSocket communication. The `eventlet.monkey_patch()` is crucial and is called in `run.py`.

-----

## 🎮 GPU Monitoring

### AMD GPU (Radeontop) Integration

The current `radeontop` integration is a basic placeholder that attempts to run `radeontop -l 1 -d -` and parse its text output.

To enable or improve it:

1.  **Install `radeontop` in Docker:** Ensure `radeontop` is included in the `apt-get install` command in your `Dockerfile`.
2.  **Device Access:** You'll likely need to pass AMD GPU devices to the container using `--device` flags during `docker run` (e.g., `--device=/dev/dri/card0 --device=/dev/kfd`). This can be hardware-specific.
3.  **Permissions:** The container might require elevated privileges or specific user group memberships to access GPU devices and `radeontop`.
4.  **Modify `backend/collectors.py`:**
      * Update the `get_radeontop_data()` function.
      * The current implementation uses `subprocess.run` to execute `radeontop` and includes a basic parser `parse_radeontop_single_line_output` for a specific output format. You might need to adjust the `radeontop` command options or the parsing logic (`parse_radeontop_single_line_output`) depending on your `radeontop` version and the desired metrics.
      * This is an advanced task and may require significant effort depending on the desired level of detail and compatibility with different `radeontop` versions.

### NVIDIA GPU Monitoring (Possibility)

Monitoring NVIDIA GPUs typically requires using NVIDIA's own tools, primarily `nvidia-smi` (NVIDIA System Management Interface).

**Conceptual Steps to Add NVIDIA GPU Monitoring:**

1.  **NVIDIA Container Toolkit:** The host system and Docker need to be configured with the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/index.html). This allows Docker containers to access NVIDIA GPU resources.
2.  **Modify Dockerfile:**
      * It's generally better to use an NVIDIA-provided base image (e.g., `nvidia/cuda:tag-base`) as these come with necessary drivers and libraries.
      * If not using an NVIDIA base image, you would need to ensure `nvidia-smi` is accessible within the container, which might involve installing NVIDIA drivers and utilities. This is complex and error-prone; the NVIDIA Container Toolkit on the host is the preferred way as it makes GPUs available to standard containers.
3.  **Update `backend/collectors.py`:**
      * Create a new function, e.g., `get_nvidia_gpu_data()`.
      * Inside this function, use `subprocess.run` to execute `nvidia-smi` commands.
          * Example: `nvidia-smi --query-gpu=timestamp,name,temperature.gpu,utilization.gpu,utilization.memory,memory.total,memory.used,memory.free --format=csv,noheader,nounits`
      * Parse the CSV output from `nvidia-smi`.
      * Structure the parsed data into a dictionary similar to other collectors.
4.  **Update `backend/app.py`:**
      * Call `get_nvidia_gpu_data()` within `get_all_stats()` and add its output to the `current_stats` dictionary.
5.  **Update `frontend/index.html`:**
      * Add new sections and/or charts to display NVIDIA GPU metrics.
      * Update the JavaScript to handle and render the new GPU data.
6.  **Docker Run Command:**
      * When running the Docker container, you'll need to include the `--gpus all` flag (or specify particular GPUs) if using the NVIDIA Container Toolkit.
    <!-- end list -->
    ```bash
    docker run -d -p 5000:5000 --name live-server-monitor --init --gpus all server-monitor-app
    ```

**Challenges:**

  * **NVIDIA Drivers & Toolkit:** Correct setup on the host is crucial.
  * **Parsing `nvidia-smi`:** While `nvidia-smi` offers CSV output, robust parsing is still needed.
  * **Container Privileges:** Ensuring the container has the right access if not using the NVIDIA Container Toolkit approach.

-----

## 🩺 Troubleshooting

  * **Container not starting/exiting immediately:**

      * Check Docker logs: `docker logs live-server-monitor` (or your container name). Look for Python errors, issues with environment variables, or problems in `run.py` or `backend/app.py` during startup.
      * Ensure the `CMD` in your `Dockerfile` is correct (e.g., `CMD ["python", "run.py"]`).
      * Verify that `eventlet.monkey_patch()` is called at the very beginning of `run.py`.

  * **No data on webpage / "Connection Error" / "Disconnected":**

      * **Verify container is running:** `docker ps`. If not listed, check `docker ps -a` and then `docker logs <container_id_or_name>`.
      * **Check Docker logs for backend errors:** `docker logs live-server-monitor`. Pay attention to errors from `collectors.py` or `app.py`.
      * **Open browser's developer console (usually F12):**
          * Look for JavaScript errors in the "Console" tab.
          * Check the "Network" tab for WebSocket connection issues (often shown as pending or failing `socket.io` requests).
      * **Firewall:** Ensure no firewall is blocking port `5000` (or the port you've mapped) on the host or between your client machine and the Docker host.
      * **CORS Issues:** The backend `app.py` is configured with `cors_allowed_origins="*"`, which should generally prevent CORS issues. If you've modified this, ensure your frontend's origin is allowed.
      * **`POLLING_INTERVAL_MS` too low:** If set extremely low (e.g., below 100ms), it might overload the server or client. The application enforces a minimum of 500ms.

  * **Incorrect storage/log paths:**

      * **Double-check volume mounts (`-v`)**: Ensure the host path exists and the container path matches what's used in `STORAGE_PATHS` or `LOG_CONFIG`. Paths are case-sensitive.
      * **Check environment variables (`-e`)**: Verify `STORAGE_PATHS` and `LOG_CONFIG` are correctly formatted (comma-separated, `Name:Path` for logs).
      * **Permissions**: Ensure the user inside the Docker container (usually root, unless specified otherwise in `Dockerfile`) has read access to the mounted volumes. The `:ro` flag helps prevent writes but read access is still needed. For the Docker socket, the user might need to be in the `docker` group, though this is usually handled by the Docker daemon's permissions on the socket itself.
  * **Default Paths**: If environment variables or `config.yaml` settings are not set or invalid, the application falls back to internal defaults. Check application logs (via `docker logs live-server-monitor`) for warnings about invalid configurations, which can help identify if `config.yaml` is not being read or if environment variables are malformed.

  * **Data not updating or updating erratically:**

      * Check `docker logs live-server-monitor` for errors in the `background_thread` in `backend/app.py` or within `get_all_stats` in `collectors.py`.
      * Ensure `socketio.sleep()` is used in the `background_thread` rather than `time.sleep()` for proper cooperative multitasking with `eventlet`. (This is correctly implemented in the provided `app.py`).

  * **CPU usage seems off or slow to update:**

      * `psutil.cpu_percent(interval=0.1)` is used. A very short interval can sometimes be less accurate or slightly delayed. The polling interval of the app itself (`POLLING_INTERVAL_MS`) is the main driver for UI updates.

  * **Network rates are zero or incorrect:**

      * The network rate calculation in `get_network_traffic` depends on the difference between two consecutive calls. The first data point will show 0 rates. Ensure the polling interval is not too short for meaningful deltas to be calculated.

  * **AMD GPU (Radeontop) section shows "Radeontop data not available" or error:**

      * **`radeontop` not installed:** Add `radeontop` to `apt-get install` in `Dockerfile`.
      * **Device not passed to container:** Use `--device=/dev/dri/cardX` and potentially `--device=/dev/kfd` with `docker run`.
      * **Permissions:** The container might need specific privileges.
      * **`radeontop` command or parsing error:** Check the status message and raw output sample in the UI. The `get_radeontop_data` function in `backend/collectors.py` captures errors. You might need to adjust the command or the `parse_radeontop_single_line_output` function if your `radeontop` version has different output.

  * **"Error creating dummy log" or "Error writing to or trimming dummy log":**

      * This usually indicates a permissions issue within the container for the path `/app/dummy_logX.log` or that the filesystem is read-only where it's trying to write. The default `Dockerfile` should allow this, but custom base images or security settings might interfere.

  * **Docker Containers section shows "Docker not available" or error:**
      * **Docker Socket Not Mounted:** Ensure you've mounted the Docker socket with `-v /var/run/docker.sock:/var/run/docker.sock:ro` in your `docker run` command.
      * **Permissions for Docker Socket:** The user running inside the container (typically root) needs permission to access the mounted Docker socket. This is usually handled by the host's Docker socket permissions.
      * **Docker Daemon Not Running on Host:** Verify the Docker daemon is active on the host machine.
      * **Incorrect Docker Library Version or Installation:** Check if the `docker` Python library is correctly installed in `requirements.txt` and the Docker image.
      * **Check application logs (`docker logs live-server-monitor`):** Look for specific errors from the `get_docker_stats` function in `backend/collectors.py`.

  * **Disk I/O section shows "Disk I/O data not available" or error:**
      * **Permissions:** The container might not have sufficient privileges to access disk performance counters. This is less common for `psutil`'s disk I/O than for specific tools like `radeontop`.
      * **Platform Support:** `psutil.disk_io_counters(perdisk=True)` support can vary across operating systems or with very old kernels.
      * **No Physical Disks:** In some virtualized or container-only environments, `psutil` might not find recognizable disk devices to report on.
      * **Check application logs:** Look for errors from `get_disk_io_stats` in `backend/collectors.py`.

  * **Process Monitoring section shows errors or is empty:**
      * **Permissions:** The user running the server monitor application might not have permissions to access information for all processes (e.g., processes owned by other users or system processes). `psutil.AccessDenied` is handled per-process, but if it occurs for many, the lists might seem sparse.
      * **`cpu_percent` behavior:** The CPU percentage for processes is calculated over an interval. The first time data is fetched, CPU percentages might be 0 or inaccurate. They should stabilize on subsequent updates.
      * **Platform Differences:** Process status strings and available information can sometimes vary slightly between OS platforms.
      * **Check application logs:** For errors from `get_process_stats` in `backend/collectors.py`.

  * **Sensor Temperatures section shows "Sensor temperature data not available..." or is empty:**
      * **Platform Support:** `psutil.sensors_temperatures()` is not universally supported. It works best on Linux with `lm-sensors` installed and configured. On Windows and macOS, it may return no data or be unavailable.
      * **Permissions:** Accessing hardware sensors can require root/administrator privileges. If the application is not run with sufficient permissions, it might not be able to read sensor data.
      * **`lm-sensors` (Linux):** Ensure `lm-sensors` is installed and `sensors-detect` has been run to configure it. The necessary kernel modules must be loaded.
      * **Virtualization:** In virtual machines, sensor data is often not passed through from the host, so this section may be empty.
      * **Check application logs:** Look for messages indicating that `psutil.sensors_temperatures()` is not available or returned no data.

-----

## 🤝 Contributing

Contributions, issues, and feature requests are welcome\!

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

-----

## 📜 License

Distributed under the GNU General Public License Version 3, 29 June 2007.
It's recommended to include the full text of the GPLv3 in a `LICENSE` file in the root of your project. You can find the full license text [here](https://www.gnu.org/licenses/gpl-3.0.txt).

-----
