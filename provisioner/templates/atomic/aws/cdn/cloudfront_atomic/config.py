"""CloudFront Atomic Template Configuration"""
from typing import Optional, List, Dict, Any
from pydantic import Field
from provisioner.templates.atomic.base import AtomicConfig


class CloudFrontAtomicConfig(AtomicConfig):
    """CloudFront Distribution Atomic Configuration
    
    Creates a CloudFront distribution with configurable origins and cache behaviors.
    
    Attributes:
        origins: List of origin configurations
        default_cache_behavior: Default cache behavior settings
        enabled: Whether the distribution is enabled
        comment: Description for the distribution
        price_class: Price class for distribution
        default_root_object: Default root object (e.g., "index.html")
        custom_error_responses: Custom error response configurations
        restrictions: Geographic restrictions
        viewer_certificate: SSL/TLS certificate configuration
        aliases: Custom domain names (CNAMEs)
        tags: Resource tags
    """
    
    # Required
    origins: List[Dict[str, Any]] = Field(
        ...,
        description="List of origin configurations"
    )
    default_cache_behavior: Dict[str, Any] = Field(
        ...,
        description="Default cache behavior configuration"
    )
    
    # Optional with defaults
    enabled: bool = Field(
        default=True,
        description="Whether the distribution is enabled"
    )
    comment: Optional[str] = Field(
        default=None,
        description="Description for the distribution"
    )
    price_class: str = Field(
        default="PriceClass_100",
        description="Price class (PriceClass_All, PriceClass_200, PriceClass_100)"
    )
    default_root_object: str = Field(
        default="index.html",
        description="Default root object"
    )
    custom_error_responses: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Custom error response configurations"
    )
    restrictions: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Geographic restrictions"
    )
    viewer_certificate: Optional[Dict[str, Any]] = Field(
        default=None,
        description="SSL/TLS certificate configuration"
    )
    aliases: Optional[List[str]] = Field(
        default=None,
        description="Custom domain names (CNAMEs)"
    )
    tags: Dict[str, str] = Field(
        default_factory=dict,
        description="Resource tags"
    )
