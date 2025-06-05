#!/bin/bash
set -e

# Automated Certificate Management Setup for Marzban
# This script sets up automated certificate generation and deployment for production

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CERTS_DIR="$PROJECT_ROOT/automated-certs"

echo "🔐 Setting up automated certificate management for Marzban"
echo "================================================="

# Create certificates directory structure
echo "📁 Creating certificate directories..."
mkdir -p "$CERTS_DIR"/{ca,panel,nodes}
mkdir -p "$PROJECT_ROOT/docker-certs"

# Set proper permissions
chmod 700 "$CERTS_DIR"
chmod 600 "$CERTS_DIR"/{ca,panel,nodes} 2>/dev/null || true

echo "✅ Certificate directories created"

# Create automated docker-compose.yml for production with certificate management
echo "🐳 Creating production docker-compose configuration..."

cat > "$PROJECT_ROOT/docker-compose.automated.yml" << 'EOF'
version: '3.8'

services:
  marzban-panel:
    build:
      context: .
      dockerfile: Dockerfile.backend
    restart: always
    env_file: .env
    ports:
      - "8000:8000"
    volumes:
      - marzban_data:/var/lib/marzban
      - ./automated-certs/ca:/etc/marzban/ca:ro                    # CA certificates
      - ./automated-certs/panel:/etc/marzban/panel-certs:ro        # Panel client certificates
      - ./xray_config/config.json:/etc/marzban/xray_config/config.json:ro
    environment:
      - UVICORN_SSL_CA_TYPE=private
      - UVICORN_HOST=0.0.0.0
      - UVICORN_PORT=8000
      - DATABASE_URL=sqlite:////var/lib/marzban/db.sqlite3
      - AUTOMATED_CERTIFICATES=true
    networks:
      - marzban_network
    depends_on:
      - marzban-db-migration

  marzban-db-migration:
    build:
      context: .
      dockerfile: Dockerfile.backend
    env_file: .env
    volumes:
      - marzban_data:/var/lib/marzban
    environment:
      - DATABASE_URL=sqlite:////var/lib/marzban/db.sqlite3
    command: ["alembic", "upgrade", "head"]
    networks:
      - marzban_network

  # Certificate management service
  marzban-cert-manager:
    build:
      context: .
      dockerfile: Dockerfile.backend
    env_file: .env
    volumes:
      - marzban_data:/var/lib/marzban
      - ./automated-certs:/app/automated-certs
      - ./scripts:/app/scripts
    environment:
      - DATABASE_URL=sqlite:////var/lib/marzban/db.sqlite3
    command: ["python", "/app/scripts/certificate-daemon.py"]
    networks:
      - marzban_network
    depends_on:
      - marzban-db-migration

networks:
  marzban_network:
    driver: bridge

volumes:
  marzban_data:
EOF

echo "✅ Production docker-compose configuration created"

# Create certificate management daemon
echo "🤖 Creating certificate management daemon..."

cat > "$PROJECT_ROOT/scripts/certificate-daemon.py" << 'EOF'
#!/usr/bin/env python3
"""
Automated Certificate Management Daemon for Marzban

This daemon runs as a background service to:
- Monitor certificate expiration
- Automatically rotate certificates
- Export certificates for Docker deployment
- Handle certificate distribution
"""

import os
import sys
import time
import logging
import schedule
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.db import get_db, init_db
from app.services.certificate_manager import CertificateManager
from app.db.crud import get_expiring_certificates, get_nodes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/marzban-cert-daemon.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('certificate-daemon')

CERT_EXPORT_DIR = "/app/automated-certs"

class CertificateDaemon:
    """Certificate management daemon"""
    
    def __init__(self):
        self.cert_manager = None
        self.db = None
        
    def initialize(self):
        """Initialize database connection and certificate manager"""
        try:
            init_db()
            self.db = next(get_db())
            self.cert_manager = CertificateManager(self.db)
            logger.info("Certificate daemon initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize certificate daemon: {e}")
            raise
    
    def check_and_rotate_certificates(self):
        """Check for expiring certificates and rotate them"""
        try:
            logger.info("Checking for expiring certificates...")
            
            # Check for certificates expiring in 30 days
            expiring = get_expiring_certificates(self.db, days_ahead=30)
            
            # Rotate CA if expiring
            if expiring["ca"]:
                logger.warning("CA certificate is expiring, regenerating...")
                self.cert_manager.get_or_create_ca()  # This will create new CA if expired
                
                # Regenerate all node certificates after CA change
                self._regenerate_all_node_certificates()
            
            # Rotate individual node certificates
            for node_cert in expiring["nodes"]:
                logger.warning(f"Node certificate for {node_cert.node_name} is expiring, rotating...")
                self.cert_manager.rotate_certificates(node_cert.node_name)
                self._export_node_certificates(node_cert.node_name)
            
            if not expiring["ca"] and not expiring["nodes"]:
                logger.info("All certificates are healthy")
                
        except Exception as e:
            logger.error(f"Error during certificate check and rotation: {e}")
    
    def export_all_certificates(self):
        """Export all certificates for Docker deployment"""
        try:
            logger.info("Exporting all certificates for Docker deployment...")
            
            # Export CA certificate
            self._export_ca_certificate()
            
            # Export all node certificates
            nodes = get_nodes(self.db)
            for node in nodes:
                self._export_node_certificates(node.name)
                
            logger.info("All certificates exported successfully")
            
        except Exception as e:
            logger.error(f"Error during certificate export: {e}")
    
    def _export_ca_certificate(self):
        """Export CA certificate to shared directory"""
        try:
            ca_cert = self.cert_manager.get_or_create_ca()
            
            ca_dir = Path(CERT_EXPORT_DIR) / "ca"
            ca_dir.mkdir(parents=True, exist_ok=True)
            
            # Export CA certificate
            (ca_dir / "ca.crt").write_text(ca_cert.certificate_pem)
            
            # Set proper permissions
            (ca_dir / "ca.crt").chmod(0o644)
            
            logger.info("CA certificate exported")
            
        except Exception as e:
            logger.error(f"Error exporting CA certificate: {e}")
    
    def _export_node_certificates(self, node_name: str):
        """Export certificates for a specific node"""
        try:
            node_certs = self.cert_manager.get_node_certificates(node_name)
            if not node_certs:
                logger.warning(f"No certificates found for node: {node_name}")
                return
            
            # Create node-specific directory
            node_dir = Path(CERT_EXPORT_DIR) / "nodes" / node_name
            node_dir.mkdir(parents=True, exist_ok=True)
            
            # Export server certificates (for node)
            (node_dir / "server.crt").write_text(node_certs.server_cert.certificate_pem)
            (node_dir / "server.key").write_text(node_certs.server_cert.private_key_pem)
            (node_dir / "ca.crt").write_text(node_certs.ca_cert.certificate_pem)
            
            # Set proper permissions
            (node_dir / "server.crt").chmod(0o644)
            (node_dir / "server.key").chmod(0o600)
            (node_dir / "ca.crt").chmod(0o644)
            
            # Export panel client certificates
            panel_dir = Path(CERT_EXPORT_DIR) / "panel"
            panel_dir.mkdir(parents=True, exist_ok=True)
            
            (panel_dir / f"{node_name}-client.crt").write_text(node_certs.panel_client_cert.certificate_pem)
            (panel_dir / f"{node_name}-client.key").write_text(node_certs.panel_client_cert.private_key_pem)
            
            # Set proper permissions
            (panel_dir / f"{node_name}-client.crt").chmod(0o644)
            (panel_dir / f"{node_name}-client.key").chmod(0o600)
            
            logger.info(f"Certificates exported for node: {node_name}")
            
        except Exception as e:
            logger.error(f"Error exporting certificates for node {node_name}: {e}")
    
    def _regenerate_all_node_certificates(self):
        """Regenerate certificates for all nodes after CA change"""
        try:
            nodes = get_nodes(self.db)
            for node in nodes:
                self.cert_manager.generate_node_certificates(node.name, node.address)
                self._export_node_certificates(node.name)
                logger.info(f"Regenerated certificates for node: {node.name}")
        except Exception as e:
            logger.error(f"Error regenerating all node certificates: {e}")

def main():
    """Main daemon loop"""
    daemon = CertificateDaemon()
    daemon.initialize()
    
    # Schedule certificate checks
    schedule.every().day.at("02:00").do(daemon.check_and_rotate_certificates)
    schedule.every().hour.do(daemon.export_all_certificates)
    
    # Initial export
    daemon.export_all_certificates()
    
    logger.info("Certificate daemon started, running scheduled tasks...")
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    main()
EOF

chmod +x "$PROJECT_ROOT/scripts/certificate-daemon.py"

echo "✅ Certificate management daemon created"

# Create node deployment script
echo "🚀 Creating automated node deployment script..."

cat > "$PROJECT_ROOT/scripts/deploy-node.sh" << 'EOF'
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
EOF

chmod +x "$PROJECT_ROOT/scripts/deploy-node.sh"

echo "✅ Node deployment script created"

# Create management CLI
echo "🔧 Creating certificate management CLI..."

cat > "$PROJECT_ROOT/scripts/cert-manager-cli.py" << 'EOF'
#!/usr/bin/env python3
"""
Certificate Management CLI for Marzban

This CLI provides easy certificate management operations:
- Generate certificates for new nodes
- Rotate existing certificates
- Export certificates for deployment
- Check certificate status
"""

import sys
import argparse
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.db import get_db, init_db
from app.services.certificate_manager import CertificateManager
from app.db.crud import get_expiring_certificates

def init_system():
    """Initialize database and return certificate manager"""
    init_db()
    db = next(get_db())
    return CertificateManager(db), db

def cmd_generate(args):
    """Generate certificates for a node"""
    cert_manager, _ = init_system()
    
    try:
        node_certs = cert_manager.generate_node_certificates(
            node_name=args.node_name,
            node_address=args.node_address
        )
        
        print(f"✅ Certificates generated for node: {args.node_name}")
        print(f"   Valid until: {node_certs.server_cert.valid_until}")
        
        if args.export:
            export_dir = args.export_dir or f"./certs-{args.node_name}"
            cert_manager.export_certificates_for_docker(args.node_name, export_dir)
            print(f"📁 Certificates exported to: {export_dir}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

def cmd_rotate(args):
    """Rotate certificates for a node"""
    cert_manager, _ = init_system()
    
    try:
        node_certs = cert_manager.rotate_certificates(args.node_name)
        print(f"🔄 Certificates rotated for node: {args.node_name}")
        print(f"   New valid until: {node_certs.server_cert.valid_until}")
        
        if args.export:
            export_dir = args.export_dir or f"./certs-{args.node_name}"
            cert_manager.export_certificates_for_docker(args.node_name, export_dir)
            print(f"📁 New certificates exported to: {export_dir}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

def cmd_status(args):
    """Check certificate status"""
    cert_manager, db = init_system()
    
    try:
        expiring = get_expiring_certificates(db, days_ahead=args.days)
        
        print("📊 Certificate Status")
        print("===================")
        
        # CA status
        if expiring["ca"]:
            print(f"⚠️  CA Certificate expiring: {expiring['ca'].valid_until}")
        else:
            ca_cert = cert_manager.get_or_create_ca()
            print(f"✅ CA Certificate healthy (expires: {ca_cert.valid_until})")
        
        # Node certificates
        if expiring["nodes"]:
            print(f"\n⚠️  {len(expiring['nodes'])} node certificates expiring:")
            for cert in expiring["nodes"]:
                print(f"   - {cert.node_name}: {cert.valid_until}")
        else:
            print("\n✅ All node certificates healthy")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

def cmd_export(args):
    """Export certificates for a node"""
    cert_manager, _ = init_system()
    
    try:
        export_dir = args.export_dir or f"./certs-{args.node_name}"
        file_paths = cert_manager.export_certificates_for_docker(args.node_name, export_dir)
        
        print(f"📁 Certificates exported for node: {args.node_name}")
        print(f"   Export directory: {export_dir}")
        print("   Files:")
        for name, path in file_paths.items():
            print(f"     {name}: {path}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Marzban Certificate Management CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate certificates for a node")
    gen_parser.add_argument("node_name", help="Name of the node")
    gen_parser.add_argument("node_address", help="IP address or hostname of the node")
    gen_parser.add_argument("--export", action="store_true", help="Export certificates after generation")
    gen_parser.add_argument("--export-dir", help="Directory to export certificates to")
    gen_parser.set_defaults(func=cmd_generate)
    
    # Rotate command
    rot_parser = subparsers.add_parser("rotate", help="Rotate certificates for a node")
    rot_parser.add_argument("node_name", help="Name of the node")
    rot_parser.add_argument("--export", action="store_true", help="Export certificates after rotation")
    rot_parser.add_argument("--export-dir", help="Directory to export certificates to")
    rot_parser.set_defaults(func=cmd_rotate)
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Check certificate status")
    status_parser.add_argument("--days", type=int, default=30, help="Check for certificates expiring within N days")
    status_parser.set_defaults(func=cmd_status)
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export certificates for a node")
    export_parser.add_argument("node_name", help="Name of the node")
    export_parser.add_argument("--export-dir", help="Directory to export certificates to")
    export_parser.set_defaults(func=cmd_export)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)

if __name__ == "__main__":
    main()
EOF

chmod +x "$PROJECT_ROOT/scripts/cert-manager-cli.py"

echo "✅ Certificate management CLI created"

# Create usage documentation
echo "📚 Creating documentation..."

cat > "$PROJECT_ROOT/CERTIFICATE_MANAGEMENT.md" << 'EOF'
# Automated Certificate Management for Marzban

This document describes the automated certificate management system that eliminates manual certificate handling.

## Features

- **Automatic CA Generation**: Self-signed CA created automatically
- **Node Certificate Generation**: Server and client certificates auto-generated for each node
- **Certificate Rotation**: Automatic renewal before expiration
- **Docker Integration**: Seamless certificate deployment to containers
- **Production Ready**: Secure storage and proper permissions

## Quick Start

### 1. Setup Automated Environment

```bash
# Run the automated setup
./scripts/setup-automated-certificates.sh

# Start the environment with automated certificates
docker-compose -f docker-compose.automated.yml up -d
```

### 2. Add a New Node (Automated)

```bash
# The certificate management is now automatic!
# Just add a node through the admin panel:
# - Go to Admin Panel → Nodes → Add New Node
# - Enter name and address
# - Certificates are generated automatically
# - No manual certificate copy/paste required!
```

### 3. Deploy Node with Auto-Generated Certificates

```bash
# Use the automated deployment script
export ADMIN_TOKEN="your-admin-token"
./scripts/deploy-node.sh node1 192.168.1.100 https://your-panel.com

# This will:
# 1. Create the node in the panel
# 2. Auto-generate certificates
# 3. Export certificates for deployment
# 4. Generate docker-compose for the node
```

## Certificate Management CLI

```bash
# Check certificate status
./scripts/cert-manager-cli.py status

# Generate certificates for a node
./scripts/cert-manager-cli.py generate node1 192.168.1.100 --export

# Rotate certificates
./scripts/cert-manager-cli.py rotate node1 --export

# Export certificates
./scripts/cert-manager-cli.py export node1 --export-dir ./my-certs
```

## API Endpoints

The system provides REST API endpoints for certificate management:

- `GET /api/admin/certificates/ca` - Get CA information
- `POST /api/admin/certificates/ca/regenerate` - Regenerate CA
- `POST /api/admin/certificates/node/{node_name}/generate` - Generate node certificates
- `GET /api/admin/certificates/node/{node_name}` - Get node certificate info
- `POST /api/admin/certificates/node/{node_name}/rotate` - Rotate node certificates
- `GET /api/admin/certificates/node/{node_name}/export` - Export for Docker
- `GET /api/admin/certificates/status` - Overall certificate status

## Architecture

### Certificate Storage
- **Database**: Secure storage of all certificates and metadata
- **Filesystem**: Exported certificates for Docker mounting
- **Memory**: Temporary certificate handling with proper cleanup

### Security Features
- **4096-bit RSA** keys for CA
- **2048-bit RSA** keys for server/client certificates
- **Proper certificate extensions** (Server Auth, Client Auth)
- **Subject Alternative Names** for IP/hostname validation
- **File permissions** (600 for private keys, 644 for certificates)

### Automation
- **Daily certificate checks** for expiration
- **Automatic rotation** 30 days before expiry
- **Background daemon** for continuous monitoring
- **Docker integration** for seamless deployment

## Migration from Manual System

1. **Backup existing certificates**:
   ```bash
   cp -r ./panel-certs ./panel-certs.backup
   cp -r ./node1-certs ./node1-certs.backup
   ```

2. **Run database migration**:
   ```bash
   docker-compose exec marzban-panel alembic upgrade head
   ```

3. **Generate certificates for existing nodes**:
   ```bash
   ./scripts/cert-manager-cli.py generate node1 192.168.1.100 --export
   ```

4. **Update Docker configurations**:
   ```bash
   # Use the new automated docker-compose
   docker-compose -f docker-compose.automated.yml up -d
   ```

## Production Deployment

For production environments:

1. **Use the automated docker-compose**:
   ```yaml
   docker-compose -f docker-compose.automated.yml up -d
   ```

2. **Enable certificate daemon**:
   The daemon runs automatically and handles:
   - Certificate expiration monitoring
   - Automatic rotation
   - Export for deployment

3. **Monitor logs**:
   ```bash
   docker-compose logs marzban-cert-manager
   ```

4. **Set up monitoring alerts** for certificate expiration

## Troubleshooting

### Certificate Generation Fails
- Check database connectivity
- Verify node name and address are valid
- Check disk space for certificate export

### Node Connection Issues
- Verify certificates are properly mounted in container
- Check certificate validity with: `openssl x509 -in cert.crt -text -noout`
- Ensure proper file permissions (600 for keys, 644 for certs)

### Certificate Rotation Issues
- Check daemon logs: `docker-compose logs marzban-cert-manager`
- Manually rotate: `./scripts/cert-manager-cli.py rotate node1`
- Verify database permissions

## Security Considerations

1. **Private Key Protection**: All private keys are stored encrypted in database
2. **Certificate Validation**: Proper certificate chain validation
3. **Access Control**: Only sudo admins can regenerate CA
4. **Audit Trail**: All certificate operations are logged
5. **Secure Defaults**: Production-grade security settings

This automated system provides enterprise-grade certificate management while maintaining ease of use for development and production deployments.
EOF

echo "✅ Documentation created: CERTIFICATE_MANAGEMENT.md"

echo ""
echo "🎉 Automated Certificate Management Setup Complete!"
echo "================================================="
echo ""
echo "🚀 Next Steps:"
echo "1. Run database migration: docker-compose exec marzban-panel alembic upgrade head"
echo "2. Start automated environment: docker-compose -f docker-compose.automated.yml up -d"
echo "3. Add nodes through admin panel - certificates generated automatically!"
echo "4. Use ./scripts/deploy-node.sh for automated node deployment"
echo ""
echo "📚 Documentation: CERTIFICATE_MANAGEMENT.md"
echo "🔧 CLI Tool: ./scripts/cert-manager-cli.py"
echo "🤖 Daemon: ./scripts/certificate-daemon.py"
echo ""
echo "✨ Manual certificate copy/paste is now eliminated!"