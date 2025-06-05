from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator

from app.models.protocol_types import ProtocolType, NetworkType, SecurityType


class NodeServiceConfigurationBase(BaseModel):
    service_name: str = Field(..., min_length=1, max_length=255, description="User-friendly name for this service configuration")
    enabled: bool = True

    protocol_type: ProtocolType
    listen_address: Optional[str] = Field("0.0.0.0", max_length=255, description="Listen IP on the node; null or 0.0.0.0 for all interfaces")
    listen_port: int = Field(..., gt=0, le=65535, description="Listening port on the node")

    network_type: Optional[NetworkType] = Field(None, description="Network type for stream settings (ws, grpc, etc.)")
    security_type: SecurityType = Field(SecurityType.NONE, description="Security for stream settings (tls, reality)")

    ws_path: Optional[str] = Field(None, max_length=255, description="Path for WebSocket (e.g., /vless). Must start with '/' if set.")
    grpc_service_name: Optional[str] = Field(None, max_length=255, description="Service name for gRPC")
    http_upgrade_path: Optional[str] = Field(None, max_length=255, description="Path for HTTP/2 upgrade. Must start with '/' if set.")


    sni: Optional[str] = Field(None, max_length=255, description="Server Name Indication for TLS/REALITY")
    fingerprint: Optional[str] = Field(None, max_length=255, description="uTLS fingerprint (for TLS) or REALITY fingerprint")
    reality_short_id: Optional[str] = Field(None, max_length=255, description="REALITY short ID")
    reality_public_key: Optional[str] = Field(None, max_length=255, description="REALITY public key")

    advanced_protocol_settings: Optional[Dict[str, Any]] = Field(None, description="JSON for Xray 'settings' object (e.g., VLESS decryption, fallbacks)")
    advanced_stream_settings: Optional[Dict[str, Any]] = Field(None, description="JSON for Xray 'streamSettings' (e.g., tcpSettings, custom ws/grpc headers)")
    advanced_tls_settings: Optional[Dict[str, Any]] = Field(None, description="JSON for Xray 'tlsSettings' (e.g., ALPN)")
    advanced_reality_settings: Optional[Dict[str, Any]] = Field(None, description="JSON for Xray 'realitySettings' (e.g., spiderX)")
    sniffing_settings: Optional[Dict[str, Any]] = Field(None, description="JSON for Xray 'sniffing' object")

    xray_inbound_tag: Optional[str] = Field(None, max_length=255, description="Optional: custom Xray tag for this inbound. Panel generates if empty.")

    @field_validator('ws_path', 'http_upgrade_path', mode='before')
    @classmethod
    def validate_paths_start_with_slash(cls, v: Optional[str], info) -> Optional[str]:
        if v is not None:
            if not isinstance(v, str):
                raise ValueError(f"{info.field_name} must be a string")
            if not v.startswith('/'):
                raise ValueError(f"{info.field_name} must start with '/'")
            if info.data.get('network_type') == NetworkType.WS and info.field_name == 'http_upgrade_path':
                raise ValueError("http_upgrade_path is not applicable when network_type is ws")
            if info.data.get('network_type') == NetworkType.HTTP and info.field_name == 'ws_path':
                raise ValueError("ws_path is not applicable when network_type is http (h2)")
        return v

    @field_validator('network_type', mode='before')
    @classmethod
    def check_network_specific_fields(cls, v: Optional[NetworkType], info) -> Optional[NetworkType]:
        if v == NetworkType.WS and not info.data.get('ws_path'):
            pass  # UI can enforce this, or generate a default path
        if v == NetworkType.GRPC and not info.data.get('grpc_service_name'):
            pass
        if v == NetworkType.HTTP and not info.data.get('http_upgrade_path'):
            pass
        if v != NetworkType.WS and info.data.get('ws_path'):
            raise ValueError("ws_path is only applicable for WS network type")
        if v != NetworkType.GRPC and info.data.get('grpc_service_name'):
            raise ValueError("grpc_service_name is only applicable for gRPC network type")
        if v != NetworkType.HTTP and info.data.get('http_upgrade_path'):
            raise ValueError("http_upgrade_path is only applicable for HTTP (h2) network type")
        return v

    @field_validator('security_type', mode='before')
    @classmethod
    def check_security_specific_fields(cls, v: SecurityType, info) -> SecurityType:
        if v in [SecurityType.TLS, SecurityType.REALITY] and not info.data.get('sni'):
            pass  # Can be made optional if Xray allows
        if v == SecurityType.REALITY and not info.data.get('reality_public_key'):
            pass  # Can be made optional if Xray allows
        return v


class NodeServiceConfigurationCreate(NodeServiceConfigurationBase):
    pass

class NodeServiceConfigurationUpdate(NodeServiceConfigurationBase):
    # Make all fields optional for updates
    service_name: Optional[str] = Field(None, min_length=1, max_length=255)
    enabled: Optional[bool] = None
    protocol_type: Optional[ProtocolType] = None
    listen_address: Optional[str] = Field(None, max_length=255)
    listen_port: Optional[int] = Field(None, gt=0, le=65535)
    network_type: Optional[NetworkType] = None
    security_type: Optional[SecurityType] = None
    ws_path: Optional[str] = Field(None, max_length=255)
    grpc_service_name: Optional[str] = Field(None, max_length=255)
    http_upgrade_path: Optional[str] = Field(None, max_length=255)
    sni: Optional[str] = Field(None, max_length=255)
    fingerprint: Optional[str] = Field(None, max_length=255)
    reality_short_id: Optional[str] = Field(None, max_length=255)
    reality_public_key: Optional[str] = Field(None, max_length=255)
    # advanced settings...
    advanced_protocol_settings: Optional[Dict[str, Any]] = None
    advanced_stream_settings: Optional[Dict[str, Any]] = None
    advanced_tls_settings: Optional[Dict[str, Any]] = None
    advanced_reality_settings: Optional[Dict[str, Any]] = None
    sniffing_settings: Optional[Dict[str, Any]] = None
    xray_inbound_tag: Optional[str] = Field(None, max_length=255)


class NodeServiceConfigurationResponse(NodeServiceConfigurationBase):
    id: int
    node_id: int
    # Ensure xray_inbound_tag is always present in response, potentially generated by backend if not provided
    xray_inbound_tag: Optional[str] # Or str if guaranteed by backend

    class Config:
        from_attributes = True