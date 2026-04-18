import os


def writes_allowed() -> bool:
    return os.environ.get("MCP_ALLOW_WRITES", "false").lower() == "true"


def check_write_gate() -> None:
    if not writes_allowed():
        raise ValueError(
            "Write operations are disabled. Set MCP_ALLOW_WRITES=true in .env to enable."
        )
