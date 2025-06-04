export enum ProtocolType {
    VLESS = "vless",
    VMESS = "vmess",
    TROJAN = "trojan",
    SHADOWSOCKS = "shadowsocks",
    HTTP = "http",
    SOCKS = "socks",
}

export enum NetworkType {
    TCP = "tcp",
    KCP = "kcp",
    WS = "ws",
    HTTP = "http", // h2
    GRPC = "grpc",
    QUIC = "quic",
}

export enum SecurityType {
    NONE = "none",
    TLS = "tls",
    REALITY = "reality",
}

export interface NodeServiceConfigurationBase {
    service_name: string;
    enabled: boolean;
    protocol_type: ProtocolType;
    listen_address?: string | null;
    listen_port: number;
    network_type?: NetworkType | null;
    security_type: SecurityType;
    ws_path?: string | null;
    grpc_service_name?: string | null;
    http_upgrade_path?: string | null; // For h2
    sni?: string | null;
    fingerprint?: string | null;
    reality_short_id?: string | null;
    reality_public_key?: string | null;
    advanced_protocol_settings?: Record<string, any> | null;
    advanced_stream_settings?: Record<string, any> | null;
    advanced_tls_settings?: Record<string, any> | null;
    advanced_reality_settings?: Record<string, any> | null;
    sniffing_settings?: Record<string, any> | null;
    xray_inbound_tag?: string | null;
}

export interface NodeServiceConfigurationCreate extends NodeServiceConfigurationBase {}

export interface NodeServiceConfigurationUpdate extends Partial<NodeServiceConfigurationBase> {} // All fields optional

export interface NodeServiceConfigurationResponse extends NodeServiceConfigurationBase {
    id: number;
    node_id: number;
}