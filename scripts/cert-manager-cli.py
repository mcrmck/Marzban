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
