"""Print the JSON Schema of every NEXUS event (envelope + typed payload) to stdout.

The frontend generates its TypeScript event types from this file
(`make types`), so both sides share one source of truth.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, create_model

from nexus.core.event_types import PAYLOADS


def schema() -> dict[str, Any]:
    variants: list[type[BaseModel]] = []
    for event_type, payload in PAYLOADS.items():
        name = (
            "".join(part.capitalize() for part in event_type.replace(".", "_").split("_")) + "Event"
        )
        variants.append(
            create_model(
                name,
                id=(str, ...),
                seq=(int, ...),
                mission_id=(str | None, None),
                thread_id=(str | None, None),
                checkpoint_id=(str | None, None),
                ts=(float, ...),
                agent_id=(str | None, None),
                node=(str | None, None),
                type=(Literal[event_type], ...),  # type: ignore[arg-type]
                payload=(payload, ...),
            )
        )
    defs: dict[str, Any] = {}
    one_of = []
    for v in variants:
        s = v.model_json_schema(ref_template="#/$defs/{model}")
        defs.update(s.pop("$defs", {}))
        defs[v.__name__] = s
        one_of.append({"$ref": f"#/$defs/{v.__name__}"})
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "NexusEvent",
        "oneOf": one_of,
        "$defs": defs,
    }


if __name__ == "__main__":
    print(json.dumps(schema(), indent=2))
