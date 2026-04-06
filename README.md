# digital_twin
# Physics-Informed Hybrid Digital Twin

A real-time, physics-informed Digital Twin for predicting the Remaining Useful Life (RUL) of high-stress aerospace components (e.g., rocket engine turbopumps). 

This project bridges the gap between purely data-driven machine learning and physical engineering constraints. By fusing a Hybrid CNN-BiLSTM neural network with absolute physical limits derived from Ansys simulations, the system achieves highly accurate degradation forecasting and visualizes the physical consequences in a real-time 3D environment.

**Note:** This is a fully virtualized software simulation. There is no physical hardware component; real-time sensor telemetry is dynamically generated based on interactive user inputs to mimic physical operations.

## 🚀 Key Features

* **Physics-Informed AI:** Integrates Ansys-derived constraints (Thermal Margin, Stress Intensity, Deformation) directly into the feature space of a CNN-BiLSTM model.
* **High Accuracy:** Achieves an RMSE of **2.89 cycles** and an MAE of **2.00 cycles** on the NASA C-MAPSS (FD001) test set, significantly outperforming standard LSTM baselines.
* **Real-Time 3D Visualization:** Uses Blender's Eevee engine and Python API to dynamically alter material shaders (glowing metal) and mesh coordinates (vibration) based on live telemetry.
* **Low-Latency Streaming:** End-to-end inference and visual rendering loop operates at under 50ms, enabling a smooth, interactive user dashboard.
* **Interactive Dashboard:** React-based UI allows users to adjust throttle/temperature on the fly and immediately observe the impact on the engine's Remaining Useful Life.

## 🏗️ System Architecture

The system operates in a continuous, bi-directional feedback loop:

1. **Frontend (React):** User adjusts operational parameters (Temp/RPM).
2. **Backend Engine Simulator (FastAPI/Python):** Mathematically simulates physical stress and generates a 21-sensor vector array mimicking engine telemetry.
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
