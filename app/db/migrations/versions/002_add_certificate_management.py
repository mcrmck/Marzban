"""Add certificate management tables

Revision ID: 002_add_certificate_management
Revises: f1e838995c42
Create Date: 2025-06-05 09:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import Column, Integer, String, DateTime, Boolean

# revision identifiers, used by Alembic.
revision = '002_add_certificate_management'
down_revision = 'f1e838995c42'
branch_labels = None
depends_on = None

def upgrade():
    # Create certificate_authority table
    op.create_table(
        'certificate_authority',
        Column('id', Integer, primary_key=True),
        Column('certificate_pem', String(4096), nullable=False),
        Column('private_key_pem', String(4096), nullable=False),
        Column('public_key_pem', String(2048), nullable=False),
        Column('subject_name', String(256), nullable=False),
        Column('issuer_name', String(256), nullable=False),
        Column('serial_number', String(64), nullable=False),
        Column('valid_from', DateTime, nullable=False),
        Column('valid_until', DateTime, nullable=False),
        Column('created_at', DateTime, nullable=False),
        Column('updated_at', DateTime, nullable=False),
    )
    
    # Create node_certificates table
    op.create_table(
        'node_certificates',
        Column('id', Integer, primary_key=True),
        Column('node_name', String(256), nullable=False, unique=True, index=True),
        Column('server_certificate_pem', String(4096), nullable=False),
        Column('server_private_key_pem', String(4096), nullable=False),
        Column('server_public_key_pem', String(2048), nullable=False),
        Column('panel_client_certificate_pem', String(4096), nullable=False),
        Column('panel_client_private_key_pem', String(4096), nullable=False),
        Column('panel_client_public_key_pem', String(2048), nullable=False),
        Column('subject_name', String(256), nullable=False),
        Column('issuer_name', String(256), nullable=False),
        Column('serial_number', String(64), nullable=False),
        Column('valid_from', DateTime, nullable=False),
        Column('valid_until', DateTime, nullable=False),
        Column('auto_renew', Boolean, default=True),
        Column('last_rotation', DateTime, nullable=False),
        Column('created_at', DateTime, nullable=False),
        Column('updated_at', DateTime, nullable=False),
    )

def downgrade():
    op.drop_table('node_certificates')
    op.drop_table('certificate_authority')