FROM postgres:16

# Installiert die offizielle pg_cron Erweiterung für PostgreSQL 16
RUN apt-get update && \
    apt-get install -y postgresql-16-cron && \
    rm -rf /var/lib/apt/lists/*