"""
GCP HTTP(S) Load Balancer Non-Prod Template

External HTTP(S) Load Balancer for development and testing:
- Global external Application Load Balancer
- Backend service with health check
- URL map with default routing
- HTTP frontend (HTTPS optional via managed certificate)

Base cost (~$18/mo):
- Forwarding rule ($0.025/hr)
- Data processing charges per GB
"""

from typing import Any, Dict, Optional
import pulumi
import pulumi_gcp as gcp

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("gcp-lb-nonprod")
class LBNonprodTemplate(InfrastructureTemplate):
    """
    GCP HTTP(S) Load Balancer Non-Prod Template

    Deploys a global external Application Load Balancer with
    backend service, health check, and URL map for non-production workloads.
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, gcp_config: Dict[str, Any] = None, **kwargs):
        """Initialize Load Balancer Non-Prod template"""
        raw_config = config or gcp_config or kwargs or {}

        if name is None:
            name = (
                raw_config.get('project_name') or
                raw_config.get('projectName') or
                raw_config.get('parameters', {}).get('gcp', {}).get('project_name') or
                'lb-nonprod'
            )

        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references
        self.health_check: Optional[object] = None
        self.backend_service: Optional[object] = None
        self.url_map: Optional[object] = None
        self.http_proxy: Optional[object] = None
        self.https_proxy: Optional[object] = None
        self.http_forwarding_rule: Optional[object] = None
        self.https_forwarding_rule: Optional[object] = None
        self.ssl_certificate: Optional[object] = None
        self.global_address: Optional[object] = None
        self.firewall_health_check: Optional[object] = None

    def _cfg(self, key: str, default=None):
        """Read config from root, parameters.gcp, or parameters (Rule #6)"""
        params = self.config.get('parameters', {})
        gcp_params = params.get('gcp', {}) if isinstance(params, dict) else {}
        return (
            self.config.get(key) or
            (gcp_params.get(key) if isinstance(gcp_params, dict) else None) or
            (params.get(key) if isinstance(params, dict) else None) or
            default
        )

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy Load Balancer infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy complete HTTP(S) Load Balancer infrastructure"""

        # Read config
        project_name = self._cfg('project_name', 'lb')
        environment = self._cfg('environment', 'dev')
        team_name = self._cfg('team_name', '')
        gcp_project = self._cfg('gcp_project', '')
        network = self._cfg('network', 'default')

        # LB config
        health_check_path = self._cfg('health_check_path', '/')
        health_check_port = int(self._cfg('health_check_port', 80))
        health_check_interval = int(self._cfg('health_check_interval_sec', 10))
        health_check_timeout = int(self._cfg('health_check_timeout_sec', 5))
        healthy_threshold = int(self._cfg('healthy_threshold', 2))
        unhealthy_threshold = int(self._cfg('unhealthy_threshold', 3))
        backend_port = int(self._cfg('backend_port', 80))
        backend_protocol = self._cfg('backend_protocol', 'HTTP')

        # HTTPS config
        enable_https = self._cfg('enable_https', False)
        if isinstance(enable_https, str):
            enable_https = enable_https.lower() in ('true', '1', 'yes')
        domain_name = self._cfg('domain_name', '')
        enable_cdn = self._cfg('enable_cdn', False)
        if isinstance(enable_cdn, str):
            enable_cdn = enable_cdn.lower() in ('true', '1', 'yes')

        # Standard GCP labels
        labels = {
            'project': project_name,
            'environment': environment,
            'template': 'gcp-lb-nonprod',
            'managed-by': 'archie',
        }
        if team_name:
            labels['team'] = team_name.lower().replace(' ', '-')
        labels.update(self._cfg('labels', {}))

        resource_name = f"{project_name}-{environment}"

        # =================================================================
        # LAYER 1: Global Static IP Address
        # =================================================================

        self.global_address = gcp.compute.GlobalAddress(
            f"{resource_name}-lb-ip",
            name=f"{resource_name}-lb-ip",
            project=gcp_project if gcp_project else None,
        )

        # =================================================================
        # LAYER 2: Health Check
        # =================================================================

        self.health_check = gcp.compute.HealthCheck(
            f"{resource_name}-hc",
            name=f"{resource_name}-hc",
            project=gcp_project if gcp_project else None,
            check_interval_sec=health_check_interval,
            timeout_sec=health_check_timeout,
            healthy_threshold=healthy_threshold,
            unhealthy_threshold=unhealthy_threshold,
            http_health_check={
                "port": health_check_port,
                "request_path": health_check_path,
            },
        )

        # Firewall rule to allow GCP health check probes
        self.firewall_health_check = gcp.compute.Firewall(
            f"{resource_name}-allow-health-check",
            name=f"{resource_name}-allow-health-check",
            project=gcp_project if gcp_project else None,
            network=network,
            direction="INGRESS",
            source_ranges=["130.211.0.0/22", "35.191.0.0/16"],
            allows=[{
                "protocol": "tcp",
                "ports": [str(health_check_port)],
            }],
            target_tags=[f"{resource_name}-backend"],
            description="Allow GCP health check probes to reach backend instances",
        )

        # =================================================================
        # LAYER 3: Backend Service
        # =================================================================

        self.backend_service = gcp.compute.BackendService(
            f"{resource_name}-backend",
            name=f"{resource_name}-backend",
            project=gcp_project if gcp_project else None,
            protocol=backend_protocol,
            port_name=f"http-{backend_port}",
            health_checks=[self.health_check.id],
            timeout_sec=30,
            enable_cdn=enable_cdn,
            connection_draining_timeout_sec=300,
            load_balancing_scheme="EXTERNAL",
            log_config={
                "enable": True,
                "sample_rate": 1.0,
            },
        )

        # =================================================================
        # LAYER 4: URL Map
        # =================================================================

        self.url_map = gcp.compute.URLMap(
            f"{resource_name}-url-map",
            name=f"{resource_name}-url-map",
            project=gcp_project if gcp_project else None,
            default_service=self.backend_service.id,
        )

        # =================================================================
        # LAYER 5: HTTP Target Proxy + Forwarding Rule
        # =================================================================

        self.http_proxy = gcp.compute.TargetHttpProxy(
            f"{resource_name}-http-proxy",
            name=f"{resource_name}-http-proxy",
            project=gcp_project if gcp_project else None,
            url_map=self.url_map.id,
        )

        self.http_forwarding_rule = gcp.compute.GlobalForwardingRule(
            f"{resource_name}-http-rule",
            name=f"{resource_name}-http-rule",
            project=gcp_project if gcp_project else None,
            target=self.http_proxy.id,
            port_range="80",
            ip_address=self.global_address.address,
            load_balancing_scheme="EXTERNAL",
            labels=labels,
        )

        # =================================================================
        # LAYER 6: HTTPS (Optional)
        # =================================================================

        if enable_https and domain_name:
            # Google-managed SSL certificate
            self.ssl_certificate = gcp.compute.ManagedSslCertificate(
                f"{resource_name}-ssl-cert",
                name=f"{resource_name}-ssl-cert",
                project=gcp_project if gcp_project else None,
                managed={
                    "domains": [domain_name],
                },
            )

            self.https_proxy = gcp.compute.TargetHttpsProxy(
                f"{resource_name}-https-proxy",
                name=f"{resource_name}-https-proxy",
                project=gcp_project if gcp_project else None,
                url_map=self.url_map.id,
                ssl_certificates=[self.ssl_certificate.id],
            )

            self.https_forwarding_rule = gcp.compute.GlobalForwardingRule(
                f"{resource_name}-https-rule",
                name=f"{resource_name}-https-rule",
                project=gcp_project if gcp_project else None,
                target=self.https_proxy.id,
                port_range="443",
                ip_address=self.global_address.address,
                load_balancing_scheme="EXTERNAL",
                labels=labels,
            )

        # =================================================================
        # Exports (Rule #2, #7)
        # =================================================================

        pulumi.export('lb_ip_address', self.global_address.address)
        pulumi.export('lb_ip_name', self.global_address.name)
        pulumi.export('health_check_id', self.health_check.id)
        pulumi.export('health_check_self_link', self.health_check.self_link)
        pulumi.export('backend_service_id', self.backend_service.id)
        pulumi.export('backend_service_self_link', self.backend_service.self_link)
        pulumi.export('url_map_id', self.url_map.id)
        pulumi.export('url_map_self_link', self.url_map.self_link)
        pulumi.export('http_proxy_id', self.http_proxy.id)
        pulumi.export('http_forwarding_rule_id', self.http_forwarding_rule.id)
        pulumi.export('lb_url', self.global_address.address.apply(lambda ip: f"http://{ip}"))
        pulumi.export('environment', environment)

        if enable_https and domain_name:
            pulumi.export('ssl_certificate_id', self.ssl_certificate.id)
            pulumi.export('https_proxy_id', self.https_proxy.id)
            pulumi.export('https_forwarding_rule_id', self.https_forwarding_rule.id)
            pulumi.export('lb_https_url', f"https://{domain_name}")

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get outputs for this template"""
        outputs = {
            "lb_ip_address": self.global_address.address if self.global_address else None,
            "lb_ip_name": self.global_address.name if self.global_address else None,
            "health_check_id": self.health_check.id if self.health_check else None,
            "health_check_self_link": self.health_check.self_link if self.health_check else None,
            "backend_service_id": self.backend_service.id if self.backend_service else None,
            "backend_service_self_link": self.backend_service.self_link if self.backend_service else None,
            "url_map_id": self.url_map.id if self.url_map else None,
            "http_proxy_id": self.http_proxy.id if self.http_proxy else None,
            "http_forwarding_rule_id": self.http_forwarding_rule.id if self.http_forwarding_rule else None,
        }
        if self.ssl_certificate:
            outputs["ssl_certificate_id"] = self.ssl_certificate.id
        if self.https_proxy:
            outputs["https_proxy_id"] = self.https_proxy.id
        if self.https_forwarding_rule:
            outputs["https_forwarding_rule_id"] = self.https_forwarding_rule.id
        return outputs

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata for the catalog UI"""
        return {
            "name": "gcp-lb-nonprod",
            "title": "HTTP(S) Load Balancer",
            "description": "Global external Application Load Balancer with backend service, health check, and URL map for non-production workloads.",
            "category": "networking",
            "version": "1.0.0",
            "author": "Archie",
            "cloud": "gcp",
            "environment": "nonprod",
            "base_cost": "$18/month",
            "features": [
                "Global external Application Load Balancer",
                "HTTP health check with configurable thresholds",
                "Backend service with connection draining",
                "URL map with default routing",
                "Static global IP address",
                "Optional HTTPS with Google-managed SSL certificate",
                "Optional Cloud CDN integration",
                "Firewall rule for GCP health check probes",
                "Request logging enabled by default",
            ],
            "tags": ["gcp", "load-balancer", "networking", "http", "https", "nonprod"],
            "deployment_time": "3-5 minutes",
            "complexity": "intermediate",
            "use_cases": [
                "Web application load balancing",
                "API gateway frontend",
                "Multi-backend traffic distribution",
                "SSL termination for dev/staging services",
                "Global anycast IP for latency-based routing",
            ],
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Fully managed load balancer with health checks and request logging",
                    "practices": [
                        "Infrastructure as Code with Pulumi for repeatable deployments",
                        "Health checks auto-detect and remove unhealthy backends",
                        "Request logging enabled for troubleshooting and analytics",
                        "Connection draining prevents in-flight request drops",
                        "Configurable health check intervals and thresholds",
                    ],
                },
                {
                    "title": "Security",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Firewall rules scoped to health check probes with optional SSL termination",
                    "practices": [
                        "Health check firewall limited to Google probe IP ranges",
                        "Optional Google-managed SSL certificate for HTTPS",
                        "Backend instances tagged for scoped firewall rules",
                        "External load balancer shields backend from direct internet access",
                        "Cloud Armor compatible for WAF and DDoS protection",
                    ],
                },
                {
                    "title": "Reliability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Global anycast with automatic failover and health monitoring",
                    "practices": [
                        "Global load balancer with anycast IP across all regions",
                        "Automatic backend health monitoring and failover",
                        "Connection draining preserves in-flight requests during changes",
                        "Google SLA-backed availability for the load balancer itself",
                    ],
                },
                {
                    "title": "Performance Efficiency",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Global anycast routing with optional CDN for edge caching",
                    "practices": [
                        "Anycast IP routes users to nearest Google edge PoP",
                        "Optional Cloud CDN caches content at edge locations",
                        "HTTP/2 support for multiplexed connections",
                        "Configurable backend timeout for long-running requests",
                    ],
                },
                {
                    "title": "Cost Optimization",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Single forwarding rule with pay-per-use data processing",
                    "practices": [
                        "Single forwarding rule minimizes fixed costs",
                        "Data processing charges scale with actual traffic",
                        "CDN reduces origin bandwidth when enabled",
                        "No minimum commitment or reserved capacity required",
                    ],
                },
                {
                    "title": "Sustainability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Shared global infrastructure reduces per-customer resource waste",
                    "practices": [
                        "Managed service shares infrastructure across customers",
                        "Anycast routing minimizes network hops",
                        "CDN caching reduces origin server load",
                        "Google Cloud carbon-neutral infrastructure",
                    ],
                },
            ],
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Configuration schema for the deploy form"""
        return {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "default": "myproject",
                    "title": "Project Name",
                    "description": "Used in resource naming (lowercase, no spaces)",
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
                "gcp_project": {
                    "type": "string",
                    "default": "",
                    "title": "GCP Project ID",
                    "description": "Google Cloud project ID (leave empty to use default)",
                    "order": 3,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "network": {
                    "type": "string",
                    "default": "default",
                    "title": "VPC Network",
                    "description": "VPC network for health check firewall rule",
                    "order": 10,
                    "group": "Network Configuration",
                },
                "backend_port": {
                    "type": "number",
                    "default": 80,
                    "title": "Backend Port",
                    "description": "Port that backend instances listen on",
                    "order": 11,
                    "group": "Network Configuration",
                },
                "backend_protocol": {
                    "type": "string",
                    "default": "HTTP",
                    "title": "Backend Protocol",
                    "description": "Protocol for communication with backends",
                    "enum": ["HTTP", "HTTPS", "HTTP2"],
                    "order": 12,
                    "group": "Network Configuration",
                },
                "health_check_path": {
                    "type": "string",
                    "default": "/",
                    "title": "Health Check Path",
                    "description": "HTTP path for health check requests",
                    "order": 20,
                    "group": "Health Check",
                },
                "health_check_port": {
                    "type": "number",
                    "default": 80,
                    "title": "Health Check Port",
                    "description": "Port for health check requests",
                    "order": 21,
                    "group": "Health Check",
                },
                "health_check_interval_sec": {
                    "type": "number",
                    "default": 10,
                    "title": "Check Interval (sec)",
                    "description": "Seconds between health check probes",
                    "minimum": 5,
                    "maximum": 300,
                    "order": 22,
                    "group": "Health Check",
                },
                "health_check_timeout_sec": {
                    "type": "number",
                    "default": 5,
                    "title": "Timeout (sec)",
                    "description": "Seconds to wait for health check response",
                    "minimum": 1,
                    "maximum": 60,
                    "order": 23,
                    "group": "Health Check",
                },
                "healthy_threshold": {
                    "type": "number",
                    "default": 2,
                    "title": "Healthy Threshold",
                    "description": "Consecutive successes to mark healthy",
                    "minimum": 1,
                    "maximum": 10,
                    "order": 24,
                    "group": "Health Check",
                },
                "unhealthy_threshold": {
                    "type": "number",
                    "default": 3,
                    "title": "Unhealthy Threshold",
                    "description": "Consecutive failures to mark unhealthy",
                    "minimum": 1,
                    "maximum": 10,
                    "order": 25,
                    "group": "Health Check",
                },
                "enable_https": {
                    "type": "boolean",
                    "default": False,
                    "title": "Enable HTTPS",
                    "description": "Add HTTPS frontend with Google-managed SSL certificate",
                    "order": 30,
                    "group": "Architecture Decisions",
                    "cost_impact": "+$0/month (certificate is free)",
                },
                "domain_name": {
                    "type": "string",
                    "default": "",
                    "title": "Domain Name",
                    "description": "Domain for SSL certificate (e.g., app.example.com)",
                    "order": 31,
                    "group": "Architecture Decisions",
                    "conditional": {"field": "enable_https"},
                },
                "enable_cdn": {
                    "type": "boolean",
                    "default": False,
                    "title": "Enable Cloud CDN",
                    "description": "Cache content at Google edge locations",
                    "order": 32,
                    "group": "Architecture Decisions",
                    "cost_impact": "+$0.02-0.20/GB cached",
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
