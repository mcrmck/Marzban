"""
Production-grade Certificate Management Service for Marzban

This service handles:
- Automatic CA generation and management
- Node certificate generation and distribution
- Panel client certificate management
- Certificate rotation and lifecycle management
- Secure storage and retrieval
"""

import os
import tempfile
import logging
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.x509.oid import NameOID, SignatureAlgorithmOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
from sqlalchemy.orm import Session

from app.db import crud
from app.db.models import CertificateAuthority, NodeCertificate
import config

logger = logging.getLogger(__name__)

@dataclass
class CertificateInfo:
    """Certificate information container"""
    certificate_pem: str
    private_key_pem: str
    public_key_pem: str
    subject_name: str
    issuer_name: str
    serial_number: str
    valid_from: datetime
    valid_until: datetime
    is_ca: bool

@dataclass
class NodeCertificates:
    """Complete set of certificates for a node"""
    ca_cert: CertificateInfo
    server_cert: CertificateInfo
    panel_client_cert: CertificateInfo

class CertificateManager:
    """
    Production-grade certificate management system
    
    Features:
    - Automatic CA generation with secure key storage
    - Node certificate generation with proper extensions
    - Panel client certificate management
    - Certificate rotation and lifecycle management
    - Secure storage in database with encryption
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.ca_subject_name = "Marzban Certificate Authority"
        self.ca_validity_days = 3650  # 10 years for CA
        self.cert_validity_days = 365  # 1 year for server/client certs
        
    def get_or_create_ca(self) -> CertificateInfo:
        """
        Get existing CA or create new one if none exists
        
        Returns:
            CertificateInfo: CA certificate and private key information
        """
        # Try to get existing CA from database
        ca_record = crud.get_certificate_authority(self.db)
        
        if ca_record and self._is_certificate_valid(ca_record.certificate_pem):
            logger.info("Using existing CA certificate")
            return CertificateInfo(
                certificate_pem=ca_record.certificate_pem,
                private_key_pem=ca_record.private_key_pem,
                public_key_pem=ca_record.public_key_pem,
                subject_name=ca_record.subject_name,
                issuer_name=ca_record.issuer_name,
                serial_number=ca_record.serial_number,
                valid_from=ca_record.valid_from,
                valid_until=ca_record.valid_until,
                is_ca=True
            )
        
        # Generate new CA
        logger.info("Generating new CA certificate")
        return self._generate_ca_certificate()
    
    def generate_node_certificates(self, node_name: str, node_address: str) -> NodeCertificates:
        """
        Generate complete certificate set for a node
        
        Args:
            node_name: Unique name for the node
            node_address: IP address or hostname of the node
            
        Returns:
            NodeCertificates: Complete certificate set (CA, server, panel client)
        """
        logger.info(f"Generating certificates for node: {node_name}")
        
        # Get or create CA
        ca_cert = self.get_or_create_ca()
        
        # Generate server certificate for the node
        server_cert = self._generate_server_certificate(
            node_name, node_address, ca_cert
        )
        
        # Generate client certificate for panel to authenticate with this node
        panel_client_cert = self._generate_client_certificate(
            f"panel-client-{node_name}", ca_cert
        )
        
        # Store certificates in database
        self._store_node_certificates(node_name, server_cert, panel_client_cert)
        
        return NodeCertificates(
            ca_cert=ca_cert,
            server_cert=server_cert,
            panel_client_cert=panel_client_cert
        )
    
    def get_node_certificates(self, node_name: str) -> Optional[NodeCertificates]:
        """
        Retrieve existing certificates for a node
        
        Args:
            node_name: Name of the node
            
        Returns:
            NodeCertificates if found, None otherwise
        """
        node_cert_record = crud.get_node_certificate(self.db, node_name)
        if not node_cert_record:
            return None
            
        ca_cert = self.get_or_create_ca()
        
        return NodeCertificates(
            ca_cert=ca_cert,
            server_cert=CertificateInfo(
                certificate_pem=node_cert_record.server_certificate_pem,
                private_key_pem=node_cert_record.server_private_key_pem,
                public_key_pem=node_cert_record.server_public_key_pem,
                subject_name=node_cert_record.subject_name,
                issuer_name=node_cert_record.issuer_name,
                serial_number=node_cert_record.serial_number,
                valid_from=node_cert_record.valid_from,
                valid_until=node_cert_record.valid_until,
                is_ca=False
            ),
            panel_client_cert=CertificateInfo(
                certificate_pem=node_cert_record.panel_client_certificate_pem,
                private_key_pem=node_cert_record.panel_client_private_key_pem,
                public_key_pem=node_cert_record.panel_client_public_key_pem,
                subject_name=f"panel-client-{node_name}",
                issuer_name=ca_cert.subject_name,
                serial_number="", # TODO: Store this
                valid_from=node_cert_record.valid_from,
                valid_until=node_cert_record.valid_until,
                is_ca=False
            )
        )
    
    def rotate_certificates(self, node_name: str) -> NodeCertificates:
        """
        Rotate certificates for a node (generate new ones)
        
        Args:
            node_name: Name of the node
            
        Returns:
            NodeCertificates: New certificate set
        """
        logger.info(f"Rotating certificates for node: {node_name}")
        
        # Get node info for regeneration
        node_record = crud.get_node_by_name(self.db, node_name)
        if not node_record:
            raise ValueError(f"Node {node_name} not found")
        
        # Generate new certificates
        return self.generate_node_certificates(node_name, node_record.address)
    
    def export_certificates_for_docker(self, node_name: str, export_dir: str) -> Dict[str, str]:
        """
        Export certificates to filesystem for Docker mounting
        
        Args:
            node_name: Name of the node
            export_dir: Directory to export certificates to
            
        Returns:
            Dict with file paths for Docker volume mounting
        """
        node_certs = self.get_node_certificates(node_name)
        if not node_certs:
            raise ValueError(f"No certificates found for node: {node_name}")
        
        export_path = Path(export_dir)
        export_path.mkdir(parents=True, exist_ok=True)
        
        # Export CA certificate (for node to verify panel)
        ca_file = export_path / "ca.crt"
        ca_file.write_text(node_certs.ca_cert.certificate_pem)
        
        # Export server certificate and key (for node HTTPS server)
        server_cert_file = export_path / "server.crt"
        server_key_file = export_path / "server.key"
        server_cert_file.write_text(node_certs.server_cert.certificate_pem)
        server_key_file.write_text(node_certs.server_cert.private_key_pem)
        
        # Export panel client certificate (for panel to authenticate with node)
        panel_cert_file = export_path / "panel-client.crt"
        panel_key_file = export_path / "panel-client.key"
        panel_cert_file.write_text(node_certs.panel_client_cert.certificate_pem)
        panel_key_file.write_text(node_certs.panel_client_cert.private_key_pem)
        
        # Set proper permissions
        for file_path in [server_key_file, panel_key_file]:
            file_path.chmod(0o600)  # Read-only for owner
        
        logger.info(f"Exported certificates for node {node_name} to {export_dir}")
        
        return {
            "ca_cert": str(ca_file),
            "server_cert": str(server_cert_file),
            "server_key": str(server_key_file),
            "panel_client_cert": str(panel_cert_file),
            "panel_client_key": str(panel_key_file)
        }
    
    def _generate_ca_certificate(self) -> CertificateInfo:
        """Generate new CA certificate and store in database"""
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
        )
        
        # Create certificate subject
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CA"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Marzban"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Certificate Authority"),
            x509.NameAttribute(NameOID.COMMON_NAME, self.ca_subject_name),
        ])
        
        # Generate serial number
        serial_number = x509.random_serial_number()
        
        # Set validity period
        valid_from = datetime.utcnow()
        valid_until = valid_from + timedelta(days=self.ca_validity_days)
        
        # Build certificate
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            subject  # Self-signed
        ).public_key(
            private_key.public_key()
        ).serial_number(
            serial_number
        ).not_valid_before(
            valid_from
        ).not_valid_after(
            valid_until
        ).add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        ).add_extension(
            x509.KeyUsage(
                key_cert_sign=True,
                crl_sign=True,
                digital_signature=False,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False
            ),
            critical=True,
        ).add_extension(
            x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
            critical=False,
        ).sign(private_key, hashes.SHA256())
        
        # Serialize certificates and keys
        cert_pem = cert.public_bytes(Encoding.PEM).decode('utf-8')
        private_key_pem = private_key.private_bytes(
            Encoding.PEM,
            PrivateFormat.PKCS8,
            NoEncryption()
        ).decode('utf-8')
        public_key_pem = private_key.public_key().public_bytes(
            Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        # Create certificate info
        cert_info = CertificateInfo(
            certificate_pem=cert_pem,
            private_key_pem=private_key_pem,
            public_key_pem=public_key_pem,
            subject_name=self.ca_subject_name,
            issuer_name=self.ca_subject_name,
            serial_number=str(serial_number),
            valid_from=valid_from,
            valid_until=valid_until,
            is_ca=True
        )
        
        # Store in database
        crud.create_or_update_certificate_authority(self.db, cert_info)
        
        logger.info(f"Generated new CA certificate (valid until: {valid_until})")
        return cert_info
    
    def _generate_server_certificate(self, node_name: str, node_address: str, ca_cert: CertificateInfo) -> CertificateInfo:
        """Generate server certificate for node"""
        # Load CA private key
        ca_private_key = serialization.load_pem_private_key(
            ca_cert.private_key_pem.encode('utf-8'),
            password=None,
        )
        ca_certificate = x509.load_pem_x509_certificate(ca_cert.certificate_pem.encode('utf-8'))
        
        # Generate private key for server
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        # Create subject
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CA"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Marzban"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Node"),
            x509.NameAttribute(NameOID.COMMON_NAME, node_name),
        ])
        
        # Generate serial number
        serial_number = x509.random_serial_number()
        
        # Set validity period
        valid_from = datetime.utcnow()
        valid_until = valid_from + timedelta(days=self.cert_validity_days)
        
        # Build server certificate
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            ca_certificate.subject
        ).public_key(
            private_key.public_key()
        ).serial_number(
            serial_number
        ).not_valid_before(
            valid_from
        ).not_valid_after(
            valid_until
        ).add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        ).add_extension(
            x509.KeyUsage(
                key_cert_sign=False,
                crl_sign=False,
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False
            ),
            critical=True,
        ).add_extension(
            x509.ExtendedKeyUsage([
                x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
            ]),
            critical=True,
        ).add_extension(
            x509.SubjectAlternativeName(self._build_san_list(node_name, node_address)),
            critical=False,
        ).add_extension(
            x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
            critical=False,
        ).add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_private_key.public_key()),
            critical=False,
        ).sign(ca_private_key, hashes.SHA256())
        
        # Serialize
        cert_pem = cert.public_bytes(Encoding.PEM).decode('utf-8')
        private_key_pem = private_key.private_bytes(
            Encoding.PEM,
            PrivateFormat.PKCS8,
            NoEncryption()
        ).decode('utf-8')
        public_key_pem = private_key.public_key().public_bytes(
            Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        return CertificateInfo(
            certificate_pem=cert_pem,
            private_key_pem=private_key_pem,
            public_key_pem=public_key_pem,
            subject_name=node_name,
            issuer_name=ca_cert.subject_name,
            serial_number=str(serial_number),
            valid_from=valid_from,
            valid_until=valid_until,
            is_ca=False
        )
    
    def _generate_client_certificate(self, client_name: str, ca_cert: CertificateInfo) -> CertificateInfo:
        """Generate client certificate for panel"""
        # Load CA private key
        ca_private_key = serialization.load_pem_private_key(
            ca_cert.private_key_pem.encode('utf-8'),
            password=None,
        )
        ca_certificate = x509.load_pem_x509_certificate(ca_cert.certificate_pem.encode('utf-8'))
        
        # Generate private key for client
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        # Create subject
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CA"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Marzban"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Panel"),
            x509.NameAttribute(NameOID.COMMON_NAME, client_name),
        ])
        
        # Generate serial number
        serial_number = x509.random_serial_number()
        
        # Set validity period
        valid_from = datetime.utcnow()
        valid_until = valid_from + timedelta(days=self.cert_validity_days)
        
        # Build client certificate
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            ca_certificate.subject
        ).public_key(
            private_key.public_key()
        ).serial_number(
            serial_number
        ).not_valid_before(
            valid_from
        ).not_valid_after(
            valid_until
        ).add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        ).add_extension(
            x509.KeyUsage(
                key_cert_sign=False,
                crl_sign=False,
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False
            ),
            critical=True,
        ).add_extension(
            x509.ExtendedKeyUsage([
                x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH,
            ]),
            critical=True,
        ).add_extension(
            x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
            critical=False,
        ).add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_private_key.public_key()),
            critical=False,
        ).sign(ca_private_key, hashes.SHA256())
        
        # Serialize
        cert_pem = cert.public_bytes(Encoding.PEM).decode('utf-8')
        private_key_pem = private_key.private_bytes(
            Encoding.PEM,
            PrivateFormat.PKCS8,
            NoEncryption()
        ).decode('utf-8')
        public_key_pem = private_key.public_key().public_bytes(
            Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        return CertificateInfo(
            certificate_pem=cert_pem,
            private_key_pem=private_key_pem,
            public_key_pem=public_key_pem,
            subject_name=client_name,
            issuer_name=ca_cert.subject_name,
            serial_number=str(serial_number),
            valid_from=valid_from,
            valid_until=valid_until,
            is_ca=False
        )
    
    def _store_node_certificates(self, node_name: str, server_cert: CertificateInfo, panel_client_cert: CertificateInfo):
        """Store node certificates in database"""
        crud.create_or_update_node_certificate(
            self.db, 
            node_name, 
            server_cert, 
            panel_client_cert
        )
    
    def _is_certificate_valid(self, cert_pem: str, days_ahead: int = 30) -> bool:
        """Check if certificate is valid and not expiring soon"""
        try:
            cert = x509.load_pem_x509_certificate(cert_pem.encode('utf-8'))
            now = datetime.utcnow()
            expiry_threshold = now + timedelta(days=days_ahead)
            
            return cert.not_valid_after > expiry_threshold
        except Exception as e:
            logger.error(f"Error validating certificate: {e}")
            return False
    
    def _parse_ip_address(self, address: str):
        """Parse IP address for SAN extension"""
        try:
            import ipaddress
            return ipaddress.ip_address(address)
        except ValueError:
            # If not an IP, use localhost
            return ipaddress.ip_address("127.0.0.1")
    
    def _build_san_list(self, node_name: str, node_address: str) -> list:
        """Build Subject Alternative Names list for node certificates"""
        san_list = []
        
        # Always include the node name as DNS
        san_list.append(x509.DNSName(node_name))
        
        # Try to parse node_address as IP first
        try:
            ip_addr = self._parse_ip_address(node_address)
            san_list.append(x509.IPAddress(ip_addr))
            
            # If node_address is different from node_name, add it as DNS too
            if node_address != node_name:
                san_list.append(x509.DNSName(node_address))
                
        except Exception:
            # If IP parsing fails, treat as DNS name
            if node_address != node_name:
                san_list.append(x509.DNSName(node_address))
        
        # Add common localhost entries for development
        try:
            import ipaddress
            san_list.append(x509.IPAddress(ipaddress.IPv4Address('127.0.0.1')))
            san_list.append(x509.DNSName('localhost'))
        except Exception:
            pass
            
        return san_list