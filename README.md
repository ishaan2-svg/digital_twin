# Physics-Informed Hybrid Digital Twin

A real-time, physics-informed Digital Twin for predicting the Remaining Useful Life (RUL) of high-stress aerospace components (e.g., rocket engine turbopumps). 

This project bridges the gap between purely data-driven machine learning and physical engineering constraints. By fusing a Hybrid CNN-BiLSTM neural network with absolute physical limits derived from Ansys simulations, the system achieves highly accurate degradation forecasting and visualizes the physical consequences in a real-time 3D environment.

**Note:** This is a fully virtualized software simulation. There is no physical hardware component; the system uses random values instead of actual sensor values to mimic physical operations and real-time telemetry.

## 🚀 Key Features

* **Physics-Informed AI:** Integrates Ansys-derived constraints (Thermal Margin, Stress Intensity, Deformation) directly into the feature space of a CNN-BiLSTM model.
* **High Accuracy:** Achieves an RMSE of **2.89 cycles** and an MAE of **2.00 cycles** on the NASA C-MAPSS (FD001) test set, significantly outperforming standard LSTM baselines.
* **Real-Time 3D Visualization:** Uses Blender's Eevee engine and Python API to dynamically alter material shaders (glowing metal) and mesh coordinates (vibration) based on live telemetry.
* **Low-Latency Streaming:** End-to-end inference and visual rendering loop operates at under 50ms, enabling a smooth, interactive user dashboard.
* **Interactive Dashboard:** React-based UI allows users to adjust throttle/temperature on the fly and immediately observe the impact on the engine's Remaining Useful Life.

## 🏗️ System Architecture

The system operates in a continuous, bi-directional feedback loop:

1. **Frontend (React):** User adjusts operational parameters (Temp/RPM).
2. **Backend Engine Simulator (FastAPI/Python):** Mathematically simulates physical stress and uses random values instead of hardware sensor values to mimic engine telemetry.
3. **Hybrid AI Inference (TensorFlow):** Computes physics features and predicts the real-time RUL and degradation rate.
4. **Digital Twin (Blender):** Receives physical data via TCP socket, updates the 3D model, and streams JPEG frames back to the backend.
5. **Dashboard Update:** Frontend displays the live video feed alongside the dynamic RUL graph.

## 🛠️ Technology Stack

* **Machine Learning:** TensorFlow, Keras, Scikit-learn, Pandas, NumPy
* **Physics Simulation (Offline):** Ansys (Finite Element Analysis)
* **Backend API & Simulator:** FastAPI, Uvicorn, Python WebSockets
* **3D Visualization:** Blender, Blender Python API (`bpy`)
* **Frontend Dashboard:** React, Recharts, Node.js

## ⚙️ Installation & Setup

### Prerequisites
* Python 3.8+
* Node.js & npm
* Blender 3.0+

### 1. Clone the Repository
```bash
git clone [https://github.com/ishaan2-svg/digital_twin.git](https://github.com/ishaan2-svg/digital_twin.git)
cd digital_twin
```

### 2. Backend Setup
Create a virtual environment and install the required Python packages.
```bash
# Create and activate virtual environment (Windows)
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Frontend Setup
Navigate to the frontend directory and install the Node modules.
```bash
cd frontend  # Replace with your actual frontend folder name
npm install
```

## 🏃‍♂️ Running the Digital Twin

To establish the continuous feedback loop, the services must be started simultaneously.

**1. Start the Backend Server**
```bash
# From the root project directory (ensure venv is activated)
python backend_server.py
```

**2. Start the Blender Server**
* Open your 3D engine model (`.blend` file) in Blender.
* Navigate to the **Scripting** workspace.
* Open `blender_server.py` and click **Run Script** (▶️) to start the TCP listener.

**3. Start the Frontend Dashboard**
```bash
# From the frontend directory
npm start
```

Open `http://localhost:3000` in your browser to interact with the Digital Twin.

## 📊 Model Performance

| Model | RMSE (Cycles) | MAE (Cycles) | Inference Time |
| :--- | :--- | :--- | :--- |
| Baseline LSTM | 7.77 | 5.41 | ~18.00 ms |
| **Physics-Informed Hybrid** | **2.89** | **2.00** | **15.76 ms** |

*The integration of Ansys physics features resulted in a ~63% improvement in overall prediction accuracy while maintaining edge-capable inference speeds.*
