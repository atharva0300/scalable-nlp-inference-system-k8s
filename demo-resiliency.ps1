Write-Host "======================================================"
Write-Host " Kubernetes Self-Healing & Adaptive Resiliency Demo "
Write-Host "======================================================"
Write-Host ""
Write-Host "This script will abruptly kill a running model pod while the router is operating."
Write-Host "Watch how Kubernetes instantly provisions a new replacement pod, while the Adaptive Router"
Write-Host "detects the timeout, opens the circuit breaker, and redirects traffic to surviving models!"
Write-Host ""

$pod = (kubectl get pods -l app=toxic-baseline -o jsonpath="{.items[0].metadata.name}")

if (-not $pod) {
    Write-Host "No toxic-baseline pod found. Please ensure the cluster is running."
    exit
}

Write-Host "1. Target Acquired: $pod"
Write-Host "2. Simulating fatal node/container crash in 3 seconds..."
Start-Sleep -Seconds 3

Write-Host "3. Executing KILL command!"
kubectl delete pod $pod --grace-period=0 --force

Write-Host ""
Write-Host "Pod destroyed. Watching Kubernetes Self-Healing response..."
Write-Host "You should immediately see a new pod transitioning to 'ContainerCreating'."
Write-Host ""

# Watch the pods for 15 seconds to demonstrate recovery
$endTime = (Get-Date).AddSeconds(20)
while ((Get-Date) -lt $endTime) {
    kubectl get pods -l app=toxic-baseline
    Start-Sleep -Seconds 2
    Write-Host "---------------------------"
}

Write-Host "Demo Complete."
Write-Host "Notice how the Adaptive Router (via Streamlit) successfully rerouted requests"
Write-Host "while the new Pod booted, demonstrating Zero-Downtime Distributed Inference!"
