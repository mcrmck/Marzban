"""drop_proxy_host_and_proxy_inbound_tables

Revision ID: 861a6b865a19
Revises: 7dfdff33b597
Create Date: 2025-06-01 13:12:57.884882

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '861a6b865a19'
down_revision = '7dfdff33b597'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop tables if they exist
    for table in ['hosts', 'inbounds', 'template_inbounds_association']:
        op.execute(f"DROP TABLE IF EXISTS {table}")

    # Create template_inbounds_association with correct foreign key
    op.create_table(
        'template_inbounds_association',
        sa.Column('user_template_id', sa.Integer(), nullable=True),
        sa.Column('inbound_tag', sa.String(length=256), nullable=True),
        sa.ForeignKeyConstraint(['inbound_tag'], ['node_service_configurations.xray_inbound_tag'], ),
        sa.ForeignKeyConstraint(['user_template_id'], ['user_templates.id'], )
    )


def downgrade() -> None:
    # Drop the new table if it exists
    op.execute("DROP TABLE IF EXISTS template_inbounds_association")

    # Recreate the old tables
    op.create_table(
        'template_inbounds_association',
        sa.Column('user_template_id', sa.Integer(), nullable=True),
        sa.Column('inbound_tag', sa.String(length=256), nullable=True),
        sa.ForeignKeyConstraint(['inbound_tag'], ['inbounds.tag'], ),
        sa.ForeignKeyConstraint(['user_template_id'], ['user_templates.id'], )
    )

    op.create_table(
        'inbounds',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tag', sa.String(length=256), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tag')
    )
    op.create_index(op.f('ix_inbounds_tag'), 'inbounds', ['tag'], unique=True)

    op.create_table(
        'hosts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('remark', sa.String(length=256), nullable=False),
        sa.Column('address', sa.String(length=256), nullable=False),
        sa.Column('port', sa.Integer(), nullable=True),
        sa.Column('path', sa.String(length=256), nullable=True),
        sa.Column('sni', sa.String(length=1000), nullable=True),
        sa.Column('host', sa.String(length=1000), nullable=True),
        sa.Column('alpn', sa.Enum('none', name='proxyhostalpn'), nullable=False),
        sa.Column('fingerprint', sa.Enum('none', name='proxyhostfingerprint'), nullable=False),
        sa.Column('inbound_tag', sa.String(length=256), nullable=False),
        sa.Column('allowinsecure', sa.Boolean(), nullable=True),
        sa.Column('is_disabled', sa.Boolean(), nullable=True),
        sa.Column('mux_enable', sa.Boolean(), nullable=False),
        sa.Column('fragment_setting', sa.String(length=100), nullable=True),
        sa.Column('noise_setting', sa.String(length=2000), nullable=True),
        sa.Column('random_user_agent', sa.Boolean(), nullable=False),
        sa.Column('use_sni_as_host', sa.Boolean(), nullable=False),
        sa.Column('node_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['inbound_tag'], ['inbounds.tag'], ),
        sa.ForeignKeyConstraint(['node_id'], ['nodes.id'], name='fk_proxy_host_node'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hosts_node_id'), 'hosts', ['node_id'], unique=False)
