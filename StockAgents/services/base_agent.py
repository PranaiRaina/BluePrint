from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseAgent(ABC):
    """
    Abstract base class for all autonomous sub-agents.
    """

    def __init__(self, name: str, client: Any):
        self.name = name
        self.client = client

    @abstractmethod
    async def run(self, task: str) -> Dict[str, Any]:
        """
        Execute the agent's main logic based on the input task.
        Returns a dictionary containing the analysis and raw data.
        """
        pass
