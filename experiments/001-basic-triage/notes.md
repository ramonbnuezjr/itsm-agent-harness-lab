# Experiment 001: Basic Triage

## Objective

Validate the v0.1 path from synthetic incident input through KB retrieval, model tool use, citation enforcement, and local audit logging.

## Environment

- Date: September 11, 2026
- Runtime: Python 3.11 virtual environment
- Model: `gpt-4o-mini`
- Data: synthetic VPN incident and local sample runbooks
- Provider storage: disabled with `store=False`

## Results

- Thirteen offline tests passed.
- The live model called `search_kb` and retrieved `vpn-access.md`.
- The final recommendation included `[vpn-access.md]`.
- The citation policy passed.
- Audit event `d55600ac-3e55-4ebd-93e7-6e15711aa3b5` was written locally.
- The API key was not present in the audit record.

## Failure Observed

The first live attempt failed during DNS resolution because the execution sandbox did not permit network access. No application code changed. Repeating the same command with approved network access succeeded, isolating the failure to the execution environment.

## Interpretation

The experiment validates one end-to-end integration path and the offline governance checks. It does not establish retrieval quality, model consistency across repeated runs, production reliability, or safe incident mutation.

## Follow-Up

Use the P1 and P3 scenario fixtures for repeated evaluations. Record model, prompt, retrieved sources, policy result, latency, and reviewer judgment. Begin v0.2 only after adopting the action controls in `docs/03-governance-model.md`.
