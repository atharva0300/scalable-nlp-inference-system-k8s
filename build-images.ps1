& minikube -p minikube docker-env --shell powershell | Invoke-Expression
cd d:\scalable-nlp-inference-system-k8s\gateway\fastapi
docker build -t my-fastapi-router:latest .
cd d:\scalable-nlp-inference-system-k8s
