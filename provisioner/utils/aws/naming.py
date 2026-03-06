"""
AWS Helper Functions - Resource Naming Conventions

Provides consistent naming patterns for all AWS resources.
"""

from typing import Optional, List, Dict
import re


def _clean_project_name(name: str) -> str:
    """
    Remove 'stack', and redundant env/region/template suffixes from project name.
    Example: 'stack-reportign-nonprod-us-east-1-vpc-prod' -> 'reportign'
    """
    if not name:
        return name
        
    # List of redundant tokens to strip (case-insensitive)
    redundant_tokens = {
        'stack', 'vpc', 'ec2', 'rds', 's3', 'db', 'cluster', 'eks', 'alb', 'tg', 'rt', 'igw', 'nat',
        'prod', 'production', 'nonprod', 'non-prod', 'dev', 'development', 'staging', 'stage', 'test', 'sandbox',
        'us', 'east', 'west', 'north', 'south', 'central', 'ap', 'sa', 'eu', 'me', 'af',
        'use1', 'use2', 'usw1', 'usw2', 'euc1', 'euw1', 'euw2', 'euw3',
        '1', '2', '3', '4', '5', 'instance'
    }
    
    # Split by hyphen and filter out redundant tokens
    # We also filter out tokens that are part of standard region names like 'us-east-1'
    parts = name.split('-')
    cleaned_parts = []
    for p in parts:
        p_low = p.lower()
        if p_low in redundant_tokens:
            continue
        # Also skip if it's just a number
        if p_low.isdigit():
            continue
        cleaned_parts.append(p)
    
    # Map app-server to appsrv
    result = "-".join(cleaned_parts)
    result = result.replace("app-server", "appsrv").replace("appserver", "appsrv")
    
    print(f"[NAMING] Original: '{name}' -> Tokens: {parts} -> Cleaned: '{result}'")
    
    # If we stripped everything, return the original to avoid empty string
    if not cleaned_parts and not result:
        return name
        
    return result


def sanitize_name(name: str, max_length: int = 32) -> str:
    """
    Sanitize a name for AWS:
    1. Replace underscores with hyphens
    2. Remove non-alphanumeric characters (except hyphens)
    3. Truncate to max_length
    
    Args:
        name: The name to sanitize
        max_length: Maximum allowed length
    
    Returns:
        str: Sanitized name
    """
    if not name:
        return "unnamed"
        
    # Replace underscores and other common separators with hyphens
    sanitized = name.replace('_', '-').replace(' ', '-').replace('.', '-')
    
    # Remove any other non-alphanumeric/hyphen characters
    sanitized = "".join(c for c in sanitized if c.isalnum() or c == '-')
    
    # Remove leading/trailing hyphens
    sanitized = sanitized.strip('-')
    
    if len(sanitized) <= max_length:
        return sanitized
        
    return sanitized[:max_length].rstrip("-")


def truncate_name(name: str, max_length: int = 32) -> str:
    """
    Compatibility wrapper for sanitize_name.
    """
    return sanitize_name(name, max_length)


def get_resource_name(
    resource_type: str,
    role: str,
    project: str,
    environment: str,
    region_short: str = "",
    config: str = ""
) -> str:
    """
    Generate consistent resource name following pattern: type-role-project[-config]-env-regioncode
    
    Args:
        resource_type: Type of resource (vpc, sub, sg, role, etc.)
        role: Functional role (main, public, web, ec2, etc.)
        project: Project name
        environment: Environment (dev, test, prod)
        region_short: Short region code (use1, usw2, etc.)
        config: Extra identifier (az, port, cidr, index)
    
    Returns:
        str: Resource name
    """
    env_short = "prod" if environment.lower() in ["production", "prod"] else "nonprod"
    clean_project = _clean_project_name(project)
    clean_config = _clean_project_name(config) if config else ""
    
    parts = [resource_type, role, clean_project]
    if clean_config:
        parts.append(clean_config)
    parts.append(env_short)
    if region_short:
        parts.append(region_short)
    
    # Filter out empty strings and join
    return "-".join(p for p in parts if p).lower()


def get_vpc_name(project: str, environment: str, region_short: str = "", network_num: str = "") -> str:
    """Get VPC name (Pattern: vpc-project-env-regioncode-num)"""
    env_short = "prod" if environment.lower() in ["production", "prod"] else "nonprod"
    parts = ["vpc", _clean_project_name(project), env_short]
    if region_short:
        parts.append(region_short)
    if network_num:
        parts.append(network_num)
    return "-".join(parts).lower()


def get_subnet_name(project: str, environment: str, tier: str, region_short: str = "", az_short: str = "", subnet_num: str = "") -> str:
    """Get Subnet name (Pattern: tier-project-env-regioncode-az-num)"""
    env_short = "prod" if environment.lower() in ["production", "prod"] else "nonprod"
    parts = [tier, _clean_project_name(project), env_short, region_short, az_short, subnet_num]
    return "-".join(p for p in parts if p).lower()


def get_igw_name(project: str, environment: str, region_short: str = "") -> str:
    """Get Internet Gateway name"""
    return get_resource_name("igw", "main", project, environment, region_short)


def get_nat_gateway_name(project: str, environment: str, az: str = "", region_short: str = "") -> str:
    """
    Get NAT Gateway name with availability zone
    
    Args:
        project: Project name
        environment: Environment
        az: Availability zone
    
    Returns:
        str: NAT Gateway name (e.g., "myapp-prod-nat-us-east-1a")
    """
    return get_resource_name("nat", "gw", project, environment, region_short, az)


def get_eip_name(project: str, environment: str, purpose: str = "nat", region_short: str = "", az: str = "") -> str:
    """
    Get Elastic IP name for NAT Gateway
    
    Args:
        project: Project name
        environment: Environment
        az: Availability zone
    
    Returns:
        str: EIP name (e.g., "myapp-prod-eip-us-east-1a")
    """
    return get_resource_name("eip", purpose, project, environment, region_short, az)


def get_route_table_name(
    project: str,
    environment: str,
    tier: str,
    region_short: str = "",
    az: str = ""
) -> str:
    """
    Get Route Table name
    
    Args:
        project: Project name
        environment: Environment
        tier: Route table tier (public, private, database)
        az: Availability zone (optional, for private route tables)
    
    Returns:
        str: Route table name
    """
    return get_resource_name("rt", tier, project, environment, region_short, az)


def get_security_group_name(
    project: str,
    environment: str,
    purpose: str = "main",
    region_short: str = "",
    config: str = ""
) -> str:
    """
    Get Security Group name
    
    Args:
        project: Project name
        environment: Environment
        purpose: Optional purpose/description (web, db, app, etc.)
    
    Returns:
        str: Security group name
    """
    return get_resource_name("secg", purpose, project, environment, region_short, config)


def get_s3_bucket_name(
    project: str,
    environment: str,
    purpose: str,
    region: str = ""
) -> str:
    """
    Get S3 bucket name (must be globally unique)
    
    Args:
        project: Project name
        environment: Environment
        purpose: Bucket purpose (logs, assets, data, etc.)
        region: Optional region suffix for global uniqueness
    
    Returns:
        str: S3 bucket name
    
    Note:
        S3 bucket names must be globally unique and follow DNS naming rules
    """
    parts = ["s3", purpose, _clean_project_name(project), environment]
    if region:
        # Use shortcode if it looks like a full region name
        if '-' in region:
            parts.append(get_region_shortcode(region))
        else:
            parts.append(region)
    return "-".join(parts).lower()


def get_safe_s3_bucket_name(
    project: str,
    environment: str,
    purpose: str,
    region: str = ""
) -> str:
    """
    Get a safe S3 bucket name that is guaranteed to be <= 63 characters.
    Uses MD5 hashing of the project name if the total length would exceed 63.
    """
    base_name = get_s3_bucket_name(project, environment, purpose, region)
    
    if len(base_name) <= 63:
        return base_name
        
    # If too long, hash the project name part to shrink it
    import hashlib
    project_hash = hashlib.md5(project.encode()).hexdigest()[:8]
    
    # Reconstruct with hashed project (truncate project to 20 chars max + hash)
    truncated_project = f"{project[:20]}-{project_hash}"
    safe_name = get_s3_bucket_name(truncated_project, environment, purpose, region)
    
    # Final safety check
    if len(safe_name) > 63:
        # Emergency truncation if still too long (e.g. very long purpose/region)
        return safe_name[:63].rstrip("-")
        
    return safe_name


def get_iam_role_name(
    project: str,
    environment: str,
    service: str,
    purpose: str = "",
    region_short: str = ""
) -> str:
    """
    Get IAM Role name
    
    Args:
        project: Project name
        environment: Environment
        service: Service using this role (lambda, ec2, ecs, etc.) - optional
    
    Returns:
        str: IAM role name
    
    Example:
        >>> get_iam_role_name("myapp", "prod", "lambda")
        "myapp-prod-lambda-role"
        >>> get_iam_role_name("archie-deploy", "global")
        "archie-deploy-global-role"
    """
    return get_resource_name("role", service, project, environment, region_short, purpose)


def get_iam_policy_name(
    project: str,
    environment: str,
    purpose: str,
    region_short: str = ""
) -> str:
    """
    Get IAM Policy name
    
    Args:
        project: Project name
        environment: Environment
        purpose: Policy purpose (s3-access, dynamodb-read, etc.)
    
    Returns:
        str: IAM policy name
    """
    return get_resource_name("policy", purpose, project, environment, region_short)


def get_lambda_function_name(
    project: str,
    environment: str,
    function_name: str,
    region_short: str = ""
) -> str:
    """
    Get Lambda function name
    
    Args:
        project: Project name
        environment: Environment
        function_name: Function purpose/name
    
    Returns:
        str: Lambda function name
    """
    return get_resource_name("lambda", function_name, project, environment, region_short)


def get_cloudwatch_log_group_name(
    project: str,
    environment: str,
    service: str
) -> str:
    """
    Get CloudWatch Log Group name
    
    Args:
        project: Project name
        environment: Environment
        service: Service generating logs
    
    Returns:
        str: Log group name with /aws/logs prefix
    """
    return f"/aws/logs/{_clean_project_name(project)}/{environment}/{service}"


def get_rds_identifier(
    project: str,
    environment: str,
    db_name: str = "db",
    region_short: str = ""
) -> str:
    """
    Get RDS DB instance identifier
    
    Args:
        project: Project name
        environment: Environment
        db_name: Database name/purpose
    
    Returns:
        str: RDS identifier
    """
    return get_resource_name("rds", db_name, project, environment, region_short)


def get_rds_subnet_group_name(
    project: str,
    environment: str,
    region_short: str = ""
) -> str:
    """
    Get RDS Subnet Group name
    
    Args:
        project: Project name
        environment: Environment
    
    Returns:
        str: RDS subnet group name
    """
    return get_resource_name("rds", "subnet-group", project, environment, region_short)


def get_elasticache_cluster_id(
    project: str,
    environment: str,
    cache_type: str = "redis",
    region_short: str = ""
) -> str:
    """
    Get ElastiCache cluster identifier
    
    Args:
        project: Project name
        environment: Environment
        cache_type: Cache type (redis, memcached)
    
    Returns:
        str: ElastiCache cluster ID
    """
    return get_resource_name("elasticache", cache_type, project, environment, region_short)


def get_alb_name(
    project: str,
    environment: str,
    tier: str = "",
    region_short: str = ""
) -> str:
    """
    Get Application Load Balancer name
    
    Args:
        project: Project name
        environment: Environment
        tier: Optional tier (public, private)
    
    Returns:
        str: ALB name
    """
    return get_resource_name("alb", tier if tier else "main", project, environment, region_short)


def get_target_group_name(
    project: str,
    environment: str,
    service: str
) -> str:
    """
    Get Target Group name
    
    Args:
        project: Project name
        environment: Environment
        service: Service name
    
    Returns:
        str: Target group name
    """
    return get_resource_name("tg", service, project, environment)


def get_ecs_cluster_name(project: str, environment: str, region_short: str = "") -> str:
    """Get ECS Cluster name"""
    return get_resource_name("cluster", "ecs", project, environment, region_short)


def get_ecs_service_name(project: str, environment: str, service: str, region_short: str = "") -> str:
    """Get ECS Service name"""
    return get_resource_name("service", service, project, environment, region_short)


def get_eks_cluster_name(project: str, environment: str, region_short: str = "") -> str:
    """Get EKS Cluster name"""
    return get_resource_name("eks", "main", project, environment, region_short)


def get_region_shortcode(region: str) -> str:
    """
    Get standardized shortcode for AWS region.
    
    Now uses dynamic region fetching from AWS EC2 API instead of hardcoded mappings.
    Falls back to algorithmic generation for unknown regions.
    
    Args:
        region: AWS region (e.g., "us-east-1", "eu-west-2")
    
    Returns:
        str: Region shortcode (e.g., "use1", "euw2")
    
    Examples:
        >>> get_region_shortcode("us-east-1")
        "use1"
        >>> get_region_shortcode("eu-central-1")
        "euc1"
    """
    # Import here to avoid circular dependency and allow fallback
    try:
        from provisioner.utils.region_mapper import get_region_code
        return get_region_code(region, 'aws')
    except ImportError:
        # Fallback algorithm if region_mapper is not available
        parts = region.split('-')
        if len(parts) >= 3:
            area = parts[0][:2] if len(parts[0]) >= 2 else parts[0]
            direction = parts[1][0] if parts[1] else ""
            number = parts[2] if parts[2].isdigit() else ""
            return f"{area}{direction}{number}"
        return region.replace('-', '')


# ============================================================================
# Enhanced Self-Documenting Resource Naming
# ============================================================================

class ResourceNamer:
    """
    Self-documenting resource namer with configuration encoding.
    
    Generates resource names that encode configuration details (CIDR ranges,
    ports, instance types) for instant identification.
    
    Usage:
        namer = ResourceNamer("myapp", "prod", "us-east-1", "vpc-nonprod")
        
        # VPC with CIDR encoding
        vpc_name = namer.vpc(cidr="10.123.0.0/16")  
        # Result: "vpc-myapp-prod-use1-123"
        
        # Subnet with tier and CIDR
        subnet_name = namer.subnet("public", "us-east-1a", "10.123.1.0/24")
        # Result: "myapp-prod-pubsub-use1-1a-1"
        
        # Security group with ports
        sg_name = namer.security_group("web", ports=[80, 443])
        # Result: "myapp-prod-web-sg-http-https"
        
        # Tags
        tags = namer.tags(Team="platform", CostCenter="engineering")
    """
    
    def __init__(self, project: str, environment: str, region: str, template: str):
        """
        Initialize ResourceNamer
        
        Args:
            project: Project name
            environment: Environment (dev, staging, prod)
            region: AWS region (e.g., "us-east-1")
            template: Template name for tagging
        """
        self.project = _clean_project_name(project)
        self.environment = environment
        self.region = region
        self.template = template
        self.region_short = get_region_shortcode(region)
    
    def vpc(self, cidr: Optional[str] = None) -> str:
        """
        Generate VPC name with original pattern: vpc-project-env-region-num
        """
        network_num = self._extract_cidr_identifier(cidr or "", octet=1)
        return get_vpc_name(self.project, self.environment, self.region_short, network_num)
    
    def subnet(self, tier: str, az: str, cidr: Optional[str] = None) -> str:
        """
        Generate subnet name with pattern: tier-project-env-regioncode-az-num
        """
        tier_map = {
            "public": "pubsub", "private": "privsub", "database": "islsub", 
            "db": "islsub", "app": "appsub", "application": "appsub", "isolated": "islsub"
        }
        tier_short = tier_map.get(tier.lower(), tier)
        az_short = self._extract_az_short(az)
        subnet_num = self._extract_cidr_identifier(cidr, octet=2) if cidr else ""
            
        return get_subnet_name(self.project, self.environment, tier_short, self.region_short, az_short, subnet_num)
    
    def security_group(self, purpose: str, ports: List[int] = None, service: str = None) -> str:
        """
        Generate security group name with port encoding.
        Pattern: sg-<purpose>-<project>-<env>-<region>[-<port-spec>]
        """
        port_spec = self._get_port_identifier(ports, service)
        return get_security_group_name(self.project, self.environment, purpose, self.region_short, port_spec)
    
    def rds(self, engine: str, identifier: Optional[str] = None, instance_type: Optional[str] = None) -> str:
        """
        Generate RDS instance name.
        Pattern: rds-<engine>-<project>-<env>-<region>[-<identifier>]
        """
        engine_map = {"postgres": "pg", "postgresql": "pg", "aurora-postgres": "aurora-pg"}
        engine_short = engine_map.get(engine.lower(), engine)
        
        config = identifier or ""
        if instance_type:
            config = f"{config}-{instance_type}" if config else instance_type
            
        return get_rds_identifier(self.project, self.environment, engine_short, self.region_short) + (f"-{config}" if config else "")
    
    def elasticache(self, cache_type: str = "redis", port: Optional[int] = None) -> str:
        """
        Generate ElastiCache cluster name.
        Pattern: ec-<type>-<project>-<env>-<region>[-p<port>]
        """
        config = f"p{port}" if port else ""
        return get_resource_name("ec", cache_type, self.project, self.environment, self.region_short, config)
    
    def nat_gateway(self, az: str) -> str:
        """Generate NAT Gateway name: nat-gw-project-env-region-az"""
        return get_nat_gateway_name(self.project, self.environment, az, self.region_short)
    
    def route_table(self, tier: str, az: Optional[str] = None) -> str:
        """Generate route table name: rt-tier-project-env-region[-az]"""
        return get_route_table_name(self.project, self.environment, tier, self.region_short, az)
    
    def vpc_endpoint(self, service: str, endpoint_type: str) -> str:
        """Generate VPC endpoint name: vpce-service-project-env-region-type"""
        type_short = "gw" if endpoint_type.lower() == "gateway" else "if"
        return get_resource_name("vpce", service, self.project, self.environment, self.region_short, type_short)
    
    def ec2_instance(self, preset: str, ip_address: Optional[str] = None, sequence: Optional[int] = None) -> str:
        """Generate EC2 instance name: ec2-preset-project-env-region[-config]"""
        config = ""
        if ip_address:
            config = ip_address.replace('.', '-')
        elif sequence is not None:
            config = f"{sequence:02d}"
            
        return get_resource_name("ec2", preset, self.project, self.environment, self.region_short, config)

    def iam_role(self, service: str, purpose: str = None) -> str:
        """Generate IAM role name: role-service-project-env-region[-purpose]"""
        return get_iam_role_name(self.project, self.environment, service, purpose, self.region_short)

    def iam_profile(self, service: str, purpose: str = None) -> str:
        """Generate IAM instance profile name: profile-service-project-env-region[-purpose]"""
        return get_resource_name("profile", service, self.project, self.environment, self.region_short, purpose)

    def s3_bucket(self, purpose: str) -> str:
        """Generate a safe S3 bucket name (<= 63 chars) using pattern: s3-purpose-project-env-region"""
        return get_safe_s3_bucket_name(
            self.project,
            self.environment,
            purpose,
            self.region_short # Use shortcode from namer context
        )

    def flow_logs(self, scope: str = "vpc", traffic: str = "all") -> str:
        """Generate Flow Logs name: fl-scope-project-env-region-traffic"""
        return get_resource_name("fl", scope, self.project, self.environment, self.region_short, traffic)
    
    def route(self, destination: str, target_type: str) -> str:
        """Generate Route name: route-dest-project-env-region-target"""
        dest_simple = destination.replace(".", "").replace("/", "")
        return get_resource_name("route", dest_simple, self.project, self.environment, self.region_short, target_type)
    
    def internet_gateway(self) -> str:
        """Generate Internet Gateway name: igw-main-project-env-region"""
        return get_igw_name(self.project, self.environment, self.region_short)
    
    def eip(self, az: str, purpose: str = "nat") -> str:
        """Generate Elastic IP name: eip-purpose-project-env-region-az"""
        return get_eip_name(self.project, self.environment, purpose, self.region_short, self._extract_az_short(az))
    
    def route_table_association(self, tier: str, index: int) -> str:
        """Generate route table association name: rta-tier-project-env-region-index"""
        return get_resource_name("rta", tier, self.project, self.environment, self.region_short, str(index))
    
    def nacl(self, tier: str = "default") -> str:
        """Generate Network ACL name: nacl-tier-project-env-region"""
        return get_resource_name("nacl", tier, self.project, self.environment, self.region_short)
    
    def tags(self, **additional) -> Dict[str, str]:
        """
        Generate standard tags with optional additions.
        
        Args:
            **additional: Additional tags (Owner, CostCenter, Team, etc.)
            
        Returns:
            Dictionary of tags
        """
        from .tags import get_standard_tags
        return get_standard_tags(
            self.project, self.environment, self.template,
            **additional
        )
    
    # Helper methods
    @staticmethod
    def _extract_cidr_identifier(cidr: str, octet: int = 1) -> str:
        """Extract octet from CIDR for name encoding. Returns 'X' if invalid/empty."""
        if not cidr or '.' not in cidr:
            return "X"
        octets = cidr.split('/')[0].split('.')
        if 0 <= octet < len(octets):
            return octets[octet]
        return "X"
    
    @staticmethod
    def _extract_az_short(az: str) -> str:
        """Extract short AZ code (e.g., 'us-east-1a' -> '1a')."""
        if az is None or not isinstance(az, str):
            return "1a"  # Default fallback
        return az[-2:] if len(az) >= 2 else az
    
    @staticmethod
    def _get_port_identifier(ports: List[int] = None, service: str = None) -> str:
        """Generate port identifier for security group names."""
        service_ports = {
            80: "http", 443: "https", 22: "ssh",
            3306: "mysql", 5432: "postgres", 6379: "redis",
            27017: "mongo", 1433: "mssql", 3389: "rdp"
        }
        
        if service:
            return service.lower()
        
        if not ports:
            return ""
        
        if len(ports) == 1:
            port = ports[0]
            return service_ports.get(port, f"p{port}")
        
        if set(ports) == {80, 443}:
            return "http-https"
        
        if len(ports) > 2 and ports == list(range(min(ports), max(ports) + 1)):
            return f"p{min(ports)}to{max(ports)}"
        
        port_names = [service_ports.get(p, f"p{p}") for p in ports]
        return "-".join(port_names[:3])
