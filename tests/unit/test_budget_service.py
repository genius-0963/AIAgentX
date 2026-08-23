"""Unit tests for budget service."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.application.services.budget_service import BudgetCheckResult, BudgetService
from app.domain.entities.run import Run
from app.domain.entities.tenant import Tenant
from app.domain.value_objects.money import Money
from app.domain.value_objects.state import RunState


@pytest.fixture
def mock_run_repository():
    """Mock run repository."""
    from unittest.mock import AsyncMock, MagicMock

    repo = MagicMock()
    repo.get = AsyncMock()
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def mock_tenant_repository():
    """Mock tenant repository."""
    from unittest.mock import AsyncMock, MagicMock

    repo = MagicMock()
    repo.get = AsyncMock()
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def mock_cost_service():
    """Mock cost service."""
    from unittest.mock import MagicMock

    service = MagicMock()
    service.calculate_cost = MagicMock(return_value=1000)  # 1000 micro-units
    return service


@pytest.fixture
def budget_service(mock_run_repository, mock_tenant_repository, mock_cost_service):
    """Create budget service with mocked dependencies."""
    return BudgetService(
        run_repository=mock_run_repository,
        tenant_repository=mock_tenant_repository,
        cost_service=mock_cost_service,
        warning_threshold_percent=80.0,
    )


@pytest.fixture
def sample_run():
    """Create a sample run entity."""
    return Run(
        id=uuid4(),
        tenant_id=uuid4(),
        agent_version_id=uuid4(),
        state=RunState.RUNNING,
        input_data={"question": "test"},
        idempotency_key="test-key",
        max_steps=100,
        max_cost=Money(10_000_000),  # $10
        spent_cost=Money(5_000_000),  # $5 spent
        timeout_seconds=90,
    )


@pytest.fixture
def sample_tenant():
    """Create a sample tenant entity."""
    return Tenant(
        id=uuid4(),
        slug="test-tenant",
        plan="professional",
        status="active",
        monthly_budget_usd=100.0,
        daily_budget_usd=10.0,
        spent_monthly_usd=5.0,
        spent_daily_usd=2.0,
    )


def test_budget_check_result_allowed():
    """Test BudgetCheckResult for allowed budget check."""
    result = BudgetCheckResult(
        allowed=True,
        remaining_budget=Money(5_000_000),
        remaining_steps=50,
        remaining_seconds=45.0,
    )
    assert result.allowed is True
    assert result.reason is None
    assert result.remaining_budget.micro_units == 5_000_000


def test_budget_check_result_denied():
    """Test BudgetCheckResult for denied budget check."""
    result = BudgetCheckResult(
        allowed=False,
        reason="Run would exceed maximum cost limit",
        remaining_budget=Money(0),
    )
    assert result.allowed is False
    assert result.reason == "Run would exceed maximum cost limit"


@pytest.mark.asyncio
async def test_check_run_budget_allowed(budget_service, sample_run, mock_run_repository):
    """Test budget check when run has sufficient budget."""
    mock_run_repository.get.return_value = sample_run

    result = await budget_service.check_run_budget(sample_run.id, Money(2_000_000))

    assert result.allowed is True
    assert result.remaining_budget.micro_units == 3_000_000  # $10 - $5 - $2 = $3
    assert result.remaining_steps == 100


@pytest.mark.asyncio
async def test_check_run_budget_exceeded(budget_service, sample_run, mock_run_repository):
    """Test budget check when run would exceed budget."""
    mock_run_repository.get.return_value = sample_run

    result = await budget_service.check_run_budget(sample_run.id, Money(6_000_000))

    assert result.allowed is False
    assert result.reason == "Run would exceed maximum cost limit"
    assert result.remaining_budget.micro_units == 5_000_000


@pytest.mark.asyncio
async def test_check_run_budget_warning(budget_service, sample_run, mock_run_repository):
    """Test budget check when warning threshold is reached."""
    # Set spent cost to 85% of max
    sample_run.spent_cost = Money(8_500_000)
    mock_run_repository.get.return_value = sample_run

    result = await budget_service.check_run_budget(sample_run.id, Money(1_000_000))

    assert result.allowed is True
    # Should have emitted a budget warning event
    assert len(sample_run.events) > 0


@pytest.mark.asyncio
async def test_check_run_budget_step_limit(budget_service, sample_run, mock_run_repository):
    """Test budget check when step limit is exceeded."""
    # Add steps to reach limit
    for i in range(100):
        sample_run.add_step(i, "model_call", {"test": "data"})

    mock_run_repository.get.return_value = sample_run

    result = await budget_service.check_run_budget(sample_run.id, Money(1_000_000))

    assert result.allowed is False
    assert result.reason == "Run would exceed maximum step limit"
    assert result.remaining_steps == 0


@pytest.mark.asyncio
async def test_check_run_budget_timeout(budget_service, sample_run, mock_run_repository):
    """Test budget check when timeout is exceeded."""
    # Set created_at to 100 seconds ago
    sample_run.created_at = datetime.now(UTC) - timedelta(seconds=100)
    mock_run_repository.get.return_value = sample_run

    result = await budget_service.check_run_budget(sample_run.id, Money(1_000_000))

    assert result.allowed is False
    assert result.reason == "Run would exceed timeout limit"
    assert result.remaining_seconds == 0.0


@pytest.mark.asyncio
async def test_check_run_budget_not_found(budget_service, mock_run_repository):
    """Test budget check when run is not found."""
    mock_run_repository.get.return_value = None

    result = await budget_service.check_run_budget(uuid4(), Money(1_000_000))

    assert result.allowed is False
    assert result.reason == "Run not found"


@pytest.mark.asyncio
async def test_check_tenant_budget_allowed(budget_service, sample_tenant, mock_tenant_repository):
    """Test tenant budget check when tenant has sufficient budget."""
    mock_tenant_repository.get.return_value = sample_tenant

    result = await budget_service.check_tenant_budget(sample_tenant.id, Money(5_000_000), "daily")

    assert result.allowed is True
    # $10 - $2 - $5 = $3 remaining
    assert result.remaining_budget.micro_units == 3_000_000


@pytest.mark.asyncio
async def test_check_tenant_budget_exceeded(budget_service, sample_tenant, mock_tenant_repository):
    """Test tenant budget check when tenant would exceed budget."""
    mock_tenant_repository.get.return_value = sample_tenant

    result = await budget_service.check_tenant_budget(sample_tenant.id, Money(9_000_000), "daily")

    assert result.allowed is False
    assert result.reason == "Tenant would exceed daily budget limit"


@pytest.mark.asyncio
async def test_record_spent_success(budget_service, sample_run, mock_run_repository):
    """Test successful cost recording."""
    mock_run_repository.get.return_value = sample_run
    mock_run_repository.update.return_value = sample_run

    await budget_service.record_spent(sample_run.id, Money(1_000_000), "openai", "gpt-4o")

    assert sample_run.spent_cost.micro_units == 6_000_000  # $5 + $1 = $6
    mock_run_repository.update.assert_called_once()


@pytest.mark.asyncio
async def test_record_spent_exceeds_budget(budget_service, sample_run, mock_run_repository):
    """Test cost recording when it would exceed budget."""
    mock_run_repository.get.return_value = sample_run

    with pytest.raises(ValueError, match="would exceed budget"):
        await budget_service.record_spent(sample_run.id, Money(6_000_000))


@pytest.mark.asyncio
async def test_record_spent_run_not_found(budget_service, mock_run_repository):
    """Test cost recording when run is not found."""
    mock_run_repository.get.return_value = None

    # Should not raise exception, just log warning
    await budget_service.record_spent(uuid4(), Money(1_000_000))


@pytest.mark.asyncio
async def test_record_provider_usage(
    budget_service,
    sample_run,
    mock_run_repository,
    mock_cost_service,
):
    """Test recording provider usage with cost calculation."""
    mock_run_repository.get.return_value = sample_run
    mock_run_repository.update.return_value = sample_run
    mock_cost_service.calculate_cost.return_value = 5000  # 5000 micro-units

    await budget_service.record_provider_usage(
        sample_run.id, "openai", "gpt-4o", 1000, 500
    )

    mock_cost_service.calculate_cost.assert_called_once_with("openai", "gpt-4o", 1000, 500)
    assert sample_run.spent_cost.micro_units == 5_005_000  # $5 + $0.005 = $5.005


@pytest.mark.asyncio
async def test_check_step_limit_true(budget_service, sample_run, mock_run_repository):
    """Test step limit check when steps remain."""
    mock_run_repository.get.return_value = sample_run

    result = await budget_service.check_step_limit(sample_run.id)

    assert result is True


@pytest.mark.asyncio
async def test_check_step_limit_false(budget_service, sample_run, mock_run_repository):
    """Test step limit check when no steps remain."""
    for i in range(100):
        sample_run.add_step(i, "model_call", {"test": "data"})

    mock_run_repository.get.return_value = sample_run

    result = await budget_service.check_step_limit(sample_run.id)

    assert result is False


@pytest.mark.asyncio
async def test_check_timeout_true(budget_service, sample_run, mock_run_repository):
    """Test timeout check when time remains."""
    mock_run_repository.get.return_value = sample_run

    result = await budget_service.check_timeout(sample_run.id)

    assert result is True


@pytest.mark.asyncio
async def test_check_timeout_false(budget_service, sample_run, mock_run_repository):
    """Test timeout check when no time remains."""
    sample_run.created_at = datetime.now(UTC) - datetime.timedelta(seconds=100)
    mock_run_repository.get.return_value = sample_run

    result = await budget_service.check_timeout(sample_run.id)

    assert result is False


@pytest.mark.asyncio
async def test_get_remaining_budget(budget_service, sample_run, mock_run_repository):
    """Test getting remaining budget."""
    mock_run_repository.get.return_value = sample_run

    remaining = await budget_service.get_remaining_budget(sample_run.id)

    assert remaining.micro_units == 5_000_000  # $10 - $5 = $5


@pytest.mark.asyncio
async def test_reset_tenant_budget(budget_service, sample_tenant, mock_tenant_repository):
    """Test resetting tenant budget."""
    mock_tenant_repository.get.return_value = sample_tenant
    mock_tenant_repository.update.return_value = sample_tenant

    await budget_service.reset_tenant_budget(sample_tenant.id, "daily")

    assert sample_tenant.spent_daily_usd == 0.0
    assert sample_tenant.budget_reset_at is not None
    mock_tenant_repository.update.assert_called_once()


@pytest.mark.asyncio
async def test_reset_tenant_budget_not_found(budget_service, mock_tenant_repository):
    """Test resetting tenant budget when tenant not found."""
    mock_tenant_repository.get.return_value = None

    # Should not raise exception, just log warning
    await budget_service.reset_tenant_budget(uuid4(), "daily")
