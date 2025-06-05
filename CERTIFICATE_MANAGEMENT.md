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
