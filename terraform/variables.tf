variable "zone_file" {
  description = "Path to the zone definition that BIND, Terraform and Infoblox all read"
  type        = string
  default     = "../zones/lab.example.yml"
}

variable "gcp_project_id" {
  description = "GCP project for the Cloud DNS zone"
  type        = string
  default     = "example-dns-lab"
}

variable "cloudflare_zone_id" {
  description = "Cloudflare zone ID for the public copy of the zone"
  type        = string
  default     = "0123456789abcdef0123456789abcdef"
}
