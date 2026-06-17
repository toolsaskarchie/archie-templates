variable "project_name" {
  description = "Tag prefix and resource name root. Typically locked by the PE."
  type        = string
  default     = "archie-demo-web"
}

variable "environment" {
  description = "Environment label (nonprod, prod). Drives which governance profile applies."
  type        = string
  default     = "nonprod"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC. Profile lever."
  type        = string
  default     = "10.40.0.0/16"
}

variable "instance_type" {
  description = "EC2 instance size. Profile lever — non-prod t3.micro, prod locked larger."
  type        = string
  default     = "t3.micro"
}

variable "ec2_instance_count" {
  description = "Number of backend EC2 instances behind the ALB. Profile lever."
  type        = number
  default     = 1
}

# ── The governance star ──────────────────────────────────────────────────────
# Default is CLOSED (private RFC1918). The wide-open demo value lives only in
# nonprod.tfvars, set explicitly. In prod this is locked to a corporate CIDR.
variable "allowed_cidrs" {
  description = "CIDRs permitted to reach the ALB. LOCK THIS per profile — the drift/remediate star."
  type        = list(string)
  default     = ["10.0.0.0/8"]
}

variable "target_port" {
  description = "Port the backend listens on."
  type        = number
  default     = 80
}

variable "internal" {
  description = "Whether the ALB is internal (no public IP)."
  type        = bool
  default     = false
}

variable "enable_https" {
  description = "Terminate HTTPS on the ALB (requires certificate_arn)."
  type        = bool
  default     = false
}

variable "certificate_arn" {
  description = "ACM certificate ARN for HTTPS (when enable_https = true)."
  type        = string
  default     = ""
}
