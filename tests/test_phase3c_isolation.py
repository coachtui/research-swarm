"""Phase 3C isolation: Sleeve B stays the control group; the strategist
never sees funnel data. These tests are permanent tripwires.

Note on the leak-word list in test_strategist_prompt_never_mentions_funnel_keys:
"conviction" is deliberately excluded from the checked words. The strategist
has legitimately emitted a "conviction" score in its own JSON response schema
since Phase 1 (see execution/strategist/prompts.py, the
`"conviction": <float 0.0-1.0>` field in the response contract) — that is a
pre-existing, unrelated use of the word, not a Sleeve-A funnel signal leak.
Checking for it would make this test permanently fail on legitimate code, so
the list below is narrowed to funnel-specific vocabulary instead.
"""
import ast
import pathlib

_CONTROL_GROUP_FILES = [
    "execution/engine/sleeve_b.py",
    "execution/engine/orders.py",
    "inngest_app/functions/execution_weekly.py",
]


def test_sleeve_b_code_never_imports_funnel_modules():
    """Sleeve B control-group files must never import funnel modules or the
    shadow broker. For ImportFrom we check node.module AND the qualified
    module.alias names, so evasive forms like `from execution import funnel`
    or `from execution.broker import shadow_client` are also flagged (the
    submodule name lives only in the alias, not node.module) — verified by
    ast-parsing both forms and confirming the walker flags them."""
    for rel in _CONTROL_GROUP_FILES:
        tree = ast.parse(pathlib.Path(rel).read_text())
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = [module] + [
                    f"{module}.{a.name}" if module else a.name
                    for a in node.names
                ]
            for name in names:
                assert not name.startswith("execution.funnel"), (
                    f"{rel} imports {name} — Sleeve B is the control group"
                )
                assert "shadow_client" not in name, f"{rel} imports the shadow broker"


def test_strategist_prompt_never_mentions_funnel_keys():
    src = pathlib.Path("execution/strategist/prompts.py").read_text()
    for leak in ("funnel", "entry_queue", "shadow", "engine_light", "sleeve_a"):
        assert leak not in src.lower(), (
            f"strategist prompt module references '{leak}' — Sleeve A signal leak"
        )
