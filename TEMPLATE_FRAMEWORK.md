# Archie Template Framework

The definitive guide for writing Archie infrastructure templates. Follow this document to produce templates that deploy real cloud resources and render correctly in the Archie UI.

All examples reference the VPC NonProd template (`templates/aws/networking/vpc_nonprod/`) as the gold standard.

---

## Table of Contents

1. [Template Anatomy](#1-template-anatomy)
2. [The Factory Pattern](#2-the-factory-pattern)
3. [Config Class Pattern](#3-config-class-pattern)
4. [Config Schema Spec (for UI Rendering)](#4-config-schema-spec-for-ui-rendering)
5. [Metadata & Well-Architected Pillars](#5-metadata--well-architected-pillars)
6. [Outputs & Exports](#6-outputs--exports)
7. [ResourceNamer API](#7-resourcenamer-api)
8. [Security Group Tiers](#8-security-group-tiers)
9. [Template Composition](#9-template-composition)
10. [User Data Scripts](#10-user-data-scripts)
11. [Pre-Publish Checklist](#11-pre-publish-checklist)
12. [Common Mistakes](#12-common-mistakes)
13. [Template Development Workflow](#13-template-development-workflow)

---

## 1. Template Anatomy

### File Structure

Every template lives under `provisioner/templates/templates/{cloud}/{category}/{template_name}/` and contains these files:

```
templates/aws/networking/vpc_nonprod/
  __init__.py          # Empty, makes directory a Python package
  pulumi.py            # Infrastructure code (THE template)
  template.yaml        # Metadata, resource manifest, config schema, outputs
  config.py            # (Optional) Custom config class for complex templates
  scripts/             # (Optional) User data scripts for EC2 templates
    web-server.sh
    wordpress.sh
```

- `pulumi.py` is the only file the engine executes. Everything else is metadata.
- `template.yaml` is the source-of-truth the UI reads for the deploy form, resource list, and cost breakdown.
- `config.py` is optional. Simple templates can use `TemplateConfig` directly (loaded from `template.yaml`). Complex templates (EC2 with presets, multi-instance) benefit from a dedicated config class.

### Registration with `@template_registry`

The decorator registers the template class so the Archie engine can look it up by action name at deploy time.

```python
from provisioner.templates.base import template_registry, InfrastructureTemplate

@template_registry("aws-vpc-nonprod")      # <-- action_name, matches template.yaml
class VPCSimpleNonprodTemplate(InfrastructureTemplate):
    ...
```

**Rules:**
- The string passed to `@template_registry` is the **action name**. It must match the `metadata.action_name` field in `template.yaml`.
- Convention: `{cloud}-{service}-{variant}` (e.g. `aws-vpc-nonprod`, `aws-ec2-nonprod`, `gcp-compute-nonprod`).
- Action names are globally unique across the entire registry.

### The `InfrastructureTemplate` Base Class

Located at `provisioner/templates/base/template.py`. Your class must implement:

| Method | Required | Purpose |
|---|---|---|
| `__init__(self, name, config, **kwargs)` | Yes | Parse config, store resource refs |
| `create_infrastructure(self) -> Dict` | Yes (abstract) | Deploy resources, return outputs |
| `get_outputs(self) -> Dict` | Yes (abstract) | Return flat dict of outputs for cross-template use |
| `get_metadata(cls) -> Dict` | Yes (classmethod) | Return template metadata for UI/marketplace |
| `get_config_schema(cls) -> Dict` | Yes (classmethod) | Return JSON schema for deploy form |

**Gold standard `__init__`:**

```python
def __init__(self, name: str = None, config: Dict[str, Any] = None, aws: Dict[str, Any] = None, **kwargs):
    raw_config = config or aws or kwargs or {}

    if name is None:
        name = (
            raw_config.get('project_name') or
            raw_config.get('projectName') or
            raw_config.get('parameters', {}).get('aws', {}).get('project_name') or
            'vpc-nonprod'   # sensible fallback
        )

    super().__init__(name, raw_config)

    # Load template.yaml-based config
    template_dir = Path(__file__).parent
    self.cfg = TemplateConfig(template_dir, raw_config)
    self.config = raw_config

    # Declare resource references (populated in create())
    self.vpc = None
    self.igw = None
    self.subnets = {}
    self.security_groups = {}
```

The `create_infrastructure` method typically delegates to a `create()` method:

```python
def create_infrastructure(self) -> Dict[str, Any]:
    return self.create()
```

---

## 2. The Factory Pattern

**Every resource in an Archie template must be created through `PulumiAtomicFactory`**. Direct Pulumi constructor calls (`aws.ec2.Vpc(...)`) are forbidden.

### Import

```python
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory
```

### Full Signature

```python
factory.create(
    resource_type: str,       # Pulumi type token
    resource_name: str,       # Logical name (unique within the stack)
    *,                        # Everything below is keyword-only
    name: str = None,         # Optional cloud resource name (passed as resource property)
    opts: pulumi.ResourceOptions = None,  # Passed via **props, extracted internally
    **props                   # All other resource properties
) -> Any
```

### `resource_type` Format

Follows Pulumi's `provider:service:Resource` convention:

| Cloud | Example |
|---|---|
| AWS | `"aws:ec2:Vpc"`, `"aws:iam:Role"`, `"aws:s3:Bucket"`, `"aws:lb:LoadBalancer"` |
| GCP | `"gcp:compute:Instance"`, `"gcp:storage:Bucket"` |
| Azure | `"azure-native:storage:StorageAccount"`, `"azure-native:resources:ResourceGroup"` |
| K8s | `"kubernetes:apps/v1:Deployment"`, `"kubernetes:core/v1:Service"` |

If a type is not in the static `RESOURCE_MAP`, the factory attempts dynamic lookup from provider modules.

### `resource_name` vs `name`

These are different things:

- **`resource_name`** (positional arg) = Pulumi logical name. Unique within the stack. Used for state tracking. If you change it, Pulumi replaces the resource.
- **`name`** (keyword-only arg) = Cloud-side resource name. Passed as the `name` property on the resource constructor. Optional, and only relevant for resources that accept a `name` property.

### What the Factory Handles

1. **Smart defaults**: Auto-adds `Name` tag if `tags` dict exists but has no `Name` key. Auto-adds `{"Name": resource_name}` tags for taggable types if no tags provided.
2. **Args conversion**: Converts plain dicts to proper Pulumi Args objects (e.g. `health_check` dicts on TargetGroup, `rules` on BucketLifecycleConfigurationV2, `expiration` nested inside rules).
3. **opts extraction**: Pulls `opts=pulumi.ResourceOptions(...)` from `**props` and passes it correctly.

### Examples from VPC NonProd

```python
# VPC with explicit tags
self.vpc = factory.create(
    "aws:ec2:Vpc",
    vpc_name,                           # resource_name = logical name
    cidr_block=vpc_cidr,
    enable_dns_support=True,
    enable_dns_hostnames=True,
    tags={**tags, "Name": vpc_name}
)

# Security Group with inline ingress/egress (plain dicts, not Args)
self.security_groups['web'] = factory.create(
    "aws:ec2:SecurityGroup",
    web_sg_name,
    vpc_id=vpc_id,
    description="Security group for web tier (HTTP/HTTPS)",
    ingress=[
        {
            "protocol": "tcp",
            "from_port": 80,
            "to_port": 80,
            "cidr_blocks": ["0.0.0.0/0"],
            "description": "HTTP from internet"
        }
    ],
    egress=[{
        "protocol": "-1",
        "from_port": 0,
        "to_port": 0,
        "cidr_blocks": ["0.0.0.0/0"],
        "description": "Allow all outbound"
    }],
    tags={**tags, "Name": web_sg_name, "Tier": "web"}
)

# Route (no tags needed)
factory.create(
    "aws:ec2:Route",
    public_route_name,
    route_table_id=self.route_tables['public'].id,
    destination_cidr_block="0.0.0.0/0",
    gateway_id=igw_id
)

# S3 Bucket Lifecycle (factory converts dicts to Args)
factory.create(
    "aws:s3:BucketLifecycleConfigurationV2",
    f"{bucket_name}-lifecycle",
    bucket=self.flow_logs_bucket.id,
    rules=[{
        "id": "delete-old-flow-logs",
        "status": "Enabled",
        "expiration": {"days": 7}
    }]
)
```

---

## 3. Config Class Pattern

Templates can use either `TemplateConfig` (automatic, loads from `template.yaml`) or a custom config class. Complex templates with presets, user data scripts, or derived values benefit from a custom class.

### Using `TemplateConfig` (Recommended for Most Templates)

```python
from provisioner.templates.template_config import TemplateConfig

template_dir = Path(__file__).parent
self.cfg = TemplateConfig(template_dir, raw_config)

# Access values:
self.cfg.project_name          # property
self.cfg.region                # property
self.cfg.enable_flow_logs      # property (from template.yaml schema default or user override)
self.cfg.get('custom_key', 'fallback')  # explicit get with default
```

`TemplateConfig` automatically:
- Loads `template.yaml` from the template directory
- Extracts the `configuration.properties` section as the schema
- Merges user input over schema defaults
- Resolves `parameters.aws` nesting (handles both `{parameters: {aws: {...}}}` and flat `{parameters: {...}}`)
- Provides attribute-style access (`self.cfg.enable_flow_logs`)

### Custom Config Class (for EC2, Presets, User Data)

When you need presets, script loading, or complex derived values:

```python
class EC2NonProdConfig:
    PRESETS = {
        'web-server': {
            'instance_type': 't3.micro',
            'ports': [80, 443],
            'script': 'web-server.sh',
            'is_template': True
        },
    }

    def __init__(self, raw_config: Dict[str, Any]):
        self.raw_config = raw_config
        # Handle both nested and flat parameter structures
        params = self.raw_config.get('parameters', {})
        self.parameters = params.get('aws', {}) or params
        self.environment = 'nonprod'
        self.region = self.raw_config.get('region', 'us-east-1')
        self.tags = self.raw_config.get('tags', {})

    def get_parameter(self, key: str, default: Any = None) -> Any:
        return self.parameters.get(key, default)

    @property
    def project_name(self) -> str:
        return (
            self.get_parameter('projectName') or
            self.get_parameter('project_name') or
            self.raw_config.get('project_name', 'my-app')
        )

    @property
    def user_data(self) -> str:
        preset = self.get_parameter('preset', 'web-server')
        preset_config = self.PRESETS.get(preset, self.PRESETS['web-server'])
        script = self._load_script(preset_config['script'])
        if preset_config.get('is_template'):
            return script.format(
                PROJECT_NAME=self.project_name,
                ENVIRONMENT=self.environment
            )
        return script
```

**Critical fields every config class must have:**
- `self.raw_config` -- the original input
- `self.parameters` -- resolved parameter dict
- `self.environment` -- string
- `self.region` -- string
- `self.tags` -- dict

---

## 4. Config Schema Spec (for UI Rendering)

The `get_config_schema()` classmethod returns a JSON schema that the Archie frontend renders as the deploy form. The schema is also persisted in `template.yaml` under `configuration:`.

### Structure

```python
@classmethod
def get_config_schema(cls) -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "field_name": { ... },
            ...
        },
        "required": ["project_name", "region"]
    }
```

### Field Types

| `type` | Renders As | Notes |
|---|---|---|
| `string` | Text input | Use `placeholder` for hint text |
| `number` / `integer` | Numeric input | |
| `boolean` | Toggle switch | |
| `select` | Dropdown | Requires `enum` array |
| `separator` | Visual divider | UI-only, no value |
| `info` | Info text block | UI-only, no value |
| `syntax` | Code block | For showing example code |

### Required Properties Per Field

| Property | Required | Description |
|---|---|---|
| `type` | Yes | One of the types above |
| `title` | Yes | Human-readable label |
| `description` | Yes | Help text shown below the field |
| `order` | Yes | Sort order within the form (lower = higher) |
| `group` | Yes | Groups fields under a heading |
| `default` | Recommended | Pre-filled value |
| `placeholder` | Optional | Greyed-out hint for text inputs |
| `readOnly` | Optional | Prevents user editing |
| `isEssential` / `is_essential` | Optional | Shows field prominently |
| `cost_impact` | Optional | e.g. `"+$32/month"`, shown next to toggle |
| `architecture_decision` | Optional | Marks as an architecture toggle |
| `conditional` | Optional | Object: `{"field": "other_field_name"}` -- shows only when other field is truthy |
| `visibleIf` | Optional | Alternative conditional syntax |

### Group Naming Conventions

Use these standard group names so the UI renders sections consistently:

| Group | Order Range | Purpose |
|---|---|---|
| `"Essentials"` | 0-9 | Project name, region, environment |
| `"Network Configuration"` | 10-29 | CIDR, DNS, subnets |
| `"Compute"` | 30-49 | Instance type, AMI, key pair |
| `"Security"` / `"Security & Access"` | 50-69 | SSH, SGs, IAM |
| `"Observability"` | 70-89 | Logging, monitoring, flow logs |
| `"Architecture Decisions"` | 100-109 | Major on/off toggles with cost impacts |
| `"High Availability & Cost"` | 110-129 | HA toggles, retention, scaling |
| `"Load Balancer"` | 130-149 | ALB/NLB settings |

### Annotated Example from VPC NonProd

```python
"enable_nat_gateway": {
    "type": "boolean",
    "default": True,
    "title": "Enable NAT Gateway",
    "description": "Provides outbound internet access for private subnets via NAT Gateway",
    "architecture_decision": True,          # Renders as architecture toggle card
    "smart_default_enabled": True,          # Default is ON
    "foundation": True,                     # Core infrastructure decision
    "section": "Internet Access",           # Sub-section label
    "order": 101,                           # Sorted within Architecture Decisions group
    "group": "Architecture Decisions",
    "cost_impact": "+$32/month"             # Shown as cost badge
},
"custom_cidr_block": {
    "type": "string",
    "default": "10.0.0.0/16",
    "title": "Custom CIDR Block",
    "description": "Specify custom IPv4 CIDR block",
    "order": 11,
    "group": "Network Configuration",
    "conditional": {                        # Only shown when use_custom_cidr is true
        "field": "use_custom_cidr"
    }
}
```

---

## 5. Metadata & Well-Architected Pillars

### `get_metadata()` Return Value

Must return a dict with all of these keys:

```python
@classmethod
def get_metadata(cls) -> Dict[str, Any]:
    return {
        "name": "aws-vpc-nonprod",                    # Action name (matches registry)
        "title": "Single-AZ VPC Foundation",           # Display title (short)
        "description": "Ultra cost-optimized...",      # One-line description
        "category": "networking",                       # networking|compute|database|serverless|storage|website|security|containers
        "cloud": "aws",                                 # aws|gcp|azure
        "version": "3.0.0",                            # Semver
        "author": "InnovativeApps",                    # Org name
        "tags": ["vpc", "networking", "nonprod"],      # Search/filter tags
        "base_cost": "$20/month",                      # Starting monthly cost
        "deployment_time": "4-6 minutes",              # Human-readable estimate
        "complexity": "beginner",                       # beginner|intermediate|advanced
        "features": [                                   # Bullet points for UI card
            "Single-AZ deployment for cost optimization",
            "1 NAT Gateway (saves $32/mo vs multi-AZ)",
            ...
        ],
        "pillars": [ ... ]                             # See below
    }
```

### Well-Architected Pillars

All 6 pillars are **required**. Each pillar object:

```python
{
    "title": "Operational Excellence",       # Exact pillar name
    "score": "excellent",                     # excellent | good | needs-improvement
    "score_color": "#10b981",                 # Green=#10b981, Yellow=#f59e0b, Red=#ef4444
    "description": "Enables infrastructure...", # One sentence summary
    "practices": [                            # 4-5 specific practices
        "Infrastructure as Code with Pulumi for repeatable deployments",
        "VPC Flow Logs for operational visibility and troubleshooting",
        "Configurable resource naming conventions for easy identification",
        "Optional VPC endpoints for centralized service access",
        "Automated subnet and routing table configuration"
    ]
}
```

### Score-to-Color Mapping

| Score | Color | Hex |
|---|---|---|
| `excellent` | Green | `#10b981` |
| `good` | Yellow/Amber | `#f59e0b` |
| `needs-improvement` | Red | `#ef4444` |

### Pillar Cheat Sheet by Resource Type

Use this as a starting point. Adjust scores and practices to match what the template actually implements.

**VPC / Networking:**
| Pillar | Typical Score | Key Practices |
|---|---|---|
| Operational Excellence | excellent | IaC, flow logs, naming conventions, automated routing |
| Security | excellent | Multi-tier SGs, private subnets, NACLs, isolated tier |
| Reliability | good/excellent | Multi-AZ (prod), NAT redundancy, endpoint HA |
| Performance Efficiency | good | Subnet isolation, VPC endpoints, configurable CIDR |
| Cost Optimization | good | NAT count optimization, S3 flow logs, gateway endpoints |
| Sustainability | good | Right-sized networking, regional services, minimal redundancy |

**EC2 / Compute:**
| Pillar | Typical Score | Key Practices |
|---|---|---|
| Operational Excellence | good | Automated provisioning, user data scripts, CloudWatch |
| Security | excellent | IMDSv2, SG tier assignment, IAM instance profiles, encrypted EBS |
| Reliability | good | Health checks, auto-recovery, snapshot policies |
| Performance Efficiency | good | Right-sized instances, EBS optimization, placement groups |
| Cost Optimization | excellent | Spot/reserved options, right-sizing, scheduled scaling |
| Sustainability | good | Graviton/ARM options, auto-shutdown, efficient instance types |

**RDS / Database:**
| Pillar | Typical Score | Key Practices |
|---|---|---|
| Operational Excellence | excellent | Automated backups, parameter groups, monitoring |
| Security | excellent | Encryption at rest, SSL in transit, private subnet, SG tier |
| Reliability | excellent | Multi-AZ, automated backups, read replicas |
| Performance Efficiency | good | Instance right-sizing, IOPS provisioning, query insights |
| Cost Optimization | good | Reserved instances, storage autoscaling, aurora serverless |
| Sustainability | good | Graviton instances, serverless scaling, storage efficiency |

**S3 / Static Website:**
| Pillar | Typical Score | Key Practices |
|---|---|---|
| Operational Excellence | good | Versioning, lifecycle policies, access logging |
| Security | excellent | Bucket policies, public access blocks, encryption, OAC |
| Reliability | excellent | 11 9s durability, cross-region replication |
| Performance Efficiency | good | CloudFront CDN, transfer acceleration |
| Cost Optimization | excellent | Lifecycle policies, intelligent tiering, no server costs |
| Sustainability | excellent | Serverless, no idle compute, efficient storage classes |

---

## 6. Outputs & Exports

Every template must export values two ways:

1. **`pulumi.export(key, value)`** -- Persisted in Pulumi state, visible in the Archie UI deployment detail drawer.
2. **`get_outputs()` return dict** -- Used for cross-template composition (group templates access child outputs).

### `pulumi.export()` in `create()`

Call at the end of `create()` for every user-relevant resource ID, ARN, endpoint, or URL:

```python
# From VPC NonProd
pulumi.export("vpc_id", self.vpc.id)
pulumi.export("vpc_cidr", self.vpc.cidr_block)
pulumi.export("vpc_arn", self.vpc.arn)
pulumi.export("internet_gateway_id", self.igw.id)
pulumi.export("nat_gateway_id", self.nat_gateway.id)
pulumi.export("public_subnet_id", self.subnets['public'].id)
pulumi.export("private_subnet_id", self.subnets['private'].id)
pulumi.export("security_group_web_id", self.security_groups['web'].id)
pulumi.export("security_group_app_id", self.security_groups['app'].id)
pulumi.export("security_group_db_id", self.security_groups['db'].id)

# Conditional outputs
if self.cfg.enable_isolated_tier:
    pulumi.export("isolated_subnet_id", self.subnets['isolated'].id)
if self.cfg.enable_flow_logs:
    pulumi.export("flow_logs_bucket", self.flow_logs_bucket.id)
```

### Output Naming Convention

- Always `snake_case`
- Descriptive and unambiguous
- Match the resource name pattern where possible

### Required Outputs by Template Type

**VPC:**
```
vpc_id, vpc_cidr, vpc_arn
internet_gateway_id, nat_gateway_id
public_subnet_id, private_subnet_id, isolated_subnet_id (conditional)
public_route_table_id, private_route_table_id
security_group_web_id, security_group_app_id, security_group_db_id
vpc_endpoint_s3_id, vpc_endpoint_dynamodb_id
flow_logs_bucket, flow_log_id (conditional)
```

**EC2:**
```
instance_id, public_ip, private_ip
security_group_id
ssh_command (e.g. "ssh -i key.pem ec2-user@<ip>")
```

**ALB:**
```
alb_arn, alb_dns_name, alb_url (http:// prefixed)
target_group_arn
listener_http_arn, listener_https_arn
```

**RDS:**
```
endpoint, port, db_name
connection_string (e.g. "postgresql://user@host:5432/dbname")
subnet_group_name
```

**EKS:**
```
cluster_name, cluster_endpoint, cluster_arn
kubeconfig_command (e.g. "aws eks update-kubeconfig --name ...")
node_group_name
```

**Static Website (S3/CloudFront):**
```
website_url, bucket_name, bucket_arn
distribution_id, distribution_domain (if CloudFront)
```

**DynamoDB:**
```
table_name, table_arn
```

### `get_outputs()` Method

Must return a **flat** dict. Nested values are acceptable only as secondary convenience (keep flat keys as primary):

```python
def get_outputs(self) -> Dict[str, Any]:
    outputs = {
        "vpc_id": self.vpc.id if self.vpc else None,
        "vpc_cidr": self.vpc.cidr_block if self.vpc else None,

        # Singular (backward compat)
        "public_subnet_id": self.subnets.get('public').id if 'public' in self.subnets else None,
        "private_subnet_id": self.subnets.get('private').id if 'private' in self.subnets else None,

        # Plural (for cross-template use -- RDS needs lists)
        "public_subnet_ids": [self.subnets['public'].id] if 'public' in self.subnets else [],
        "private_subnet_ids": [self.subnets['private'].id] if 'private' in self.subnets else [],

        # Flat security group IDs
        "web_security_group_id": self.security_groups.get('web').id if 'web' in self.security_groups else None,
        "app_security_group_id": self.security_groups.get('app').id if 'app' in self.security_groups else None,
        "db_security_group_id": self.security_groups.get('db').id if 'db' in self.security_groups else None,
    }

    # Map isolated subnet to db_subnet_ids for RDS template consumption
    if 'isolated' in self.subnets:
        outputs["db_subnet_ids"] = [self.subnets['isolated'].id]
    elif 'private' in self.subnets:
        outputs["db_subnet_ids"] = [self.subnets['private'].id]

    return outputs
```

---

## 7. ResourceNamer API

`ResourceNamer` generates consistent, self-documenting resource names that encode configuration details (CIDR ranges, ports, instance types).

### Import and Constructor

```python
from provisioner.utils.aws import ResourceNamer

namer = ResourceNamer(
    project="my-app",          # Project name (auto-cleaned)
    environment="nonprod",     # Environment string
    region="us-east-1",        # Full AWS region
    template="aws-vpc-nonprod" # Template action name (for tags)
)
```

### Naming Pattern

All names follow: `type-role-project[-config]-env-regioncode`

Example: `vpc-myapp-nonprod-use1-123`

### Available Methods

| Method | Signature | Example Output |
|---|---|---|
| `vpc()` | `vpc(cidr="10.123.0.0/16")` | `vpc-myapp-nonprod-use1-123` |
| `subnet()` | `subnet("public", "us-east-1a", cidr="10.0.0.0/20")` | `pubsub-myapp-nonprod-use1-1a-0` |
| `security_group()` | `security_group("web", ports=[80, 443])` | `secg-web-myapp-nonprod-use1-http-https` |
| `internet_gateway()` | `internet_gateway()` | `igw-main-myapp-nonprod-use1` |
| `nat_gateway()` | `nat_gateway("us-east-1a")` | `nat-gw-myapp-nonprod-use1-1a` |
| `eip()` | `eip("us-east-1a")` | `eip-nat-myapp-nonprod-use1-1a` |
| `route_table()` | `route_table("public")` | `rt-public-myapp-nonprod-use1` |
| `route()` | `route("0.0.0.0/0", "igw")` | `route-00000-myapp-nonprod-use1-igw` |
| `route_table_association()` | `route_table_association("public", 1)` | `rta-public-myapp-nonprod-use1-1` |
| `vpc_endpoint()` | `vpc_endpoint("s3", "gateway")` | `vpce-s3-myapp-nonprod-use1-gw` |
| `flow_logs()` | `flow_logs("vpc", "all")` | `fl-vpc-myapp-nonprod-use1-all` |
| `s3_bucket()` | `s3_bucket("flowlogs")` | `s3-flowlogs-myapp-nonprod-use1` |
| `ec2_instance()` | `ec2_instance("web-server")` | `ec2-web-server-myapp-nonprod-use1` |
| `iam_role()` | `iam_role("ec2", "ssm")` | `role-ec2-myapp-nonprod-use1-ssm` |
| `iam_profile()` | `iam_profile("ec2")` | `profile-ec2-myapp-nonprod-use1` |
| `rds()` | `rds("postgres")` | `rds-pg-myapp-nonprod-use1` |
| `elasticache()` | `elasticache("redis")` | `ec-redis-myapp-nonprod-use1` |
| `nacl()` | `nacl("public")` | `nacl-public-myapp-nonprod-use1` |
| `tags()` | `tags(Team="platform")` | `{"Project": ..., "Team": "platform", ...}` |

### `_clean_project_name()` -- Critical Behavior

The namer strips redundant tokens from the project name before using it. These tokens are removed:

- **Infrastructure terms**: `stack`, `vpc`, `ec2`, `rds`, `s3`, `db`, `cluster`, `eks`, `alb`, `instance`
- **Environment terms**: `prod`, `nonprod`, `dev`, `staging`, `test`, `sandbox`
- **Region terms**: `us`, `east`, `west`, `north`, `south`, `central`, `use1`, `euw2`, etc.
- **Single digits**: `1`, `2`, `3`, `4`, `5` and any string that is purely numeric

**This means single digits are NOT safe differentiators.** If you have two instances in a group template, do NOT name them `server-1` and `server-2` (both clean to `server`). Instead use alphabetic labels:

```python
# BAD -- both resolve to the same cleaned name
"my-app-1"  # -> "my-app"
"my-app-2"  # -> "my-app"  COLLISION

# GOOD -- distinct after cleaning
"my-app-alpha"  # -> "my-app-alpha"
"my-app-bravo"  # -> "my-app-bravo"
```

---

## 8. Security Group Tiers

VPC templates create a 3-tier security group architecture. Downstream templates (EC2, RDS, ALB) reference these tiers rather than defining their own rules.

### The Three Tiers

| Tier | Purpose | Inbound From | Ports |
|---|---|---|---|
| **web** | Public-facing (ALB, web servers) | `0.0.0.0/0` | 80, 443 |
| **app** | Application layer | web SG only | 3000, 8080 |
| **db** | Database layer | app SG only | 3306, 5432, 1433 |

### How They Chain

```
Internet --> [web SG: 80,443] --> [app SG: 3000,8080] --> [db SG: 3306,5432]
```

Each tier only accepts traffic from the tier above it (via security group references, not CIDR blocks).

### VPC NonProd Implementation

```python
# Web tier -- open to internet
self.security_groups['web'] = factory.create(
    "aws:ec2:SecurityGroup", web_sg_name,
    vpc_id=vpc_id,
    ingress=[
        {"protocol": "tcp", "from_port": 80, "to_port": 80,
         "cidr_blocks": ["0.0.0.0/0"], "description": "HTTP from internet"},
        {"protocol": "tcp", "from_port": 443, "to_port": 443,
         "cidr_blocks": ["0.0.0.0/0"], "description": "HTTPS from internet"}
    ],
    egress=[{"protocol": "-1", "from_port": 0, "to_port": 0,
             "cidr_blocks": ["0.0.0.0/0"], "description": "Allow all outbound"}],
    tags={**tags, "Name": web_sg_name, "Tier": "web"}
)

# App tier -- only from web SG
self.security_groups['app'] = factory.create(
    "aws:ec2:SecurityGroup", app_sg_name,
    vpc_id=vpc_id,
    ingress=[
        {"protocol": "tcp", "from_port": 3000, "to_port": 3000,
         "security_groups": [self.security_groups['web'].id],
         "description": "App traffic from web tier"},
        {"protocol": "tcp", "from_port": 8080, "to_port": 8080,
         "security_groups": [self.security_groups['web'].id],
         "description": "Alt app port from web tier"}
    ],
    ...
)

# DB tier -- only from app SG
self.security_groups['db'] = factory.create(
    "aws:ec2:SecurityGroup", db_sg_name,
    vpc_id=vpc_id,
    ingress=[
        {"protocol": "tcp", "from_port": 3306, "to_port": 3306,
         "security_groups": [self.security_groups['app'].id],
         "description": "MySQL from app tier"},
        {"protocol": "tcp", "from_port": 5432, "to_port": 5432,
         "security_groups": [self.security_groups['app'].id],
         "description": "PostgreSQL from app tier"}
    ],
    ...
)
```

### EC2 Preset-to-SG Mapping

When an EC2 template deploys into a VPC with these SGs, it picks the right tier based on preset:

| Preset | Assigned SG Tier | Why |
|---|---|---|
| `web-server` | web | Needs public HTTP/HTTPS access |
| `wordpress` | web | Needs public HTTP/HTTPS access |
| `alb-backend` | app | Receives traffic from ALB (web tier) |
| `nodejs` | app | Backend service behind proxy |
| `mysql` | db | Database, only app tier connects |

**Never hardcode SG rules in EC2 templates.** Always reference the VPC's tier SGs.

### Optional Access SG

For SSH/RDP access, the VPC can optionally create a 4th SG (`access`) restricted to a specific IP:

```python
if self.cfg.get('enable_ssh_access', False):
    ssh_access_ip = self.cfg.get('ssh_access_ip', '1.2.3.4/32')
    self.security_groups['access'] = factory.create(
        "aws:ec2:SecurityGroup", access_sg_name,
        ingress=[
            {"protocol": "tcp", "from_port": 22, "to_port": 22,
             "cidr_blocks": [ssh_access_ip], "description": f"SSH from {ssh_access_ip}"}
        ],
        ...
    )
```

---

## 9. Template Composition

Group templates compose multiple child templates into a single deployable stack (e.g., ALB group = VPC + EC2 + LoadBalancer).

### Architecture

```
Group Template (pulumi.py)
  |
  +-- Instantiates Child Template A (VPC)
  +-- Instantiates Child Template B (EC2)
  +-- Wires outputs: VPC.vpc_id -> EC2.vpc_id
```

### Config Passing

Pass config under `parameters.aws` for child templates:

```python
vpc_config = {
    "parameters": {
        "aws": {
            "project_name": f"{project_name}-alpha",  # Unique name!
            "region": region,
            "environment": environment,
            "enable_nat_gateway": True,
        }
    }
}

vpc_template = VPCSimpleNonprodTemplate(config=vpc_config)
vpc_outputs = vpc_template.create()
```

### Avoiding URN Collisions

Each child template creates resources with names derived from the project name. If two children use the same project name, their resource logical names will collide.

**Use alphabetic labels, not numbers:**

```python
# GOOD
vpc_alpha = VPCTemplate(config={"parameters": {"aws": {"project_name": "myapp-alpha"}}})
vpc_bravo = VPCTemplate(config={"parameters": {"aws": {"project_name": "myapp-bravo"}}})

# BAD -- digits get stripped by _clean_project_name()
vpc_1 = VPCTemplate(config={"parameters": {"aws": {"project_name": "myapp-1"}}})
vpc_2 = VPCTemplate(config={"parameters": {"aws": {"project_name": "myapp-2"}}})
# Both resolve to "myapp" after cleaning -- COLLISION
```

### Wiring Child Outputs

Use `get_outputs()` to pass values between children:

```python
vpc_outputs = vpc_template.get_outputs()

ec2_config = {
    "parameters": {
        "aws": {
            "project_name": project_name,
            "vpc_id": vpc_outputs["vpc_id"],
            "subnet_id": vpc_outputs["public_subnet_id"],
            "security_group_ids": [vpc_outputs["web_security_group_id"]],
        }
    }
}
ec2_template = EC2NonProdTemplate(config=ec2_config)
ec2_template.create()
```

---

## 10. User Data Scripts

EC2 templates can include shell scripts that run on first boot. These live in a `scripts/` directory next to `pulumi.py`.

### File Layout

```
templates/aws/compute/ec2_nonprod/
  pulumi.py
  config.py
  template.yaml
  scripts/
    web-server.sh
    wordpress.sh
    mysql.sh
    nodejs.sh
    alb-backend.sh
```

### Preset Mapping

The config class maps presets to scripts:

```python
PRESETS = {
    'web-server': {
        'instance_type': 't3.micro',
        'ports': [80, 443],
        'script': 'web-server.sh',
        'is_template': True       # True = Python format() substitution applied
    },
    'wordpress': {
        'instance_type': 't3.small',
        'ports': [80, 443],
        'script': 'wordpress.sh',
        'is_template': False      # False = script used as-is
    },
}
```

### Loading and Formatting

```python
def _load_script(self, filename: str) -> str:
    script_path = Path(__file__).parent / 'scripts' / filename
    with open(script_path, 'r') as f:
        return f.read()

@property
def user_data(self) -> str:
    preset = self.get_parameter('preset', 'web-server')
    preset_config = self.PRESETS.get(preset, self.PRESETS['web-server'])
    script = self._load_script(preset_config['script'])
    if preset_config.get('is_template'):
        return script.format(
            PROJECT_NAME=self.project_name,
            ENVIRONMENT=self.environment
        )
    return script
```

### Escaping Bash Variables

When `is_template` is `True`, Python's `format()` is called on the script. This means **bare `$` signs will break**.

**Rule: Double the braces around bash variables.**

```bash
# WRONG -- Python format() will try to substitute {counter}
counter=0
while [ $counter -lt 10 ]; do
    echo "Count: ${counter}"
done

# CORRECT -- Escaped for Python format()
counter=0
while [ $counter -lt 10 ]; do
    echo "Count: ${{counter}}"
done
```

Archie variables use single braces and are substituted:

```bash
echo "Deploying {PROJECT_NAME} to {ENVIRONMENT}"
# After format(): "Deploying my-app to nonprod"
```

Summary:
- `{PROJECT_NAME}` -- Archie substitution variable (single braces)
- `${{BASH_VAR}}` -- Bash variable that should survive Python `format()` (doubled braces)
- `$BASH_VAR` -- Safe as-is (no braces, Python ignores it)

---

## 11. Pre-Publish Checklist

Before publishing a template to the marketplace, verify every item:

- [ ] All resources created via `factory.create()` -- zero direct Pulumi constructor calls
- [ ] Config class (or `TemplateConfig`) has: `environment`, `region`, `tags`, `project_name`
- [ ] Config schema has: `group`, `order`, `description`, and `default` on every field
- [ ] Metadata has all 6 Well-Architected pillars with scores and 4-5 practices each
- [ ] All relevant outputs exported via `pulumi.export()` at the end of `create()`
- [ ] `get_outputs()` returns a flat dict with both singular and plural ID keys
- [ ] `ResourceNamer` used for all resource naming -- no hand-crafted name strings
- [ ] Security groups use the tier system (web/app/db chain)
- [ ] User data scripts escape bash variables with `${{...}}` when `is_template: True`
- [ ] `template.yaml` has a `resources:` section listing every resource the template creates
- [ ] `template.yaml` `metadata.action_name` matches the `@template_registry` string
- [ ] `template.yaml` `outputs:` section lists every `pulumi.export()` key
- [ ] `pulumi preview` passes without errors
- [ ] `pulumi up` creates real resources successfully
- [ ] `pulumi destroy` cleanly removes all resources

---

## 12. Common Mistakes

### 1. `name` kwarg on factory.create

`name` is keyword-only. This works:
```python
factory.create("aws:iam:Role", "my-role", name="role-name")
```
This does NOT work (positional):
```python
factory.create("aws:iam:Role", "my-role", "role-name")  # TypeError
```

### 2. `_clean_project_name()` strips digits

Single digits (`1`, `2`, `3`) are stripped from project names. If you use `myapp-1` and `myapp-2` as child project names in a group template, both clean to `myapp` and you get URN collisions.

**Fix:** Use `myapp-alpha`, `myapp-bravo`.

### 3. Config reading `parameters.aws`

The config might arrive as `{"parameters": {"aws": {...}}}` or as flat `{"parameters": {...}}`. Always handle both:

```python
params = raw_config.get('parameters', {})
self.parameters = params.get('aws', {}) or params
```

### 4. Missing `self.region` or `self.tags` on config class

Both are used by `ResourceNamer` and tag generation. If your config class omits them, namer calls will fail silently or produce wrong names.

### 5. Missing imports

```python
from typing import Dict, Any, Optional, List  # Always need these
```

### 6. Forgetting `pulumi.export()` calls

If you create resources but don't export their IDs, the Archie UI shows an empty outputs section. The deployment drawer looks broken. Always export every meaningful ID, ARN, and endpoint.

### 7. EC2 assigned to wrong SG tier

A `web-server` preset EC2 must be in the **web** SG (public HTTP access). A common mistake is assigning it to the **app** SG, which only accepts traffic from the web SG -- meaning no public access.

| Preset | Correct SG | Wrong SG |
|---|---|---|
| `web-server` | web | app |
| `alb-backend` | app | web |
| `mysql` | db | app |

### 8. User data `${BASH_VAR}` not escaped

If a script has `is_template: True` and contains `${SOME_VAR}`, Python's `format()` raises `KeyError`. Escape as `${{SOME_VAR}}`.

### 9. S3 bucket names too long

S3 bucket names have a 63-character limit. Use `namer.s3_bucket()` which calls `get_safe_s3_bucket_name()` internally -- it hashes the project name if the total would exceed 63 chars.

### 10. SecurityGroup inline rules vs standalone rules

When using `factory.create("aws:ec2:SecurityGroup", ...)`, pass `ingress` and `egress` as **plain dicts**. The factory knows NOT to convert them to Args objects (Pulumi handles it internally).

Only standalone `SecurityGroupRule` resources need Args objects, and you should avoid them in favor of inline rules.

### 11. Conditional resources without matching exports

If you conditionally create a resource (e.g., `if self.cfg.enable_isolated_tier`), you must also conditionally export it:

```python
# WRONG -- crashes when isolated tier is disabled
pulumi.export("isolated_subnet_id", self.subnets['isolated'].id)

# CORRECT
if self.cfg.enable_isolated_tier:
    pulumi.export("isolated_subnet_id", self.subnets['isolated'].id)
```

### 12. Forgetting `force_destroy=True` on S3 buckets

Without `force_destroy=True`, `pulumi destroy` will fail if the bucket contains objects (e.g., flow logs). Always set it for non-production buckets:

```python
factory.create("aws:s3:Bucket", bucket_name,
    bucket=bucket_name,
    force_destroy=True,    # Required for clean teardown
    tags={...}
)
```

---

## 13. Template Development Workflow

The complete lifecycle for writing, testing, and publishing an Archie template:

```
1. Write pulumi.py          ← Infrastructure code (source of truth)
2. Write config.py          ← Configuration class with parameters
3. Run pulumi-extractor     ← Generates template.yaml from code
4. Review template.yaml     ← Verify resources, add descriptions
5. Run validate-templates   ← Check framework compliance
6. Run seed-marketplace     ← Push to DynamoDB catalog
7. Test in UI               ← Verify catalog card, detail, deploy form, outputs
```

### Step 1-2: Write the template

Follow sections 1-10 of this guide. The `pulumi.py` and `config.py` are the **source of truth** for everything.

### Step 3: Run the Pulumi Extractor

The extractor scans your Python source code and generates/updates `template.yaml` with the correct resources list, config fields, outputs, and metadata.

```bash
# From the archie-backend repo:
cd archie-backend

# Extract a single template
python3 scripts/new/generate_templates/pulumi-extractor.py \
  --template aws-vpc-nonprod --generate-base

# The extractor:
# 1. Parses pulumi.py AST to find factory.create() calls → resources list
# 2. Calls get_metadata() → metadata section (title, pillars, cost, etc.)
# 3. Calls get_config_schema() → configuration section
# 4. Finds pulumi.export() calls → outputs section
# 5. Writes everything to template.yaml
```

**When to run it:** After writing or modifying any template's `pulumi.py` or `config.py`.

**What it generates vs what you write:**

| Field | Auto-extracted | Manual |
|-------|---------------|--------|
| `resources` list | ✓ From `factory.create()` calls | Fix names/descriptions if needed |
| `metadata` (title, description, cost, pillars) | ✓ From `get_metadata()` | Write in `pulumi.py` first |
| `configuration` fields | ✓ From `get_config_schema()` | Write in `config.py` first |
| `outputs` | ✓ From `pulumi.export()` calls | Write in `pulumi.py` first |
| `featured_outputs` | ✗ | Add manually if needed |
| `next_steps` | ✗ | Add manually if needed |
| Resource `description` | Partial (generic) | Improve descriptions manually |
| Resource `category` | ✗ | Added by seed-marketplace.py |

### Step 4: Review template.yaml

After extraction, review the generated `template.yaml`:
- Are all resources listed?
- Do resources have meaningful descriptions?
- Are all 6 pillars present with `description` field?
- Are config fields correctly typed and grouped?
- Are outputs listed?

### Step 5: Validate

```bash
# From the archie-templates repo:
cd archie-templates

# Validate all templates
python3 validate-templates.py

# Validate a specific template
python3 validate-templates.py --template aws-vpc-nonprod

# Show fix suggestions
python3 validate-templates.py --fix
```

The validator checks:
- `get_metadata()` returns a dict with all 6 pillars + `score_color`
- `template.yaml` has resources and config sections
- `pulumi.export()` calls exist
- No direct Pulumi resource calls (all through `factory.create()`)
- Config class has `environment`, `region`, `tags`, `project_name`

### Step 6: Seed the marketplace

```bash
# Dry run (see what would be seeded)
python3 seed-marketplace.py --env prod --dry-run

# Seed production
python3 seed-marketplace.py --env prod

# Seed sandbox
python3 seed-marketplace.py --env sandbox

# Seed both
python3 seed-marketplace.py --env both
```

The seeder:
- Reads `template.yaml` for each template
- Converts resources dict → list with categories (Networking, Compute, IAM, etc.)
- Converts config properties → list with `label`, `group`, `helpText`
- Ensures pillars have `description` field
- Upserts into DynamoDB marketplace table

### Step 7: Test in UI

After seeding, verify in the app:
1. **Catalog card** — title, description, cloud badge, cost, complexity
2. **Detail view** — resources grouped by category, config by group, 6 pillars with descriptions
3. **Deploy form** — config fields render correctly, defaults pre-filled
4. **Deploy completion** — Quick Access shows `public_ip`, `ssh_command`, URLs; All Outputs collapsible
5. **Stacks list** — deployed stack appears with correct name, cloud, status
