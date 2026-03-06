"""
PulumiAtomicFactory - Dynamic atomic resource factory
Eliminates code duplication by creating Pulumi resources on-the-fly from schemas.
"""

import pulumi
import pulumi_aws as aws
import pulumi_gcp as gcp
import pulumi_azure_native as azure
import pulumi_kubernetes as kubernetes
from typing import Any, Dict, Optional


class PulumiAtomicFactory:
    """
    Factory for creating atomic Pulumi resources dynamically across providers.
    Replaces multiple atomic template directories with a single factory approach.
    """
    
    # Map Pulumi resource types to their classes
    RESOURCE_MAP = {
        # AWS: EC2/VPC Networking
        "aws:ec2:Vpc": aws.ec2.Vpc,
        "aws:ec2:Subnet": aws.ec2.Subnet,
        "aws:ec2:InternetGateway": aws.ec2.InternetGateway,
        "aws:ec2:NatGateway": aws.ec2.NatGateway,
        "aws:ec2:Eip": aws.ec2.Eip,
        "aws:ec2:RouteTable": aws.ec2.RouteTable,
        "aws:ec2:Route": aws.ec2.Route,
        "aws:ec2:RouteTableAssociation": aws.ec2.RouteTableAssociation,
        "aws:ec2:SecurityGroup": aws.ec2.SecurityGroup,
        "aws:ec2:SecurityGroupRule": aws.ec2.SecurityGroupRule,
        "aws:ec2:FlowLog": aws.ec2.FlowLog,
        "aws:ec2:NetworkAcl": aws.ec2.NetworkAcl,
        "aws:ec2:VpcEndpoint": aws.ec2.VpcEndpoint,
        
        # AWS: IAM
        "aws:iam:Role": aws.iam.Role,
        "aws:iam:Policy": aws.iam.Policy,
        "aws:iam:RolePolicyAttachment": aws.iam.RolePolicyAttachment,
        "aws:iam:InstanceProfile": aws.iam.InstanceProfile,
        
        # AWS: S3
        "aws:s3:Bucket": aws.s3.Bucket,
        "aws:s3:BucketV2": aws.s3.BucketV2,
        "aws:s3:BucketPublicAccessBlock": aws.s3.BucketPublicAccessBlock,
        "aws:s3:BucketObject": aws.s3.BucketObject,
        "aws:s3:BucketPolicy": aws.s3.BucketPolicy,
        "aws:s3:BucketWebsiteConfigurationV2": aws.s3.BucketWebsiteConfigurationV2,
        "aws:s3:BucketLifecycleConfigurationV2": aws.s3.BucketLifecycleConfigurationV2,
        
        # AWS: Logs
        "aws:cloudwatch:LogGroup": aws.cloudwatch.LogGroup,
        
        # AWS: Compute
        "aws:ec2:Instance": aws.ec2.Instance,
        "aws:ec2:KeyPair": aws.ec2.KeyPair,
        
        # AWS: RDS
        "aws:rds:Instance": aws.rds.Instance,
        "aws:rds:SubnetGroup": aws.rds.SubnetGroup,
        
        # AWS: ECS
        "aws:ecs:Cluster": aws.ecs.Cluster,
        "aws:ecs:Service": aws.ecs.Service,
        "aws:ecs:TaskDefinition": aws.ecs.TaskDefinition,
        
        # AWS: ALB/NLB
        "aws:lb:LoadBalancer": aws.lb.LoadBalancer,
        "aws:lb:TargetGroup": aws.lb.TargetGroup,
        "aws:lb:Listener": aws.lb.Listener,
        
        # AWS: Lambda
        "aws:lambda:Function": aws.lambda_.Function,
        
        # AWS: DynamoDB
        "aws:dynamodb:Table": aws.dynamodb.Table,

        # AWS: CloudFront
        "aws:cloudfront:Distribution": aws.cloudfront.Distribution,
        "aws:cloudfront:OriginAccessControl": aws.cloudfront.OriginAccessControl,
        "aws:cloudfront:ResponseHeadersPolicy": aws.cloudfront.ResponseHeadersPolicy,
        "aws:cloudfront:CachePolicy": aws.cloudfront.CachePolicy,

        # AWS: ElastiCache
        "aws:elasticache:Cluster": aws.elasticache.Cluster,
        "aws:elasticache:SubnetGroup": aws.elasticache.SubnetGroup,
        "aws:elasticache:ParameterGroup": aws.elasticache.ParameterGroup,
        "aws:elasticache:ReplicationGroup": aws.elasticache.ReplicationGroup,

        # GCP: Compute
        "gcp:compute:Instance": gcp.compute.Instance,
        "gcp:compute:Firewall": gcp.compute.Firewall,
        "gcp:compute:Network": gcp.compute.Network,
        "gcp:compute:Subnetwork": gcp.compute.Subnetwork,
        "gcp:compute:Router": gcp.compute.Router,
        "gcp:compute:RouterNat": gcp.compute.RouterNat,

        # GCP: Storage
        "gcp:storage:Bucket": gcp.storage.Bucket,
        "gcp:storage:BucketIAMBinding": gcp.storage.BucketIAMBinding,
        "gcp:storage:BucketObject": gcp.storage.BucketObject,

        # Azure: Storage
        "azure-native:storage:StorageAccount": azure.storage.StorageAccount,
        "azure-native:storage:StorageAccountStaticWebsite": azure.storage.StorageAccountStaticWebsite,
        "azure-native:resources:ResourceGroup": azure.resources.ResourceGroup,
        "azure-native:web:WebApp": azure.web.WebApp,
        "azure-native:web:AppServicePlan": azure.web.AppServicePlan,

        # AWS: SecretsManager
        "aws:secretsmanager:Secret": aws.secretsmanager.Secret,
        "aws:secretsmanager:SecretVersion": aws.secretsmanager.SecretVersion,

        # Kubernetes
        "kubernetes:apps/v1:Deployment": kubernetes.apps.v1.Deployment,
        "kubernetes:core/v1:Service": kubernetes.core.v1.Service,
        "kubernetes:networking.k8s.io/v1:Ingress": kubernetes.networking.v1.Ingress,
        "kubernetes:core/v1:ConfigMap": kubernetes.core.v1.ConfigMap,
        "kubernetes:core/v1:Namespace": kubernetes.core.v1.Namespace,
    }
    
    @classmethod
    def create(cls, resource_type: str, name: str, **props) -> Any:
        # Try to get from static map first
        resource_class = cls.RESOURCE_MAP.get(resource_type)
        
        # If not in map, try dynamic lookup from provider modules
        if resource_class is None:
            resource_class = cls._dynamic_lookup(resource_type)
        
        if resource_class is None:
            raise ValueError(f"Unsupported resource type: {resource_type}. Available types: {list(cls.RESOURCE_MAP.keys())}")
        
        # Extract opts if provided
        opts = props.pop('opts', None)
        
        # Apply smart defaults for common patterns
        props = cls._apply_smart_defaults(resource_type, name, props)
        
        # Convert dict arguments to proper Pulumi Args objects
        props = cls._convert_args(resource_type, props, resource_class)
        
        # Create and return the resource
        if opts:
            return resource_class(name, opts=opts, **props)
        else:
            return resource_class(name, **props)
    
    @classmethod
    def _dynamic_lookup(cls, resource_type: str) -> Optional[Any]:
        """
        Dynamically lookup a resource class from provider modules.
        
        Args:
            resource_type: Pulumi resource type (e.g., "aws:s3:BucketLifecycleConfigurationV2", "gcp:compute:Address")
            
        Returns:
            Resource class or None if not found
        """
        try:
            parts = resource_type.split(":")
            if len(parts) < 3:
                return None
            
            provider, service = parts[0], parts[1]
            resource_name = parts[-1]
            
            # Select provider module
            if provider == "aws":
                provider_module = aws
            elif provider == "gcp":
                provider_module = gcp
            elif provider == "azure-native":
                provider_module = azure
            elif provider == "kubernetes":
                provider_module = kubernetes
            else:
                return None
            
            # Get the service module
            service_module = getattr(provider_module, service, None)
            if service_module is None:
                # Some providers might have a different structure (like azure-native or kubernetes)
                # Try nested lookup for kubernetes or azure if needed
                if provider == "kubernetes":
                  # handled by static map for common ones, but for others:
                  pass
                return None
            
            # Get the resource class from the service module
            resource_class = getattr(service_module, resource_name, None)
            return resource_class
            
        except (AttributeError, ValueError):
            return None
    
    @classmethod
    def _convert_args(cls, resource_type: str, props: Dict[str, Any], resource_class: Any) -> Dict[str, Any]:
        """
        Convert dictionary arguments to proper Pulumi Args objects.
        
        Some Pulumi resources require nested properties to be specific Args types.
        This method handles common conversions.
        """
        # SecurityGroup inline rules - NO conversion needed, stay as dicts
        # Only standalone SecurityGroupRule resources need Args objects
        if resource_type == "aws:ec2:SecurityGroup":
            # For inline rules in SecurityGroup, keep as plain dicts
            # Pulumi handles the conversion internally
            pass
        
        # BucketLifecycleConfigurationV2 rules
        elif resource_type == "aws:s3:BucketLifecycleConfigurationV2":
            if "rules" in props and isinstance(props["rules"], list):
                converted_rules = []
                for rule in props["rules"]:
                    if isinstance(rule, dict):
                        # Convert nested expiration dict
                        if "expiration" in rule and isinstance(rule["expiration"], dict):
                            rule["expiration"] = aws.s3.BucketLifecycleConfigurationV2RuleExpirationArgs(**rule["expiration"])
                        converted_rules.append(aws.s3.BucketLifecycleConfigurationV2RuleArgs(**rule))
                    else:
                        converted_rules.append(rule)
                props["rules"] = converted_rules
        
        return props
    
    @classmethod
    def _apply_smart_defaults(cls, resource_type: str, name: str, props: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply smart defaults and naming conventions.
        Can be extended based on organizational standards.
        """
        # Add Name tag if tags exist but no Name tag
        if "tags" in props and isinstance(props["tags"], dict):
            if "Name" not in props["tags"]:
                props["tags"]["Name"] = name
        
        # For resources that commonly need tags, add default tags structure
        taggable_types = [
            "aws:ec2:Vpc", "aws:ec2:Subnet", "aws:ec2:InternetGateway",
            "aws:ec2:NatGateway", "aws:ec2:RouteTable", "aws:ec2:SecurityGroup",
            "aws:s3:Bucket", "aws:s3:BucketV2", "aws:iam:Role",
            "aws:rds:Instance", "aws:ecs:Cluster", "aws:lb:LoadBalancer"
        ]
        
        if resource_type in taggable_types and "tags" not in props:
            props["tags"] = {"Name": name}
        
        return props
    
    @classmethod
    def get_supported_types(cls) -> list[str]:
        """Get list of all supported resource types."""
        return list(cls.RESOURCE_MAP.keys())
    
    @classmethod
    def is_supported(cls, resource_type: str) -> bool:
        """Check if a resource type is supported."""
        return resource_type in cls.RESOURCE_MAP
