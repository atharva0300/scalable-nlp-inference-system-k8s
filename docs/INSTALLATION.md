# Installation Guide

This guide provides step-by-step instructions for setting up the environment required to run the **Scalable NLP Inference System**.

## 💻 System Requirements

- **Operating System**: Windows 11 (with WSL2), macOS (M1/M2/Intel), or Linux (Ubuntu 20.04+).
- **Architecture**: x86_64 or ARM64.
- **Memory**: Minimum 16GB RAM (32GB recommended for running multiple transformer models locally).
- **CPU**: 4+ Cores.

## 📦 Required Software

Before proceeding, ensure the following core dependencies are installed:

1. **Python**: `v3.10` or higher.
2. **Docker Desktop**: Must be running with WSL2 integration enabled (if on Windows).
3. **Minikube**: Local Kubernetes engine.
4. **kubectl**: Kubernetes command-line tool.

### Optional (For Automation & CI/CD)
5. **Ansible**: For infrastructure automation.
6. **Jenkins**: For CI/CD pipelines.
7. **k6**: For benchmarking and load generation.

---

## 🛠 Step-by-Step Setup

### 1. Python Environment
We recommend using a virtual environment to avoid dependency conflicts.
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Docker & Minikube
Ensure Docker Desktop is open and running. Then, install and start Minikube using the Docker driver:
```bash
minikube start --driver=docker --memory=8192 --cpus=4
```
*Note: We allocate 8GB of RAM explicitly to Minikube to comfortably hold the NLP models.*

Verify the cluster is running:
```bash
kubectl get nodes
```

### 3. Enable Metrics-Server (Crucial for HPA)
The Horizontal Pod Autoscaler (HPA) requires real-time CPU telemetry. You must enable the Minikube addon:
```bash
minikube addons enable metrics-server
```
*Wait ~60 seconds for the metrics API to initialize.*

### 4. Install k6 (For Benchmarking)
If you wish to run the performance testing suite:
- **Windows**: `winget install k6`
- **Mac**: `brew install k6`
- **Linux**: `sudo apt install k6`

### 5. Install Ansible (For Deployment Automation)
Ansible is Python-based. You can install it directly via pip:
```bash
pip install ansible
```

---

## ✅ Environment Validation

Run the following commands to guarantee your environment is ready for deployment:

```bash
docker --version      # Should return Docker version
kubectl version       # Should return Client and Server K8s versions
minikube status       # Should report Host, Kubelet, API Server as "Running"
k6 version            # Should return k6 version (Optional)
ansible --version     # Should return ansible version (Optional)
```

If all commands succeed, you are ready to proceed to [Running the Project](RUNNING_THE_PROJECT.md)!
