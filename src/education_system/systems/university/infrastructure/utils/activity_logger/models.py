import json
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum


class LogLevel(Enum):
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class OutputFormat(Enum):
    JSON = "json"
    CSV = "csv"
    DATABASE = "database"
    SYSLOG = "syslog"
    CLOUD = "cloud"


class SecurityLevel(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class LogEntry:
    """Enhanced log entry with comprehensive metadata"""
    timestamp: str
    user_id: str
    username: str
    role: str
    action: str
    module: str
    details: str
    status: str
    log_level: str
    session_id: str
    ip_address: str
    user_agent: str
    request_size: int
    response_size: int
    processing_time: float
    geolocation: Dict[str, str]
    security_level: str
    trace_id: str
    stack_trace: Optional[str] = None
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
