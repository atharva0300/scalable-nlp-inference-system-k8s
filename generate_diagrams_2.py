import base64
import urllib.request
import json
import os

diagrams = {
    "5_Observability_and_Logging_Pipeline": """graph TD
    classDef default fill:#ffffff,stroke:#333,stroke-width:2px,color:#000;
    classDef highlight fill:#e6f3ff,stroke:#0066cc,stroke-width:2px;
    classDef external fill:#f9f9f9,stroke:#666,stroke-width:2px,stroke-dasharray: 5 5;

    subgraph K8s["Kubernetes Cluster"]
        direction TB
        Pods["K8s Inference Pods<br/>(FastAPI, Baseline, BERT, RoBERTa)"]
    end

    subgraph Telemetry["Telemetry Collection"]
        direction LR
        AppLogs["Application Logs<br/>(JSON)"]
        Metrics["Node/Pod Metrics<br/>(CPU, Mem, Latency, Queue)"]
    end
    
    Pods -->|stdout / stderr| AppLogs
    Pods -->|cAdvisor / Metrics-Server| Metrics

    subgraph Observability["Centralized Observability Stack"]
        direction TB
        Promtail["Promtail<br/>(Log Aggregator)"]
        Loki["Loki<br/>(Central Log Storage)"]
        Grafana["Grafana<br/>(Visualization & Dashboards)"]
    end

    AppLogs --> Promtail
    Promtail --> Loki
    Metrics --> Grafana
    Loki -->|LogQL| Grafana

    subgraph Visualizations["Grafana Visualization Panels"]
        direction LR
        V1["Latency & Throughput Graphs"]
        V2["Queue Depth & Routing Metrics"]
        V3["HPA Autoscaling Telemetry"]
    end
    
    Grafana --> Visualizations

    class K8s highlight;
    class Telemetry default;
    class Observability default;
    class Visualizations external;
    """,

    "3_Adaptive_Routing_and_Load_Balancing": """graph TD
    classDef default fill:#ffffff,stroke:#333,stroke-width:2px,color:#000;
    classDef engine fill:#e6f3ff,stroke:#0066cc,stroke-width:2px;
    classDef models fill:#f9f9f9,stroke:#666,stroke-width:2px;
    classDef decision fill:#fff2e6,stroke:#cc6600,stroke-width:2px;

    Req[Incoming User Request] --> Gateway[FastAPI Gateway]
    Gateway --> Router[Adaptive Routing Engine]
    
    class Router engine;

    subgraph Eval["Runtime Evaluation Stages"]
        direction TB
        E1[EWMA Latency Evaluation]
        E2[Queue Depth Evaluation]
        E3[Timeout Penalty Check]
        E4[Failure Penalty Check]
        
        E1 --> Calc[Routing Score Calculation]
        E2 --> Calc
        E3 --> Calc
        E4 --> Calc
    end

    Router --> Eval
    
    Calc --> Hys{Hysteresis &<br/>Cooldown Logic}
    class Hys decision;

    Hys -->|Avoid Overloaded Models| Dist[Dynamic Traffic Redistribution]
    
    subgraph K8s["Kubernetes Services & Models"]
        direction LR
        M1[Baseline Model Pods]
        M2[BERT Model Pods]
        M3[RoBERTa Model Pods]
    end

    Dist -->|Route 1| M1
    Dist -->|Route 2| M2
    Dist -->|Route 3| M3

    class K8s models;
    """,

    "7_k6_Benchmarking_Workflow": """graph TD
    classDef default fill:#ffffff,stroke:#333,stroke-width:2px,color:#000;
    classDef k8s fill:#e6f3ff,stroke:#0066cc,stroke-width:2px;
    classDef ext fill:#f9f9f9,stroke:#666,stroke-width:2px;

    subgraph LoadGen["Load Generation Phase"]
        K6["k6 Load Generator"] -->|Concurrent HTTP Requests| ReqStream["Traffic Stream"]
    end

    subgraph Cluster["Kubernetes Infrastructure"]
        direction TB
        Gateway["FastAPI Gateway"]
        Router["Adaptive Router"]
        Svc["Kubernetes Services"]
        Pods["Inference Pods"]
        
        Gateway --> Router
        Router --> Svc
        Svc -->|Load Balances| Pods
    end

    ReqStream --> Gateway

    subgraph Evaluation["Performance Evaluation & Telemetry"]
        direction LR
        Met1["Latency Measurement"]
        Met2["Throughput Calculation"]
        Met3["Routing Metrics"]
        
        Pods -.-> Met1
        Pods -.-> Met2
        Router -.-> Met3
    end

    subgraph Trigger["Autoscaling"]
        HPA["Kubernetes HPA"]
        Pods -.->|CPU Spike| HPA
        HPA -.->|Scale Out| Pods
    end

    subgraph Mon["Observability"]
        Graf["Grafana Monitoring"]
        Met1 --> Graf
        Met2 --> Graf
        Met3 --> Graf
        HPA -.-> Graf
    end

    class Cluster k8s;
    class LoadGen ext;
    class Evaluation default;
    class Trigger ext;
    class Mon default;
    """
}

os.makedirs("diagrams", exist_ok=True)

for name, code in diagrams.items():
    print(f"Generating {name}.png...")
    
    b64 = base64.urlsafe_b64encode(code.encode('utf-8')).decode('ascii')
    
    url = f"https://mermaid.ink/img/{b64}?type=png&bgColor=FFFFFF"
    
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response, open(f"diagrams/{name}.png", 'wb') as out_file:
            out_file.write(response.read())
        print(f"Successfully saved diagrams/{name}.png")
    except Exception as e:
        print(f"Error on {name}: {e}")
