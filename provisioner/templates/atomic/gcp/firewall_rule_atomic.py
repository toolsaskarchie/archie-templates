"""
GCP Firewall Rule Atomic Template

Google Cloud VPC firewall rule for controlling network access.
"""
from typing import Any, Dict, List
import pulumi
import pulumi_gcp as gcp

from provisioner.templates.atomic.base import AtomicTemplate
class GcpFirewallRuleAtomicTemplate(AtomicTemplate):
    """
    GCP Firewall Rule Atomic - Creates VPC firewall rule
    
    Configuration:
        name: Firewall rule name
        network: Network name or self_link
        project: GCP project ID
        direction: INGRESS or EGRESS
        priority: Rule priority (0-65535)
        source_ranges: Source IP ranges (for INGRESS)
        destination_ranges: Destination IP ranges (for EGRESS)
        source_tags: Source instance tags
        target_tags: Target instance tags
        allows: List of allow rules with protocol and ports
        denies: List of deny rules with protocol and ports
        description: Rule description
    
    Outputs:
        firewall_id: Firewall rule ID
        firewall_name: Firewall rule name
        self_link: Firewall rule self link
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.firewall: gcp.compute.Firewall = None
        self._outputs = {}
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create GCP firewall rule using Component"""
        
        firewall_name = self.config.get('name', self.name)
        network = self.config.get('network', 'default')
        direction = self.config.get('direction', 'INGRESS')
        
        # Build firewall arguments
        firewall_kwargs = {
            'direction': direction,
            'priority': self.config.get('priority', 1000),
            'description': self.config.get('description', f'Firewall rule for {firewall_name}'),
            'project': self.config.get('project')
        }
        
        # Add source/destination ranges based on direction
        if direction == 'INGRESS':
            firewall_kwargs['source_ranges'] = self.config.get('source_ranges', ['0.0.0.0/0'])
            if 'source_tags' in self.config:
                firewall_kwargs['source_tags'] = self.config['source_tags']
        else:  # EGRESS
            firewall_kwargs['destination_ranges'] = self.config.get('destination_ranges', ['0.0.0.0/0'])
        
        # Add target tags if specified
        if 'target_tags' in self.config:
            firewall_kwargs['target_tags'] = self.config['target_tags']
        
        # Add allow/deny rules
        firewall_kwargs['allows'] = self.config.get('allows')
        if 'denies' in self.config:
            firewall_kwargs['denies'] = self.config['denies']
        
        # Create firewall rule directly
        self.firewall = gcp.compute.Firewall(
            f"{self.name}-firewall",
            name=firewall_name,
            network=network,
            **firewall_kwargs
        )
        
        outputs = {
            'firewall_id': self.firewall.id,
            'firewall_name': self.firewall.name,
            'self_link': self.firewall.self_link
        }
        
        self._outputs = outputs
        return outputs

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        return self._outputs

    def get_metadata(self) -> Dict[str, Any]:
        """Get template metadata"""
        return {
            "name": "gcp-firewall-rule-atomic",
            "title": "GCP Firewall Rule",
            "description": "Atomic GCP VPC firewall rule.",
            "category": "networking",
            "provider": "gcp",
            "tier": "atomic"
        }
