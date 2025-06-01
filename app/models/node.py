from enum import Enum
from typing import List, Optional

from pydantic import ConfigDict, BaseModel, Field
from app.models.node_service import NodeServiceConfigurationResponse


class NodeStatus(str, Enum):
    connected = "connected"
    connecting = "connecting"
    error = "error"
    disabled = "disabled"


class NodeSettings(BaseModel):
    min_node_version: str = "v0.2.0"
    certificate: str


class Node(BaseModel):
    name: str
    address: str
    port: int = 62050
    api_port: int = 62051
    usage_coefficient: float = Field(gt=0, default=1.0)
    panel_client_cert_pem: Optional[str] = None
    panel_client_key_pem: Optional[str] = None


class NodeCreate(Node):
    panel_client_cert: Optional[str] = None  # Frontend field name
    panel_client_key: Optional[str] = None   # Frontend field name
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "DE node",
            "address": "192.168.1.1",
            "port": 62050,
            "api_port": 62051,
            "usage_coefficient": 1,
            "panel_client_cert": "-----BEGIN CERTIFICATE-----\n...",
            "panel_client_key": "-----BEGIN PRIVATE KEY-----\n..."
        }
    })

    def model_post_init(self, __context) -> None:
        # Map frontend field names to backend field names
        if self.panel_client_cert:
            self.panel_client_cert_pem = self.panel_client_cert
        if self.panel_client_key:
            self.panel_client_key_pem = self.panel_client_key
        super().model_post_init(__context)


class NodeModify(Node):
    name: Optional[str] = Field(None, nullable=True)
    address: Optional[str] = Field(None, nullable=True)
    port: Optional[int] = Field(None, nullable=True)
    api_port: Optional[int] = Field(None, nullable=True)
    status: Optional[NodeStatus] = Field(None, nullable=True)
    usage_coefficient: Optional[float] = Field(None, nullable=True)
    panel_client_cert: Optional[str] = Field(None, nullable=True)  # Frontend field name
    panel_client_key: Optional[str] = Field(None, nullable=True)   # Frontend field name
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "DE node",
            "address": "192.168.1.1",
            "port": 62050,
            "api_port": 62051,
            "status": "disabled",
            "usage_coefficient": 1.0,
            "panel_client_cert": "-----BEGIN CERTIFICATE-----\n...",
            "panel_client_key": "-----BEGIN PRIVATE KEY-----\n..."
        }
    })


class NodeResponse(Node):
    id: int
    xray_version: Optional[str] = None
    status: NodeStatus
    message: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)
    service_configurations: List[NodeServiceConfigurationResponse] = []



class NodeUsageResponse(BaseModel):
    node_id: Optional[int] = None
    node_name: str
    uplink: int
    downlink: int


class NodesUsageResponse(BaseModel):
    usages: List[NodeUsageResponse]
