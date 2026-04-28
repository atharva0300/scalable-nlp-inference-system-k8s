FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir "numpy<2"
RUN pip install --no-cache-dir -r requirements.txt

ARG MODEL_NAME=distilbert-base-uncased-finetuned-sst-2-english
ENV MODEL_NAME=${MODEL_NAME}

COPY download_model.py .
RUN python download_model.py

COPY main.py .

EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]