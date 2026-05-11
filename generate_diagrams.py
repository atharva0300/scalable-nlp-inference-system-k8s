import base64
import urllib.request
import json
import os

diagrams = {
    "1_High_Level_Architecture": """graph TD
    subgraph K8s["Kubernetes Cluster"]
        direction TB
        subgraph Gateway["API Gateway"]
            F[FastAPI Gateway] --> R[Adaptive Routing Engine]
        end
        
        subgraph Services["Inference Services (K8s Services & Pods)"]
            R -->|Model Selection| S1[Baseline Toxicity Model]
            R -->|Model Selection| S2[BERT Toxicity Model]
            R -->|Model Selection| S3[RoBERTa Toxicity Model]
        end
        
        HPA[Horizontal Pod Autoscaler] -.->|Autoscaling| Services
    end

    U[Frontend Dashboard<br>Streamlit] -->|User Request| F

    subgraph Observability["Observability Stack"]
        Services -.->|Logs| PT[Promtail]
        PT -.->|Log Stream| L[Loki]
        L -.->|Visualization| G[Grafana]
    end
    
    style U fill:#f9f9f9,stroke:#333,stroke-width:2px
    style K8s fill:#e6f3ff,stroke:#0066cc,stroke-width:2px
    style Gateway fill:#ffffff,stroke:#333,stroke-width:1px
    style Services fill:#ffffff,stroke:#333,stroke-width:1px
    style Observability fill:#f2f2f2,stroke:#666,stroke-width:2px""",

    "2_End_to_End_Request_Lifecycle": """sequenceDiagram
    participant U as User (Frontend)
    participant F as FastAPI Gateway
    participant R as Adaptive Router
    participant KS as Kubernetes Service
    participant P as Model Pod (Inference)
    
    U->>F: HTTP POST /toxicity (text)
    activate F
    F->>R: Initiate Model Selection
    activate R
    R->>R: Evaluate Latency & Queue Depth
    R-->>F: Select Target Model
    deactivate R
    F->>KS: Forward Request
    activate KS
    KS->>P: Load Balance to Pod
    activate P
    P-->>P: Toxicity Inference Execution
    P-->>KS: Return JSON Response
    deactivate P
    KS-->>F: Route Response
    deactivate KS
    F->>F: Update Runtime Telemetry (Routing Score)
    F-->>U: Return Final Response & Routing Metadata
    deactivate F""",

    "3_Adaptive_Routing_and_Load_Balancing": """graph TD
    Req[Incoming Request] --> Col[Runtime Metric Collection]
    Col --> EWMA[EWMA Latency Evaluation]
    Col --> QD[Queue Depth Evaluation]
    Col --> TO[Timeout Penalty Evaluation]
    
    EWMA --> Score[Routing Score Calculation]
    QD --> Score
    TO --> Score
    
    Score --> Hys{Hysteresis & Cooldown Check}
    Hys -->|Threshold Met / Cooldown Expired| Switch[Switch to Better Model]
    Hys -->|Threshold Not Met| Keep[Keep Current Model]
    
    Switch --> Route[Traffic Routing]
    Keep --> Route
    
    Route --> M1[Baseline Model]
    Route --> M2[BERT Model]
    Route --> M3[RoBERTa Model]
    
    style Req fill:#e6ffe6,stroke:#006600
    style Route fill:#ffe6e6,stroke:#cc0000
    style Hys fill:#fff2e6,stroke:#cc6600""",

    "4_Kubernetes_Deployment_Architecture": """graph TB
    subgraph Minikube["Minikube Cluster"]
        direction TB
        
        subgraph CP["Control Plane Controllers"]
            HPA[Horizontal Pod Autoscalers]
        end

        subgraph Svc["Kubernetes Services"]
            SvcR[fastapi-router-svc]
            Svc1[toxic-baseline-svc]
            Svc2[toxic-bert-svc]
            Svc3[toxic-roberta-svc]
        end

        subgraph Deps["Deployments & Replica Pods"]
            D_R[FastAPI Deployment] --> P_R1(Pod) & P_R2(Pod)
            D_B[Baseline Deployment] --> P_B1(Pod) & P_B2(Pod)
            D_BE[BERT Deployment] --> P_BE1(Pod) & P_BE2(Pod)
            D_RO[RoBERTa Deployment] --> P_RO1(Pod) & P_RO2(Pod)
        end
        
        SvcR --> D_R
        Svc1 --> D_B
        Svc2 --> D_BE
        Svc3 --> D_RO
        
        HPA -.->|Scale Metrics| Deps
    end
    
    style Minikube fill:#f4f8ff,stroke:#0055ff,stroke-width:2px
    style Svc fill:#ffffff,stroke:#333
    style Deps fill:#ffffff,stroke:#333""",

    "5_Observability_and_Logging_Pipeline": """graph LR
    subgraph K8s["Kubernetes Pods"]
        P1[FastAPI Router]
        P2[Inference Workers]
    end

    subgraph LogPipe["Logging Pipeline"]
        PT[Promtail] -->|Tail stdout/stderr| Loki[Loki Central Log Storage]
    end

    subgraph MetricsPipe["Metrics Pipeline"]
        MS[Metrics Server] -->|CPU / Memory| Kube[Kubernetes API]
    end

    P1 -.->|JSON Logs| PT
    P2 -.->|JSON Logs| PT
    
    P1 -.->|Metrics| MS
    P2 -.->|Metrics| MS

    subgraph Dashboards["Grafana / Streamlit Dashboards"]
        G1[Latency & Throughput]
        G2[Routing Telemetry]
        G3[Autoscaling Events]
    end

    Loki --> Dashboards
    Kube --> Dashboards
    
    style K8s fill:#e6f3ff,stroke:#0066cc
    style LogPipe fill:#fff2e6,stroke:#cc6600
    style Dashboards fill:#e6ffe6,stroke:#006600""",

    "6_CI_CD_and_Infrastructure_Automation": """graph LR
    Git[GitHub Repository] --> J1[Jenkins: Checkout]
    J1 --> J2[Jenkins: Lint & Smoke Test]
    J2 --> J3[Jenkins: Build Docker Image]
    J3 --> Hub[Docker Registry]
    J3 --> J4[Jenkins: K8s Deployment]
    
    subgraph Ansible["Ansible Automation"]
        J4 --> A1[Apply K8s Manifests]
        A1 --> A2[Trigger Rolling Restart]
    end
    
    A2 --> Val[Benchmark Validation]
    Val --> Obs[Observability Verification]
    
    style Git fill:#f9f9f9,stroke:#333
    style Hub fill:#e6f3ff,stroke:#0066cc
    style Ansible fill:#f2f2f2,stroke:#666"""
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
