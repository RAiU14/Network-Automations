# EN-NMS: Enterprise Network Management System

A high-performance, async SNMP-based network monitoring prototype with a premium Glassmorphism Interface.

## 🚀 Features
- **Tiered Polling**: 
  - **Light Cycle**: Fast-poll (60s) for health, status, and traffic.
  - **Heavy Cycle**: Comprehensive (1h) inventory discovery (MAC Address collection).
- **On-Demand Control**: "Force Heavy Poll" button for immediate ASIC-level inventory.
- **Visual Analytics**: Interactive bandwidth peak and network availability charts.
- **Audit Logging**: Traceability of all system events and polling failures.
- **Dual-Theme Support**: High-contrast Dark and Light modes using a semantic design system.
- **Inventory Tracking**: MAC address collection and aggregate hardware visibility.

## 🛠️ Tech Stack
- **Backend**: FastAPI (Python), SQLite
- **Poller**: PySNMP (Async/Wait-Free)
- **Frontend**: React (Vite)
- **Design**: Vanilla CSS with Glassmorphism and Semantic Variables

## 🚦 Quick Start

1.  **Backend Setup**:
    ```powershell
    # Windows
    .\auto_start.ps1
    ```
2.  **Frontend Setup**:
    ```powershell
    cd frontend
    npm install
    npm run dev
    ```
3.  **Access**:
    Open `http://localhost:5173` in your browser.

## 🧪 Hardware Integration
For detailed instructions on testing with physical Cisco hardware, refer to the [HARDWARE_GUIDE.md](file:///HARDWARE_GUIDE.md).

## 📊 Project Logic
The core polling logic is located in `poller.py`, utilizing an async semaphore for maximum concurrency without CPU thrashing. Metrics are stored in `db/nms.db` and served via REST API in `backend.py`.

---

**Built by Antigravity x RAiU**
