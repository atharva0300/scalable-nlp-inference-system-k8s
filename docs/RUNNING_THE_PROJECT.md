# Project Execution Guide

This document outlines the step-by-step workflow for launching the **Scalable NLP Inference System**, validating its health, and utilizing the experimental MLOps dashboard.

*Note: Ensure you have completed the [Installation Guide](INSTALLATION.md) before proceeding.*

---

## 1. Prepare the Kubernetes Environment

Point your local Docker daemon to the Minikube internal Docker registry. This allows Kubernetes to pull your locally built images without requiring a push to DockerHub.
```bash
# On Linux / Mac:
eval $(minikube docker-env)

# On Windows PowerShell:
& minikube -p minikube docker-env --shell powershell | Invoke-Expression
```

## 2. Build the Docker Image
Build the unified FastAPI router and worker image. The script dynamically adopts its role based on Kubernetes environment variables.
```bash
cd gateway/fastapi
docker build -t my-fastapi-router:latest .
cd ../../
```

## 3. Deploy Kubernetes Resources
Apply the configuration files to provision the system. 
*(Alternatively, you can automate this step using Ansible. See the [Ansible Guide](ANSIBLE_GUIDE.md)).*

```bash
# Deploy Secrets
kubectl apply -f k8s/secrets/

# Deploy Pods
kubectl apply -f k8s/deployments/

# Expose Services
kubectl apply -f k8s/services/

# Attach Horizontal Pod Autoscalers (HPA)
kubectl apply -f k8s/hpa/
```

Verify that the pods are spinning up:
```bash
kubectl get pods -w
```
*Wait until all pods show `Running` and `1/1` READY state.*

## 4. Port Forwarding the Gateway
To allow local tools and the Streamlit dashboard to communicate with the cluster, open a dedicated terminal and bind the internal service to your localhost:
```bash
kubectl port-forward svc/fastapi-router-service 8000:8000
```
*Leave this terminal running in the background.*

## 5. Launch the Streamlit Dashboard
Open a new terminal window, activate your Python virtual environment, and boot the MLOps research dashboard:
```bash
streamlit run frontend/app.py
```
This will automatically open your browser to `http://localhost:8501`.

---

## 🔬 Running Experiments & Benchmarks

Once the dashboard is online, you can interact with the system in multiple ways:

### A. Single Query Mode
1. Enter a contextual sentence into the sidebar (e.g., *"I will kill you for deleting my code"*).
2. Click **Run Single Query**.
3. Read the **Routing Explanation Panel** to understand *why* the Adaptive Router mathematically chose a specific NLP model based on current EWMA latency and queue depth.

### B. Sustained Benchmarking (k6 Integration)
To truly stress the system and trigger Kubernetes Autoscaling:
1. On the Streamlit sidebar, configure a benchmark (e.g., `200 Total Requests`, `50 Concurrency`).
2. Click **Run Benchmark**.
3. Watch the right-hand **Infrastructure Status** panel. The state will shift from 🟢 `STABLE` to 🟡 `SCALING UP` as the `k6` load generator overwhelms the pods.
4. Observe the **HPA Scaling Timeline** table explicitly logging the provisioning of new replicas.

### C. Exporting Data
After a benchmark completes, use the **Export Benchmark to CSV** button to download the precise `latency`, `queue_depth`, and `routing_score` for every single request. This is highly useful for generating graphs for academic and performance reports.
