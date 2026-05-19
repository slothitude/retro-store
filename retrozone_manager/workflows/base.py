"""BaseWorkflow ABC — name, steps, prompt builders."""
from abc import ABC, abstractmethod
from ..db_layer import StoreDB


class BaseWorkflow(ABC):
    """Base class for all workflows. Subclass and implement methods."""

    name: str = "Unnamed Workflow"
    description: str = ""
    risk_level: str = "low"  # default risk for proposals

    def __init__(self):
        self.db = StoreDB()

    @abstractmethod
    def get_steps(self) -> list:
        """Return list of step dicts:
        [{"name": "Step Name", "type": "analyze"|"propose"|"execute",
          "prompt": "...", "system_extra": "..."}]
        """
        pass

    @abstractmethod
    def build_analyze_prompt(self) -> str:
        """Build the analysis prompt for Claude."""
        pass

    def build_propose_prompt(self, analyze_result: str) -> str:
        """Build the proposal prompt. Override if workflow has a propose step."""
        return (
            f"Based on your analysis:\n{analyze_result}\n\n"
            "Propose specific actions as a JSON array. Each action MUST have:\n"
            '- "description": what to do (plain English)\n'
            '- "reason": why\n'
            '- "sql": the exact SQL statement\n'
            '- "reversible": true/false\n'
            '- "risk": "low"/"medium"/"high"\n\n'
            "Return ONLY the JSON array, no other text."
        )

    def parse_proposals(self, claude_response: str) -> list:
        """Parse Claude's response into action dicts."""
        import json
        import re

        # Try to extract JSON from response
        text = claude_response.strip()

        # Look for JSON array in the response
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            try:
                actions = json.loads(match.group())
                return actions
            except json.JSONDecodeError:
                pass

        # Fallback: treat entire response as a single informational action
        return [{
            "description": "Review Claude's analysis (no executable actions parsed)",
            "reason": text[:200],
            "sql": "—",
            "reversible": True,
            "risk": "low",
        }]

    def execute_action(self, action: dict):
        """Execute an approved action in the database. Override for custom logic."""
        sql = action.get("sql", "")
        if sql and sql != "—":
            conn = self.db._conn()
            try:
                conn.execute(sql)
                conn.commit()
            finally:
                conn.close()
