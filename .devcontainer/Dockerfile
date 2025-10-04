# Dev Container for Mini Foundry Supply Chain
# Based on Python 3.12 with uv package manager

FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

# Install system dependencies
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
    build-essential \
    curl \
    git \
    vim \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install uv - modern Python package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set environment variables for uv
ENV UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Create non-root user (vscode)
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# The base image already has vscode user, so we just ensure proper permissions
RUN mkdir -p /workspace && chown -R ${USERNAME}:${USERNAME} /workspace

# Set working directory
WORKDIR /workspace

# Switch to non-root user
USER ${USERNAME}

# Configure shell prompt
RUN echo 'export PS1="\[\033[01;32m\]\u@devcontainer\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ "' >> ~/.bashrc

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python3 --version || exit 1
