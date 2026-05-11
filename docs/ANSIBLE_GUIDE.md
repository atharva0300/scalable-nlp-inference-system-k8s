# Ansible Automation Guide

In enterprise MLOps architectures, manually executing `kubectl apply` commands introduces human error and limits repeatability. To achieve **Infrastructure as Code (IaC)**, this project integrates [Ansible](https://www.ansible.com/) for declarative infrastructure orchestration.

The playbooks located in the `ansible/` directory automate the entire lifecycle of the Kubernetes deployment.

---

## 🏗 Directory Structure

```text
ansible/
├── inventory        # Defines the target environment (localhost/K8s)
├── deploy.yml       # Provisions Minikube, Secrets, Deployments, and HPA
├── status.yml       # Audits the active cluster state
└── cleanup.yml      # Safely tears down all project resources
```

## 🚀 Playbook Execution

### 1. Provisioning the Cluster (`deploy.yml`)
This playbook handles end-to-end bootstrapping. It guarantees Minikube is running, enables the crucial `metrics-server` for autoscaling, injects Kubernetes Secrets, applies the microservice manifests, and performs a zero-downtime rolling restart.

```bash
cd ansible
ansible-playbook -i inventory deploy.yml
```
**Expected Output**: You will see a series of `changed` or `ok` statuses for each task, ending with a confirmation that the deployments have stabilized.

### 2. Auditing the Cluster (`status.yml`)
Use this playbook as a diagnostic tool. It queries the Kubernetes API and retrieves the current running Pod states and the Horizontal Pod Autoscaler (HPA) CPU utilization targets.

```bash
ansible-playbook -i inventory status.yml
```
**Expected Output**: A clean JSON-structured output showing exactly which models are currently online and how much load they are under.

### 3. Tearing Down the Cluster (`cleanup.yml`)
When finishing development or resetting the environment for a clean benchmark, use the cleanup playbook to gracefully terminate all Pods, Services, and Autoscalers.

```bash
ansible-playbook -i inventory cleanup.yml
```

---

## 🔧 How Kubernetes is Orchestrated

Ansible communicates with the Kubernetes cluster via the local `kubectl` binary (as defined by `ansible_connection=local` in the `inventory` file). 

Because Ansible is declarative, running `deploy.yml` multiple times is safe (idempotent). If the resources already exist, Ansible will simply report `ok` and skip re-creation, unless the underlying YAML files in `k8s/` have been modified, in which case it will intelligently apply the diffs.
