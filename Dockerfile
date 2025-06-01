ARG PYTHON_VERSION=3.12

# Stage 1: Build frontend assets for production (THIS STAGE IS ESSENTIAL)
FROM node:20-slim AS node-build
WORKDIR /app
COPY app/dashboard/package*.json ./
RUN npm install
COPY app/dashboard/ ./
# This creates the production build in /app/build
RUN npm run build -- --outDir build --assetsDir statics

# Stage 2: Build Python environment and install XRay
FROM python:${PYTHON_VERSION}-slim AS python-build-env
ENV PYTHONUNBUFFERED=1
WORKDIR /code
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl unzip gcc python3-dev libpq-dev \
    && curl -L https://github.com/Gozargah/Marzban-scripts/raw/master/install_latest_xray.sh | bash \
    && rm -rf /var/lib/apt/lists/*
COPY ./requirements.txt /code/
RUN python3 -m pip install --upgrade pip setuptools \
    && pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Stage 3: Final application image
FROM python:${PYTHON_VERSION}-slim
ENV PYTHONUNBUFFERED=1
ENV PYTHON_LIB_PATH=/usr/local/lib/python${PYTHON_VERSION%.*}/site-packages
WORKDIR /code

# Copy pre-built Python environment and ensure all binaries are available
COPY --from=python-build-env $PYTHON_LIB_PATH $PYTHON_LIB_PATH
COPY --from=python-build-env /usr/local/bin/ /usr/local/bin/
COPY --from=python-build-env /usr/local/bin/xray /usr/local/bin/xray
COPY --from=python-build-env /usr/local/share/xray /usr/local/share/xray

# Copy production-built dashboard assets from the node-build stage
# This is critical for mount_static_files() to work.
COPY --from=node-build /app/build /code/app/dashboard/build

# Copy all application source code (Python files, config, etc.)
COPY . /code

# Node.js, npm, and dashboard dev dependencies (npm install in final stage) are NO LONGER NEEDED
# as we are always serving the pre-built assets.

# Setup marzban-cli
RUN ln -s /code/marzban-cli.py /usr/bin/marzban-cli \
    && chmod +x /usr/bin/marzban-cli \
    && marzban-cli completion install --shell bash

# Add the entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]