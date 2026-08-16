"""Run SQLAlchemy repository."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.entities.run import Run, RunStep
from app.domain.repositories.run import RunRepository
from app.domain.value_objects.state import RunState
from app.infrastructure.db.models.run import RunModel, RunStepModel
from app.infrastructure.db.repositories.base import BaseRepository


class SQLRunRepository(BaseRepository[Run, RunModel], RunRepository):
    """SQLAlchemy implementation of RunRepository."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, RunModel, Run)

    def _to_entity(self, model: RunModel) -> Run:
        run = Run(
            id=model.id,
            tenant_id=model.tenant_id,
            agent_version_id=model.agent_version_id,
            state=model.state,
            input_data=model.input_data,
            output_data=model.output_data,
            idempotency_key=model.idempotency_key,
            attempt=model.attempt,
            max_steps=model.max_steps,
            spent_cost=model.spent_cost_microunits,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
        run.max_cost = run.max_cost.__class__(model.max_cost_microunits)
        if model.lease_owner:
            run.lease_owner = model.lease_owner
        if model.lease_expires_at:
            run.lease_expires_at = model.lease_expires_at
        if model.cancel_requested_at:
            run.cancel_requested_at = model.cancel_requested_at

        # Load steps if available
        if hasattr(model, "steps") and model.steps:
            for sm in model.steps:
                step = RunStep(
                    id=sm.id,
                    run_id=sm.run_id,
                    sequence=sm.sequence,
                    kind=sm.kind,
                    state=sm.state,
                    input_data=sm.input_data,
                    output_data=sm.output_data,
                    error=sm.error,
                    created_at=sm.created_at,
                    updated_at=sm.updated_at,
                )
                run._steps.append(step)
        return run

    def _to_model(self, entity: Run) -> RunModel:
        return RunModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            agent_version_id=entity.agent_version_id,
            state=entity.state,
            input_data=entity.input_data,
            output_data=entity.output_data,
            idempotency_key=entity.idempotency_key,
            attempt=entity.attempt,
            max_steps=entity.max_steps,
            max_cost_microunits=entity.max_cost.micro_units,
            spent_cost_microunits=entity.spent_cost.micro_units,
            lease_owner=entity.lease_owner,
            lease_expires_at=entity.lease_expires_at,
            cancel_requested_at=entity.cancel_requested_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def create(self, run: Run) -> Run:
        model = self._to_model(run)
        await self._add(model)
        return self._to_entity(model)

    async def get(self, run_id: UUID) -> Run | None:
        stmt = select(RunModel).options(selectinload(RunModel.steps)).where(RunModel.id == run_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_idempotency_key(self, tenant_id: UUID, key: str) -> Run | None:
        stmt = (
            select(RunModel)
            .options(selectinload(RunModel.steps))
            .where(RunModel.tenant_id == tenant_id, RunModel.idempotency_key == key)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def update(self, run: Run) -> Run:
        stmt = select(RunModel).where(RunModel.id == run.id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"Run {run.id} not found")

        model.state = run.state
        model.output_data = run.output_data
        model.attempt = run.attempt
        model.spent_cost_microunits = run.spent_cost.micro_units
        model.lease_owner = run.lease_owner
        model.lease_expires_at = run.lease_expires_at
        model.cancel_requested_at = run.cancel_requested_at
        model.updated_at = run.updated_at

        await self._update(model)
        return self._to_entity(model)

    async def list(
        self,
        tenant_id: UUID,
        state: RunState | None = None,
        agent_version_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Run]:
        stmt = (
            select(RunModel)
            .options(selectinload(RunModel.steps))
            .where(RunModel.tenant_id == tenant_id)
            .offset(offset)
            .limit(limit)
        )
        if state:
            stmt = stmt.where(RunModel.state == state)
        if agent_version_id:
            stmt = stmt.where(RunModel.agent_version_id == agent_version_id)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_queued_runs(
        self,
        tenant_id: UUID | None = None,
        limit: int = 100,
    ) -> Sequence[Run]:
        stmt = select(RunModel).where(RunModel.state == RunState.QUEUED).limit(limit)
        if tenant_id:
            stmt = stmt.where(RunModel.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_running_runs(
        self,
        tenant_id: UUID | None = None,
        limit: int = 100,
    ) -> Sequence[Run]:
        stmt = select(RunModel).where(RunModel.state == RunState.RUNNING).limit(limit)
        if tenant_id:
            stmt = stmt.where(RunModel.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    # Step operations
    async def add_step(self, step: RunStep) -> RunStep:
        model = RunStepModel(
            id=step.id,
            run_id=step.run_id,
            sequence=step.sequence,
            kind=step.kind,
            state=step.state,
            input_data=step.input_data,
            output_data=step.output_data,
            error=step.error,
            created_at=step.created_at,
            updated_at=step.updated_at,
        )
        await self._add(model)
        return step

    async def get_step(self, run_id: UUID, sequence: int) -> RunStep | None:
        stmt = select(RunStepModel).where(
            RunStepModel.run_id == run_id, RunStepModel.sequence == sequence
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        return RunStep(
            id=model.id,
            run_id=model.run_id,
            sequence=model.sequence,
            kind=model.kind,
            state=model.state,
            input_data=model.input_data,
            output_data=model.output_data,
            error=model.error,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def update_step(self, step: RunStep) -> RunStep:
        stmt = select(RunStepModel).where(RunStepModel.id == step.id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"Step {step.id} not found")

        model.state = step.state
        model.output_data = step.output_data
        model.error = step.error
        model.updated_at = step.updated_at

        await self._update(model)
        return step

    async def list_steps(self, run_id: UUID) -> Sequence[RunStep]:
        stmt = (
            select(RunStepModel)
            .where(RunStepModel.run_id == run_id)
            .order_by(RunStepModel.sequence)
        )
        result = await self._session.execute(stmt)
        return [
            RunStep(
                id=m.id,
                run_id=m.run_id,
                sequence=m.sequence,
                kind=m.kind,
                state=m.state,
                input_data=m.input_data,
                output_data=m.output_data,
                error=m.error,
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            for m in result.scalars().all()
        ]
