from app.services.llm import _strict_response_schema
from app.services.supervisor_v4 import PerspectiveDiscoveryOutput


def test_strict_response_schema_requires_every_object_property():
    schema = _strict_response_schema(PerspectiveDiscoveryOutput.model_json_schema())

    def assert_strict(node):
        if isinstance(node, dict):
            if node.get("type") == "object" or "properties" in node:
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node.get("properties", {}))
            assert "default" not in node
            for value in node.values():
                assert_strict(value)
        elif isinstance(node, list):
            for value in node:
                assert_strict(value)

    assert_strict(schema)
