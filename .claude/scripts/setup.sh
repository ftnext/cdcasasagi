#!/bin/bash

if [ "$CLAUDE_CODE_REMOTE" != "true" ]; then
    exit 0
fi

PROJECT_DIR=$(dirname $(dirname $(dirname $0)))
echo "${PROJECT_DIR}"
echo "Setting up Claude Code on the Web environment..."

echo "Install gh..."
bun x gh-setup-hooks

GAUGE_VERSION=1.6.28
if ! command -v gauge &> /dev/null || [ "$(gauge --version | head -n 1 | awk '{print $NF}')" != "${GAUGE_VERSION}" ]; then
    echo "Install gauge ${GAUGE_VERSION}..."
    mkdir -p "${HOME}/.local/bin"
    curl -SsL -o /tmp/gauge.zip "https://github.com/getgauge/gauge/releases/download/v${GAUGE_VERSION}/gauge-${GAUGE_VERSION}-linux.x86_64.zip"
    unzip -o /tmp/gauge.zip -d "${HOME}/.local/bin"
    rm /tmp/gauge.zip
    export PATH="${HOME}/.local/bin:${PATH}"
fi

echo "Install gauge plugins..."
gauge install python
gauge install html-report
gauge install screenshot

if [ ! -d "${PROJECT_DIR}/.venv" ]; then
    echo "Create Python virtual environment..."
    uv sync --group dev --frozen
fi

echo "Setup complete!"
