import streamlit as st
import asyncio
import httpx
import pandas as pd
import time
import json
import requests
from datetime import datetime

import os

st.set_page_config(page_title="Distributed MLOps Platform", layout="wide")

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")
BASE_URL = API_URL
TELEMETRY_URL = API_URL

def get_cluster_telemetry():
    try:
        r = requests.get(f"{TELEMETRY_URL}/telemetry/cluster", timeout=5)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def get_hpa_telemetry():
    try:
        r = requests.get(f"{TELEMETRY_URL}/telemetry/hpa", timeout=5)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def get_metrics_telemetry():
    try:
        r = requests.get(f"{TELEMETRY_URL}/telemetry/metrics", timeout=5)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

st.title("Scalable NLP Inference System using Kubernetes")



async def set_routing_mode(mode):
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(f"{BASE_URL}/routing-mode", json={"mode": mode}, timeout=2.0)
            return r.json()
        except:
            return {"error": "unreachable"}

async def send_one(client, text, sem):
    async with sem:
        try:
            start = time.time()
            r = await client.post(f"{BASE_URL}/toxicity", json={"text": text, "model": "auto"}, timeout=30.0, headers={"Connection": "close"})
            res = r.json()
            latency = round(time.time() - start, 3)
            if "error" in res:
                return {"routing_mode": "error", "final_model": "error", "error": res["error"], "latency": latency, "toxicity": "unknown", "confidence": 0, "ewma_latency": 0, "routing_score": 0, "active_requests": 0, "replica_path": "[]"}
            
            return {
                "routing_mode": res.get("routing_mode"),
                "output": f"{res.get('toxicity', '').upper()} ({round(res.get('confidence', 0) * 100, 1)}%)",
                "routing_reason": res.get("routing_reason"),
                "routing_score": res.get("routing_score", 0),
                "active_requests": res.get("active_requests_on_model", 0),
                "ewma_latency": res.get("ewma_latency", 0),
                "final_model": res.get("final_model"),
                "toxicity": res.get("toxicity"),
                "confidence": res.get("confidence"),
                "replica_path": json.dumps(res.get("replica_path", [])),
                "latency": latency,
                "timestamp": datetime.now().strftime("%H:%M:%S")
            }
        except Exception as e:
            return {"routing_mode": "error", "final_model": "error", "error": str(e), "latency": 0, "toxicity": "unknown", "confidence": 0, "ewma_latency": 0, "routing_score": 0, "active_requests": 0, "replica_path": "[]"}

async def send_batch(text, total, conc):
    sem = asyncio.Semaphore(conc)
    transport = httpx.AsyncHTTPTransport(retries=1)
    async with httpx.AsyncClient(transport=transport, limits=httpx.Limits(max_keepalive_connections=conc, max_connections=conc)) as client:
        tasks = [send_one(client, text, sem) for _ in range(total)]
        return await asyncio.gather(*tasks)

# --- Sidebar ---
st.sidebar.header("Global Routing Controller")
selected_mode = st.sidebar.radio("Routing Strategy", ["adaptive", "static"])
if "last_mode" not in st.session_state:
    st.session_state["last_mode"] = None

if selected_mode != st.session_state["last_mode"]:
    try:
        asyncio.run(set_routing_mode(selected_mode))
        st.session_state["last_mode"] = selected_mode
    except:
        pass

st.sidebar.markdown("---")
st.sidebar.header("Payload")
text_input = st.sidebar.text_area("Contextual Text", "“I could kill you for deleting my files,” he joked during the cybersecurity workshop, while the lecturer explained why toxic language detection systems often misclassify sarcastic or quoted threats as genuine abuse.")

st.sidebar.markdown("---")
st.sidebar.header("Execution Modes")
run_single_btn = st.sidebar.button("Run Single Query")
st.sidebar.markdown("---")
total_requests = st.sidebar.number_input("Total Requests (Benchmark)", min_value=1, max_value=5000, value=200)
concurrency = st.sidebar.slider("Concurrency", 1, 200, 50)
run_btn = st.sidebar.button("Run Benchmark")

# --- Layout ---
col1, col2 = st.columns([2, 1.2])

with col1:
    if run_single_btn:
        st.markdown("### Single Query Inspection")
        with st.spinner("Analyzing..."):
            try:
                start = time.time()
                r = requests.post(f"{BASE_URL}/toxicity", json={"text": text_input, "model": "auto"}, timeout=30.0)
                res = r.json()
                latency = round(time.time() - start, 3)
                
                if "error" in res and res["error"]:
                    st.error(f"Error: {res['error']}")
                else:
                    res["latency"] = latency
                    st.success(f"**Prediction:** {res['toxicity'].upper()} (Confidence: {res['confidence']})")
                    replica_path = res.get('replica_path', [])
                    replica_str = replica_path[0] if replica_path else 'unknown'
                    if isinstance(replica_path, str):
                        try:
                            replica_str = json.loads(replica_path)[0]
                        except:
                            replica_str = replica_path
                    st.info(f"**Routing Explanation:** The `{res.get('routing_mode', 'unknown')}` strategy selected **{res.get('final_model', 'unknown')}** running on pod `{replica_str}` because of: `{res.get('routing_reason', 'unknown')}`. Its current EWMA latency was {res.get('ewma_latency', 0)}s and its queue depth was {res.get('active_requests_on_model', 0)}.")
                    st.json(res)
            except Exception as e:
                st.error(f"Failed: {e}")

    if run_btn:
        st.markdown(f"### Benchmarking: `{selected_mode.upper()}` Mode")
        with st.spinner(f"Processing {total_requests} requests (Max {concurrency} concurrently)..."):
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                results = loop.run_until_complete(send_batch(text_input, total_requests, concurrency))
                loop.close()
            except Exception as e:
                st.error(f"Failed during benchmark: {e}")
                results = []

        success = [r for r in results if "error" not in r]
        fail = [r for r in results if "error" in r]

        if success:
            df = pd.DataFrame(success)
            avg_latency = round(df["latency"].mean(), 3)
            p95_latency = round(df["latency"].quantile(0.95), 3)
            throughput = round(len(success) / max(df["latency"].sum(), 0.001), 2)
            
            # Traffic Distribution Visualization
            counts = df["final_model"].value_counts()
            dist_str = " | ".join([f"{k.capitalize()}: {int(v/len(df)*100)}%" for k, v in counts.items()])
            
            # Explicitly count ONLY adaptive hysteresis switches (ignoring random static choices)
            switches = df[df["routing_reason"] == "adaptive_hysteresis_switch"].shape[0]
        else:
            avg_latency = p95_latency = throughput = switches = 0
            df = pd.DataFrame()
            dist_str = "None"

        st.success(f"Benchmark Complete! {len(success)} success | {len(fail)} failed/timeouts.")
        st.markdown(f"**Final Traffic Distribution:** {dist_str}")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Avg Latency (s)", avg_latency)
        m2.metric("P95 Latency (s)", p95_latency)
        m3.metric("Throughput (r/s)", throughput)
        m4.metric("Adaptive Route Changes", switches)

        if not df.empty:
            st.markdown("#### Per-Request Model Response Table")
            display_df = df[[
                "timestamp",
                "final_model",
                "output",
                "replica_path",
                "latency",
                "ewma_latency",
                "routing_score",
                "routing_reason"
            ]]
            st.dataframe(display_df, height=300)
            
            st.download_button(
                label="Export Benchmark to CSV",
                data=df.to_csv(index=False).encode('utf-8'),
                file_name=f"benchmark_{selected_mode}_{total_requests}req.csv",
                mime="text/csv",
            )

            st.markdown("#### Routing Distribution Heatmap")
            st.bar_chart(df["final_model"].value_counts())

            routing_counts = df["final_model"].value_counts()

            st.markdown("#### Adaptive Routing Distribution")

            st.dataframe(
                pd.DataFrame({
                    "model": routing_counts.index,
                    "requests": routing_counts.values
                })
            )

            st.markdown("#### Latency Curve vs Concurrency")
            latency_df = df[["timestamp", "latency"]].copy()
            latency_df = latency_df.set_index("timestamp")

            st.line_chart(latency_df)

with col2:
    st.markdown("### Infrastructure Status")

    cluster_data = get_cluster_telemetry()
    hpa_data = get_hpa_telemetry()
    metrics_data = get_metrics_telemetry()

    if "error" not in cluster_data:

        st.markdown(
            f"#### Cluster State: **{cluster_data.get('cluster_state')}**"
        )

        st.caption(
            f"Total Active Pods: {cluster_data.get('total_active_pods')}"
        )

        pods = cluster_data.get("pods", [])

        if pods:

            for pod in pods:

                status = pod.get("status", "Unknown")
                st.markdown(
                    f"""
                    ### {pod.get('name')}

                    - Namespace: `{pod.get('namespace')}`
                    - Status: `{status}`
                    """
                )

    else:
        st.error(cluster_data["error"])

    st.markdown("---")

    st.markdown("#### HPA Status")

    if "error" not in hpa_data:

        hpa_df = pd.DataFrame(hpa_data.get("hpas", []))

        if not hpa_df.empty:
            st.dataframe(hpa_df)

    else:
        st.error(hpa_data["error"])

    st.markdown("---")

    st.markdown("#### Live Prometheus Metrics")

    if "error" not in metrics_data:

        cpu_results = (
            metrics_data
            .get("cpu", {})
            .get("data", {})
            .get("result", [])
        )

        mem_results = (
            metrics_data
            .get("memory", {})
            .get("data", {})
            .get("result", [])
        )

        col_cpu, col_mem = st.columns(2)

        with col_cpu:
            st.subheader("CPU Usage")

            if cpu_results:
                cpu_df = pd.DataFrame([
                    {
                        "pod": item["metric"].get("pod", "unknown"),
                        "value": round(float(item["value"][1]), 4)
                    }
                    for item in cpu_results
                ])

                st.bar_chart(cpu_df.set_index("pod"))

            else:
                st.warning("No CPU metrics available yet.")

        with col_mem:
            st.subheader("Memory Usage")

            if mem_results:
                mem_df = pd.DataFrame([
                    {
                        "pod": item["metric"].get("pod", "unknown"),
                        "value_mb": round(float(item["value"][1]) / 1024 / 1024, 2)
                    }
                    for item in mem_results
                ])

                st.bar_chart(mem_df.set_index("pod"))

            else:
                st.warning("No memory metrics available yet.")

    else:
        st.error(metrics_data["error"])

        
    st.markdown("### Architecture Guide: K8s vs Router")
    st.info("**1. Adaptive Routing (Model Selection)**: The FastAPI Router dynamically selects which *Model Service* to query (e.g. `toxic-baseline`) based on EWMA latency, Hysteresis, and Queue Depth.\n\n**2. Kubernetes Load Balancing (Pod Selection)**: Once the Router mathematically selects the optimal Model, the underlying *Kubernetes Service* abstraction natively distributes that request across the underlying *Pod Replicas* using connection-level Load Balancing.")