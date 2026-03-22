# CLAUDE.md — AskArchie Templates

## Quick Orientation
Open-source Pulumi template library for AskArchie. Templates are Python classes that create cloud infrastructure via Pulumi Automation API. Two tiers: **atomic** (single resource) and **composed** (full stacks combining atomics). Public repo: `toolsaskarchie/archie-templates`.

## Directory Structure
```
provisioner/
  templates/
    base/
      template.py          → InfrastructureTemplate base class + registry
    atomic/                → Single-resource templates
      aws/
        compute/           → ec2_atomic, asg_atomic, launch_template
        networking/        → vpc_atomic, subnet_atomic, igw_atomic, nat_gateway_atomic,
                             route_table_atomic, route_atomic, rta_atomic, security_group_atomic,
                             alb_atomic, listener, target_group, eip_atomic, nacl_atomic,
                             vpc_endpoint_atomic, flow_logs_atomic, subnet_public
        storage/           → s3_atomic, dynamodb_atomic
        database/          → rds_atomic, aurora_atomic, elasticache_atomic
        identity/          → iam_role_atomic
      gcp/
        compute/           → gce_atomic
        networking/        → vpc_atomic, subnet_atomic, router_atomic, nat_atomic, firewall_atomic
      azure/
        networking/        → vnet_atomic
      kubernetes/          → deployment_atomic
    templates/             → Composed (full-stack) templates
      aws/
        compute/
          ec2_nonprod/     → VPC + SGs + EC2 instance
          ec2_prod/        → VPC + SGs + EC2 (prod, 3 AZs)
        networking/
          vpc_nonprod/     → VPC + subnets + NAT + endpoints (1 AZ)
          vpc_prod/        → VPC + subnets + NATs + endpoints (3 AZs)
          alb_nonprod/     → VPC + ALB + SGs + target groups
        database/
          rds_nonprod/     → VPC + RDS instance
          aurora_nonprod/  → VPC + Aurora cluster
        storage/
          s3/              → S3 bucket with lifecycle
          dynamodb/        → DynamoDB table
        messaging/
          sqs/             → SQS queue
          sns/             → SNS topic
      gcp/
        networking/
          vpc_nonprod/     → GCP VPC + subnets + NAT + firewall
        compute/
          gce_nonprod/     → GCP VPC + GCE instance
        hosting/
          static_website/  → GCS static website
      azure/
        hosting/
          static_website/  → Azure Blob static website
  utils/
    aws/
      naming.py            → ResourceNamer class — deterministic resource naming
      __init__.py           → Exports ResourceNamer
    cidr_calculator.py     → Subnet CIDR calculation
    nonce_generator.py     → Random nonce for unique names
```

## Base Template Class (`base/template.py`)
```python
class InfrastructureTemplate(ABC):
    def __init__(self, config: dict):
        self.config = config
        self.cfg = TemplateConfig(config)  # Typed config access

    @abstractmethod
    def deploy(self, factory): ...

    def get_bool(self, key, default=False): ...   # DynamoDB Decimal-safe
    def get_int(self, key, default=0): ...
    def get_str(self, key, default=""): ...
```

## TemplateConfig
- Wraps raw config dict with typed getters
- `self.cfg.region`, `self.cfg.project_name`, etc. via `__getattr__`
- Config priority: `parameters.aws` > `parameters` > root config
- `get_parameter(key)` checks camelCase and snake_case

## ResourceNamer (`utils/aws/naming.py`)
Generates deterministic, self-documenting resource names:
- `namer.vpc(cidr=)` → `vpc-{project}-{env}-{region}-{cidr_id}`
- `namer.subnet(tier, az, cidr=)` → `{tier}sub-{project}-{env}-{region}-{az}-{cidr_id}`
- `namer.security_group(purpose)` → `sg-{purpose}-{project}-{env}-{region}`
- `namer.nat_gateway(az)` → `nat-{project}-{az}-{env}-{region}`

## Template Architecture Rules
1. **Always pass complete config** to child templates — `{**self.config}`, never cherry-pick
2. **Export every generated value** (names, CIDRs, bucket names) as Pulumi outputs
3. **Prefer injected values** over generating new ones (for upgrade/remediate idempotency)
4. **Use typed getters** (`get_bool`, `get_int`, `get_str`) — never raw `bool()`
5. **Always use CIDR suffix** in subnet names — no `is_upgrade` conditional
6. **Explicitly declare ALL security-sensitive attributes**, even if empty. If Pulumi doesn't know the desired state, it can't remediate drift. Examples:
   - SGs: always set `ingress=[]` even if rules are added via separate `SecurityGroupRule` resources
   - S3: always set `policy`, `acl`, `versioning`, `encryption` explicitly
   - IAM roles: declare `inline_policy=[]` if no inline policies are intended
   - NACLs: declare rules explicitly, don't rely on AWS defaults
   - Route tables: declare routes explicitly
   - **Why**: Pulumi only manages attributes it knows about. Omitting an attribute = "I don't care" = manual changes persist through remediation
7. **Read injected names from both config levels**: `(self.config.get('key') or self.config.get('parameters', {}).get('key'))` — outputs are injected into `parameters`, not root config

## Config Classes
Each composed template has a `config.py` with a dataclass:
```python
class VpcProdConfig(TemplateConfig):
    @property
    def enable_nat_gateway(self) -> bool:
        val = self.get_parameter('enable_nat_gateway')
        return self._to_bool(val) if val is not None else True
```
All config classes use `parameters.aws or parameters` fallback for flat governance values.

## Bool Coercion (`_to_bool`)
DynamoDB stores booleans as `Decimal(1)`. Pulumi needs Python `bool`.
```python
def _to_bool(val):
    if isinstance(val, bool): return val
    if isinstance(val, (int, float, Decimal)): return bool(int(val))
    if isinstance(val, str): return val.lower() in ('true', '1', 'yes')
    return bool(val)
```

## Upgrade Compatibility
- `vpc_name` from outputs → reuse existing VPC (no replacement)
- `vpc_cidr` from outputs → reuse existing CIDR (no new random)
- `flow_logs_bucket` from outputs → reuse existing S3 bucket
- Subnet names always include CIDR suffix for Pulumi state consistency

## Worker Template Loading
- Docker image bundles templates at `/provisioner/`
- Worker also clones from GitHub for registry templates
- Direct Python imports bypass runtime clone → **must sync bundled copies manually**
- Composed templates import atomics via Python module path

## Deploy Commands
```bash
# Push to main triggers GH Actions build + ECR push
git push origin main
```

## Known Issues
- Worker bundles templates in Docker — should clone from repo at runtime
- `__path__` override was attempted and REVERTED — breaks atomic import chain
