import os
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
    func,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import select, text

from app import xray
from app.db.base import Base
from app.models.node import NodeStatus
from app.models.proxy import ProxyTypes
from app.models.protocol_types import ProtocolType, NetworkType, SecurityType
from app.models.user import ReminderType, UserDataLimitResetStrategy, UserStatus
import enum


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True)
    username = Column(String(34), unique=True, index=True)
    hashed_password = Column(String(128))
    created_at = Column(DateTime, default=datetime.utcnow)
    is_sudo = Column(Boolean, default=False)
    password_reset_at = Column(DateTime, nullable=True)
    telegram_id = Column(BigInteger, nullable=True, default=None)
    discord_webhook = Column(String(1024), nullable=True, default=None)
    users_usage = Column(BigInteger, nullable=False, default=0)
    usage_logs = relationship("AdminUsageLogs", back_populates="admin")


class AdminUsageLogs(Base):
    __tablename__ = "admin_usage_logs"

    id = Column(Integer, primary_key=True)
    admin_id = Column(Integer, ForeignKey("admins.id"))
    admin = relationship("Admin", back_populates="usage_logs")
    used_traffic_at_reset = Column(BigInteger, nullable=False)
    reset_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    account_number = Column(String(36), unique=True, index=True, nullable=False)

    proxies = relationship("Proxy", back_populates="user", cascade="all, delete-orphan")
    status = Column(Enum(UserStatus), nullable=False, default=UserStatus.active)
    used_traffic = Column(BigInteger, default=0)
    node_usages = relationship("NodeUserUsage", back_populates="user", cascade="all, delete-orphan")
    notification_reminders = relationship("NotificationReminder", back_populates="user", cascade="all, delete-orphan")
    data_limit = Column(BigInteger, nullable=True)
    data_limit_reset_strategy = Column(
        Enum(UserDataLimitResetStrategy),
        nullable=False,
        default=UserDataLimitResetStrategy.no_reset,
    )
    usage_logs = relationship("UserUsageResetLogs", back_populates="user")
    expire = Column(Integer, nullable=True)
    sub_revoked_at = Column(DateTime, nullable=True, default=None)
    sub_updated_at = Column(DateTime, nullable=True, default=None)
    sub_last_user_agent = Column(String(512), nullable=True, default=None)
    created_at = Column(DateTime, default=datetime.utcnow)
    note = Column(String(500), nullable=True, default=None)
    online_at = Column(DateTime, nullable=True, default=None)
    on_hold_expire_duration = Column(BigInteger, nullable=True, default=None)
    on_hold_timeout = Column(DateTime, nullable=True, default=None)
    auto_delete_in_days = Column(Integer, nullable=True, default=None)
    edit_at = Column(DateTime, nullable=True, default=None)
    last_status_change = Column(DateTime, default=datetime.utcnow, nullable=True)
    active_node_id = Column(Integer, ForeignKey("nodes.id", name="fk_user_active_node"), nullable=True, index=True)
    active_node = relationship("Node", foreign_keys=[active_node_id], backref="active_users")

    next_plan = relationship(
        "NextPlan",
        uselist=False,
        back_populates="user",
        cascade="all, delete-orphan"
    )

    @hybrid_property
    def reseted_usage(self) -> int:
        return int(sum([log.used_traffic_at_reset for log in self.usage_logs]))

    @reseted_usage.expression
    def reseted_usage(cls):
        return (
            select(func.sum(UserUsageResetLogs.used_traffic_at_reset)).
            where(UserUsageResetLogs.user_id == cls.id).
            label('reseted_usage')
        )

    @property
    def lifetime_used_traffic(self) -> int:
        return int(
            sum([log.used_traffic_at_reset for log in self.usage_logs])
            + self.used_traffic
        )

    @property
    def last_traffic_reset_time(self):
        return self.usage_logs[-1].reset_at if self.usage_logs else self.created_at

    # REMOVED: excluded_inbounds property (as it relied on proxy.excluded_inbounds)
    # @property
    # def excluded_inbounds(self):
    #     _ = {}
    #     for proxy in self.proxies:
    #         # This line used proxy.excluded_inbounds which is now removed
    #         # _[proxy.type] = [i.tag for i in proxy.excluded_inbounds]
    #         _[proxy.type] = [] # Placeholder, this property should be removed entirely
    #     return _

    @property
    def inbounds(self):
        """
        Returns all available inbounds for the user's configured proxy types.
        This means if a user has a 'vmess' proxy configured in their User.proxies,
        they get all system-defined 'vmess' inbounds.
        """
        _ = {}
        # Ensure xray.config and xray.config.inbounds_by_protocol are loaded and accessible
        if not hasattr(xray, 'config') or not hasattr(xray.config, 'inbounds_by_protocol'):
            # Log a warning or handle appropriately if xray config isn't ready
            return _

        active_proxy_types = {p.type for p in self.proxies if p.type} # Get unique proxy types from user's proxies

        for proxy_type_enum in active_proxy_types:
            proxy_type_str = proxy_type_enum.value # e.g., "vmess"

            # Ensure xray.config.inbounds_by_protocol is a dictionary
            if not isinstance(xray.config.inbounds_by_protocol, dict):
                continue # Or log error

            inbounds_for_protocol = xray.config.inbounds_by_protocol.get(proxy_type_str, [])

            # Ensure each inbound is a dictionary and has a 'tag'
            _[proxy_type_enum] = [
                inbound.get("tag")
                for inbound in inbounds_for_protocol
                if isinstance(inbound, dict) and inbound.get("tag")
            ]
        return _

template_inbounds_association = Table(
    "template_inbounds_association",
    Base.metadata,
    Column("user_template_id", ForeignKey("user_templates.id")),
    Column("inbound_tag", ForeignKey("node_service_configurations.xray_inbound_tag")),
)


class NextPlan(Base):
    __tablename__ = 'next_plans'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    data_limit = Column(BigInteger, nullable=False)
    expire = Column(Integer, nullable=True)
    add_remaining_traffic = Column(Boolean, nullable=False, default=False, server_default='0')
    fire_on_either = Column(Boolean, nullable=False, default=True, server_default='0')

    user = relationship("User", back_populates="next_plan")


class UserTemplate(Base):
    __tablename__ = "user_templates"

    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False, unique=True)
    data_limit = Column(BigInteger, default=0)
    expire_duration = Column(BigInteger, default=0)  # in seconds
    username_prefix = Column(String(20), nullable=True)
    username_suffix = Column(String(20), nullable=True)

    # Removed inbounds relationship as it's no longer needed


class UserUsageResetLogs(Base):
    __tablename__ = "user_usage_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="usage_logs")
    used_traffic_at_reset = Column(BigInteger, nullable=False)
    reset_at = Column(DateTime, default=datetime.utcnow)


class Proxy(Base):
    __tablename__ = "proxies"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="proxies")
    type = Column(Enum(ProxyTypes), nullable=False) # Ensure ProxyTypes is correctly defined
    settings = Column(JSON, nullable=False)


class System(Base):
    __tablename__ = "system"

    id = Column(Integer, primary_key=True)
    uplink = Column(BigInteger, default=0)
    downlink = Column(BigInteger, default=0)


class JWT(Base):
    __tablename__ = "jwt"

    id = Column(Integer, primary_key=True)
    secret_key = Column(
        String(64), nullable=False, default=lambda: os.urandom(32).hex()
    )


class TLS(Base):
    __tablename__ = "tls"

    id = Column(Integer, primary_key=True)
    key = Column(String(4096), nullable=False)
    certificate = Column(String(2048), nullable=False)


class Node(Base):
    __tablename__ = "nodes"

    id = Column(Integer, primary_key=True)
    name = Column(String(256, collation='NOCASE'), unique=True)
    address = Column(String(256), unique=False, nullable=False)
    port = Column(Integer, unique=False, nullable=False)
    api_port = Column(Integer, unique=False, nullable=False)
    xray_version = Column(String(32), nullable=True)
    status = Column(Enum(NodeStatus), nullable=False, default=NodeStatus.connecting)
    message = Column(String(1024), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_status_change = Column(DateTime, default=datetime.utcnow)
    uplink = Column(BigInteger, default=0)
    downlink = Column(BigInteger, default=0)
    usage_coefficient = Column(Float, nullable=False, server_default=text("1.0"), default=1.0)
    panel_client_cert_pem = Column(String, nullable=True)
    panel_client_key_pem = Column(String, nullable=True)

    # Relationships
    user_usages = relationship("NodeUserUsage", back_populates="node", cascade="all, delete-orphan")
    usages = relationship("NodeUsage", back_populates="node", cascade="all, delete-orphan")
    service_configurations = relationship(
        "NodeServiceConfiguration",
        back_populates="node",
        cascade="all, delete-orphan"
    )


class NodeUserUsage(Base):
    __tablename__ = "node_user_usages"
    __table_args__ = (
        UniqueConstraint('created_at', 'user_id', 'node_id'),
    )

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, unique=False, nullable=False)  # one hour per record
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="node_usages")
    node_id = Column(Integer, ForeignKey("nodes.id"))
    node = relationship("Node", back_populates="user_usages")
    used_traffic = Column(BigInteger, default=0)


class NodeUsage(Base):
    __tablename__ = "node_usages"
    __table_args__ = (
        UniqueConstraint('created_at', 'node_id'),
    )

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, unique=False, nullable=False)  # one hour per record
    node_id = Column(Integer, ForeignKey("nodes.id"))
    node = relationship("Node", back_populates="usages")
    uplink = Column(BigInteger, default=0)
    downlink = Column(BigInteger, default=0)


class NotificationReminder(Base):
    __tablename__ = "notification_reminders"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="notification_reminders")
    type = Column(Enum(ReminderType), nullable=False)
    threshold = Column(Integer, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class NodeServiceConfiguration(Base):
    __tablename__ = "node_service_configurations"

    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(Integer, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False) # Ensure cascade delete

    service_name = Column(String(255), nullable=False, index=True, comment="User-friendly name for this service, e.g., 'US-VLESS-WS-TLS'")
    enabled = Column(Boolean, default=True, nullable=False)

    # Core Inbound Details
    protocol_type = Column(Enum(ProtocolType, name="protocol_type_enum"), nullable=False)
    listen_address = Column(String(255), nullable=True, default="0.0.0.0", comment="Listen IP on the node; null or 0.0.0.0 for all interfaces")
    listen_port = Column(Integer, nullable=False, comment="Listening port on the node for this service")

    # Stream Settings - Common
    network_type = Column(Enum(NetworkType, name="network_type_enum"), nullable=True, comment="Network type for stream settings (ws, grpc, etc.)")
    security_type = Column(Enum(SecurityType, name="security_type_enum"), nullable=False, default=SecurityType.NONE, comment="Security for stream settings (tls, reality)")

    # Stream Settings - Specific Paths/Identifiers (denormalized for ease of use and UI)
    ws_path = Column(String(255), nullable=True, comment="Path for WebSocket (e.g., /vless)")
    grpc_service_name = Column(String(255), nullable=True, comment="Service name for gRPC")
    http_upgrade_path = Column(String(255), nullable=True, comment="Path for HTTP/2 upgrade (if network_type is http)") # For h2

    # Security Settings - Common (denormalized for ease of use and UI)
    sni = Column(String(255), nullable=True, comment="Server Name Indication for TLS/REALITY")
    fingerprint = Column(String(255), nullable=True, comment="uTLS fingerprint or REALITY fingerprint")
    reality_short_id = Column(String(255), nullable=True, comment="REALITY short ID")
    reality_public_key = Column(String(255), nullable=True, comment="REALITY public key")
    # reality_private_key is sensitive and should ideally be managed on the node or securely pushed,
    # but if panel generates it, it needs secure storage or to be transient. For now, let's assume panel might store/provide public part.

    # Advanced/Raw JSON settings for full Xray compatibility
    # These allow storing parts of the Xray config that are not covered by specific fields
    # or for overriding behavior.
    # Note: User-specific client lists (like VLESS/VMess/Trojan 'clients') are NOT stored here.
    # They are generated at runtime when pushing config to the node, by combining these service
    # settings with the User.proxies data.

    advanced_protocol_settings = Column(JSON, nullable=True, comment="JSON for Xray 'settings' object (protocol-specific, e.g., VLESS decryption, fallbacks)")
    advanced_stream_settings = Column(JSON, nullable=True, comment="JSON for Xray 'streamSettings' (e.g., tcpSettings, kcpSettings, QUIC params, specific ws/grpc headers)")
    advanced_tls_settings = Column(JSON, nullable=True, comment="JSON for Xray 'tlsSettings' (e.g., ALPN, custom certs if not panel-managed)")
    advanced_reality_settings = Column(JSON, nullable=True, comment="JSON for Xray 'realitySettings' (e.g., spiderX, advanced REALITY params)")
    sniffing_settings = Column(JSON, nullable=True, comment="JSON for Xray 'sniffing' object")

    # Panel-generated tag for this inbound in the Xray config. Could be like "service-{id}-{protocol}"
    # Needs to be unique per Xray instance.
    xray_inbound_tag = Column(String(255), nullable=True, unique=False, index=True, comment="Internal Xray tag for this inbound; panel generates if null. Must be unique per node.")


    node = relationship("Node", back_populates="service_configurations")

    def __repr__(self):
        return f"<NodeServiceConfiguration(id={self.id}, name='{self.service_name}', node_id={self.node_id})>"


class Plan(Base):
    __tablename__ = "plans"

    id = Column(String(36), primary_key=True)
    name = Column(String(256), nullable=False)
    description = Column(String(1024), nullable=False)
    price = Column(Float, nullable=False)
    duration_days = Column(Integer, nullable=False)
    data_limit = Column(BigInteger, nullable=True)  # None means unlimited
    stripe_price_id = Column(String(256), nullable=True)
    features = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
