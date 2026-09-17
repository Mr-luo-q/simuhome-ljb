FROM python:3.13-slim

WORKDIR /app

COPY simuhome_bridge_project/simuhome.api-requirements.txt /tmp/simuhome.api-requirements.txt

RUN pip install --no-cache-dir -r /tmp/simuhome.api-requirements.txt

CMD ["python", "-m", "src.simulator.api.app"]
