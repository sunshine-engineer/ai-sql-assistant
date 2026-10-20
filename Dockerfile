FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    ASSISTANT_DEPLOYMENT=reviewer ASSISTANT_TELEMETRY_PATH=/app/.telemetry/requests.db
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 reviewer
COPY --chown=reviewer:reviewer assistant ./assistant
COPY --chown=reviewer:reviewer evaluation/retail_v1.json evaluation/heldout_v1.json ./evaluation/
COPY --chown=reviewer:reviewer evaluation/reports ./evaluation/reports
COPY --chown=reviewer:reviewer app.py student.db ./
RUN mkdir -p data .telemetry && chown -R reviewer:reviewer data .telemetry
USER reviewer
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health',timeout=2)"
CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.headless=true", "--browser.gatherUsageStats=false"]
