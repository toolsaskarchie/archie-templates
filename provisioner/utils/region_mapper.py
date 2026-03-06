"""
Multi-Cloud Region Code Mapper

Provides standardized tri-gram region codes for AWS, GCP, and Azure.
For AWS, dynamically fetches regions from the EC2 API.
"""
from typing import Dict, Optional
import boto3
from botocore.exceptions import ClientError


# Cache for AWS regions to avoid repeated API calls
_AWS_REGIONS_CACHE: Optional[Dict[str, str]] = None


def get_aws_regions_from_api() -> Dict[str, str]:
    """
    Fetch AWS regions dynamically from EC2 DescribeRegions API.
    
    Returns:
        Dict mapping region names to tri-gram codes
        
    Examples:
        >>> regions = get_aws_regions_from_api()
        >>> regions['us-east-1']
        'use1'
    """
    global _AWS_REGIONS_CACHE
    
    # Return cached result if available
    if _AWS_REGIONS_CACHE is not None:
        return _AWS_REGIONS_CACHE
    
    try:
        # Create EC2 client (uses default credentials)
        ec2 = boto3.client('ec2', region_name='us-east-1')
        
        # Fetch all regions
        response = ec2.describe_regions(AllRegions=True)
        
        # Build region mapping
        region_map = {}
        for region_info in response.get('Regions', []):
            region_name = region_info['RegionName']
            tri_gram = _generate_aws_trigram(region_name)
            region_map[region_name] = tri_gram
        
        # Cache the result
        _AWS_REGIONS_CACHE = region_map
        return region_map
        
    except (ClientError, Exception) as e:
        print(f"[WARN] Failed to fetch AWS regions from API: {e}")
        # Return empty dict on failure, will use fallback algorithm
        return {}


def _generate_aws_trigram(region: str) -> str:
    """
    Generate tri-gram code for AWS region using standard pattern.
    
    Pattern: [area][direction][number]
    - area: 2-letter continent/area code (us, eu, ap, ca, sa, me, af)
    - direction: 1-letter direction (e=east, w=west, n=north, s=south, c=central)
    - number: zone number
    
    Args:
        region: AWS region name (e.g., "us-east-1")
        
    Returns:
        Tri-gram code (e.g., "use1")
    """
    parts = region.split('-')
    
    if len(parts) >= 3:
        # Standard AWS format: area-direction-number
        area = parts[0][:2] if len(parts[0]) >= 2 else parts[0]
        direction = parts[1][0] if parts[1] else ""
        number = parts[2] if parts[2].isdigit() else parts[2][:1]
        return f"{area}{direction}{number}"
    
    # Fallback: remove hyphens
    return region.replace('-', '')[:4]


def _generate_gcp_trigram(region: str) -> str:
    """
    Generate tri-gram code for GCP region.
    
    GCP Patterns:
    - us-central1 → usc1
    - europe-west1 → euw1
    - asia-northeast1 → asne1
    
    Args:
        region: GCP region name
        
    Returns:
        Tri-gram code
    """
    parts = region.split('-')
    
    if len(parts) >= 2:
        # Map common GCP area names
        area_map = {
            'us': 'us',
            'europe': 'eu',
            'asia': 'as',
            'australia': 'au',
            'southamerica': 'sa',
            'northamerica': 'na'
        }
        
        area = area_map.get(parts[0], parts[0][:2])
        direction = parts[1][0] if len(parts) > 1 else ""
        number = parts[2] if len(parts) > 2 and parts[2].isdigit() else "1"
        
        return f"{area}{direction}{number}"
    
    return region[:4]


def _generate_azure_trigram(region: str) -> str:
    """
    Generate tri-gram code for Azure region.
    
    Azure Patterns:
    - eastus → eus
    - westeurope → weu
    - southeastasia → sea
    
    Args:
        region: Azure region name
        
    Returns:
        Tri-gram code
    """
    # Azure region mapping (hardcoded since Azure doesn't have a simple pattern)
    azure_map = {
        'eastus': 'eus',
        'eastus2': 'eus2',
        'westus': 'wus',
        'westus2': 'wus2',
        'westus3': 'wus3',
        'centralus': 'cus',
        'northcentralus': 'ncus',
        'southcentralus': 'scus',
        'westcentralus': 'wcus',
        'canadacentral': 'cac',
        'canadaeast': 'cae',
        'brazilsouth': 'brs',
        'northeurope': 'neu',
        'westeurope': 'weu',
        'uksouth': 'uks',
        'ukwest': 'ukw',
        'francecentral': 'frc',
        'francesouth': 'frs',
        'germanywestcentral': 'gwc',
        'norwayeast': 'nwe',
        'switzerlandnorth': 'swn',
        'swedencentral': 'swe',
        'eastasia': 'eas',
        'southeastasia': 'sea',
        'australiaeast': 'aue',
        'australiacentral': 'auc',
        'japaneast': 'jpe',
        'japanwest': 'jpw',
        'koreacentral': 'krc',
        'koreasouth': 'krs',
        'southindia': 'sin',
        'centralindia': 'cin',
        'westindia': 'win',
        'uaenorth': 'uan',
        'southafricanorth': 'san',
    }
    
    return azure_map.get(region.lower(), region[:4].lower())


def get_region_code(region: str, cloud_provider: str = 'aws') -> str:
    """
    Get standardized tri-gram region code for multi-cloud regions.
    
    Args:
        region: Cloud region name
        cloud_provider: One of 'aws', 'gcp', 'azure'
        
    Returns:
        Tri-gram region code
        
    Examples:
        >>> get_region_code('us-east-1', 'aws')
        'use1'
        >>> get_region_code('us-central1', 'gcp')
        'usc1'
        >>> get_region_code('eastus', 'azure')
        'eus'
    """
    provider = cloud_provider.lower()
    
    if provider == 'aws':
        # Try to get from AWS API cache first
        aws_regions = get_aws_regions_from_api()
        if region in aws_regions:
            return aws_regions[region]
        
        # Fallback to generation algorithm
        return _generate_aws_trigram(region)
    
    elif provider == 'gcp':
        return _generate_gcp_trigram(region)
    
    elif provider == 'azure':
        return _generate_azure_trigram(region)
    
    else:
        # Unknown provider, try AWS algorithm as fallback
        return _generate_aws_trigram(region)


# Backward compatibility alias for existing code
def get_region_shortcode(region: str) -> str:
    """
    Get AWS region shortcode (backward compatibility).
    
    This is a wrapper around get_region_code for AWS.
    Legacy function maintained for backward compatibility.
    """
    return get_region_code(region, 'aws')
