import logging
from unittest.mock import MagicMock

import pytest

from jarvis.config import JarvisConfig
from jarvis.reasoning import PlanningResponseError, ReasoningModule

# Configure logging to capture output during tests
logging.basicConfig(level=logging.DEBUG)


class TestReasoningModuleParsing:
    @pytest.fixture
    def reasoning_module(self):
        config = MagicMock(spec=JarvisConfig)
        llm_client = MagicMock()
        return ReasoningModule(config, llm_client)

    def test_parse_valid_json(self, reasoning_module):
        response_text = (
            '{"description": "Test Plan", "steps": [{"step_number": 1, "description": "Step 1"}]}'
        )
        parsed = reasoning_module._parse_planning_response(response_text)
        assert parsed["description"] == "Test Plan"
        assert len(parsed["steps"]) == 1

    def test_parse_markdown_json(self, reasoning_module):
        response_text = """Here is the plan:
```json
{
    "description": "Markdown Plan",
    "steps": []
}
```
Hope this helps."""
        parsed = reasoning_module._parse_planning_response(response_text)
        assert parsed["description"] == "Markdown Plan"

    def test_parse_single_quotes_json(self, reasoning_module):
        # This should now succeed with repair
        response_text = "{'description': 'Single Quote Plan', 'steps': []}"
        parsed = reasoning_module._parse_planning_response(response_text)
        assert parsed["description"] == "Single Quote Plan"

    def test_parse_trailing_commas(self, reasoning_module):
        # This should now succeed with repair
        response_text = '{"description": "Trailing Comma", "steps": [],}'
        parsed = reasoning_module._parse_planning_response(response_text)
        assert parsed["description"] == "Trailing Comma"

    def test_parse_mixed_quotes(self, reasoning_module):
        # Testing key normalization and value normalization
        response_text = (
            "{'description': \"Mixed Quotes\", "
            "'steps': [{'step_number': 1, 'description': 'Do something'}]}"
        )
        parsed = reasoning_module._parse_planning_response(response_text)
        assert parsed["description"] == "Mixed Quotes"
        assert parsed["steps"][0]["description"] == "Do something"

    def test_parse_truncated_json_raises(self, reasoning_module):
        # Truncated string inside JSON usually cannot be repaired easily without complex logic
        # So we expect this to raise PlanningResponseError
        response_text = (
            '{"description": "Truncated Plan", "steps": [{"step_number": 1, "description": "Ste'
        )
        with pytest.raises(PlanningResponseError):
            reasoning_module._parse_planning_response(response_text)

    def test_parse_unbalanced_braces_repaired(self, reasoning_module):
        # Missing closing brace
        response_text = '{"description": "Unbalanced", "steps": []'
        parsed = reasoning_module._parse_planning_response(response_text)
        assert parsed["description"] == "Unbalanced"

    def test_plan_actions_fallback_on_bad_json(self, reasoning_module):
        reasoning_module.llm_client.generate.return_value = "This is not JSON at all."
        reasoning_module.config.safety = MagicMock()
        reasoning_module.config.safety.enable_input_validation = False

        plan = reasoning_module.plan_actions("Do something")

        assert plan.description.startswith("Fallback plan")
        assert len(plan.steps) == 3  # Default fallback has 3 steps
