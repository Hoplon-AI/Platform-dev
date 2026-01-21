# CDK Stack Tests

This directory contains unit tests for the AWS CDK infrastructure stacks.

## Important: No AWS Resources Created

**These tests do NOT deploy any resources to AWS.** They use `Template.from_stack()` which only synthesizes CloudFormation templates in memory. This means:

- ✅ **No AWS resources are created** - tests run entirely locally
- ✅ **No cleanup needed** - nothing is deployed, so nothing to clean up
- ✅ **No AWS credentials required** - tests can run without AWS access
- ✅ **Fast execution** - no network calls or deployment wait times
- ✅ **Cost-free** - no AWS charges from running these tests

The tests validate that:
- Stacks synthesize without errors
- Resources are defined with correct properties
- CloudFormation templates are valid
- Stack structure matches expectations

## Test Structure

```
tests/
├── __init__.py
├── conftest.py          # Pytest fixtures and configuration
└── unit/
    ├── __init__.py
    ├── test_networking_stack.py
    ├── test_security_stack.py
    ├── test_data_stack.py
    ├── test_compute_stack.py
    └── test_observability_stack.py
```

## Running Tests

### Install Dependencies

```bash
cd infrastructure/aws/cdk
source .venv/bin/activate  # or your virtual environment
pip install -r requirements-dev.txt
```

### Run All Tests

```bash
pytest tests/unit/ -v
```

### Run Specific Test File

```bash
pytest tests/unit/test_networking_stack.py -v
```

### Run with Coverage

```bash
pytest tests/unit/ --cov=cdk --cov-report=html
```

Coverage report will be generated in `htmlcov/index.html`.

## Test Coverage

Current test coverage: **92%**

The tests validate (in memory, no AWS deployment):
- ✅ Stack synthesis (no errors)
- ✅ Resource definitions (VPC, S3, RDS, ECS, etc. are defined correctly)
- ✅ Resource properties (encryption, tags, configurations)
- ✅ Stack outputs
- ✅ Security configurations (SSL-only policies, KMS encryption)
- ✅ IAM roles and policies
- ✅ CloudFormation template structure

## Writing New Tests

### Example Test Structure

```python
import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template
from cdk.your_stack import YourStack

@pytest.fixture
def app():
    return cdk.App()

@pytest.fixture
def env():
    return cdk.Environment(account="123456789012", region="eu-west-1")

@pytest.fixture
def stack(app, env):
    return YourStack(app, "TestStack", env=env)

@pytest.fixture
def template(stack):
    return Template.from_stack(stack)

def test_resource_created(template):
    """Test that a resource is created."""
    template.has_resource_properties(
        "AWS::Service::Resource",
        {
            "Property": "value",
        },
    )
```

## Test Best Practices

1. **Use fixtures** for common setup (app, env, stack, template)
2. **Test one thing per test** - keep tests focused
3. **Use descriptive test names** - `test_vpc_has_correct_cidr` not `test_vpc`
4. **Test both positive and negative cases** when relevant
5. **Use `Match` patterns** for flexible assertions
6. **Test stack outputs** to ensure they're exported correctly

## Continuous Integration

Tests should be run in CI/CD pipelines before deploying stacks. The GitHub Actions workflow (`.github/workflows/cdk-deploy-dev.yml`) includes a test step.
