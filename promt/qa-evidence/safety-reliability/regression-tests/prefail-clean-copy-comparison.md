# Pre-existing backend failures — clean-copy comparison (closure gate)

Date: 2026-10-10. Branch HEAD 22e772f vs pristine baseline 986e25f,
each in an isolated `git worktree` (removed afterwards).

## Result: IDENTICAL on both — pre-existing, environment-dependent.

- test_genio_core.py::TestPlanning::test_parse_plan_injects_auditor
- test_genio_core.py::TestEndToEndDryRun::test_pipeline_dispatch

Neither is introduced by fix/safety-reliability-gate (no diff touches
planning, config, or the tutorial pipeline).

## Traceback 1 (both copies)

engine = PlanningEngine()
genio_executive_core.py:236: self.router = router or LLMRouter()
/data/ai_tools/llm_utils.py:223: self.ollama_client = LLMClient("ollama")
/data/ai_tools/llm_utils.py:26:
    self.model = model or self.config.ollama.model
E   AttributeError: 'OllamaConfig' object has no attribute 'model'

Root cause: EXTERNAL shared module /data/ai_tools/llm_utils.py
(outside this repo) expects config field `ollama.model` that the
installed config does not provide. Environment-dependent; fails
before any repo code under review executes.

## Traceback 2 (both copies)

results, ctx = run(scenario())
E AssertionError: {'final_audit': None,
E                  'preflight_env': 'Critical service(s) down',
E                  'write_tutorial': None}

Root cause: the `preflight_env` node probes live critical services and
reports them down in THIS environment (sandbox/cięcie services not
running). Environment-dependent integration assertion, unrelated to
the safety diff.

## Verdict

Both: PRE-EXISTING + ENVIRONMENTAL. Not suppressed: they remain
failing, deselected only with explicit names in suite runs, and are
recorded here with tracebacks. No action in this branch.
