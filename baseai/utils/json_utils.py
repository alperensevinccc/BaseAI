import json
from typing import Any, Dict


def json_to_dict(json_string: str) -> Dict[str, Any]:
    return json.loads(json_string)


def dict_to_json(data: Dict[str, Any]) -> str:
    return json.dumps(data, indent=4)
