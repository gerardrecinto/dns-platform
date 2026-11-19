mock_provider "aws" {}
mock_provider "google" {}
mock_provider "cloudflare" {}

run "one_zone_file_feeds_three_providers" {
  command = plan

  assert {
    condition     = length(aws_route53_record.this) == 7
    error_message = "Route 53 should get seven record sets from the lab zone (everything except the apex NS)."
  }

  assert {
    condition     = aws_route53_record.this["api|A"].name == "api.lab.example" && aws_route53_record.this["api|A"].ttl == 60
    error_message = "A per-record ttl must carry through."
  }

  assert {
    condition     = one(aws_route53_record.this["@|TXT"].records) == "\"v=spf1 -all\""
    error_message = "TXT values must be quoted for Route 53."
  }
}

run "cloudflare_skips_types_it_cannot_take" {
  command = plan

  assert {
    condition     = length(module.cloudflare_dns.record_ids) == 6
    error_message = "Cloudflare gets A, CNAME and TXT only: six records, and the SRV record is skipped."
  }
}
