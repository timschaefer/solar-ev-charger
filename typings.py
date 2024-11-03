from dataclasses import dataclass
from typing import Optional

@dataclass
class Config:
    enabled: bool
    api_url: Optional[str] = None