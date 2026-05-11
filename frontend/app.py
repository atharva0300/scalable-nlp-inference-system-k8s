import streamlit as st
import asyncio
import httpx
import pandas as pd
import time
import json
import subprocess

st.set_page_config(page_title="Latency-Aware Load Balancer", layout="wide")

BASE_URL = "http://127.0.0.1:8000"

st.title("Distributed Toxicity Inference Platform")
st.subheader("Adaptive Latency-Aware Routing Architecture")

def kubectl(cmd):
    try:
        return subprocess.check_output(cmd, shell=True).decode()
    except Exception as e:
        return f"Error: {str(e)}"

async def send_one(text, model_name):
    transport = httpx.AsyncHTTPTransport(retries=1)
    async with httpx.AsyncClient(transport=transport, limits=httpx.Limits(keepalive_expiry=0, max_keepalive_connections=0)) as client:
        try:
            start = time.time()
            r = await client.post(f"{BASE_URL}/toxicity", json={"text": text, "model": model_name}, timeout=30.0, headers={"Connection": "close"})
            res = r.json()
            latency = round(time.time() - start, 3)
            if "error" in res:
                return {"replica_id": "error", "final_model": "error", "error": res["error"], "latency": latency}
            
            return {
                "routing": res.get("routing"),
                "routing_reason": res.get("routing_reason"),
                "routing_score": res.get("routing_score", 0),
                "active_requests": res.get("active_requests_on_model", 0),
                "final_model": res.get("final_model", model_name),
                "toxicity": res.get("toxicity"),
                "confidence": round(res.get("confidence", 0), 4),
                "replica_path": json.dumps(res.get("replica_path", [])),
                "latency": latency
            }
        except Exception as e:
            return {"replica_id": "error", "final_model": "error", "error": str(e), "latency": 0}

async def send_batch(text, model_name, count):
    tasks = [send_one(text, model_name) for _ in range(count)]
    return await asyncio.gather(*tasks)

# --- Sidebar ---
st.sidebar.header("Input")
text_input = st.sidebar.text_area("Enter Text", "I completely disagree with everything you just said!")
selected_model = st.sidebar.selectbox("Routing Strategy", ["adaptive", "baseline", "bert", "roberta"])

st.sidebar.markdown("---")
st.sidebar.header("Execution")
run_single_btn = st.sidebar.button("Run Single Analysis")
concurrency = st.sidebar.slider("Concurrent Requests", 1, 1000, 100)
run_btn = st.sidebar.button("Run Batch Load Test")

# --- Layout ---
col1, col2 = st.columns([2, 1])

with col1:
    if run_single_btn:
        st.markdown("### Single Request Result")
        with st.spinner(f"Analyzing..."):
            try:
                try:
                    res = asyncio.run(send_one(text_input, selected_model))
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    res = loop.run_until_complete(send_one(text_input, selected_model))
                
                if "error" in res and res["error"]:
                    st.error(f"Error: {res['error']}")
                else:
                    st.success(f"Routed to: {res.get('final_model')} | Latency: {res.get('latency')}s | Score: {res.get('routing_score')}")
                    st.json(res)
            except Exception as e:
                st.error(f"Failed: {e}")

    if run_btn:
        st.markdown("### Batch Load Test Metrics")
        with st.spinner(f"Sending {concurrency} requests using {selected_model}..."):
            try:
                try:
                    results = asyncio.run(send_batch(text_input, selected_model, concurrency))
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    results = loop.run_until_complete(send_batch(text_input, selected_model, concurrency))
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                results = loop.run_until_complete(send_batch(text_input, selected_model, concurrency))

        success = [r for r in results if "error" not in r]
        fail = [r for r in results if "error" in r]

        if success:
            avg_latency = round(sum(r["latency"] for r in success) / len(success), 3)
            throughput = round(len(success) / max(sum(r["latency"] for r in success), 0.001), 2)
            
            models_hit = {}
            pods_hit = {}
            for r in success:
                mod = r.get("final_model")
                models_hit[mod] = models_hit.get(mod, 0) + 1
                
                path_str = r.get("replica_path")
                if path_str:
                    path = json.loads(path_str)
                    if path:
                        pod = path[-1]
                        pods_hit[pod] = pods_hit.get(pod, 0) + 1
        else:
            avg_latency = 0
            throughput = 0
            models_hit = {}
            pods_hit = {}

        st.success(f"Completed {len(success)} successful requests, {len(fail)} failed.")

        m1, m2, m3 = st.columns(3)
        m1.metric("Avg Latency (sec)", avg_latency)
        m2.metric("Failures/Timeouts", len(fail))
        m3.metric("Throughput (req/s)", throughput)

        if success:
            df = pd.DataFrame(success)
            st.markdown("#### 🚀 Latency-Aware Distribution (Model Level)")
            st.bar_chart(pd.DataFrame.from_dict(models_hit, orient='index', columns=['Requests']))
            
            st.markdown("#### 🎯 Kubernetes Real Load Balancing (Pod Level)")
            st.bar_chart(pd.DataFrame.from_dict(pods_hit, orient='index', columns=['Requests']))

            st.markdown("#### ⚡ Latency Timeline")
            st.line_chart(df["latency"])

            st.markdown("#### 🔄 In-Flight Active Requests Queue")
            st.line_chart(df["active_requests"])

            with st.expander("View Raw Responses Table"):
                st.dataframe(df)

with col2:
    st.markdown("### 📊 Router Active Telemetry")
    if st.button("Refresh Telemetry"):
        pass
        
    try:
        r = httpx.get(f"{BASE_URL}/routing-stats", timeout=2.0)
        stats = r.json().get("stats", {})
        
        st.markdown("#### 🧠 Real-Time Routing Scores")
        for m, s in stats.items():
            col_a, col_b = st.columns(2)
            col_a.metric(f"Score ({m})", s.get("routing_score", 0))
            col_b.metric(f"Active Queue", s.get("active_requests", 0))
            st.caption(f"Avg Latency: {s.get('avg_latency')}s | Failures: {s.get('failures')} | Timeouts: {s.get('timeouts')}")
            st.progress(min(s.get("routing_score", 0) / 10.0, 1.0))
            st.markdown("---")
            
    except:
        st.warning("Router unreachable. Start port-forwarding!")
        
    st.markdown("### ⚙️ Kubernetes Control Plane")
    st.markdown("#### Horizontal Pod Autoscalers (HPA)")
    st.code(kubectl("kubectl get hpa"))
    
    st.markdown("#### Active Service Pods")
    st.code(kubectl("kubectl get pods -l 'app in (fastapi-router, toxic-baseline, toxic-bert, toxic-roberta)'"))
    
    st.markdown("### 📚 Architecture Guide")
    st.info("**Latency-Aware Scheduling**: The Router tracks real-time `queue depth` and `rolling latency` for each model service. It dynamically calculates a **Routing Score** and routes new requests to the least congested service! If a service timeouts, a circuit-breaker opens automatically.")
    
    st.markdown("**Grafana Access**")
    st.write("Since we use a lightweight Loki setup without a backend database, there are no pre-built dashboards. To view logs:")
    st.write("1. Open `http://localhost:3000`")
    st.write("2. Click **Explore** (Compass Icon on left bar).")
    st.write("3. Select **Loki** from the top-left dropdown.")
    st.write("4. Enter `{app=\"fastapi-router\"}` and hit 'Run query'.")