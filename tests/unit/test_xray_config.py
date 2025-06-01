import pytest
from unittest.mock import Mock, patch
from app.xray.config import XRayConfig
from app.models.proxy import ProxyTypes
from app.db.models import NodeServiceConfiguration, User, Node, SecurityType
from app.models.user import UserStatus


# Fixtures for common test data
@pytest.fixture
def mock_node():
    node = Mock(spec=Node)
    node.id = 1
    node.name = "Test Node"
    node.api_port = 62051
    return node

@pytest.fixture
def mock_vless_service():
    service = Mock(spec=NodeServiceConfiguration)
    service.id = 1
    service.protocol_type = ProxyTypes.VLESS
    service.network_type = "tcp"
    service.security_type = SecurityType.TLS
    service.listen_address = "0.0.0.0"
    service.listen_port = 443
    service.sni = "example.com"
    service.enabled = True
    service.xray_inbound_tag = "vless_tls"
    service.advanced_protocol_settings = {}
    service.advanced_fallback_settings_json = {}
    service.advanced_stream_settings = {}
    service.advanced_tls_settings = {}
    service.advanced_sniffing_settings_json = None
    return service

@pytest.fixture
def mock_vmess_service():
    service = Mock(spec=NodeServiceConfiguration)
    service.id = 2
    service.protocol_type = ProxyTypes.VMess
    service.network_type = "ws"
    service.security_type = SecurityType.NONE
    service.listen_address = "0.0.0.0"
    service.listen_port = 8080
    service.ws_path = "/vmess"
    service.enabled = True
    service.xray_inbound_tag = "vmess_ws"
    service.advanced_protocol_settings = {}
    service.advanced_fallback_settings_json = {}
    service.advanced_stream_settings = {}
    service.advanced_tls_settings = {}
    service.advanced_sniffing_settings_json = None
    return service

@pytest.fixture
def mock_user():
    user = Mock(spec=User)
    user.id = 1
    user.account_number = "test123"
    user.status = UserStatus.active
    user.proxies = []
    return user

class TestXRayConfig:
    def test_generate_inbound_dict_vless_tls(self, mock_vless_service, mock_user):
        # Setup VLESS proxy settings for the user
        vless_proxy = Mock()
        vless_proxy.type = ProxyTypes.VLESS
        vless_proxy.settings = {
            "id": "test-uuid",
            "flow": "xtls-rprx-vision"
        }
        mock_user.proxies = [vless_proxy]

        config = XRayConfig()
        inbound_dict = config._generate_inbound_dict(mock_vless_service, [mock_user])

        assert inbound_dict["tag"] == "vless_tls"
        assert inbound_dict["protocol"] == "vless"
        assert inbound_dict["port"] == 443
        assert inbound_dict["listen"] == "0.0.0.0"

        # Check stream settings
        stream_settings = inbound_dict["streamSettings"]
        assert stream_settings["network"] == "tcp"
        assert stream_settings["security"] == "tls"
        assert "tlsSettings" in stream_settings
        assert stream_settings["tlsSettings"]["serverName"] == "example.com"

        # Check client settings
        clients = inbound_dict["settings"]["clients"]
        assert len(clients) == 1
        client = clients[0]
        assert client["email"] == "1.test123"
        assert client["id"] == "test-uuid"
        assert client["flow"] == "xtls-rprx-vision"

    def test_generate_inbound_dict_vmess_ws(self, mock_vmess_service, mock_user):
        # Setup VMess proxy settings for the user
        vmess_proxy = Mock()
        vmess_proxy.type = ProxyTypes.VMess
        vmess_proxy.settings = {
            "id": "test-uuid",
            "alterId": 0
        }
        mock_user.proxies = [vmess_proxy]

        config = XRayConfig()
        inbound_dict = config._generate_inbound_dict(mock_vmess_service, [mock_user])

        assert inbound_dict["tag"] == "vmess_ws"
        assert inbound_dict["protocol"] == "vmess"
        assert inbound_dict["port"] == 8080
        assert inbound_dict["listen"] == "0.0.0.0"

        # Check stream settings
        stream_settings = inbound_dict["streamSettings"]
        assert stream_settings["network"] == "ws"
        assert "wsSettings" in stream_settings
        assert stream_settings["wsSettings"]["path"] == "/vmess"

        # Check client settings
        clients = inbound_dict["settings"]["clients"]
        assert len(clients) == 1
        client = clients[0]
        assert client["email"] == "1.test123"
        assert client["id"] == "test-uuid"
        assert client["alterId"] == 0

    def test_build_node_config(self, mock_node, mock_vless_service, mock_vmess_service, mock_user):
        # Setup node with multiple services
        mock_node.service_configurations = [mock_vless_service, mock_vmess_service]

        # Setup user with both VLESS and VMess proxies
        vless_proxy = Mock()
        vless_proxy.type = ProxyTypes.VLESS
        vless_proxy.settings = {"id": "vless-uuid", "flow": "xtls-rprx-vision"}

        vmess_proxy = Mock()
        vmess_proxy.type = ProxyTypes.VMess
        vmess_proxy.settings = {"id": "vmess-uuid", "alterId": 0}

        mock_user.proxies = [vless_proxy, vmess_proxy]

        config = XRayConfig()
        node_config = config.build_node_config(mock_node, [mock_user])

        # Check API inbound
        api_inbound = next(inb for inb in node_config["inbounds"] if inb["tag"] == "API_GRPC_INBOUND")
        assert api_inbound["port"] == 62051
        assert api_inbound["protocol"] == "dokodemo-door"

        # Check service inbounds
        service_inbounds = [inb for inb in node_config["inbounds"] if inb["tag"] in ["vless_tls", "vmess_ws"]]
        assert len(service_inbounds) == 2

        # Verify VLESS inbound
        vless_inbound = next(inb for inb in service_inbounds if inb["tag"] == "vless_tls")
        assert vless_inbound["protocol"] == "vless"
        assert len(vless_inbound["settings"]["clients"]) == 1
        assert vless_inbound["settings"]["clients"][0]["id"] == "vless-uuid"

        # Verify VMess inbound
        vmess_inbound = next(inb for inb in service_inbounds if inb["tag"] == "vmess_ws")
        assert vmess_inbound["protocol"] == "vmess"
        assert len(vmess_inbound["settings"]["clients"]) == 1
        assert vmess_inbound["settings"]["clients"][0]["id"] == "vmess-uuid"

        # Check policy and stats
        assert "policy" in node_config
        assert "stats" in node_config
        assert "routing" in node_config

    def test_build_node_config_no_users(self, mock_node, mock_vless_service):
        # Setup node with a service but no users
        mock_node.service_configurations = [mock_vless_service]

        config = XRayConfig()
        node_config = config.build_node_config(mock_node, [])

        # Should only have API inbound
        assert len(node_config["inbounds"]) == 1
        assert node_config["inbounds"][0]["tag"] == "API_GRPC_INBOUND"

    def test_build_node_config_disabled_service(self, mock_node, mock_vless_service, mock_user):
        # Setup disabled service
        mock_vless_service.enabled = False
        mock_node.service_configurations = [mock_vless_service]

        # Setup user with VLESS proxy
        vless_proxy = Mock()
        vless_proxy.type = ProxyTypes.VLESS
        vless_proxy.settings = {"id": "test-uuid"}
        mock_user.proxies = [vless_proxy]

        config = XRayConfig()
        node_config = config.build_node_config(mock_node, [mock_user])

        # Should only have API inbound
        assert len(node_config["inbounds"]) == 1
        assert node_config["inbounds"][0]["tag"] == "API_GRPC_INBOUND"