variable "team" {
  description = "The team this project is for (e.g. networking). Names the namespace, the Argo CD project and the default group, and labels everything as archie.io/team."
  type        = string

  validation {
    condition     = length(trimspace(var.team)) > 0
    error_message = "team is required: the project is named after the team it is for."
  }
}

variable "namespaces" {
  description = "Namespaces the team deploys into. Empty = one namespace, team-<team>."
  type        = list(string)
  default     = []
}

variable "project_name" {
  description = "Name of the team's Argo CD AppProject. Empty = team-<team>."
  type        = string
  default     = ""
}

variable "group" {
  description = "The team's group, as the cluster's identity provider names it (an SSO / OIDC group). Bound to group_role in each namespace and given the team role in the Argo CD project. Empty = team-<team>."
  type        = string
  default     = ""
}

variable "group_role" {
  description = "ClusterRole the team's group gets inside its namespaces (a RoleBinding, so it never reaches outside them). Kubernetes' built-in roles: view, edit, admin."
  type        = string
  default     = "edit"
}

variable "argocd_project" {
  description = "Create the team's Argo CD AppProject. Needs Argo CD on the cluster first (its AppProject CRD); Archie turns this on when the path installs Argo CD."
  type        = bool
  default     = false
}

variable "argocd_namespace" {
  description = "Namespace Argo CD runs in (where AppProjects live)."
  type        = string
  default     = "argocd"
}

variable "source_repos" {
  description = "Git repositories (URLs or Argo CD patterns) the team's applications may be sourced from. Empty = none yet: the project allows no source until the team's repos are listed."
  type        = list(string)
  default     = []
}

variable "quota_requests_cpu" {
  description = "ResourceQuota: total CPU the team's pods may request, per namespace."
  type        = string
  default     = "4"
}

variable "quota_requests_memory" {
  description = "ResourceQuota: total memory the team's pods may request, per namespace."
  type        = string
  default     = "8Gi"
}

variable "quota_limits_cpu" {
  description = "ResourceQuota: total CPU limit across the team's pods, per namespace."
  type        = string
  default     = "8"
}

variable "quota_limits_memory" {
  description = "ResourceQuota: total memory limit across the team's pods, per namespace."
  type        = string
  default     = "16Gi"
}

variable "quota_pods" {
  description = "ResourceQuota: most pods per namespace."
  type        = string
  default     = "50"
}

variable "default_request_cpu" {
  description = "LimitRange: CPU request given to a container that sets none."
  type        = string
  default     = "100m"
}

variable "default_request_memory" {
  description = "LimitRange: memory request given to a container that sets none."
  type        = string
  default     = "128Mi"
}

variable "default_limit_cpu" {
  description = "LimitRange: CPU limit given to a container that sets none."
  type        = string
  default     = "500m"
}

variable "default_limit_memory" {
  description = "LimitRange: memory limit given to a container that sets none."
  type        = string
  default     = "512Mi"
}

variable "labels" {
  description = "Extra labels on every object (archie.io/team is always set)."
  type        = map(string)
  default     = {}
}
