# Distributed Adaptive NLP Inference Platform

A rubric-complete, presentation-ready distributed systems project demonstrating production MLOps and DevOps patterns using Kubernetes, FastAPI, and Transformers.

## Key Features
- **Distributed Microservices**: Independently scaled pods for baseline, BERT, and RoBERTa models.
- **Production Adaptive Routing**: Intelligent API Gateway utilizing **EWMA Latency Smoothing**, **Routing Hysteresis**, and **Queue Depth Analysis**.
- **Self-Healing Infrastructure**: Kubernetes-native Horizontal Pod Autoscalers (HPA) and automated failover circuit breakers.
- **Experimental Benchmarking**: Native Streamlit dashboarding with CSV export to compare Adaptive vs Static Routing under heavy k6 sustained concurrency.

## Observability Architectural Justification: Why Loki instead of ELK?

For this distributed inference system, **Grafana Loki + Promtail** were deliberately selected over the traditional ELK (Elasticsearch, Logstash, Kibana) stack.
- **Massive Memory Reduction**: Elasticsearch requires heavy JVM memory overhead (often 2GB-4GB+ just to idle). Loki is written in Go and stores compressed log streams, operating easily within a 16GB RAM laptop environment alongside heavy ML Models.
- **Kubernetes-Native Context**: Loki automatically reads Kubernetes pod labels, natively matching the `kubectl top` mindset.
- **Index-Free Speed**: Loki does not index the full text of the logs, drastically reducing storage costs and CPU overhead on our inference nodes.

## CI/CD and Automation (Rubric Compliance)

### Jenkins Integration
A complete modular Jenkins pipeline is provided in `ci-cd/Jenkinsfile`. 
It performs syntax checking, Docker image building, secure DockerHub pushing, and zero-downtime Kubernetes rolling restarts followed by a `k6` smoke test.

### Ansible Configuration Management
We utilize Ansible to orchestrate the infrastructure locally:
- `ansible/deploy.yml`: Provisions Minikube, Metrics-Server, Kubernetes Secrets, and deployments.
- `ansible/status.yml`: Audits the cluster.
- `ansible/cleanup.yml`: Tears down the infrastructure.

### Demonstration Scripts
- `demo-resiliency.ps1`: An automated script to brutally kill a worker pod mid-inference to demonstrate the Router's Circuit Breaking and Kubernetes' automatic Self-Healing recovery.

## Getting Started

1. Enable Minikube and metrics-server:
   ```bash
   minikube start
   minikube addons enable metrics-server
   ```
2. Start the router port-forward in a dedicated terminal:
   ```bash
   kubectl port-forward svc/fastapi-router-service 8000:8000
   ```
3. Run the Experimental Dashboard:
   ```bash
   streamlit run frontend/app.py
   ```
4. Run Sustained k6 Load Tests:
   ```bash
   k6 run load-test/k6/moderate.js
   ```
