variable "regional_id" {
  description = "Regional cluster identifier, used for S3 bucket naming and CloudFront comment"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.regional_id))
    error_message = "regional_id must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "org_id" {
  description = "AWS Organization ID — used in the bucket policy to grant write access to any account within the org (all management clusters)"
  type        = string

  validation {
    condition     = can(regex("^o-[a-z0-9]{10,32}$", var.org_id))
    error_message = "org_id must be a valid AWS Organization ID (e.g., o-aa111bb222cc)."
  }
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
