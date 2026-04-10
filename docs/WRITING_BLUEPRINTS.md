# Writing Archie Blueprints

> **When to use this guide:** Archie Studio can generate blueprints automatically for most AWS, Azure, GCP, and Kubernetes workloads. Use this guide when you need to write a blueprint manually — for example, when a cloud service (like AWS Bedrock AgentCore) isn't yet supported by Studio, or when you're using an external AI (ChatGPT, Claude, Copilot) to help write the template. **Give this document to any AI tool** and it will produce blueprints that pass Archie's template validator.

Blueprints are Pulumi Python programs that follow a specific class structure so Archie can deploy, upgrade, drift-check, and govern them.

## Quick Start

Every blueprint is a Python class that extends `InfrastructureTemplate`. Here's the minimal structure:

```python
from typing import Any, Dict, Optional
from pathlib import Path
import pulumi
import pulumi_aws as aws

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory
from provisioner.utils.aws import ResourceNamer, get_standard_tags


@template_registry("aws-my-template")
class MyTemplate(InfrastructureTemplate):

    def __init__(self, name: str = None, config: Dict[str, Any] = None, aws_config: Dict[str, Any] = None, **kwargs):
        raw_config = config or aws_config or kwargs or {}
        if name is None:
            name = (
                raw_config.get('project_name') or
                raw_config.get('projectName') or
                raw_config.get('parameters', {}).get('aws', {}).get('project_name') or
                'my-template'
            )
        super().__init__(name, raw_config)
        self.config = raw_config

        # Declare resource references (populated in create())
        self.bucket: Optional[object] = None

    def _cfg(self, key: str, default=None):
        """Read config from root, parameters.aws, or parameters (Rule #6)"""
        params = self.config.get('parameters', {})
        aws_params = params.get('aws', {}) if isinstance(params, dict) else {}
        return (
            self.config.get(key) or
            (aws_params.get(key) if isinstance(aws_params, dict) else None) or
            (params.get(key) if isinstance(params, dict) else None) or
            default
        )

    def create_infrastructure(self) -> Dict[str, Any]:
        return self.create()

    def create(self) -> Dict[str, Any]:
        # Read config
        project = self._cfg('project_name', 'myproject')
        env = self._cfg('environment', 'dev')
        team_name = self._cfg('team_name', '')

        # Standard tags + namer
        tags = get_standard_tags(project=project, environment=env, template='my-template')
        tags['ManagedBy'] = 'Archie'
        if team_name:
            tags['Team'] = team_name

        # Create resources via factory
        self.bucket = factory.create(
            "aws:s3:Bucket",
            f"bucket-{project}-{env}",
            tags={**tags, "Name": f"bucket-{project}-{env}"},
        )

        # Export all generated values (Rule #2, #7)
        pulumi.export('bucket_name', self.bucket.bucket)
        pulumi.export('bucket_arn', self.bucket.arn)
        pulumi.export('environment', env)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        return {
            "bucket_name": self.bucket.bucket if self.bucket else None,
            "bucket_arn": self.bucket.arn if self.bucket else None,
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        return {
            "name": "aws-my-template",
            "title": "My S3 Bucket",
            "description": "Creates an S3 bucket with standard tags and encryption.",
            "category": "storage",
            "version": "1.0.0",
            "author": "Your Name",
            "cloud": "aws",
            "environment": "nonprod",
            "base_cost": "$1/month",
            "features": ["S3 bucket with server-side encryption", "Standard tagging"],
            "tags": ["s3", "storage"],
            "deployment_time": "1-2 minutes",
            "complexity": "beginner",
            "use_cases": ["Static file storage", "Application data"],
            "pillars": [
                {
                    "title": "Security",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Encrypted at rest with AES-256",
                    "practices": ["Server-side encryption enabled", "Public access blocked"]
                },
            ],
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "default": "myproject",
                    "title": "Project Name",
                    "description": "Used in resource naming",
                    "order": 1,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "environment": {
                    "type": "string",
                    "default": "dev",
                    "title": "Environment",
                    "description": "Deployment environment",
                    "enum": ["dev", "staging", "prod"],
                    "order": 2,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "team_name": {
                    "type": "string",
                    "default": "",
                    "title": "Team Name",
                    "description": "Team that owns this resource",
                    "order": 50,
                    "group": "Tags",
                },
            },
            "required": ["project_name"],
        }
```

---

## Required Methods

Every blueprint must implement these 6 methods:

| Method | Type | Purpose |
|--------|------|---------|
| `__init__` | Instance | Parse config, call `super().__init__()`, declare resource refs |
| `create_infrastructure` | Instance | Abstract method — just call `self.create()` |
| `create` | Instance | Build all resources, export values, return `get_outputs()` |
| `get_outputs` | Instance | Return dict of resource attributes for downstream templates |
| `get_metadata` | Classmethod | Template info for the catalog UI (title, description, pillars) |
| `get_config_schema` | Classmethod | Config fields rendered in the deploy form |

---

## The 7 Golden Rules

1. **Pass complete config** to child templates — never cherry-pick. Use `{**self.config}`.
2. **Export everything** — every generated name, ID, ARN via `pulumi.export()`.
3. **Prefer injected values** — check config before generating new values. Makes upgrades safe.
4. **Use typed getters** — `get_bool()`, `get_int()` for DynamoDB/string/bool compatibility.
5. **Declare security attributes explicitly** — encryption, ACLs, ingress rules. Never rely on defaults.
6. **Read from both config levels** — values live in `config.key` OR `config.parameters.key`.
7. **Export generated names** — namer-generated names must be exported and re-read on upgrade.

---

## Config Field Types

The `get_config_schema()` properties render as form fields in the deploy modal:

| Type | Renders As | Extra Fields |
|------|-----------|--------------|
| `string` | Text input | `enum` → dropdown, `format: "textarea"` → multiline |
| `boolean` | Toggle switch | `default: true/false` |
| `number` | Number input | `minimum`, `maximum` |
| `select` | Dropdown | `enum: [...]` for allowed values |

### Field Properties

```python
"my_field": {
    "type": "string",              # Required: string, boolean, number
    "title": "My Field",           # Required: label shown in UI
    "description": "Help text",    # Required: shown below the field
    "default": "value",            # Default value (pre-filled in form)
    "order": 10,                   # Sort order in the form
    "group": "Network",            # Group heading in deploy form
    "isEssential": True,           # Show in collapsed "Essentials" section
    "required": True,              # Field is required (from "required" array)
    "enum": ["a", "b", "c"],       # Dropdown options
    "format": "textarea",          # Multiline text input
    "sensitive": True,             # Mask value (API keys, secrets)
    "cost_impact": "+$32/month",   # Cost indicator badge
    "conditional": {"field": "enable_x"},  # Only show when enable_x is true
}
```

### Config Field Groups

Standard group names used across templates:

| Group | Fields |
|-------|--------|
| **Essentials** | `project_name`, `environment` — always first |
| **Network Configuration** | CIDRs, subnets, DNS settings |
| **Architecture Decisions** | Feature toggles with cost impact |
| **Security & Access** | SSH, encryption, access control |
| **Agent Configuration** | Model, prompt, container (AI templates) |
| **Features** | Optional feature toggles |
| **Tags** | `team_name`, custom tags — always last |

---

## Metadata & Well-Architected Pillars

The `get_metadata()` return value populates the catalog card and detail page.

### Required Fields

| Field | Type | Example |
|-------|------|---------|
| `name` | string | `"aws-vpc-nonprod"` (matches `@template_registry`) |
| `title` | string | `"Single-AZ VPC Foundation"` |
| `description` | string | 1-2 sentences describing what it deploys |
| `category` | string | `networking`, `compute`, `database`, `storage`, `security`, `ai`, `cdn`, `serverless`, `web` |
| `version` | string | `"1.0.0"` (semver) |
| `author` | string | `"Archie"` or company name |
| `cloud` | string | `"aws"`, `"gcp"`, `"azure"`, `"kubernetes"` |
| `environment` | string | `"nonprod"` or `"prod"` |
| `base_cost` | string | `"$20/month"` |
| `features` | list | Feature bullet points |
| `tags` | list | Search keywords |
| `deployment_time` | string | `"3-5 minutes"` |
| `complexity` | string | `"beginner"`, `"intermediate"`, `"advanced"` |
| `use_cases` | list | What users build with this |
| `pillars` | list | Well-Architected pillar assessments |

### Pillar Format

Every template should assess itself against AWS Well-Architected pillars:

```python
"pillars": [
    {
        "title": "Security",                    # Pillar name
        "score": "excellent",                   # excellent, good, needs-improvement
        "score_color": "#10b981",               # green=#10b981, yellow=#f59e0b, red=#ef4444
        "description": "One-line summary",      # Short description
        "practices": [                          # 3-5 bullet points
            "Least-privilege IAM roles",
            "Encryption at rest with AES-256",
            "VPC Flow Logs for audit trail",
        ]
    },
    # Include: Security, Operational Excellence, Cost Optimization, Reliability, Sustainability
]
```

---

## Factory Pattern

Use `factory.create()` instead of direct Pulumi resource constructors. The factory handles resource tracking, naming consistency, and UI integration.

```python
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory

# Good: factory.create()
self.vpc = factory.create(
    "aws:ec2:Vpc",              # Provider:Service:Resource format
    f"vpc-{project}-{env}",     # Logical resource name
    cidr_block="10.0.0.0/16",
    tags={**tags, "Name": f"vpc-{project}-{env}"},
)

# Bad: direct constructor (only use for resources factory doesn't support)
self.vpc = aws.ec2.Vpc(...)
```

### Common Resource Types

| Type String | AWS Resource |
|-------------|-------------|
| `aws:ec2:Vpc` | VPC |
| `aws:ec2:Subnet` | Subnet |
| `aws:ec2:SecurityGroup` | Security Group |
| `aws:ec2:Instance` | EC2 Instance |
| `aws:s3:Bucket` | S3 Bucket |
| `aws:rds:Instance` | RDS Database |
| `aws:iam:Role` | IAM Role |
| `aws:iam:Policy` | IAM Managed Policy |
| `aws:iam:RolePolicy` | IAM Inline Policy |
| `aws:iam:RolePolicyAttachment` | Policy Attachment |
| `aws:cloudwatch:LogGroup` | CloudWatch Log Group |
| `aws:ecr:Repository` | ECR Container Registry |
| `aws:eks:Cluster` | EKS Kubernetes Cluster |
| `aws:elasticache:Cluster` | ElastiCache (Redis) |

---

## Tags

Every resource should have standard tags:

```python
from provisioner.utils.aws.tags import get_standard_tags

tags = get_standard_tags(
    project=project,
    environment=env,
    template='aws-my-template'
)
tags['ManagedBy'] = 'Archie'
tags.update(self._cfg('tags', {}))  # Allow custom tags from config
if team_name:
    tags['Team'] = team_name

# Apply to every resource:
factory.create("aws:s3:Bucket", name, tags={**tags, "Name": name})
```

---

## Outputs & Exports

Templates export values for two reasons:
1. **Downstream templates** consume them (VPC exports subnet IDs → RDS reads them)
2. **Upgrades** re-inject them to prevent resource replacement

```python
# In create():
pulumi.export('vpc_id', self.vpc.id)
pulumi.export('vpc_cidr', self.vpc.cidr_block)
pulumi.export('public_subnet_ids', [subnet.id for subnet in self.public_subnets])

# In get_outputs():
def get_outputs(self) -> Dict[str, Any]:
    return {
        "vpc_id": self.vpc.id if self.vpc else None,
        "vpc_cidr": self.vpc.cidr_block if self.vpc else None,
        "public_subnet_ids": [s.id for s in self.public_subnets] if self.public_subnets else [],
    }
```

---

## Folder Structure

```
provisioner/templates/templates/{cloud}/{category}/{template_name}/
├── __init__.py      # Empty file (required for Python imports)
├── pulumi.py        # Main template class (required)
├── config.py        # Config class (optional, for complex templates)
└── README.md        # Template documentation (optional)
```

### Naming Convention

| Item | Format | Example |
|------|--------|---------|
| Folder name | `snake_case` (no cloud prefix) | `vpc_nonprod` |
| action_name | `cloud-kebab-case` | `aws-vpc-nonprod` |
| Registry key | Same as action_name | `@template_registry("aws-vpc-nonprod")` |
| Class name | PascalCase | `VPCNonprodTemplate` |

---

## Publishing to Archie

After writing your template, publish it to the marketplace:

1. **Fork from catalog** — If based on an existing template, fork it first
2. **Edit code** — Modify the forked blueprint's code in the Blueprint Editor
3. **Validate** — Use Template Checker (`/template-checker`) to validate
4. **Publish** — Click "Publish" to make it available to developers

### Or import via API:

Templates can be registered in the marketplace DynamoDB table with these fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Same as `action_name` |
| `version` | string | Yes | `"latest"` for current version |
| `action_name` | string | Yes | Template identifier |
| `title` | string | Yes | Display name |
| `description` | string | Yes | Template description |
| `category` | string | Yes | Category for filtering |
| `cloud` | string | Yes | Cloud provider |
| `config_fields` | list | Yes | Deploy form field definitions |
| `pillars` | list | Yes | Well-Architected assessments |
| `pulumiCode` | string | Yes | Full Python source code |
| `features` | list | Yes | Feature list |
| `estimated_cost` | string | Yes | Cost estimate |
| `deployment_time` | string | Yes | Deploy time estimate |
| `is_listed_in_marketplace` | boolean | Yes | `true` to show in catalog |

### Config Fields Format (DynamoDB)

```json
{
  "name": "project_name",
  "label": "Project Name",
  "type": "text",
  "default": "myproject",
  "required": true,
  "group": "Essentials",
  "helpText": "Used in resource naming"
}
```

For dropdowns:
```json
{
  "name": "environment",
  "label": "Environment",
  "type": "select",
  "default": "dev",
  "required": true,
  "group": "Essentials",
  "helpText": "Target environment",
  "options": [
    {"value": "dev", "label": "Dev"},
    {"value": "staging", "label": "Staging"},
    {"value": "prod", "label": "Production"}
  ]
}
```

---

## Common Patterns

### Boolean Config Fields

```python
enable_feature = self._cfg('enable_feature', False)
# Handle string/bool/Decimal from DynamoDB
if isinstance(enable_feature, str):
    enable_feature = enable_feature.lower() in ('true', '1', 'yes')

if enable_feature:
    # Create optional resource
```

### Conditional Resources

```python
if self._cfg('enable_monitoring', True):
    self.dashboard = factory.create("aws:cloudwatch:Dashboard", ...)
    pulumi.export('dashboard_url', self.dashboard.dashboard_arn)
```

### Brownfield (Existing Resources)

```python
vpc_mode = self._cfg('vpc_mode', 'new')  # "new" or "existing"

if vpc_mode == 'existing':
    vpc_id = self._cfg('existing_vpc_id')
    self.vpc = aws.ec2.Vpc.get("existing-vpc", vpc_id)
else:
    self.vpc = factory.create("aws:ec2:Vpc", ...)
```

### IAM Eventual Consistency

```python
import time

def _wait_for_iam(arn):
    time.sleep(30)
    return arn

# Use .apply() to wait before using the role
runtime = aws.bedrock.AgentcoreAgentRuntime(
    "my-runtime",
    role_arn=role.arn.apply(_wait_for_iam),
    opts=pulumi.ResourceOptions(depends_on=[role, policy]),
)
```

---

## Checklist Before Publishing

- [ ] Class extends `InfrastructureTemplate`
- [ ] `@template_registry("action-name")` decorator
- [ ] `__init__` has type hints, calls `super().__init__(name, raw_config)`
- [ ] `create_infrastructure()` wraps `create()`
- [ ] `_cfg()` reads from root + parameters + parameters.aws
- [ ] All resources use `factory.create()` where possible
- [ ] Every resource has `tags={**tags, "Name": ...}`
- [ ] `pulumi.export()` for every generated value
- [ ] `get_outputs()` returns resource references (not empty dict)
- [ ] `get_metadata()` has all required fields including pillars with scores
- [ ] `get_config_schema()` defines all config fields with groups and order
- [ ] `project_name` and `environment` in Essentials group
- [ ] `team_name` in Tags group
- [ ] `__init__.py` exists in template folder
- [ ] Category matches one of: networking, compute, database, storage, security, ai, cdn, serverless, web
