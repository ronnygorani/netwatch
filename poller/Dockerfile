FROM python:3.12-slim

RUN groupadd --gid 1001 netauto && \
    useradd --uid 1001 --gid netauto --no-create-home netauto

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY poller.py .

USER netauto

CMD ["python", "poller.py"]
