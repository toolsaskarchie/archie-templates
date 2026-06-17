# Production profile — hardened. In Archie's Govern step these become LOCKED on
# the production profile. allowed_cidrs is restricted to a corporate range —
# replace 203.0.113.0/24 with your real office/VPN CIDR.
project_name       = "archie-demo-web"
environment        = "prod"
vpc_cidr           = "10.50.0.0/16"
instance_type      = "t3.large"         # LOCKED — prod floor
ec2_instance_count = 3                  # LOCKED — HA
allowed_cidrs      = ["203.0.113.0/24"] # LOCKED — corporate CIDR only (no 0.0.0.0/0)
target_port        = 80
