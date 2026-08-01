# These become the capability's PARAMETERS — the same way TF variables become a
# blueprint's config fields. Archie classifies them: no-default/identity -> the
# operator supplies them; defaulted -> governed. A PE can lock `region` so the op
# only ever runs in an approved region.

variable "volume_id" {
  description = "The EBS volume to snapshot (vol-xxxxxxxx). The operator supplies this."
  type        = string

  validation {
    condition     = can(regex("^vol-[0-9a-f]+$", var.volume_id))
    error_message = "volume_id must look like vol-0123abcd."
  }
}

variable "region" {
  description = "AWS region the volume lives in."
  type        = string
  default     = "us-east-1"
}

variable "description" {
  description = "Label stored on the snapshot."
  type        = string
  default     = "archie-capability: on-demand EBS backup"
}
