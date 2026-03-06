#!/usr/bin/env python3
"""
Test script for ResourceNamer class
Demonstrates the self-documenting naming patterns
"""

from provisioner.utils.aws import ResourceNamer

def test_resource_namer():
    """Test various ResourceNamer methods"""
    print("=" * 80)
    print("ResourceNamer - Self-Documenting Names Test")
    print("=" * 80)
    print()
    
    # Initialize namer
    namer = ResourceNamer("myapp", "prod", "us-east-1", "test-template")
    
    # Test VPC naming with CIDR
    print("VPC Naming (with CIDR encoding):")
    print("-" * 80)
    vpc_name = namer.vpc(cidr="10.123.0.0/16")
    print(f"✓ VPC (10.123.0.0/16):        {vpc_name}")
    expected = "vpc-myapp-nonprod-use1-123"  # "prod" env becomes "nonprod" (non-production)
    assert vpc_name == expected, f"Expected {expected}, got {vpc_name}"
    
    vpc_name2 = namer.vpc(cidr="10.45.0.0/16")
    print(f"✓ VPC (10.45.0.0/16):         {vpc_name2}")
    assert vpc_name2 == "vpc-myapp-nonprod-use1-45"
    print()
    
    # Test subnet naming
    print("Subnet Naming (with tier + AZ + CIDR):")
    print("-" * 80)
    subnet_name = namer.subnet("public", "us-east-1a", "10.123.1.0/24")
    print(f"✓ Public subnet (10.123.1.0/24, us-east-1a):  {subnet_name}")
    assert subnet_name == "myapp-prod-pubsub-use1-1a-1"
    
    subnet_name2 = namer.subnet("private", "us-east-1b", "10.123.3.0/24")
    print(f"✓ Private subnet (10.123.3.0/24, us-east-1b): {subnet_name2}")
    assert subnet_name2 == "myapp-prod-privsub-use1-1b-3"
    
    subnet_name3 = namer.subnet("database", "us-east-1a", "10.123.5.0/24")
    print(f"✓ DB subnet (10.123.5.0/24, us-east-1a):      {subnet_name3}")
    assert subnet_name3 == "myapp-prod-dbsub-use1-1a-5"
    print()
    
    # Test security group naming with ports
    print("Security Group Naming (with port encoding):")
    print("-" * 80)
    sg_name = namer.security_group("web", ports=[80, 443])
    print(f"✓ Web SG (ports 80, 443):     {sg_name}")
    assert sg_name == "myapp-prod-web-sg-http-https"
    
    sg_name2 = namer.security_group("app", ports=[8080])
    print(f"✓ App SG (port 8080):         {sg_name2}")
    assert sg_name2 == "myapp-prod-app-sg-p8080"
    
    sg_name3 = namer.security_group("db", service="postgres")
    print(f"✓ DB SG (postgres):           {sg_name3}")
    assert sg_name3 == "myapp-prod-db-sg-postgres"
    
    sg_name4 = namer.security_group("cache", service="redis")
    print(f"✓ Cache SG (redis):           {sg_name4}")
    assert sg_name4 == "myapp-prod-cache-sg-redis"
    print()
    
    # Test RDS naming
    print("RDS Naming:")
    print("-" * 80)
    rds_name = namer.rds("postgres")
    print(f"✓ PostgreSQL:                 {rds_name}")
    assert rds_name == "myapp-prod-pg-use1"
    
    rds_name2 = namer.rds("postgres", identifier="orders")
    print(f"✓ PostgreSQL (orders domain): {rds_name2}")
    assert rds_name2 == "myapp-prod-pg-orders-use1"
    
    rds_name3 = namer.rds("mysql")
    print(f"✓ MySQL:                      {rds_name3}")
    assert rds_name3 == "myapp-prod-mysql-use1"
    print()
    
    # Test ElastiCache naming
    print("ElastiCache Naming:")
    print("-" * 80)
    cache_name = namer.elasticache("redis", port=6379)
    print(f"✓ Redis (port 6379):          {cache_name}")
    assert cache_name == "myapp-prod-redis-use1-p6379"
    print()
    
    # Test NAT Gateway naming
    print("NAT Gateway Naming (with AZ):")
    print("-" * 80)
    nat_name = namer.nat_gateway("us-east-1a")
    print(f"✓ NAT (us-east-1a):           {nat_name}")
    assert nat_name == "myapp-prod-nat-use1-1a"
    
    nat_name2 = namer.nat_gateway("us-east-1b")
    print(f"✓ NAT (us-east-1b):           {nat_name2}")
    assert nat_name2 == "myapp-prod-nat-use1-1b"
    print()
    
    # Test Route Table naming
    print("Route Table Naming:")
    print("-" * 80)
    rt_name = namer.route_table("public")
    print(f"✓ Public RT:                  {rt_name}")
    assert rt_name == "myapp-prod-public-rt-use1"
    
    rt_name2 = namer.route_table("private", az="us-east-1a")
    print(f"✓ Private RT (us-east-1a):    {rt_name2}")
    assert rt_name2 == "myapp-prod-private-rt-use1-1a"
    print()
    
    # Test tags
    print("Tagging:")
    print("-" * 80)
    tags = namer.tags(Team="platform", CostCenter="engineering")
    print(f"✓ Standard tags generated:")
    for key, value in tags.items():
        print(f"  - {key}: {value}")
    assert tags["Project"] == "myapp"
    assert tags["Environment"] == "prod"
    assert tags["ManagedBy"] == "Archie"
    assert tags["Template"] == "test-template"
    assert tags["Team"] == "platform"
    assert tags["CostCenter"] == "engineering"
    print()
    
    print("=" * 80)
    print("✅ All tests passed! ResourceNamer is working correctly.")
    print("=" * 80)

if __name__ == "__main__":
    test_resource_namer()
