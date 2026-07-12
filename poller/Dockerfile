FROM python:3.12-slim

RUN groupadd --gid 1001 netwatch && \
    useradd --uid 1001 --gid netwatch --no-create-home netwatch

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY poller.py parsers.py runner.py ./

USER netwatch

CMD ["python", "poller.py"]
