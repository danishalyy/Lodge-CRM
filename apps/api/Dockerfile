FROM python:3.12-slim
WORKDIR /app
COPY requirements.lock.txt .
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi \
 && pip install --no-cache-dir -r requirements.lock.txt
COPY . .
RUN python -c "import app.main; print('API import smoke test passed')"
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
