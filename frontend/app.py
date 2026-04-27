import streamlit as st
import requests
import time
import pandas as pd
import plotly.express as px
import concurrent.futures
import subprocess

API_URL = "http://localhost:30080/generate"

st.set_page_config(page_title="SPE Load Tester", page_icon="☸️", layout="wide")

st.markdown("""
<style>
    .k8s-box { background-color: #1e1e1e; color: #00ff00; padding: 10px; border-radius: 5px; font-family: monospace; font-size: 0.85em; overflow-x: auto; white-space: pre-wrap; }
    .stChatInput { padding-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = []

st.title("☸️ SPE Load Tester & Kubernetes Analyzer")
st.markdown("Single pane interface for testing adaptive inference routing and analyzing backend Kubernetes auto-scaling behavior.")

# --- CONTROLS ---
with st.expander("🛠️ Load Spike & System Controls", expanded=True):
    col1, col2 = st.columns([3, 1])
    with col1:
        spike_prompt = st.text_input("Batch Prompt:", "Explain systems performance engineering in one word.")
        concurrent_reqs = st.slider("Concurrent Requests:", min_value=1, max_value=100, value=15)
    with col2:
        st.write("")
        st.write("")
        launch_spike = st.button("🔥 Launch Load Spike", use_container_width=True)
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

def get_k8s_stats():
    try:
        pods = subprocess.getoutput("kubectl get pods -o wide")
        hpa = subprocess.getoutput("kubectl get hpa")
        top = subprocess.getoutput("kubectl top pods --request-timeout=3s 2>/dev/null || echo 'Metrics server not ready or no data'")
        return f"--- PODS STATUS ---\n{pods}\n\n--- HORIZONTAL POD AUTOSCALERS ---\n{hpa}\n\n--- POD RESOURCE USAGE (CPU/Memory) ---\n{top}"
    except Exception as e:
        return f"Error fetching k8s stats: {str(e)}"

# --- RENDER CHAT HISTORY ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        
        if "dataframe" in msg:
            st.dataframe(msg["dataframe"], use_container_width=True)
            
        if "k8s_stats" in msg:
            st.markdown(f"<div class='k8s-box'>{msg['k8s_stats']}</div>", unsafe_allow_html=True)
            
        if "charts" in msg:
            df = msg["charts"]
            c1, c2 = st.columns(2)
            with c1:
                fig_pie = px.pie(df, names="model", title="Model Routing Distribution", hole=0.4)
                st.plotly_chart(fig_pie, use_container_width=True)
            with c2:
                fig_line = px.line(df, y="latency", color="model", markers=True, title="Latency over Time")
                st.plotly_chart(fig_line, use_container_width=True)

# --- BATCH LOGIC ---
if launch_spike:
    with st.chat_message("user"):
        st.write(f"**[BATCH]** Running {concurrent_reqs} requests with prompt: '{spike_prompt}'")
    st.session_state.messages.append({"role": "user", "content": f"**[BATCH]** Running {concurrent_reqs} requests with prompt: '{spike_prompt}'"})
    
    with st.chat_message("assistant"):
        st.write("⏳ Pumping traffic to the gateway...")
        
        def send_request(idx):
            start = time.time()
            try:
                res = requests.post(API_URL, json={"prompt": spike_prompt}, timeout=300)
                res.raise_for_status()
                data = res.json()
                return {"id": idx+1, "model": data.get("model_used"), "latency": data.get("latency_sec"), "response": data.get("response", ""), "success": True}
            except Exception as e:
                return {"id": idx+1, "model": "error", "latency": time.time() - start, "response": f"Error: {str(e)}", "success": False}

        results = []
        with st.spinner(f"Processing {concurrent_reqs} requests..."):
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_reqs) as executor:
                results = list(executor.map(send_request, range(concurrent_reqs)))
        
        df = pd.DataFrame(results)
        
        # Gather k8s stats right after load spike
        k8s_out = get_k8s_stats()
        
        st.success("Batch complete!")
        st.markdown("### Responses & Routing Table")
        st.dataframe(df, use_container_width=True)
        
        st.markdown("### Backend Kubernetes Telemetry")
        st.markdown(f"<div class='k8s-box'>{k8s_out}</div>", unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        with c1:
            fig_pie = px.pie(df, names="model", title="Model Routing Distribution", hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)
        with c2:
            fig_line = px.line(df, y="latency", color="model", markers=True, title="Latency over Time")
            st.plotly_chart(fig_line, use_container_width=True)
            
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"Completed batch of {concurrent_reqs} requests.",
            "dataframe": df,
            "charts": df,
            "k8s_stats": k8s_out
        })

# --- SINGLE REQUEST LOGIC ---
if prompt := st.chat_input("Send a single request..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("⏳ *Routing request...*")
        
        try:
            start_t = time.time()
            res = requests.post(API_URL, json={"prompt": prompt}, timeout=300)
            res.raise_for_status()
            data = res.json()
            
            model = data.get("model_used", "unknown")
            latency = data.get("latency_sec", 0)
            resp = data.get("response", "")
            
            k8s_out = get_k8s_stats()
            
            output = f"**Routed to:** `{model}` (Latency: {latency}s)\n\n**Response:**\n{resp}"
            message_placeholder.markdown(output)
            st.markdown("### Backend Kubernetes Telemetry")
            st.markdown(f"<div class='k8s-box'>{k8s_out}</div>", unsafe_allow_html=True)
            
            st.session_state.messages.append({
                "role": "assistant",
                "content": output,
                "k8s_stats": k8s_out
            })
            
        except Exception as e:
            message_placeholder.error(f"Failed: {str(e)}")
            st.session_state.messages.append({"role": "assistant", "content": f"**Error:** {str(e)}"})
