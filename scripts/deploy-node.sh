#!/bin/bash
set -e

# Automated Node Deployment Script
# Usage: ./deploy-node.sh <node-name> <node-address> [panel-api-url]

NODE_NAME="$1"
NODE_ADDRESS="$2"
PANEL_API_URL="${3:-http://localhost:8000}"

if [ -z "$NODE_NAME" ] || [ -z "$NODE_ADDRESS" ]; then
    echo "Usage: $0 <node-name> <node-address> [panel-api-url]"
    echo "Example: $0 node1 192.168.1.100 https://panel.example.com"
    exit 1
fi

echo "🚀 Deploying node: $NODE_NAME at $NODE_ADDRESS"
echo "================================================="

# Create node via API (this will auto-generate certificates)
echo "📝 Creating node in panel..."
curl -X POST "$PANEL_API_URL/api/admin/node" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d "{
    \"name\": \"$NODE_NAME\",
    \"address\": \"$NODE_ADDRESS\",
    \"port\": 6001,
    \"api_port\": 62051,
    \"usage_coefficient\": 1.0
  }"

# Export certificates for the node
echo "🔐 Exporting certificates..."
curl -X GET "$PANEL_API_URL/api/admin/certificates/node/$NODE_NAME/export" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Generate docker-compose for the node
echo "🐳 Generating docker-compose for node..."
cat > "docker-compose.node-$NODE_NAME.yml" << COMPOSE_EOF
version: '3.8'

services:
  marzban-node-$NODE_NAME:
    image: marzban/node:latest
    restart: always
    ports:
      - "443:443"
      - "80:80"
      - "6001:6001"
    volumes:
      - ./automated-certs/nodes/$NODE_NAME:/etc/marzban-node/certs:ro
    environment:
      - SERVICE_PORT=6001
      - SERVICE_PROTOCOL=rest
      - SSL_CERT_FILE=/etc/marzban-node/certs/server.crt
      - SSL_KEY_FILE=/etc/marzban-node/certs/server.key
      - SSL_CLIENT_CERT_FILE=/etc/marzban-node/certs/ca.crt
    networks:
      - marzban_network

networks:
  marzban_network:
    external: true
COMPOSE_EOF

echo "✅ Node deployment completed!"
echo "📋 Next steps:"
echo "   1. Copy automated-certs/nodes/$NODE_NAME/ to your node server"
echo "   2. Run: docker-compose -f docker-compose.node-$NODE_NAME.yml up -d"
echo "   3. The node will automatically connect to the panel"
