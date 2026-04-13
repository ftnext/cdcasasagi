#!/bin/bash

if [ "$CLAUDE_CODE_REMOTE" != "true" ]; then
    exit 0
fi

PROJECT_DIR=$(dirname $(dirname $(dirname $0)))
echo "${PROJECT_DIR}"
echo "Setting up Claude Code on the Web environment..."

echo "Install gh..."
bun x gh-setup-hooks

if [ ! -d "${PROJECT_DIR}/.venv" ]; then
    echo "Create Python virtual environment..."
    uv sync --group dev
fi

echo "Setup complete!"
