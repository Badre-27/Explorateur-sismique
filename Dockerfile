FROM mongo:7

# Seed data and auto-import script, run once on first start
COPY data/events.json /seed/events.json
COPY mongo/init-import.sh /docker-entrypoint-initdb.d/init-import.sh
RUN sed -i 's/\r$//' /docker-entrypoint-initdb.d/init-import.sh && chmod +x /docker-entrypoint-initdb.d/init-import.sh
RUN chmod +x /docker-entrypoint-initdb.d/init-import.sh

EXPOSE 27017
