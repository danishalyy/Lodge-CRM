FROM python:3.12-slim
WORKDIR /app
COPY requirements.lock.txt .
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi \
 && pip install --no-cache-dir -r requirements.lock.txt
COPY . .
RUN chmod -R a+rX /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 10001:10001
RUN python -c "import app.main; print('API import smoke test passed')"
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
