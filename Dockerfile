ARG PYTHON_VERSION=3.12

# Stage 1: Build frontend assets for production
FROM node:20-slim AS node-build
WORKDIR /app

# Copy package files
COPY app/dashboard/package*.json ./

# Install dependencies including @types/node
RUN npm install && \
    npm install --save-dev @types/node

# Copy source code
COPY app/dashboard/ ./

# Create environment files with correct API base URL
RUN echo "VITE_API_BASE_URL=/api\nVITE_BASE_API=/api\nUVICORN_PORT=8000\nXRAY_SUBSCRIPTION_PATH=sub" > .env && \
    echo "VITE_APP_TYPE=admin\nVITE_BASE_API=/api/admin" > .env.admin && \
    echo "VITE_APP_TYPE=portal\nVITE_BASE_API=/api/portal" > .env.portal

# Build admin panel with error checking
RUN npm run build:admin || (echo "Admin panel build failed" && exit 1)

# Build client portal with error checking
RUN npm run build:portal || (echo "Portal build failed" && exit 1)

# Rename HTML files to index.html
RUN mv dist_admin/admin.html dist_admin/index.html && \
    mv dist_portal/portal.html dist_portal/index.html

# Verify builds exist
RUN ls -la dist_admin/ && \
    ls -la dist_portal/ && \
    test -f dist_admin/index.html && \
    test -f dist_portal/index.html

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

# Copy production-built frontend assets from the node-build stage
COPY --from=node-build /app/dist_admin /code/app/dashboard/dist_admin
COPY --from=node-build /app/dist_portal /code/app/dashboard/dist_portal

# Verify frontend assets exist in final image
RUN ls -la /code/app/dashboard/dist_admin/ && \
    ls -la /code/app/dashboard/dist_portal/ && \
    test -f /code/app/dashboard/dist_admin/index.html && \
    test -f /code/app/dashboard/dist_portal/index.html

# Copy all application source code (Python files, config, etc.)
COPY . /code

# Setup marzban-cli
RUN ln -s /code/marzban-cli.py /usr/bin/marzban-cli \
    && chmod +x /usr/bin/marzban-cli \
    && marzban-cli completion install --shell bash

# Add the entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]