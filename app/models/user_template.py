from typing import Dict, List, Optional

from pydantic import field_validator, ConfigDict, BaseModel, Field

from app import xray
from app.models.proxy import ProxyTypes
from app.db.models import NodeServiceConfiguration


class ServiceConfigurationResponse(BaseModel):
    id: int
    node_id: int
    service_name: str
    enabled: bool
    protocol_type: str
    listen_address: Optional[str] = None
    listen_port: int
    network_type: Optional[str] = None
    security_type: str
    ws_path: Optional[str] = None
    grpc_service_name: Optional[str] = None
    http_upgrade_path: Optional[str] = None
    sni: Optional[str] = None
    fingerprint: Optional[str] = None
    reality_short_id: Optional[str] = None
    reality_public_key: Optional[str] = None
    xray_inbound_tag: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UserTemplate(BaseModel):
    name: Optional[str] = Field(None, nullable=True)
    data_limit: Optional[int] = Field(
        ge=0, default=None, description="data_limit can be 0 or greater"
    )
    expire_duration: Optional[int] = Field(
        ge=0, default=None, description="expire_duration can be 0 or greater in seconds"
    )
    username_prefix: Optional[str] = Field(max_length=20, min_length=1, default=None)
    username_suffix: Optional[str] = Field(max_length=20, min_length=1, default=None)

    inbounds: Dict[ProxyTypes, List[str]] = {}
    service_configurations: List[ServiceConfigurationResponse] = []

    model_config = ConfigDict(from_attributes=True)


class UserTemplateCreate(UserTemplate):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "my template 1",
            "username_prefix": None,
            "username_suffix": None,
            "inbounds": {"vmess": ["VMESS_INBOUND"], "vless": ["VLESS_INBOUND"]},
            "data_limit": 0,
            "expire_duration": 0,
        }
    })


class UserTemplateModify(UserTemplate):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "my template 1",
            "username_prefix": None,
            "username_suffix": None,
            "inbounds": {"vmess": ["VMESS_INBOUND"], "vless": ["VLESS_INBOUND"]},
            "data_limit": 0,
            "expire_duration": 0,
        }
    })


class UserTemplateResponse(UserTemplate):
    id: int

    @field_validator("inbounds", mode="before")
    @classmethod
    def validate_inbounds(cls, v):
        final = {}
        if isinstance(v, list) and all(isinstance(i, NodeServiceConfiguration) for i in v):
            inbound_tags = [i.xray_inbound_tag for i in v if i.xray_inbound_tag]
        else:
            inbound_tags = [i.tag for i in v] if isinstance(v, list) else []

        for protocol, inbounds in xray.config.inbounds_by_protocol.items():
            for inbound in inbounds:
                if inbound["tag"] in inbound_tags:
                    if protocol in final:
                        final[protocol].append(inbound["tag"])
                    else:
                        final[protocol] = [inbound["tag"]]
        return final
    model_config = ConfigDict(from_attributes=True)
