FROM python:3.13.5-alpine3.22
RUN addgroup -g 1000 forgeops && adduser -D -u 1000 -G forgeops forgeops
COPY tools/sandbox_security/e3_probe.py /opt/forgeops/e3_probe.py
USER 1000:1000
ENTRYPOINT ["python3", "/opt/forgeops/e3_probe.py"]
