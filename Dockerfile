FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      bind9 bind9-utils dnsutils ansible-core python3-dnspython python3-yaml procps iproute2 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /lab
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
