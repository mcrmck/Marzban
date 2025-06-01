#!/bin/bash
# Ensure this script is in the Marzban/ directory and run from there.

CERT_DIR_NODE="./node1-certs"
CERT_DIR_PANEL="./panel-certs"
CA_PEM_PANEL="./MyMarzbanCA.pem" # This will be the CA cert used by the panel to verify nodes

mkdir -p "$CERT_DIR_NODE"
mkdir -p "$CERT_DIR_PANEL"

# Generate CA certificate (This CA will sign both node server certs and panel client certs)
openssl genrsa -out "$CERT_DIR_NODE/ca.key" 2048
openssl req -new -x509 -days 3650 -key "$CERT_DIR_NODE/ca.key" -out "$CERT_DIR_NODE/ca.crt" -subj "/CN=Marzban Internal CA"
echo "CA Certificate created: $CERT_DIR_NODE/ca.crt"

# Generate server certificate for marzban-node-1 (signed by Marzban Internal CA)
openssl genrsa -out "$CERT_DIR_NODE/server.key" 2048
openssl req -new -key "$CERT_DIR_NODE/server.key" -out "$CERT_DIR_NODE/server.csr" -subj "/CN=marzban-node-1"
openssl x509 -req -days 3650 -in "$CERT_DIR_NODE/server.csr" -CA "$CERT_DIR_NODE/ca.crt" -CAkey "$CERT_DIR_NODE/ca.key" -CAcreateserial -out "$CERT_DIR_NODE/server.crt"
echo "Node server certificate created: $CERT_DIR_NODE/server.crt"

# Generate client certificate for marzban-panel (signed by Marzban Internal CA)
openssl genrsa -out "$CERT_DIR_PANEL/client.key" 2048
openssl req -new -key "$CERT_DIR_PANEL/client.key" -out "$CERT_DIR_PANEL/client.csr" -subj "/CN=marzban-panel"
openssl x509 -req -days 3650 -in "$CERT_DIR_PANEL/client.csr" -CA "$CERT_DIR_NODE/ca.crt" -CAkey "$CERT_DIR_NODE/ca.key" -CAcreateserial -out "$CERT_DIR_PANEL/client.crt"
echo "Panel client certificate created: $CERT_DIR_PANEL/client.crt"

# Copy the CA certificate for the panel to use for verifying nodes
cp "$CERT_DIR_NODE/ca.crt" "$CA_PEM_PANEL"
echo "CA certificate for panel verification created: $CA_PEM_PANEL"

# Copy CA cert to panel-certs as well (optional, for consistency if panel needs its own CA copy)
cp "$CERT_DIR_NODE/ca.crt" "$CERT_DIR_PANEL/ca.crt"

# Create .srl file for CA if it doesn't exist (needed for -CAcreateserial)
if [ ! -f "$CERT_DIR_NODE/ca.srl" ]; then
  openssl rand -hex 16 > "$CERT_DIR_NODE/ca.srl" # Or use echo "01" > "$CERT_DIR_NODE/ca.srl"
  echo "Created $CERT_DIR_NODE/ca.srl"
fi

chmod 644 "$CERT_DIR_NODE"/*.crt "$CERT_DIR_PANEL"/*.crt "$CA_PEM_PANEL"
chmod 600 "$CERT_DIR_NODE"/*.key "$CERT_DIR_PANEL"/*.key

echo "Certificates generated successfully!"