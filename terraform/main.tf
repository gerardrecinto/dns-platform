locals {
  zone      = yamldecode(file(var.zone_file))
  zone_name = trimsuffix(local.zone.zone, ".")

  # Apex NS records stay with each provider's own name servers.
  publishable = [for r in local.zone.records : r if !(r.type == "NS" && r.name == "@")]

  # One entry per name and type, so several values become one record set.
  grouped = {
    for k, rs in { for r in local.publishable : "${r.name}|${r.type}" => r... } : k => {
      name   = rs[0].name
      type   = rs[0].type
      ttl    = try(rs[0].ttl, local.zone.ttl)
      values = [for r in rs : r.value]
    }
  }
}

# AWS Route 53
resource "aws_route53_zone" "this" {
  name = local.zone_name
}

resource "aws_route53_record" "this" {
  for_each = local.grouped

  zone_id = aws_route53_zone.this.zone_id
  name    = each.value.name == "@" ? local.zone_name : "${each.value.name}.${local.zone_name}"
  type    = each.value.type
  ttl     = each.value.ttl
  records = each.value.type == "TXT" ? [for v in each.value.values : "\"${v}\""] : each.value.values
}

# Google Cloud DNS, using the blueprint module
module "cloud_dns" {
  source = "git::https://github.com/gerardrecinto/terraform-infra-blueprints.git//GCP/modules/cloud_dns?ref=main"

  project_id       = var.gcp_project_id
  zone_name        = replace(local.zone_name, ".", "-")
  dns_name         = local.zone.zone
  visibility       = "private"
  private_networks = ["https://www.googleapis.com/compute/v1/projects/${var.gcp_project_id}/global/networks/main"]

  records = {
    for k, g in local.grouped : k => {
      name    = g.name
      type    = g.type
      ttl     = g.ttl
      rrdatas = g.type == "TXT" ? [for v in g.values : "\"${v}\""] : g.values
    }
  }
}

# Cloudflare, using the blueprint module (A, CNAME and TXT only)
module "cloudflare_dns" {
  source = "git::https://github.com/gerardrecinto/terraform-infra-blueprints.git//Cloudflare/modules/dns_records?ref=main"

  zone_id = var.cloudflare_zone_id

  records = merge([
    for k, g in local.grouped : {
      for i, v in g.values : "${k}|${i}" => {
        name    = g.name == "@" ? local.zone_name : "${g.name}.${local.zone_name}"
        type    = g.type
        content = g.type == "CNAME" ? trimsuffix(v, ".") : v
        ttl     = g.ttl
      }
    } if contains(["A", "CNAME", "TXT"], g.type)
  ]...)
}
