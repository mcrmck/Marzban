#!/bin/bash
set -e

echo "Entrypoint: Applying database migrations..."
alembic upgrade head
echo "Entrypoint: Database migrations applied."

if [ -n "$SUDO_USERNAME" ] && [ -n "$SUDO_PASSWORD" ]; then
    echo "Entrypoint: Importing sudo admin '$SUDO_USERNAME' from environment variables into the database..."
    if marzban-cli admin import-from-env --yes; then
        echo "Entrypoint: Sudo admin '$SUDO_USERNAME' imported/updated successfully from .env variables."
    else
        echo "Entrypoint: CRITICAL - 'marzban-cli admin import-from-env' for '$SUDO_USERNAME' failed. The application might not authenticate correctly."

    fi
else
    echo "Entrypoint: SUDO_USERNAME or SUDO_PASSWORD not set in .env. Skipping automatic admin import."
fi

echo "Entrypoint: Starting Marzban application..."
exec python main.py