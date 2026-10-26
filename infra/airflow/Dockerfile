FROM apache/airflow:3.1.7-python3.11
USER root
RUN mkdir -p /opt/airflow/state && chown airflow:root /opt/airflow/state
USER airflow
COPY --chown=airflow:root infra/airflow/start.py /opt/airflow/start.py
COPY --chown=airflow:root infra/airflow/health.py /opt/airflow/health.py
CMD ["python", "/opt/airflow/start.py"]
