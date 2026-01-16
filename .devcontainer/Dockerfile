# Development Dockerfile for textual-cmdorc
# For use with VS Code Remote Development

FROM python:3.12-slim AS base

# Prevent apt from prompting for input
ENV DEBIAN_FRONTEND=noninteractive

# Install essential packages
RUN apt-get update && apt-get install -y \
    asciinema \
    curl \
    fonts-noto-color-emoji \
    fonts-noto-mono \
    fonts-symbola \
    gh \
    git \
    locales \
    npm \
    sudo \
    tmux \
    tree \
    vim \
    && rm -rf /var/lib/apt/lists/* \
    && sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen \
    && locale-gen

# Install agg (asciinema gif generator)
RUN AGG_VERSION=1.5.0 && \
    curl -fsSL "https://github.com/asciinema/agg/releases/download/v${AGG_VERSION}/agg-x86_64-unknown-linux-gnu" -o /usr/local/bin/agg && \
    chmod +x /usr/local/bin/agg

# Install Chrome dependencies (required by VHS for rendering)
RUN apt-get update && apt-get install -y \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Install VHS from pre-built .deb package (includes all dependencies)
RUN VHS_VERSION=0.8.0 && \
    curl -fsSL "https://github.com/charmbracelet/vhs/releases/download/v${VHS_VERSION}/vhs_${VHS_VERSION}_amd64.deb" -o /tmp/vhs.deb && \
    apt-get update && \
    apt-get install -y /tmp/vhs.deb && \
    rm /tmp/vhs.deb && \
    rm -rf /var/lib/apt/lists/*

# Install ttyd (required by VHS for terminal recording)
RUN TTYD_VERSION=1.7.7 && \
    curl -fsSL "https://github.com/tsl0922/ttyd/releases/download/${TTYD_VERSION}/ttyd.x86_64" -o /usr/local/bin/ttyd && \
    chmod +x /usr/local/bin/ttyd

# Create the developer user and set up permissions
RUN useradd -s /bin/bash -m developer && \
    usermod -aG sudo developer && \
    echo "developer ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

# Add claude code globally
RUN npm install -g @anthropic-ai/claude-code 

# Install Language Servers (as root, globally available)
# Python LSP
RUN pip install --no-cache-dir pyright

# TypeScript/JavaScript LSP
RUN npm install -g @vtsls/language-server typescript

# Enable LSP tool for claude code
ENV ENABLE_LSP_TOOL=1

# Disable Chrome sandbox for VHS recording in container environment
ENV VHS_NO_SANDBOX=true

# Switch to developer user for remaining operations
USER developer

# Set up Python environment
ENV PATH=/home/developer/.local/bin:$PATH
WORKDIR /workspaces/textual-cmdorc

# Install Python packages
RUN python -m ensurepip --default-pip && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir pdm

RUN pip install --no-cache-dir \
    build \
    GitPython \
    pdm \
    pydantic \
    prepdir \
    pytest \
    ruff \
    twine

RUN git config --global --add safe.directory /workspaces/textual-cmdorc && \
    git config --global --add safe.directory /mounted/dev/textual-cmdorc


RUN echo "alias upc='sudo npm i -g @anthropic-ai/claude-code'" >> /home/developer/.bash_aliases