# AIAgentX Developer Guide

## Overview

This guide provides comprehensive information for developers working on AIAgentX, including development environment setup, code organization, testing strategies, contributing guidelines, and best practices.

## Development Environment Setup

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| **Python** | 3.12+ | Runtime environment |
| **uv** | 0.4+ | Fast Python package manager |
| **Docker** | 24.0+ | Containerization |
| **Git** | 2.30+ | Version control |
| **Make** | 3.8+ | Build automation |

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/AIAgentX/aiagentx.git
cd aiagentx

# Install dependencies using uv
uv sync

# Activate virtual environment
source .venv/bin/activate  # On Linux/Mac
.venv\Scripts\activate  # On Windows

# Set up pre-commit hooks
uv run pre-commit install
```

### Development Commands

```bash
# Run development server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run database migrations
uv run alembic upgrade head

# Create new migration
uv run alembic revision --autogenerate -m "description"

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=app --cov-report=html

# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Type check
uv run mypy app
```

## Project Structure

### Directory Organization

```mermaid
graph TB
    subgraph "Root Directory"
        ROOT[aiagentx/]
    end
    
    subgraph "Application Code"
        APP[app/]
        API[app/api/]
        APPLICATION[app/application/]
        DOMAIN[app/domain/]
        INFRASTRUCTURE[app/infrastructure/]
        WORKERS[app/workers/]
    end
    
    subgraph "Configuration"
        CONFIG[.env.example]
        ALEMBIC[alembic.ini]
        DOCKER[docker-compose.yml]
        PYPROJECT[pyproject.toml]
    end
    
    subgraph "Documentation"
        DOCS[docs/]
        README[README.md]
    end
    
    subgraph "Testing"
        TESTS[tests/]
    end
    
    subgraph "Scripts"
        SCRIPTS[scripts/]
    end
    
    ROOT --> APP
    APP --> API
    APP --> APPLICATION
    APP --> DOMAIN
    APP --> INFRASTRUCTURE
    APP --> WORKERS
    
    ROOT --> CONFIG
    ROOT --> DOCS
    ROOT --> TESTS
    ROOT --> SCRIPTS
```

### Key Directories

| Directory | Purpose |
|-----------|---------|
| `app/api/` | FastAPI routers, middleware, error handlers |
| `app/application/` | Use cases, application services |
| `app/domain/` | Domain entities, value objects, repository interfaces |
| `app/infrastructure/` | Database, cache, providers, external services |
| `app/workers/` | Background job execution |
| `tests/` | Unit and integration tests |
| `scripts/` | Development and deployment scripts |
| `docs/` | Documentation files |

## Code Organization

### Clean Architecture Layers

```mermaid
graph TB
    subgraph "API Layer"
        ROUTERS[app/api/v1/]
        MIDDLEWARE[app/api/middleware/]
        SCHEMAS[app/api/v1/schemas/]
    end
    
    subgraph "Application Layer"
        USE_CASES[app/application/use_cases/]
        SERVICES[app/application/services/]
    end
    
    subgraph "Domain Layer"
        ENTITIES[app/domain/entities/]
        VALUE_OBJECTS[app/domain/value_objects/]
        REPOSITORIES[app/domain/repositories/]
        EVENTS[app/domain/events/]
    end
    
    subgraph "Infrastructure Layer"
        DB[app/infrastructure/db/]
        CACHE[app/infrastructure/cache/]
        PROVIDERS[app/infrastructure/providers/]
        AUTH[app/infrastructure/auth/]
    end
    
    ROUTERS --> USE_CASES
    MIDDLEWARE --> USE_CASES
    USE_CASES --> ENTITIES
    SERVICES --> REPOSITORIES
    REPOSITORIES --> DB
    SERVICES --> CACHE
    SERVICES --> PROVIDERS
    MIDDLEWARE --> AUTH
```

### Adding New Features

#### 1. Add Domain Entity

```python
# app/domain/entities/new_feature.py
from dataclasses import dataclass
from app.domain.entities.base import AggregateRoot

@dataclass(slots=True, kw_only=True)
class NewFeature(AggregateRoot):
    """New feature aggregate root."""
    tenant_id: UUID
    name: str
    # Add your fields here
    
    def __post_init__(self) -> None:
        # Add validation logic
        if not self.name or not self.name.strip():
            raise ValueError("Name cannot be empty")
```

#### 2. Add Repository Interface

```python
# app/domain/repositories/new_feature.py
from abc import ABC, abstractmethod
from uuid import UUID
from app.domain.entities.new_feature import NewFeature

class NewFeatureRepository(ABC):
    """Repository interface for NewFeature."""
    
    @abstractmethod
    async def create(self, entity: NewFeature) -> NewFeature:
        """Create a new feature."""
        ...
    
    @abstractmethod
    async def get(self, entity_id: UUID) -> NewFeature | None:
        """Get feature by ID."""
        ...
    
    @abstractmethod
    async def update(self, entity: NewFeature) -> NewFeature:
        """Update feature."""
        ...
```

#### 3. Add Repository Implementation

```python
# app/infrastructure/db/repositories/new_feature.py
from app.domain.repositories.new_feature import NewFeatureRepository
from app.infrastructure.db.repositories.base import SQLRepository
from app.domain.entities.new_feature import NewFeature

class SQLNewFeatureRepository(SQLRepository[NewFeature], NewFeatureRepository):
    """SQL implementation of NewFeatureRepository."""
    
    async def create(self, entity: NewFeature) -> NewFeature:
        # Implementation
        ...
    
    async def get(self, entity_id: UUID) -> NewFeature | None:
        # Implementation
        ...
    
    async def update(self, entity: NewFeature) -> NewFeature:
        # Implementation
        ...
```

#### 4. Add Use Case

```python
# app/application/use_cases/new_feature.py
from app.domain.entities.new_feature import NewFeature
from app.domain.repositories.new_feature import NewFeatureRepository

class NewFeatureUseCases:
    """Use cases for new feature."""
    
    def __init__(self, repository: NewFeatureRepository) -> None:
        self._repository = repository
    
    async def create_feature(self, tenant_id: UUID, name: str) -> NewFeature:
        """Create a new feature."""
        feature = NewFeature(tenant_id=tenant_id, name=name)
        return await self._repository.create(feature)
```

#### 5. Add API Endpoint

```python
# app/api/v1/new_feature/router.py
from fastapi import APIRouter, Depends
from app.application.use_cases.new_feature import NewFeatureUseCases
from app.infrastructure.db.repositories.new_feature import SQLNewFeatureRepository
from app.infrastructure.db.session import get_db_session

router = APIRouter(prefix="/new-feature", tags=["new-feature"])

async def get_use_cases(session=Depends(get_db_session)) -> NewFeatureUseCases:
    repository = SQLNewFeatureRepository(session)
    return NewFeatureUseCases(repository)

@router.post("")
async def create_feature(
    name: str,
    use_cases: NewFeatureUseCases = Depends(get_use_cases)
):
    return await use_cases.create_feature(tenant_id=UUID(...), name=name)
```

## Testing Strategy

### Test Organization

```mermaid
graph TB
    subgraph "Test Structure"
        UNIT[Unit Tests]
        INTEGRATION[Integration Tests]
        E2E[End-to-End Tests]
    end
    
    subgraph "Unit Tests"
        DOMAIN_TESTS[Domain Layer Tests]
        APPLICATION_TESTS[Application Layer Tests]
        INFRASTRUCTURE_TESTS[Infrastructure Tests]
    end
    
    subgraph "Integration Tests"
        API_TESTS[API Integration Tests]
        DB_TESTS[Database Integration Tests]
        PROVIDER_TESTS[Provider Integration Tests]
    end
    
    subgraph "Test Utilities"
        FIXTURES[Test Fixtures]
        MOCKS[Test Mocks]
        HELPERS[Test Helpers]
    end
    
    UNIT --> DOMAIN_TESTS
    UNIT --> APPLICATION_TESTS
    UNIT --> INFRASTRUCTURE_TESTS
    
    INTEGRATION --> API_TESTS
    INTEGRATION --> DB_TESTS
    INTEGRATION --> PROVIDER_TESTS
    
    UNIT --> FIXTURES
    UNIT --> MOCKS
    INTEGRATION --> FIXTURES
    INTEGRATION --> HELPERS
```

### Writing Unit Tests

```python
# tests/unit/domain/test_new_feature.py
import pytest
from uuid import uuid4
from app.domain.entities.new_feature import NewFeature

def test_create_feature_success():
    """Test successful feature creation."""
    feature = NewFeature(
        tenant_id=uuid4(),
        name="test-feature"
    )
    assert feature.name == "test-feature"
    assert feature.tenant_id is not None

def test_create_feature_empty_name():
    """Test feature creation with empty name."""
    with pytest.raises(ValueError, match="Name cannot be empty"):
        NewFeature(
            tenant_id=uuid4(),
            name=""
        )
```

### Writing Integration Tests

```python
# tests/integration/api/test_new_feature.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_create_feature_endpoint():
    """Test feature creation via API."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/v1/new-feature",
            json={"name": "test-feature"},
            headers={"Authorization": "Bearer test-token"}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-feature"
```

### Test Fixtures

```python
# tests/conftest.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.infrastructure.db.base import Base
from app.infrastructure.db.session import get_db_session

@pytest.fixture
async def db_session():
    """Create test database session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        yield session
    
    await engine.dispose()
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run unit tests only
uv run pytest tests/unit

# Run integration tests only
uv run pytest tests/integration

# Run specific test file
uv run pytest tests/unit/domain/test_new_feature.py

# Run with coverage
uv run pytest --cov=app --cov-report=html

# Run with verbose output
uv run pytest -v

# Run specific test
uv run pytest tests/unit/domain/test_new_feature.py::test_create_feature_success
```

## Code Style and Quality

### Code Formatting

AIAgentX uses Ruff for code formatting:

```bash
# Format code
uv run ruff format .

# Check formatting without making changes
uv run ruff format --check .

# Format specific file
uv run ruff format app/domain/entities/agent.py
```

### Linting

```bash
# Run linter
uv run ruff check .

# Fix auto-fixable issues
uv run ruff check --fix .

# Check specific directory
uv run ruff check app/domain/

# Show detailed explanation
uv run ruff check app/domain/ --explain
```

### Type Checking

```bash
# Run type checker
uv run mypy app

# Check specific file
uv run mypy app/domain/entities/agent.py

# Show detailed error messages
uv run mypy app --show-error-codes
```

### Pre-commit Hooks

The project uses pre-commit hooks to ensure code quality:

```bash
# Install pre-commit hooks
uv run pre-commit install

# Run pre-commit manually
uv run pre-commit run --all-files

# Update pre-commit hooks
uv run pre-commit autoupdate
```

## Development Workflow

### Feature Development Workflow

```mermaid
graph TB
    subgraph "Development Process"
        PLAN[Plan Feature]
        BRANCH[Create Branch]
        DEVELOP[Develop Feature]
        TEST[Write Tests]
        REVIEW[Code Review]
        MERGE[Merge to Main]
    end
    
    subgraph "Quality Gates"
        LINT[Linting]
        TYPE_CHECK[Type Checking]
        UNIT_TESTS[Unit Tests]
        INTEGRATION_TESTS[Integration Tests]
    end
    
    PLAN --> BRANCH
    BRANCH --> DEVELOP
    DEVELOP --> TEST
    TEST --> LINT
    LINT --> TYPE_CHECK
    TYPE_CHECK --> UNIT_TESTS
    UNIT_TESTS --> INTEGRATION_TESTS
    INTEGRATION_TESTS --> REVIEW
    REVIEW --> MERGE
```

### Branch Naming Convention

- `feature/feature-name` - New features
- `bugfix/bug-description` - Bug fixes
- `hotfix/critical-issue` - Critical production fixes
- `refactor/refactor-description` - Code refactoring
- `docs/documentation-update` - Documentation updates

### Commit Message Convention

Follow conventional commits:

```
feat: add new feature for user management
fix: resolve database connection timeout issue
docs: update API documentation
refactor: simplify provider abstraction layer
test: add integration tests for memory system
chore: update dependencies
```

## Debugging

### Local Debugging

```bash
# Run with debugger
uv run python -m debugpy --listen 5678 --wait-for-client -m app.main

# Set breakpoints in IDE
# Connect debugger to localhost:5678
```

### Logging Configuration

```python
# Configure logging for development
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)
```

### Database Debugging

```bash
# Connect to local database
psql postgresql://aiagentx:aiagentx@localhost:5432/aiagentx

# Check tables
\dt

# Run query
SELECT * FROM agents LIMIT 10;

# Check indexes
\di
```

## Performance Profiling

### Profiling Setup

```python
# Add profiling to your code
import cProfile
import pstats

def profile_function():
    profiler = cProfile.Profile()
    profiler.enable()
    
    # Your code here
    your_function()
    
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(10)
```

### Memory Profiling

```bash
# Install memory profiler
uv add memory-profiler

# Run with memory profiling
uv run python -m memory_profiler app/main.py
```

## Contributing Guidelines

### Contribution Process

1. **Fork the repository**
2. **Create a feature branch**
3. **Make your changes**
4. **Write tests**
5. **Ensure code quality**
6. **Submit pull request**

### Pull Request Checklist

- [ ] Code follows project style guidelines
- [ ] All tests pass
- [ ] New tests added for new features
- [ ] Documentation updated
- [ ] Commit messages follow convention
- [ ] No merge conflicts
- [ ] Code reviewed by at least one maintainer

### Code Review Guidelines

- **Be constructive** in feedback
- **Focus on code quality** and maintainability
- **Consider performance** implications
- **Check for security** issues
- **Verify tests** are adequate
- **Ensure documentation** is updated

## Best Practices

### Domain Layer

- **Keep domain logic pure** - no external dependencies
- **Use value objects** for domain concepts
- **Implement domain events** for important state changes
- **Validate invariants** in entity constructors
- **Use aggregates** to maintain consistency boundaries

### Application Layer

- **Keep use cases focused** - single responsibility
- **Use services** for cross-aggregate operations
- **Handle transactions** at use case level
- **Map between layers** appropriately
- **Don't leak domain** details to API layer

### Infrastructure Layer

- **Implement repository interfaces** faithfully
- **Handle external service failures** gracefully
- **Use connection pooling** for databases
- **Cache appropriately** based on data volatility
- **Log external interactions** for debugging

### API Layer

- **Validate input** using Pydantic models
- **Use proper HTTP status codes**
- **Handle errors consistently**
- **Document endpoints** with OpenAPI
- **Rate limit appropriately**
- **Use dependency injection** for testability

## Troubleshooting Development Issues

### Common Issues

#### Import Errors
```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies
uv sync
```

#### Database Connection Issues
```bash
# Check PostgreSQL is running
docker compose ps postgres

# Check database logs
docker compose logs postgres

# Restart database
docker compose restart postgres
```

#### Migration Issues
```bash
# Check current migration version
uv run alembic current

# Rollback to specific version
uv run alembic downgrade <revision>

# Create new migration
uv run alembic revision --autogenerate -m "description"
```

#### Test Failures
```bash
# Run specific test with verbose output
uv run pytest tests/unit/test_file.py::test_function -v

# Run with pdb debugger
uv run pytest --pdb

# Check test isolation
uv run pytest --forcexit
```

## Resources

### Internal Documentation

- [Architecture Documentation](ARCHITECTURE.md)
- [Data Flow Documentation](DATA_FLOWS.md)
- [Security Documentation](SECURITY.md)
- [API Reference](API_REFERENCE.md)

### External Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [Python AsyncIO](https://docs.python.org/3/library/asyncio.html)

This developer guide provides comprehensive information for contributing to AIAgentX, including development environment setup, code organization, testing strategies, and best practices for maintaining code quality and consistency.