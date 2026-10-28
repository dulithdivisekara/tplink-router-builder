"""Data models for SMS messages and USSD execution results."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class SMSMessage:
    index: int
    sender: str
    content: str
    received_time: str
    unread: bool = False
    folder: str = "inbox"


@dataclass
class USSDResult:
    command: str
    response: str
    success: bool = True
    error_message: Optional[str] = None
