import asyncio
from uuid import UUID

import structlog

from teleautomata.application.actions import execute_action
from teleautomata.domain.errors import (
    PermanentActionError,
    RateLimitError,
    TransientActionError,
)
from teleautomata.domain.models import ActionResult, ExecutionSummary, OperationStatus
from teleautomata.domain.ports import TelegramGateway
from teleautomata.infrastructure.persistence import OperationRepository
from teleautomata.infrastructure.scheduling import AccountRateLimiter, retry_delay
from teleautomata.workflows.schema import ActionDefinition, RetryPolicy, WorkflowDefinition

log = structlog.get_logger(__name__)


class WorkflowEngine:
    def __init__(
        self,
        repository: OperationRepository,
        gateway: TelegramGateway,
        limiter: AccountRateLimiter,
        *,
        max_concurrency: int,
        max_flood_wait_seconds: int,
        default_retry: RetryPolicy,
    ) -> None:
        self._repository, self._gateway, self._limiter = repository, gateway, limiter
        self._max_concurrency = max_concurrency
        self._max_flood_wait, self._default_retry = max_flood_wait_seconds, default_retry

    async def run(
        self, workflow: WorkflowDefinition, resume_execution_id: UUID | None = None
    ) -> ExecutionSummary:
        execution_id = resume_execution_id or await self._repository.create_execution(
            workflow.name,
            workflow.account,
            workflow.model_dump(mode="json", by_alias=True),
        )
        action_results: dict[str, ActionResult] = {}
        pending = {action.id: action for action in workflow.actions}
        if resume_execution_id is not None:
            await self._repository.mark_execution_running(execution_id)
            statuses = await self._repository.action_statuses(execution_id)
            for action_id, status in statuses.items():
                if status == OperationStatus.SUCCEEDED and action_id in pending:
                    action_results[action_id] = ActionResult(
                        status, {"reason": "already_succeeded"}
                    )
                    del pending[action_id]
        semaphore = asyncio.Semaphore(1 if workflow.dry_run else self._max_concurrency)
        while pending:
            ready = [
                a for a in pending.values() if all(dep in action_results for dep in a.depends_on)
            ]
            if not ready:
                raise RuntimeError("validated workflow unexpectedly has no ready actions")
            batch = await asyncio.gather(
                *(
                    self._run_action(execution_id, workflow, action, action_results, semaphore)
                    for action in ready
                )
            )
            for action, result in zip(ready, batch, strict=True):
                action_results[action.id] = result
                del pending[action.id]
        failed = sum(result.status == OperationStatus.FAILED for result in action_results.values())
        skipped = sum(
            result.status == OperationStatus.SKIPPED for result in action_results.values()
        )
        succeeded = sum(
            result.status == OperationStatus.SUCCEEDED for result in action_results.values()
        )
        # The execution as a whole only fails on failures that were not
        # explicitly tolerated with continue_on_error; the per-action counts
        # above still report every real failure faithfully.
        blocking_failure = any(
            result.status == OperationStatus.FAILED
            and not workflow.actions_by_id[action_id].continue_on_error
            for action_id, result in action_results.items()
        )
        status = OperationStatus.FAILED if blocking_failure else OperationStatus.SUCCEEDED
        await self._repository.finish_execution(execution_id, status)
        return ExecutionSummary(execution_id, status, succeeded, failed, skipped)

    @staticmethod
    def _dependency_blocks(
        workflow: WorkflowDefinition, dependency_status: OperationStatus, dependency_id: str
    ) -> bool:
        """Decide whether a dependency's outcome should skip its descendants.

        A skipped dependency never produced a usable result, so it always
        propagates. A failed dependency blocks descendants unless it was
        explicitly marked ``continue_on_error``, letting an optional step fail
        without abandoning the rest of the workflow.
        """
        if dependency_status == OperationStatus.SKIPPED:
            return True
        if dependency_status == OperationStatus.FAILED:
            return not workflow.actions_by_id[dependency_id].continue_on_error
        return False

    async def _run_action(
        self,
        execution_id: UUID,
        workflow: WorkflowDefinition,
        action: ActionDefinition,
        previous: dict[str, ActionResult],
        semaphore: asyncio.Semaphore,
    ) -> ActionResult:
        operation_id = await self._repository.create_operation(execution_id, action.id, action.type)
        if workflow.dry_run:
            # Nothing executes in a dry run, so dependencies cannot meaningfully
            # fail; report every action uniformly as planned-but-not-run.
            result = ActionResult(
                OperationStatus.SKIPPED, {"reason": "dry_run", "action_type": action.type}
            )
            await self._repository.update_operation(
                operation_id, result.status, attempts=0, output=result.output
            )
            return result
        dependency_failed = any(
            self._dependency_blocks(workflow, previous[dep].status, dep)
            for dep in action.depends_on
        )
        if dependency_failed:
            result = ActionResult(OperationStatus.SKIPPED, {"reason": "dependency_failed"})
            await self._repository.update_operation(
                operation_id, result.status, attempts=0, output=result.output
            )
            return result
        policy = action.retry or self._default_retry
        for attempt in range(1, policy.max_attempts + 1):
            await self._repository.update_operation(
                operation_id, OperationStatus.RUNNING, attempts=attempt
            )
            try:
                async with semaphore:
                    await self._limiter.acquire(workflow.account)
                    output = await execute_action(self._gateway, action)
                result = ActionResult(OperationStatus.SUCCEEDED, output)
                await self._repository.update_operation(
                    operation_id, result.status, attempts=attempt, output=output
                )
                log.info(
                    "operation_succeeded",
                    execution_id=str(execution_id),
                    action_id=action.id,
                    attempt=attempt,
                )
                return result
            except RateLimitError as exc:
                if exc.retry_after_seconds > self._max_flood_wait:
                    return await self._fail(operation_id, attempt, "flood_wait_too_long", str(exc))
                if attempt == policy.max_attempts:
                    return await self._fail(
                        operation_id, attempt, "flood_wait_retry_exhausted", str(exc)
                    )
                await self._repository.update_operation(
                    operation_id,
                    OperationStatus.RETRY_SCHEDULED,
                    attempts=attempt,
                    error_code="flood_wait",
                    error_detail=str(exc),
                )
                await asyncio.sleep(exc.retry_after_seconds)
            except TransientActionError as exc:
                if attempt == policy.max_attempts:
                    return await self._fail(operation_id, attempt, "transient_error", str(exc))
                delay = retry_delay(policy.initial_delay_seconds, policy.max_delay_seconds, attempt)
                await self._repository.update_operation(
                    operation_id,
                    OperationStatus.RETRY_SCHEDULED,
                    attempts=attempt,
                    error_code="transient_error",
                    error_detail=str(exc),
                )
                await asyncio.sleep(delay)
            except PermanentActionError as exc:
                return await self._fail(operation_id, attempt, "permanent_error", str(exc))
        return await self._fail(
            operation_id, policy.max_attempts, "retry_exhausted", "retry policy exhausted"
        )

    async def _fail(
        self, operation_id: UUID, attempts: int, code: str, detail: str
    ) -> ActionResult:
        result = ActionResult(OperationStatus.FAILED, {}, error_code=code)
        await self._repository.update_operation(
            operation_id, result.status, attempts=attempts, error_code=code, error_detail=detail
        )
        return result
