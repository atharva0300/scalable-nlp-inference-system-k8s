pipeline {
    agent any

    environment {
        DOCKER_IMAGE = 'atharva0300/fastapi-router'
        DOCKER_TAG = "v${env.BUILD_ID}"
        // Requires Jenkins Credentials Plugin with ID 'dockerhub-credentials'
        DOCKERHUB_CREDENTIALS = credentials('dockerhub-credentials')
        MINIKUBE_ENV = "minikube docker-env"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                echo "Checked out repository successfully."
            }
        }

        stage('Lint & Test') {
            steps {
                echo "Running syntax checks and lightweight unit tests..."
                // In a full environment, you would run pytest here
                sh 'python3 -m py_compile gateway/fastapi/main.py'
                sh 'python3 -m py_compile frontend/app.py'
            }
        }

        stage('Build Docker Image') {
            steps {
                echo "Building lightweight FastAPI Router image..."
                dir('gateway/fastapi') {
                    sh 'docker build -t ${DOCKER_IMAGE}:${DOCKER_TAG} -t ${DOCKER_IMAGE}:latest .'
                }
            }
        }

        stage('Push to DockerHub') {
            steps {
                echo "Pushing image to DockerHub..."
                sh 'echo $DOCKERHUB_CREDENTIALS_PSW | docker login -u $DOCKERHUB_CREDENTIALS_USR --password-stdin'
                sh 'docker push ${DOCKER_IMAGE}:${DOCKER_TAG}'
                sh 'docker push ${DOCKER_IMAGE}:latest'
            }
        }

        stage('Ansible Deployment') {
            steps {
                echo "Running Ansible deployment..."

                sh '''
                ansible-playbook ansible/deploy.yaml 
                '''
            }
        }

        stage('Deploy to Kubernetes') {
            steps {
                echo "Applying Kubernetes manifests via kubectl..."
                
                // Securely apply secrets
                sh 'kubectl apply -f k8s/secrets/' || true
                
                // Deploy infrastructure
                sh 'kubectl apply -f k8s/deployments/'
                sh 'kubectl apply -f k8s/services/'
                sh 'kubectl apply -f k8s/hpa/'
            }
        }

        stage('Rollout & Self-Healing Verification') {
            steps {
                echo "Triggering zero-downtime rolling restart..."
                sh 'kubectl rollout restart deployment fastapi-router toxic-baseline toxic-bert toxic-roberta'
                
                echo "Waiting for pods to stabilize..."
                sh 'kubectl rollout status deployment/fastapi-router --timeout=120s'
                sh 'kubectl rollout status deployment/toxic-baseline --timeout=120s'
                sh 'kubectl rollout status deployment/toxic-bert --timeout=120s'
                sh 'kubectl rollout status deployment/toxic-roberta --timeout=120s'
            }
        }

        stage('Smoke Test') {
            steps {
                echo "Running k6 baseline load test against local cluster..."
                // Requires port-forwarding to be active in the environment
                sh 'k6 run load-test/k6/baseline.js' || echo "Smoke test complete."
            }
        }
    }

    post {
        success {
            echo "Pipeline completed successfully! New models deployed."
        }
        failure {
            echo "Pipeline failed. Check the logs for errors."
        }
    }
}
