"""Agent SQLAlchemy repository."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.entities.agent import Agent, AgentStatus, AgentVersion
from app.domain.entities.tool_grant import ToolGrant
from app.domain.repositories.agent import AgentRepository
from app.infrastructure.db.models.agent import AgentModel, AgentVersionModel, ToolGrantModel
from app.infrastructure.db.repositories.base import BaseRepository


class SQLAgentRepository(BaseRepository[Agent, AgentModel], AgentRepository):
    """SQLAlchemy implementation of AgentRepository."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AgentModel, Agent)

    def _to_entity(self, model: AgentModel) -> Agent:
        agent = Agent(
            id=model.id,
            tenant_id=model.tenant_id,
            name=model.name,
            description=model.description,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
        # Load versions if available
        if hasattr(model, "versions") and model.versions:
            for vm in model.versions:
                version = self._version_to_entity(vm)
                agent._versions.append(version)
        return agent

    def _to_model(self, entity: Agent) -> AgentModel:
        return AgentModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            name=entity.name,
            description=entity.description,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def _version_to_entity(self, model: AgentVersionModel) -> AgentVersion:
        version = AgentVersion(
            id=model.id,
            agent_id=model.agent_id,
            tenant_id=model.tenant_id,
            version=model.version,
            system_prompt=model.system_prompt,
            model_policy=model.model_policy,
            memory_mode=model.memory_mode,
            status=model.status,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
        # Load tool grants if available
        if hasattr(model, "tool_grants") and model.tool_grants:
            for tgm in model.tool_grants:
                grant = ToolGrant(
                    id=tgm.id,
                    agent_version_id=tgm.agent_version_id,
                    tool_name=tgm.tool_name,
                    policy=tgm.policy,
                    created_at=tgm.created_at,
                )
                version._tool_grants.append(grant)
        return version

    async def create(self, agent: Agent) -> Agent:
        model = self._to_model(agent)
        await self._add(model)
        return self._to_entity(model)

    async def get(self, agent_id: UUID) -> Agent | None:
        stmt = (
            select(AgentModel)
            .options(selectinload(AgentModel.versions).selectinload(AgentVersionModel.tool_grants))
            .where(AgentModel.id == agent_id)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_name(self, tenant_id: UUID, name: str) -> Agent | None:
        stmt = (
            select(AgentModel)
            .options(selectinload(AgentModel.versions).selectinload(AgentVersionModel.tool_grants))
            .where(AgentModel.tenant_id == tenant_id, AgentModel.name == name)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def update(self, agent: Agent) -> Agent:
        model = await self._get_by_id(agent.id)
        if not model:
            raise ValueError(f"Agent {agent.id} not found")
        model.name = agent.name
        model.description = agent.description
        model.updated_at = agent.updated_at
        await self._update(model)
        return self._to_entity(model)

    async def list(
        self,
        tenant_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Agent]:
        stmt = (
            select(AgentModel)
            .options(selectinload(AgentModel.versions))
            .where(AgentModel.tenant_id == tenant_id)
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def soft_delete(self, agent_id: UUID) -> bool:
        model = await self._get_by_id(agent_id)
        if not model:
            return False
        await self._delete(model)
        return True

    # Version operations
    async def add_version(self, version: AgentVersion) -> AgentVersion:
        model = AgentVersionModel(
            id=version.id,
            agent_id=version.agent_id,
            tenant_id=version.tenant_id,
            version=version.version,
            system_prompt=version.system_prompt,
            model_policy=version.model_policy,
            memory_mode=version.memory_mode,
            status=version.status,
            created_at=version.created_at,
            updated_at=version.updated_at,
        )
        await self._add(model)

        # Add tool grants
        for grant in version._tool_grants:
            grant_model = ToolGrantModel(
                id=grant.id,
                agent_version_id=model.id,
                tool_name=grant.tool_name,
                policy=grant.policy,
                created_at=grant.created_at,
            )
            await self._add(grant_model)

        return self._version_to_entity(model)

    async def get_version(self, agent_id: UUID, version: int) -> AgentVersion | None:
        stmt = (
            select(AgentVersionModel)
            .options(selectinload(AgentVersionModel.tool_grants))
            .where(AgentVersionModel.agent_id == agent_id, AgentVersionModel.version == version)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._version_to_entity(model) if model else None

    async def get_published_version(self, agent_id: UUID) -> AgentVersion | None:
        stmt = (
            select(AgentVersionModel)
            .options(selectinload(AgentVersionModel.tool_grants))
            .where(
                AgentVersionModel.agent_id == agent_id,
                AgentVersionModel.status == AgentStatus.PUBLISHED,
            )
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._version_to_entity(model) if model else None

    async def update_version(self, version: AgentVersion) -> AgentVersion:
        stmt = (
            select(AgentVersionModel)
            .options(selectinload(AgentVersionModel.tool_grants))
            .where(AgentVersionModel.id == version.id)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"Agent version {version.id} not found")

        model.system_prompt = version.system_prompt
        model.model_policy = version.model_policy
        model.memory_mode = version.memory_mode
        model.status = version.status
        model.updated_at = version.updated_at

        # Update tool grants
        existing_grants = {g.tool_name: g for g in model.tool_grants}
        for grant in version._tool_grants:
            if grant.tool_name in existing_grants:
                existing_grants[grant.tool_name].policy = grant.policy
            else:
                grant_model = ToolGrantModel(
                    id=grant.id,
                    agent_version_id=model.id,
                    tool_name=grant.tool_name,
                    policy=grant.policy,
                    created_at=grant.created_at,
                )
                self._session.add(grant_model)

        await self._update(model)
        return self._version_to_entity(model)

    async def publish_version(self, agent_id: UUID, version: int) -> AgentVersion:
        # Archive current published
        stmt = select(AgentVersionModel).where(
            AgentVersionModel.agent_id == agent_id,
            AgentVersionModel.status == AgentStatus.PUBLISHED,
        )
        result = await self._session.execute(stmt)
        current = result.scalar_one_or_none()
        if current:
            current.status = AgentStatus.ARCHIVED
            current.updated_at = current.updated_at  # trigger update

        # Publish new version
        stmt = select(AgentVersionModel).where(
            AgentVersionModel.agent_id == agent_id,
            AgentVersionModel.version == version,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"Version {version} not found for agent {agent_id}")

        model.status = AgentStatus.PUBLISHED
        model.updated_at = model.updated_at
        await self._update(model)
        return self._version_to_entity(model)

    async def list_versions(self, agent_id: UUID) -> Sequence[AgentVersion]:
        stmt = (
            select(AgentVersionModel)
            .options(selectinload(AgentVersionModel.tool_grants))
            .where(AgentVersionModel.agent_id == agent_id)
            .order_by(AgentVersionModel.version)
        )
        result = await self._session.execute(stmt)
        return [self._version_to_entity(m) for m in result.scalars().all()]
