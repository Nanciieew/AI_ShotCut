"""Base provider interface."""

from abc import ABC, abstractmethod


class BaseProvider(ABC):
    @abstractmethod
    def send(self, messages: list[dict], **kwargs) -> dict: ...
    @abstractmethod
    def health_check(self) -> bool: ...
