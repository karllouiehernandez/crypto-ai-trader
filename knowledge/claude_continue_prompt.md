# Claude Continuation Prompt

Use this exact prompt when handing the repo to Claude Code.

```text
Read HANDOFF.md first, then knowledge/agent_resume.md. Treat Codex and Claude Code as one shared developer stream on the same branch and workspace.

Do not revert, overwrite, or "clean up" existing Codex work unless the user explicitly asks. Before editing, run git status --short and inspect the current dirty files. Treat them as shared state.

Hard safety rules:
1. Stay on branch codex/sprint-27-responsive-chart unless the user explicitly asks otherwise.
2. Do not run git reset --hard, git checkout -- <file>, or delete uncommitted files.
3. Do not edit or stage knowledge/experiment_log.md unless you intentionally stop the runtime process writing to it.
4. Do not stage runtime-generated reports/ or .streamlit_eval.* artifacts unless the user explicitly asks.
5. Pytest must use the repo's tests/conftest.py temp-DB isolation. Do not point tests at the live app DB.
6. Do not clear active paper/live artifact settings as incidental test cleanup.

Current protected baseline:
- protection commit: b207a44
- pytest tests/ -q -> 614 passed, 4 warnings
- python run_ui_agent.py --data-only -> 0 FAIL, 2 PARTIAL, 1 SKIP
- maintained MVP universe restored to 30 days for BTCUSDT, ETHUSDT, BNBUSDT
- active paper target should be rsi_mean_reversion_v1 artifact #2 unless the user explicitly changes it

Continue Sprint 42 from the next priority in HANDOFF.md. Update HANDOFF.md last with what you changed, what you verified, and what remains next.
```
