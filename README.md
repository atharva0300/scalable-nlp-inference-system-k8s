# Scalable NLP Inference System using Kubernetes

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.95+-00a393.svg)](https://fastapi.tiangolo.com/)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-1.28+-326ce5.svg)](https://kubernetes.io/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ed.svg)](https://www.docker.com/)
[![Grafana](https://img.shields.io/badge/Grafana-Enabled-F46800.svg)](https://grafana.com/)
[![Ansible](https://img.shields.io/badge/Ansible-Automation-EE0000.svg)](https://www.ansible.com/)
[![Jenkins](https://img.shields.io/badge/Jenkins-CI%2FCD-D24939.svg)](https://www.jenkins.io/)
[![k6](https://img.shields.io/badge/k6-Load_Testing-7D64FF.svg)](https://k6.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An enterprise-grade, cloud-native Machine Learning Operations (MLOps) platform demonstrating distributed natural language processing (NLP) inference. This system serves multiple toxicity detection models (Baseline, BERT, RoBERTa) orchestrated by a custom-built Adaptive API Gateway, deployed on Kubernetes, and monitored by a lightweight observability stack.

---

## 📖 Project Overview

Modern NLP transformer models are notoriously resource-intensive. When deploying these models at scale, traditional static load balancing often leads to queue congestion and high tail-latencies (P95). 

This project solves this by introducing a **Latency-Aware Adaptive Routing Engine**. The gateway mathematically evaluates real-time queue depth and Exponentially Weighted Moving Average (EWMA) latency to intelligently distribute incoming requests across varying sizes of ML models. This ensures high throughput and latency stability under sustained traffic spikes, while Kubernetes Horizontal Pod Autoscalers (HPA) seamlessly provision new replicas in the background.

## ✨ Key Features

- **Distributed Microservices Architecture**: Distinct, containerized pods for FastAPI Gateway, Baseline Model, BERT, and RoBERTa.
- **Production Adaptive Routing**: Intelligent load balancing using EWMA latency smoothing, queue depth analysis, hysteresis thresholds, and cooldown windows.
- **Kubernetes Self-Healing & Autoscaling**: Integrated `metrics-server` driving Horizontal Pod Autoscalers (HPA) alongside automated failover circuit breakers.
- **Lightweight Observability Stack**: Grafana, Loki, and Promtail (replacing heavy ELK stacks) for real-time log aggregation and performance visualization.
- **Enterprise Automation**: Fully automated infrastructure provisioning via **Ansible** and CI/CD pipelines via **Jenkins**.
- **Experimental Benchmarking**: Built-in Streamlit dashboard and `k6` load-test suites to actively benchmark and export CSV metrics comparing Adaptive vs. Static routing.

---

## 🛠 v2.0 Architectural Overhaul (Recent Stabilization Updates)

The system has undergone a major production-grade stabilization refactor to resolve structural bottlenecks, race conditions, and infrastructure blind spots:

1. **High-Concurrency Thread Synchronization**: 
   * Global state variables inside the FastAPI Gateway (e.g., `queue_depth`, `ewma_latency`) are now strictly synchronized using `asyncio.Lock()` to eliminate race conditions during high-volume `k6` benchmark spikes.
   * Increased the `anyio` thread limiter to 100 to prevent artificial HTTP bottlenecks.

2. **Aggressive Circuit Breaker Evolution**:
   * Previously, the routing algorithm assigned a score of `9999.0` to failing nodes, which inadvertently caused traffic to eventually route to dead pods during massive congestion.
   * The circuit breaker now strictly returns `float('inf')` during open states, forcing a `503` fail-fast behavior and zero-downtime rerouting.

3. **Infrastructure Observability & cAdvisor Integration**:
   * Replaced pseudo-CPU queries with native Kubernetes hardware metrics.
   * Upgraded the `Prometheus` deployment by integrating a strict `ClusterRole` and scraping the `kubelet/cadvisor` proxy endpoints, successfully exposing live container `CPU` and `Memory` byte metrics directly to the Streamlit UI.

4. **Zero-Downtime Model Bootstrapping**:
   * Upgraded the Kubernetes ML worker manifests (`fastapi.yaml`) to utilize `startupProbe` alongside `readinessProbe`. This ensures gigabyte-sized HuggingFace transformer models have infinite time to download into memory upon boot without being prematurely terminated by rigid readiness checks.

5. **RBAC Least Privilege Hardening**:
   * The Gateway's Kubernetes telemetry API polling was restricted to the `default` namespace using scoped `Role` and `RoleBinding` objects, entirely stripping away dangerous cluster-wide privileges.
   * `imagePullPolicy` was strictly configured to support localized Docker image builds inside Minikube to prevent pulling outdated, non-functional code from public registries.

---

## 🏛 System Architecture

![High-Level Architecture](diagrams/1_High_Level_Architecture.png)

### Adaptive Routing Workflow
The API Gateway evaluates the cluster health upon every request. Rather than oscillating violently during micro-stutters, the router utilizes a `0.95` decay penalty, a `15%` hysteresis threshold, and a `3-second` freeze window to guarantee production stability.

![Adaptive Routing](diagrams/3_Adaptive_Routing_and_Load_Balancing.png)

---

## 📂 Repository Structure

The repository follows standard cloud-native structure guidelines:

```text
.
├── ansible/               # Ansible playbooks (deploy, status, cleanup)
├── ci-cd/                 # Jenkinsfile and CI/CD pipeline definitions
├── diagrams/              # High-res architecture diagrams
├── docs/                  # Extensive documentation guides
├── frontend/              # Streamlit Research Dashboard
├── gateway/               # FastAPI Router and ML Worker services
├── k8s/                   # Kubernetes Manifests (Deployments, Services, HPA, Secrets)
└── load-test/             # k6 benchmarking scripts (moderate, stress, queue-pressure)
```

---

## 🚀 Getting Started

### Quick Start
To launch the system immediately using Minikube and Streamlit, run the following commands:

1. **Start Local Cluster**:
```bash
minikube start
```

2. **Build the Local Docker Image** (Inside Minikube):
Since we've made custom changes to the Python backend, we need to build it into the cluster's local registry so the pods run our new code instead of the public Docker Hub version.
```bash
eval $(minikube docker-env)
docker build -t my-fastapi-router:latest gateway/fastapi/
```

3. **Deploy Kubernetes Infrastructure**:
```bash
kubectl apply -f k8s/secrets/
kubectl apply -f k8s/rbac/
kubectl apply -f k8s/deployments/
kubectl apply -f k8s/services/
kubectl apply -f k8s/hpa/
```
Wait for all pods to show `Running`: `kubectl get pods -w`

3. **Expose the Gateway**:
Open a separate terminal and port-forward the API router:
```bash
kubectl port-forward svc/fastapi-router-service 8000:8000
```

4. **Launch the Dashboard**:
Open another terminal, create a virtual environment, install the frontend dependencies, and boot the MLOps Streamlit interface:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r frontend/requirements.txt
streamlit run frontend/app.py
```
This will open the benchmarking dashboard at `http://localhost:8501`.

### Detailed Documentation
To ensure a seamless setup, we have modularized the extensive documentation. Please follow the guides in order for deep-dives into Ansible, Jenkins, and Architecture:

1. **[Installation Guide](docs/INSTALLATION.md)**: System requirements, dependencies, and environment setup.
2. **[Running the Project](docs/RUNNING_THE_PROJECT.md)**: Full step-by-step execution to spin up the cluster and access the UI.
3. **[Ansible Deployment Guide](docs/ANSIBLE_GUIDE.md)**: How to automate infrastructure provisioning.
4. **[Jenkins CI/CD Guide](docs/JENKINS_GUIDE.md)**: Setting up continuous integration and automated rollouts.
5. **[Tech Stack Documentation](docs/TECH_STACK.md)**: Deep dive into why each technology was chosen.
6. **[Troubleshooting](docs/TROUBLESHOOTING.md)**: Solutions to common Kubernetes, Minikube, and Docker issues.

---

## Environment and Dependency Versions

The project was developed and tested using the following software versions.

| Component | Version |
|---|---|
| Python | 3.11 |
| Docker Desktop | 28.x |
| Minikube | v1.35+ |
| Kubernetes (kubectl) | v1.32+ |
| Helm | v3.17+ |
| Streamlit | 1.45+ |
| FastAPI | 0.115+ |
| Transformers | 4.51+ |
| PyTorch | 2.7+ |
| Grafana | 11.x |
| Loki | 3.x |
| Promtail | 3.x |
| Jenkins | 2.x |
| Ansible | 11.x |
| k6 | 1.0+ |

> Note: Minor version differences may still work, but the above versions were used during development, benchmarking, and experimentation.


## 📊 Benchmarking & Autoscaling Results

### Static vs Adaptive Routing Comparison
By utilizing `k6` to simulate 200 concurrent users (`load-test/k6/queue-pressure-test.js`), we observed the following under our Minikube deployment:

* **Static Routing**: Suffers from queue congestion as heavier models (RoBERTa) bottleneck the round-robin sequence, artificially inflating cluster P95 latency.
* **Adaptive Routing**: The EWMA Gateway detects the RoBERTa congestion in real-time, opens the hysteresis threshold, and dynamically bleeds the excess traffic to the faster Baseline model, preserving throughput and stabilizing tail latency.

### Resiliency Demonstration
The system guarantees zero-downtime inference. By executing `demo-resiliency.ps1`, a worker pod is violently terminated. The Gateway instantly catches the connection timeout, opens the circuit breaker, applies a mathematical failure penalty to the dead route, and redirects all traffic to surviving replicas while Kubernetes natively spins up a replacement pod in the background.

---

## 🔮 Future Improvements

- **GPU Acceleration**: Migrating the `transformers` pipeline to leverage CUDA nodes for massive throughput increases.
- **gRPC Integration**: Replacing HTTP/JSON transport between the Gateway and Worker pods with Protocol Buffers for lower serialization overhead.
- **Prometheus Integration**: Expanding the metrics pipeline to include native Prometheus scraping for highly granular HPA custom metrics.

---

## 👨‍💻 Contributors
Developed as a comprehensive MLOps Systems Engineering project demonstrating scalable NLP architectures, Kubernetes orchestration, and intelligent API gateway design.
