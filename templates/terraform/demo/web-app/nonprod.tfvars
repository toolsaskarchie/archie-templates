# Non-prod profile — a sandbox the world can reach (so the demo app is clickable).
# allowed_cidrs is wide open here ON PURPOSE and set EXPLICITLY (the variable
# default is closed). This is the value the drift demo will protect.
project_name       = "archie-demo-web"
environment        = "nonprod"
vpc_cidr           = "10.40.0.0/16"
instance_type      = "t3.micro"
ec2_instance_count = 1
allowed_cidrs      = ["0.0.0.0/0"]
target_port        = 80
