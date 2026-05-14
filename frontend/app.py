import streamlit as st
import asyncio
import httpx
import pandas as pd
import time
import json
import subprocess
import re
from datetime import datetime

st.set_page_config(page_title="Distributed MLOps Platform", layout="wide")

BASE_URL = "http://127.0.0.1:8000"

st.title("Scalable NLP Inference System using Kubernetes")

def kubectl(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode()
    except subprocess.CalledProcessError as e:
        return f"Error: {e.output.decode()}"
    except Exception as e:
        return f"Error: {str(e)}"

def get_pod_metrics():
    if 'cached_pod_metrics' not in st.session_state:
        st.session_state['cached_pod_metrics'] = pd.DataFrame()
        st.session_state['metrics_health'] = "Warming Up / Unavailable"

    out = kubectl("kubectl top pods --no-headers")
    data = []
    
    # Check for valid metrics output
    if "error:" not in out.lower() and "Error" not in out and out.strip():
        for line in out.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 3 and parts[1] != "0m": # Simple validation
                name, cpu, mem = parts[0], parts[1], parts[2]
                try:
                    cpu_val = int(re.sub(r'\D', '', cpu))
                    mem_val = int(re.sub(r'\D', '', mem))
                    data.append({"Pod": name, "CPU (m)": cpu_val, "Memory (Mi)": mem_val})
                except:
                    pass
                    
        if data:
            st.session_state['cached_pod_metrics'] = pd.DataFrame(data)
            st.session_state['metrics_health'] = "Healthy"
            return st.session_state['cached_pod_metrics']
            
    # Fallback to cache if transient failure
    if not st.session_state['cached_pod_metrics'].empty:
        st.session_state['metrics_health'] = "Delayed (Using Cache)"
        return st.session_state['cached_pod_metrics']
        
    st.session_state['metrics_health'] = "Warming Up..."
    return pd.DataFrame()



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
    async with httpx.AsyncClient(transport=transport, limits=httpx.Limits(keepalive_expiry=0, max_keepalive_connections=0)) as client:
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
            async def wrap_send_one():
                sem = asyncio.Semaphore(1)
                async with httpx.AsyncClient() as client:
                    return await send_one(client, text_input, sem)
            try:
                try:
                    res = asyncio.run(wrap_send_one())
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    res = loop.run_until_complete(wrap_send_one())
                
                if "error" in res and res["error"]:
                    st.error(f"Error: {res['error']}")
                else:
                    st.success(f"**Prediction:** {res['toxicity'].upper()} (Confidence: {res['confidence']})")
                    st.info(f"**Routing Explanation:** The `{res['routing_mode']}` strategy selected **{res['final_model']}** running on pod `{json.loads(res['replica_path'])[0]}` because of: `{res['routing_reason']}`. Its current EWMA latency was {res['ewma_latency']}s and its queue depth was {res['active_requests']}.")
                    st.json(res)
            except Exception as e:
                st.error(f"Failed: {e}")

    if run_btn:
        st.markdown(f"### Benchmarking: `{selected_mode.upper()}` Mode")
        with st.spinner(f"Processing {total_requests} requests (Max {concurrency} concurrently)..."):
            try:
                try:
                    results = asyncio.run(send_batch(text_input, total_requests, concurrency))
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    results = loop.run_until_complete(send_batch(text_input, total_requests, concurrency))
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                results = loop.run_until_complete(send_batch(text_input, total_requests, concurrency))

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

            st.markdown("#### Latency Curve vs Concurrency")
            st.line_chart(df["latency"])

with col2:
    st.markdown("### Infrastructure Status")
    
    # Scale Status Logic
    hpa_out = kubectl("kubectl get hpa")
    pods_out = kubectl('kubectl get pods -l "app in (fastapi-router, toxic-baseline, toxic-bert, toxic-roberta)"')
    pod_count = pods_out.count("Running")
    
    status_label = "STABLE"
    recent_events = kubectl('kubectl get events --field-selector involvedObject.kind=HorizontalPodAutoscaler')
    if "SuccessfulRescale" in recent_events and "New size:" in recent_events:
        if "scale down" in recent_events.lower():
            status_label = "SCALING DOWN (Cooldown)"
        else:
            status_label = "SCALING UP (Load Spiked)"
            
    st.markdown(f"#### Cluster State: **{status_label}**")
    st.caption(f"Total Active Pods: {pod_count}")
    
    if st.button("Refresh Telemetry"):
        pass
        
    try:
        r = httpx.get(f"{BASE_URL}/routing-stats", timeout=2.0)
        data = r.json()
        st.info(f"Active Cluster Mode: **{data.get('mode', 'unknown').upper()}**")
        stats = data.get("stats", {})
        
        for m, s in stats.items():
            st.metric(
                f"Score ({m})",
                s.get("routing_score", 0)
            )
            st.caption(f"EWMA: {s.get('ewma_latency')}s | Failures: {s.get('failures')} | Timeouts: {s.get('timeouts')}")
            st.markdown("---")
    except Exception as e:
        st.warning(f"Telemetry Error: {e}")

    st.markdown("#### CPU / Memory Summary")
    metrics_df = get_pod_metrics()
    st.caption(f"Metrics Health: **{st.session_state.get('metrics_health', 'Unknown')}**")
    st.caption("Metrics are collected from Kubernetes metrics-server. Temporary delays may occur during pod startup or autoscaling stabilization.")
    if not metrics_df.empty:
        st.dataframe(metrics_df, height=200)

    st.markdown("#### HPA Status Overview")
    st.code(hpa_out)
    
    st.markdown("#### Active Replicas")
    st.code(pods_out)

        

    st.markdown("### Architecture Guide: K8s vs Router")
    st.info("**1. Adaptive Routing (Model Selection)**: The FastAPI Router dynamically selects which *Model Service* to query (e.g. `toxic-baseline`) based on EWMA latency, Hysteresis, and Queue Depth.\n\n**2. Kubernetes Load Balancing (Pod Selection)**: Once the Router mathematically selects the optimal Model, the underlying *Kubernetes Service* abstraction natively distributes that request across the underlying *Pod Replicas* using connection-level Load Balancing.")