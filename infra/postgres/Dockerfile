FROM postgres:16.13-bookworm
COPY infra/postgres/init-apps.sh /docker-entrypoint-initdb.d/10-apps.sh
# Source through the official entrypoint; avoid executable bind mounts on macOS.
RUN chmod 0644 /docker-entrypoint-initdb.d/10-apps.sh
