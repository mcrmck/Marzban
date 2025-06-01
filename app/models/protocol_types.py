import enum

class ProtocolType(str, enum.Enum):
    VLESS = "vless"
    VMESS = "vmess"
    TROJAN = "trojan"
    SHADOWSOCKS = "shadowsocks"
    HTTP = "http"
    SOCKS = "socks"

class NetworkType(str, enum.Enum):
    TCP = "tcp"
    KCP = "kcp"
    WS = "ws"
    HTTP = "http"  # Represents HTTP/2 (h2) for streamSettings
    GRPC = "grpc"
    QUIC = "quic"
    # DOMAINSOCKET is likely not needed for remote nodes

class SecurityType(str, enum.Enum):
    NONE = "none"
    TLS = "tls"
    REALITY = "reality"