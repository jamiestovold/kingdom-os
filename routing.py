"""
Kingdom Core — Agent Routing
Assigns the correct agent to a task based on task_type.

Routing rules:
- architecture  → claude   (needs deep reasoning)
- review        → codex    (independent code challenge)
- research      → claude   (needs synthesis and judgment)
- analysis      → claude   (needs interpretation)
- build         → local_llm (mechanical code generation, free)
- test          → codex    (code-heavy, independent)
- document      → local_llm (repetitive, mechanical)
- infra         → script   (no AI needed, pure system operation)
- general       → claude   (default to most capable)
"""

ROUTING_TABLE = {
    "general":      "claude",
    "architecture": "claude",
    "review":       "codex",
    "research":     "claude",
    "analysis":     "claude",
    "build":        "local_llm",
    "test":         "codex",
    "document":     "local_llm",
    "infra":        "script",
}


def assign_agent(task_type: str) -> str:
    """
    Returns the agent name for a given task_type.
    Falls back to claude if task_type is unrecognised.
    """
    return ROUTING_TABLE.get(task_type, "claude")
