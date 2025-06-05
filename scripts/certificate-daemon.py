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
