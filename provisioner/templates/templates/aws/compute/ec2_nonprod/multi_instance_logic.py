"""
Multi-Instance EC2 Creation Logic
This is the refactored loop logic to be integrated into pulumi.py
"""

# ==================================================================
# MULTI-INSTANCE LOOP: Create each EC2 instance from instances array
# ==================================================================
instances_config = self.cfg.instances
print(f"[EC2] Creating {len(instances_config)} instance(s)")

for idx, instance_config in enumerate(instances_config, start=1):
    # Extract instance-specific configuration
    instance_name_base = instance_config.get('instance_name', '')
    instance_type = instance_config.get('instance_type', 't3.micro')
    config_preset = instance_config.get('config_preset', 'web-server')
    ami_os_override = instance_config.get('ami_os')
    ami_id_override = instance_config.get('ami_id')
    enable_ssm = instance_config.get('enable_ssm', True)
    
    # Generate unique instance name with index
    if not instance_name_base or instance_name_base.lower() == 'auto-assign':
        preset_name = config_preset if config_preset != 'custom' else "instance"
        instance_name_base = namer.ec2_instance(preset=preset_name)
    
    # Add index suffix for multi-instance deployments
    if len(instances_config) > 1:
        instance_name = f"{instance_name_base}-{idx:02d}"
    else:
        instance_name = instance_name_base
    
    instance_name = instance_name.split('(')[0].strip() if isinstance(instance_name, str) and '(' in instance_name else instance_name
    
    print(f"[EC2] Creating instance {idx}/{len(instances_config)}: {instance_name}")
    
    # Use instance-specific AMI if provided, otherwise use template default
    instance_ami_os = ami_os_override or ami_os
    instance_ami_id = ami_id_override or ami_id
    
    # Build EC2 Atomic config for this instance
    ec2_atomic_config = {
        "parameters": {
            "aws": {
                "instance_name": instance_name,
                "instance_type": instance_type,
                "ami_id": instance_ami_id,
                "subnet_id": subnet_id,
                "security_group_ids": security_group_ids,
                "iam_instance_profile": instance_profile_name,
                "key_name": self.cfg.key_name,
                "user_data": self.cfg.user_data,
                "project_name": self.cfg.project_name,
                "environment": self.cfg.environment,
                "region": self.cfg.region
            }
        }
    }
    
    # Call EC2 Atomic template (Layer 3)
    ec2_instance = EC2AtomicTemplate(
        name=instance_name,
        config=ec2_atomic_config
    )
    ec2_instance.create_infrastructure()
    self.ec2_instances.append(ec2_instance)
    
    print(f"[EC2] Instance {instance_name} created successfully")

# ==================================================================
# OUTPUTS: Export all instance information
# ==================================================================

# Export instance arrays
instance_ids = [ec2.get_outputs()['instance_id'] for ec2 in self.ec2_instances]
instance_names = [ec2.get_outputs().get('instance_name', '') for ec2 in self.ec2_instances]
private_ips = [ec2.get_outputs()['private_ip'] for ec2 in self.ec2_instances]
public_ips = [ec2.get_outputs().get('public_ip') for ec2 in self.ec2_instances]

pulumi.export("instance_ids", instance_ids)
pulumi.export("instance_names", instance_names)
pulumi.export("private_ips", private_ips)
pulumi.export("public_ips", public_ips)
pulumi.export("instance_count", len(self.ec2_instances))

# Backward compatibility: export first instance as singular
if self.ec2_instances:
    first_instance = self.ec2_instances[0].get_outputs()
    pulumi.export("instance_id", first_instance['instance_id'])
    pulumi.export("instance_name", first_instance.get('instance_name', ''))
    pulumi.export("private_ip", first_instance['private_ip'])
    pulumi.export("public_ip", first_instance.get('public_ip'))
