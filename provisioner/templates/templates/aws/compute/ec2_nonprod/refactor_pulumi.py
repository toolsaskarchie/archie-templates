#!/usr/bin/env python3
"""
Script to refactor EC2 nonprod pulumi.py for multi-instance support
Replaces single instance creation with loop over instances array
"""

import re

# Read the original file
with open('/Users/Gregory_Lazarus/Documents/Greg/Archielabs/newarchie/newarchie-backend/lambda/worker-lambda/provisioner/templates/templates/aws/compute/ec2_nonprod/pulumi.py', 'r') as f:
    content = f.read()

# Find the section to replace (from line 373 to line 493)
# We'll use markers to identify the section
start_marker = "        # Create EC2 instance using EC2 Atomic template (Layer 3)"
end_marker = "        return {"

# Find start and end positions
start_pos = content.find(start_marker)
if start_pos == -1:
    print("ERROR: Could not find start marker")
    exit(1)

# Find the return statement after the exports
end_search_start = content.find("pulumi.export(\"vpc_id\", vpc_id)", start_pos)
if end_search_start == -1:
    end_search_start = content.find("# Export VPC info if created", start_pos)

end_pos = content.find(end_marker, end_search_start)
if end_pos == -1:
    print("ERROR: Could not find end marker")
    exit(1)

# The new multi-instance code
new_code = '''        
        # ==================================================================
        # MULTI-INSTANCE LOOP: Create each EC2 instance from instances array
        # ==================================================================
        instances_config = self.cfg.instances
        print(f"[EC2] Creating {len(instances_config)} instance(s)")
        
        for idx, instance_config in enumerate(instances_config, start=1):
            # Extract instance-specific configuration
            instance_name_cfg = instance_config.get('instance_name', '')
            instance_type = instance_config.get('instance_type', self.cfg.instance_type)
            config_preset = instance_config.get('config_preset', self.cfg.config_preset)
            ami_os_override = instance_config.get('ami_os')
            ami_id_override = instance_config.get('ami_id')
            
            # Generate unique instance name with index
            if not instance_name_cfg or instance_name_cfg.lower() == 'auto-assign':
                preset_name = config_preset if config_preset != 'custom' else "instance"
                instance_name_base = namer.ec2_instance(preset=preset_name)
            else:
                instance_name_base = instance_name_cfg
            
            # Add index suffix for multi-instance deployments
            if len(instances_config) > 1:
                instance_name_final = f"{instance_name_base}-{idx:02d}"
            else:
                instance_name_final = instance_name_base
            
            instance_name_final = instance_name_final.split('(')[0].strip() if isinstance(instance_name_final, str) and '(' in instance_name_final else instance_name_final
            
            print(f"[EC2] Creating instance {idx}/{len(instances_config)}: {instance_name_final}")
            
            # Use instance-specific AMI if provided, otherwise use template default
            instance_ami_id = ami_id_override or ami_id
            
            # Log preset configuration
            if config_preset != 'custom':
                print(f"[EC2] Using preset configuration: {config_preset}")
                print(f"[EC2] Instance type: {instance_type}")
            
            # Build EC2 Atomic config for this instance
            ec2_atomic_config = {
                "parameters": {
                    "aws": {
                        "instance_name": instance_name_final,
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
                name=instance_name_final,
                config=ec2_atomic_config
            )
            ec2_instance.create_infrastructure()
            self.ec2_instances.append(ec2_instance)
            
            print(f"[EC2] Instance {instance_name_final} created successfully")
        
        # ==================================================================
        # OUTPUTS: Export all instance information
        # ==================================================================
        
        # Helper to serialize SG rules for readable outputs
        def serialize_sg_rules(rules):
            if not rules:
                return "[]"
            serialized = []
            for rule in rules:
                if isinstance(rule, dict):
                    clean_rule = {k: v for k, v in {
                        "protocol": rule.get("protocol", "-1"),
                        "from_port": rule.get("from_port"),
                        "to_port": rule.get("to_port"),
                        "cidr_blocks": rule.get("cidr_blocks", []),
                        "description": rule.get("description", "")
                    }.items() if v is not None}
                    serialized.append(clean_rule)
            return json.dumps(serialized, indent=2)

        # Export instance arrays
        instance_ids = [ec2.get_outputs()['instance_id'] for ec2 in self.ec2_instances]
        private_ips = [ec2.get_outputs()['private_ip'] for ec2 in self.ec2_instances]
        public_ips = [ec2.get_outputs().get('public_ip') for ec2 in self.ec2_instances]
        
        pulumi.export("instance_ids", instance_ids)
        pulumi.export("private_ips", private_ips)
        pulumi.export("public_ips", public_ips)
        pulumi.export("instance_count", len(self.ec2_instances))
        
        # Backward compatibility: export first instance as singular
        if self.ec2_instances:
            first_instance = self.ec2_instances[0].get_outputs()
            pulumi.export("instance_id", first_instance['instance_id'])
            pulumi.export("private_ip", first_instance['private_ip'])
            pulumi.export("public_ip", first_instance.get('public_ip'))
            
            # Generate display name for first instance
            preset_for_output = self.cfg.config_preset if self.cfg.config_preset != 'custom' else "instance"
            def generate_ip_name(ip):
                if not ip: return instance_name_final
                return namer.ec2_instance(preset=preset_for_output, ip_address=ip)
            
            display_name = first_instance['private_ip'].apply(generate_ip_name)
            pulumi.export("instance_name", display_name)
            
            # Export website URL for web-server preset
            if self.cfg.config_preset == 'web-server' and first_instance.get('public_ip'):
                def generate_url(ip):
                    return f"http://{ip}" if ip else "pending"
                pulumi.export("website_url", first_instance['public_ip'].apply(generate_url))
        
        # Export SSH Security Group Rules if created (Existing VPC Mode)
        if 'ssh_sg_ingress' in locals():
             pulumi.export("ssh_security_group_ingress", serialize_sg_rules(ssh_sg_ingress))
        
        # Export VPC info if created
        if self.vpc_template:
            pulumi.export("vpc_id", vpc_id)
            pulumi.export("vpc_cidr", vpc_cidr)
        
        return {'''

# Replace the section
new_content = content[:start_pos] + new_code + content[end_pos:]

# Write the refactored file
with open('/Users/Gregory_Lazarus/Documents/Greg/Archielabs/newarchie/newarchie-backend/lambda/worker-lambda/provisioner/templates/templates/aws/compute/ec2_nonprod/pulumi.py', 'w') as f:
    f.write(new_content)

print("✅ Successfully refactored pulumi.py for multi-instance support")
print(f"   Replaced {end_pos - start_pos} characters")
print(f"   New file length: {len(new_content)} characters")
