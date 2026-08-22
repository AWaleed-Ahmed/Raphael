"""Counterfactual Sandbox Interventions & Delta Debugging (FLE / Steps 11-12).

Tests causality by applying single-variable interventions in the sandbox:
1. Revert candidate hunk / restore value
2. Check if causal fingerprint disappears
3. Apply delta debugging to isolate minimal causal patch
4. Advance lifecycle: suspected -> localized -> causal -> confirmed_fix
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from raphael_agent.localization.candidates import FaultCandidate


@dataclass
class InterventionResult:
    candidate: FaultCandidate
    initial_reproduced: bool
    post_intervention_reproduced: bool
    is_causal: bool
    runs_passed: int = 0
    reintroduced_failure: bool | None = None
    regression_passed: bool | None = None
    security_passed: bool | None = None
    final_state: str = "suspected"  # suspected | localized | causal | confirmed_fix
    notes: list[str] = field(default_factory=list)


class SandboxInterventionController:
    """Executes counterfactual sandbox tests and delta debugging."""

    def __init__(self, repeat_count: int = 3) -> None:
        self.repeat_count = repeat_count

    def evaluate_candidate_causality(
        self,
        candidate: FaultCandidate,
        *,
        sandbox_deploy_fn: Callable[[dict[str, Any]], bool],  # returns True if failure reproduced
        candidate_patch_hunk: str | None = None,
        reintroduce_fn: Callable[[dict[str, Any]], bool] | None = None,
        regression_fn: Callable[[], bool] | None = None,
        security_fn: Callable[[], bool] | None = None,
    ) -> InterventionResult:
        """Run counterfactual verification loop on a candidate."""
        # 1. Negative Control: Verify failure reproduces on unpatched SHA
        initial_repro = sandbox_deploy_fn({"revision": candidate.git_sha, "patch": None})
        if not initial_repro:
            return InterventionResult(
                candidate=candidate,
                initial_reproduced=False,
                post_intervention_reproduced=False,
                is_causal=False,
                final_state="suspected",
                notes=["Failure did not reproduce on unpatched baseline in sandbox"],
            )

        # 2. Positive Control: Apply single-variable candidate patch / revert
        patch_to_test = candidate_patch_hunk or candidate.diff_hunk or f"revert:{candidate.path}:{candidate.line}"
        post_repro = sandbox_deploy_fn({"revision": candidate.git_sha, "patch": patch_to_test})

        # Causal if failure disappeared post-intervention
        is_causal = not post_repro

        if not is_causal:
            return InterventionResult(
                candidate=candidate,
                initial_reproduced=True,
                post_intervention_reproduced=True,
                is_causal=False,
                final_state="localized",
                notes=["Intervention did not eliminate the failure signature"],
            )

        # 3. Repeatability Flake Check: Run 3 consecutive test executions
        passed_runs = 1
        for run_idx in range(2, self.repeat_count + 1):
            still_failing = sandbox_deploy_fn({"revision": candidate.git_sha, "patch": patch_to_test})
            if not still_failing:
                passed_runs += 1

        all_passed = (passed_runs == self.repeat_count)
        reintroduced_failure: bool | None = None
        regression_passed: bool | None = None
        security_passed: bool | None = None
        notes = [
            f"Counterfactual intervention eliminated failure (passed {passed_runs}/{self.repeat_count} validation runs)"
        ]
        if reintroduce_fn is not None and all_passed:
            # Optional positive reintroduction control: restore the candidate
            # and require the original failure to return.
            reintroduced_failure = bool(
                reintroduce_fn({
                    "revision": candidate.git_sha,
                    "patch": f"reintroduce:{candidate.path}:{candidate.line}",
                })
            )
            notes.append(f"Reintroduction control: {'failed again' if reintroduced_failure else 'did not fail'}")
        if regression_fn is not None:
            regression_passed = bool(regression_fn())
            notes.append(f"Regression checks: {'passed' if regression_passed else 'failed'}")
        if security_fn is not None:
            security_passed = bool(security_fn())
            notes.append(f"Security checks: {'passed' if security_passed else 'failed'}")
        confirmed = all_passed and (reintroduced_failure is not False) and (regression_passed is not False) and (security_passed is not False)
        final_state = "confirmed_fix" if confirmed else "causal"
        candidate.state = final_state

        return InterventionResult(
            candidate=candidate,
            initial_reproduced=True,
            post_intervention_reproduced=False,
            is_causal=True,
            runs_passed=passed_runs,
            reintroduced_failure=reintroduced_failure,
            regression_passed=regression_passed,
            security_passed=security_passed,
            final_state=final_state,
            notes=notes,
        )

    def delta_debug_minimize_hunks(
        self,
        candidate_hunks: list[str],
        sandbox_deploy_fn: Callable[[list[str]], bool],  # returns True if fixed
    ) -> list[str]:
        """Apply Zeller's delta debugging to minimize a successful multi-hunk patch into minimal causal hunks."""
        if len(candidate_hunks) <= 1:
            return candidate_hunks

        # Try single hunks first
        for single_hunk in candidate_hunks:
            if sandbox_deploy_fn([single_hunk]):
                return [single_hunk]  # Found single causal hunk!

        # Try halves (divide and conquer)
        mid = len(candidate_hunks) // 2
        left = candidate_hunks[:mid]
        right = candidate_hunks[mid:]

        if sandbox_deploy_fn(left):
            return self.delta_debug_minimize_hunks(left, sandbox_deploy_fn)
        if sandbox_deploy_fn(right):
            return self.delta_debug_minimize_hunks(right, sandbox_deploy_fn)

        return candidate_hunks
