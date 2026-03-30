# Live Server Monitor Dashboard 📊💻

A real-time, ultra-compact, and flicker-free web dashboard to monitor your server's vital statistics. Built entirely in Python using Streamlit, psutil, and Docker. 

![Dashboard Screenshot](https://github.com/PrestonWest87/SrvrMon/blob/main/Screenshot%202026-03-29%20203346.png)

## ✨ Features
* **Command Center Layout:** Everything fits on a single screen. No endless scrolling.
* **Flicker-Free Updates:** Uses Streamlit fragments and static placeholders to push data via WebSockets without redrawing the UI.
* **Hardware Deep Dive:** Live CPU, RAM, Network, and Disk I/O charting.
* **Thermal & GPU Tracking:** Auto-detects NVIDIA and AMD GPUs, plus aggregates CPU core temperatures into a live thermal graph.
* **Process & Docker Visibility:** View top CPU/Memory hogs and monitor all running Docker containers natively.
* **Live System Logs:** Tails your host's Syslog (or any configured logs) with automatic timestamp cleanup and reverse chronological sorting.

## 🛠️ Tech Stack
* **Python 3.10+**
* **Streamlit** (Frontend & WebSocket handling)
* **Pandas** (Data table rendering)
* **psutil & docker** (System metric collection)

---

## 🚀 Quick Start (Docker Compose)

The easiest way to deploy SrvrMon is using Docker Compose. It requires specific privileges (`pid: host` and `/sys` volume mounts) to break out of the container and read your host machine's hardware stats.

1. **Create a `docker-compose.yml` file:**
   (Copy the contents from the repository's `docker-compose.yml`)

2. **Deploy the stack:**
   ```bash
   docker-compose up -d

    Access the Dashboard:
    Navigate to http://<your-server-ip>:8501

🐳 Configuration (Environment Variables)

You can customize the monitor directly in your docker-compose.yml under the environment: section:

    POLLING_INTERVAL_MS: How often the dashboard updates (Default: 5000 / 5 seconds).

    STORAGE_PATHS: Comma-separated list of mounted paths to monitor for disk space (e.g., /host_root,/mnt/media).

    LOG_CONFIG: Comma-separated list of Name:Path pairs for log tailing. (e.g., Syslog:/host_root/var/log/syslog,CasaOS:/host_root/var/log/casaos.log).

📜 License

Distributed under the GNU General Public License Version 3. See LICENSE for more information.


---

### Step 5: Push to Docker Hub
Now that your code is clean, local, and uses Compose, you can build and push it to Docker Hub so others can use it!

1. **Log in to Docker Hub via your terminal:**
   ```bash
   docker login

    Build the image using your Docker Hub username:
    (Replace yourusername with your actual Docker Hub username)
    Bash

    docker build -t yourusername/srvrmon:latest .

    Push the image to the public registry:
    Bash

    docker push yourusername/srvrmon:latest

Once that push finishes, anyone in the world can run your dashboard by just copying your docker-compose.yml file and typing docker-compose up -d!
