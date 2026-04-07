from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ToolResult:
    success: bool
    output: str


class BaseTool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def execute(self, params: dict) -> ToolResult: ...

    def validate(self, params: dict) -> str | None:
        return None
