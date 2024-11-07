from dataclasses import dataclass


@dataclass
class IAMConfig:
    base_url: str
    client_id: str
    redirect_uri: str
    use_pkce_flow: bool
    username: str
    password: str


@dataclass
class IoTConfig:
    base_url: str
    installation_id: str
    gateway_id: str


@dataclass
class ViessmannConfig:
    iam: IAMConfig
    iot: IoTConfig


@dataclass
class Config:
    enabled: bool
    viessmann: ViessmannConfig
