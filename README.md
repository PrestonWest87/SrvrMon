# Live Server Monitor Dashboard 📊💻

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.x-green.svg)](https://flask.palletsprojects.com/)
[![Socket.IO](https://img.shields.io/badge/Socket.IO-4.x-yellow.svg)](https://socket.io/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blueviolet.svg)](https://www.docker.com/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

A real-time, web-based dashboard to monitor your server's vital statistics. Built with Python, Flask, Socket.IO, psutil, and Docker for easy deployment. The frontend uses HTML, Tailwind CSS, and Chart.js for a modern, responsive, and themeable interface.

![Screenshot Placeholder - Consider adding a screenshot of your dashboard here!](https://placehold.co/800x400/1f2937/e5e7eb?text=Server+Monitor+Dashboard+UI)
*(Replace the placeholder above with an actual screenshot of your dashboard)*

## ✨ Features

* **🖥️ Live CPU Usage:** Overall and per-core CPU utilization percentages, updated in real-time.
* **🧠 Live RAM Usage:** Total, used, and available memory (GB), along with usage percentage.
* **💾 Live Storage Usage:** Disk space utilization (total, used, free in GB, and percentage) for configurable mount points.
* **🌐 Live Network Traffic:**
    * Total bytes sent/received per network interface (MB).
    * Live send/receive rates per interface (Kbps).
    * Packet counts and error/drop statistics.
* **⏱️ System Uptime & Load Average:** Displays current server uptime and 1, 5, and 15-minute load averages.
* **📜 Live System Log Tailing:** Tails and displays the latest lines from configured log files.
* **🎮 AMD GPU Monitoring (Basic):** Placeholder for `radeontop` integration. Shows status message; can be extended.
* **🌐 Web-Based UI:** Accessible from any modern web browser.
* **⚡ Real-time Updates:** Uses WebSockets (Socket.IO) for instant data updates without page reloads.
* **🎨 Themeable Interface:**
    * Defaults to a sleek **Dark Mode**.
    * **Toggleable Light Mode** available.
    * Theme preference is saved in browser `localStorage`.
* **📱 Responsive Design:** Adapts to different screen sizes (desktop, tablet, mobile).
* **⚙️ Configurable Polling Interval:** Adjust data refresh rate via an environment variable.
* **🐳 Dockerized:** Easy to build and deploy as a Docker container.

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

## 📂 Project Structure

server-monitor-docker/├── Dockerfile                # Defines the Docker image├── requirements.txt          # Python dependencies├── backend/│   ├── app.py                # Flask application, Socket.IO handling, routes│   └── collectors.py         # Data collection logic using psutil└── frontend/└── index.html            # Main HTML page with CSS and JavaScript
## 🚀 Getting Started

### Prerequisites

* **Docker:** Ensure Docker is installed and running on your system. [Get Docker](https://docs.docker.com/get-docker/)
* **Git (Optional):** For cloning if this project is in a Git repository.

### Installation & Setup

1.  **Create Project Directory:**
    If you haven't cloned a repository, create the project directory structure:
    ```bash
    mkdir server-monitor-docker
    cd server-monitor-docker
    mkdir backend
    mkdir frontend
    ```

2.  **Populate Files:**
    Place the provided code files into their respective directories:
    * `Dockerfile` (in `server-monitor-docker/`)
    * `requirements.txt` (in `server-monitor-docker/`)
    * `backend/app.py`
    * `backend/collectors.py`
    * `frontend/index.html`

    *(Ensure you have the latest versions of these files as provided in the development process.)*

### Building the Docker Image

Navigate to the root of the project directory (`server-monitor-docker/`) in your terminal and run:

```bash
docker build -t server-monitor-app .
```

Running the Docker Container
Basic Run

To run the container with default settings (2-second polling, monitoring container's root filesystem and dummy logs):
```
docker run -d -p 5000:5000 --name live-server-monitor --init server-monitor-app
```
    -d: Run in detached mode (background).

    -p 5000:5000: Map port 5000 of the host to port 5000 of the container.

    --name live-server-monitor: Assign a name to the container for easier management.

    --init: Runs an init process as PID 1 in the container, which helps manage signals and zombie processes.

Running with Custom Configurations

You can customize the monitor's behavior using environment variables and Docker volume mounts:

Environment Variables:

    POLLING_INTERVAL_MS: Data refresh interval in milliseconds (e.g., 1000 for 1 second, 5000 for 5 seconds). Default: 2000.

    STORAGE_PATHS: Comma-separated list of absolute paths inside the container to monitor for storage usage. Example: STORAGE_PATHS="/,/mnt/data,/mnt/backups"

    LOG_CONFIG: Comma-separated list of Name:Path pairs for log files to monitor. Name is the display name in the UI, Path is the absolute path inside the container. Example: LOG_CONFIG="Syslog:/var/log/syslog_host,App Log:/app/my_app_host.log"

Volume Mounts (for monitoring host system resources):

    To monitor host storage, mount host directories into the container and specify the container paths in STORAGE_PATHS.

    To monitor host log files, mount them into the container and specify the container paths in LOG_CONFIG.

Example: Advanced Run Command

This example runs the monitor with:

    3-second polling.

    Monitors the host's root (/) and /mnt/important_data directories for storage.

    Tails the host's /var/log/syslog and /var/log/auth.log.
```
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
    server-monitor-app
```
    :ro makes the mounted volumes read-only, which is recommended for monitoring.

Accessing the Monitor

Once the container is running, open your web browser and navigate to:

http://localhost:5000

(If running Docker on a remote machine or VM, replace localhost with the machine's IP address).
🔧 Customization & Modification
Polling Interval

Set the POLLING_INTERVAL_MS environment variable when running docker run.
Example: -e POLLING_INTERVAL_MS=1000 for 1-second updates. The minimum effective interval is around 500ms.
Monitored Storage

    Modify the -v /host/path:/container/path:ro Docker run option to mount the desired host storage directories.

    Set the STORAGE_PATHS environment variable to a comma-separated list of the container paths you've mapped.
    Example: -v /data/drive1:/mnt/drive1_data:ro -e STORAGE_PATHS="/,/mnt/drive1_data"

Monitored Logs

    Modify the -v /host/logfile.log:/container/logfile.log:ro Docker run option to mount the desired host log files.

    Set the LOG_CONFIG environment variable.
    Example: -v /var/log/my_app.log:/applogs/app.log:ro -e LOG_CONFIG="My Application Log:/applogs/app.log"

Frontend Styling & Appearance

    Tailwind CSS: Styles are primarily managed using Tailwind CSS classes directly in frontend/index.html. You can modify these classes to change the appearance.

    Theme Colors: Dark and light mode colors are defined using CSS custom properties (variables) in the <style> section of frontend/index.html. You can adjust these variables (e.g., --bg-color-primary, --text-color-accent) to change the theme.

    Charts: Chart appearance (colors, types) can be modified in the JavaScript section of frontend/index.html, specifically in the createTimeSeriesChart function and where charts are initialized.

Backend Logic

    Data Collection (backend/collectors.py): If you need to add new metrics or change how existing ones are collected, this is the primary file to modify. It uses the psutil library.

    Application & WebSocket Handling (backend/app.py): This file handles the Flask routes, Socket.IO events, and manages the background thread for emitting stats. Modifications here would be for changing API behavior or WebSocket communication.

AMD GPU (Radeontop) Integration

The current radeontop integration is a placeholder. To enable it fully:

    Install radeontop in Docker: Add radeontop to the apt-get install command in your Dockerfile.

    Device Access: You'll likely need to pass AMD GPU devices to the container using --device flags during docker run (e.g., --device=/dev/dri/card0 --device=/dev/kfd). This can be hardware-specific.

    Permissions: The container might require elevated privileges.

    Modify backend/collectors.py: Update the get_radeontop_data() function to:

        Execute the radeontop command (e.g., using subprocess.run(['radeontop', '-d', '-', '-l', '1'], ...) to get a single dump of data).

        Parse the output of radeontop to extract meaningful statistics.

        Return the parsed data in a structured format.

        This is an advanced task and may require significant effort depending on the desired level of detail.

🩺 Troubleshooting

    Container not starting/exiting: Check Docker logs: docker logs live-server-monitor (or your container name).

    No data on webpage / "Connection Error":

        Verify the container is running: docker ps

        Check Docker logs for backend errors.

        Open your browser's developer console (usually F12) and check for JavaScript errors or WebSocket connection issues.

        Ensure no firewall is blocking port 5000.

    Incorrect storage/log paths: Double-check your volume mounts (-v) in the docker run command and the corresponding paths set in STORAGE_PATHS or LOG_CONFIG environment variables. Paths are case-sensitive.

🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check issues page (if this were a public repo).

    Fork the Project

    Create your Feature Branch (git checkout -b feature/AmazingFeature)

    Commit your Changes (git commit -m 'Add some AmazingFeature')

    Push to the Branch (git push origin feature/AmazingFeature)

    Open a Pull Request

📜 License

Distributed under the GNU General Public License Version 3, 29 June 2007.
It's recommended to include the full text of the GPLv3 in a LICENSE file in the root of your project. You can find the full license text [here]
