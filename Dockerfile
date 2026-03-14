FROM ubuntu:22.04

USER root

# Install Python and common CLI utilities.
RUN apt-get update && \
	DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
		bash \
		openjdk-17-jre-headless \
		python3 \
		python3-pip \
		python3-venv \
		git \
		curl \
		wget \
		ca-certificates \
		zip \
		unzip \
		vim \
		less \
		jq \
		procps \
		net-tools \
		iputils-ping && \
	rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

WORKDIR /app

COPY . .
