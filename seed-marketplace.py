#!/usr/bin/env python3
"""
Marketplace Seeder — reads template.yaml files and upserts into DynamoDB.

Usage:
    python3 seed-marketplace.py --env sandbox
    python3 seed-marketplace.py --env prod
    python3 seed-marketplace.py --env both
    python3 seed-marketplace.py --env prod --dry-run
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import yaml

try:
    import boto3
except ImportError:
    print("ERROR: boto3 is required. Install with: pip install boto3")
    sys.exit(1)


TEMPLATES_DIR = Path(__file__).parent / "provisioner" / "templates" / "templates"

TABLE_NAMES = {
    "sandbox": "v2-archie-marketplace-sandbox-use1",
    "prod": "v2-archie-marketplace-prod-use1",
}

PROFILES = {
    "sandbox": "askarchie-sandbox",
    "prod": "askarchie-prod",
}


def convert_to_dynamo(obj):
    """Recursively convert Python objects to DynamoDB-safe types.

    - floats/ints → Decimal
    - None → removed (DynamoDB doesn't support None)
    - Empty strings → removed (DynamoDB doesn't support empty strings)
    - Nested dicts/lists handled recursively
    """
    if isinstance(obj, dict):
        cleaned = {}
        for k, v in obj.items():
            converted = convert_to_dynamo(v)
            if converted is not None:
                cleaned[k] = converted
        return cleaned if cleaned else None
    elif isinstance(obj, list):
        return [convert_to_dynamo(item) for item in obj if convert_to_dynamo(item) is not None]
    elif isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, int):
        return Decimal(obj)
    elif isinstance(obj, bool):
        return obj
    elif isinstance(obj, str):
        return obj if obj else None
    elif obj is None:
        return None
    else:
        return obj


def parse_template(template_path: Path) -> dict | None:
    """Parse a template.yaml and return a marketplace item dict."""
    try:
        with open(template_path, "r") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f"  WARNING: Failed to parse {template_path}: {e}")
        return None

    if not data or "metadata" not in data:
        print(f"  WARNING: No metadata in {template_path}")
        return None

    meta = data["metadata"]
    action_name = meta.get("action_name") or meta.get("name", "")
    if not action_name:
        print(f"  WARNING: No action_name or name in {template_path}")
        return None

    # Build the marketplace item
    item = {
        "id": action_name,
        "version": "latest",
        "title": meta.get("title", action_name),
        "description": meta.get("description", ""),
        "category": meta.get("category", ""),
        "cloud": meta.get("cloud", ""),
        "template_version": meta.get("version", "1.0.0"),
        "author": meta.get("author", "AskArchie"),
        "base_cost": meta.get("base_cost", ""),
        "deployment_time": meta.get("deployment_time", ""),
        "complexity": meta.get("complexity", "medium"),
        "features": meta.get("features", []),
        "tags": meta.get("tags", []),
        "pillars": meta.get("pillars", []),
        "action_name": action_name,
        "template_type": "standard",
        "tier": "standard",
        "scope": "standard",
        "is_listed": True,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Resources section — convert dict to list format the API expects
    resources = data.get("resources")
    if resources and isinstance(resources, dict):
        resource_list = []
        for res_name, res_def in resources.items():
            if isinstance(res_def, dict):
                resource_list.append({"name": res_name, **res_def})
        item["resources"] = resource_list
    elif resources:
        item["resources"] = resources

    # Configuration / config_fields — convert dict to list format the API expects
    config = data.get("configuration", {})
    properties = config.get("properties") if config else None
    if properties and isinstance(properties, dict):
        config_fields = []
        for field_name, field_def in properties.items():
            if isinstance(field_def, dict):
                field = {"name": field_name, **field_def}
                config_fields.append(field)
        item["config_fields"] = config_fields
    elif properties:
        item["config_fields"] = properties

    # Outputs
    outputs = data.get("outputs")
    if outputs:
        item["outputs"] = outputs

    # Optional fields
    if meta.get("featured_outputs"):
        item["featured_outputs"] = meta["featured_outputs"]
    if meta.get("next_steps"):
        item["next_steps"] = meta["next_steps"]
    if meta.get("marketplace_group"):
        item["marketplace_group"] = meta["marketplace_group"]
    if meta.get("use_cases"):
        item["use_cases"] = meta["use_cases"]
    if meta.get("architecture"):
        item["architecture"] = meta["architecture"]

    return item


def get_existing_count(table) -> int:
    """Get approximate item count from DynamoDB table."""
    try:
        response = table.scan(Select="COUNT")
        count = response.get("Count", 0)
        # Handle pagination for large tables
        while "LastEvaluatedKey" in response:
            response = table.scan(Select="COUNT", ExclusiveStartKey=response["LastEvaluatedKey"])
            count += response.get("Count", 0)
        return count
    except Exception:
        return 0


def seed_environment(env: str, items: list[dict], dry_run: bool = False):
    """Seed items into a specific environment's DynamoDB table."""
    table_name = TABLE_NAMES[env]
    profile = PROFILES[env]

    print(f"\n{'=' * 60}")
    print(f"  Environment: {env.upper()}")
    print(f"  Table:       {table_name}")
    print(f"  Profile:     {profile}")
    print(f"  Mode:        {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"{'=' * 60}")

    if dry_run:
        print(f"\n  Would upsert {len(items)} items:")
        print_summary_table(items)
        return

    session = boto3.Session(profile_name=profile, region_name="us-east-1")
    dynamodb = session.resource("dynamodb")
    table = dynamodb.Table(table_name)

    before_count = get_existing_count(table)
    print(f"\n  Items before: {before_count}")

    success = 0
    errors = 0
    for item in items:
        dynamo_item = convert_to_dynamo(item)
        if not dynamo_item:
            errors += 1
            continue
        try:
            table.put_item(Item=dynamo_item)
            success += 1
            print(f"  ✓ {item['id']}")
        except Exception as e:
            errors += 1
            print(f"  ✗ {item['id']}: {e}")

    after_count = get_existing_count(table)
    print(f"\n  Items after:  {after_count}")
    print(f"  Upserted:     {success}")
    if errors:
        print(f"  Errors:       {errors}")


def print_summary_table(items: list[dict]):
    """Print a formatted summary of items."""
    # Column widths
    id_w = max(len(i["id"]) for i in items) if items else 10
    title_w = max(len(i.get("title", "")[:40]) for i in items) if items else 10
    cloud_w = 10
    cat_w = 12

    header = f"  {'ID':<{id_w}}  {'TITLE':<{title_w}}  {'CLOUD':<{cloud_w}}  {'CATEGORY':<{cat_w}}"
    print(f"\n{header}")
    print(f"  {'-' * (id_w + title_w + cloud_w + cat_w + 6)}")

    for item in sorted(items, key=lambda x: (x.get("cloud", ""), x["id"])):
        title = item.get("title", "")[:40]
        cloud = item.get("cloud", "")
        category = item.get("category", "")
        print(f"  {item['id']:<{id_w}}  {title:<{title_w}}  {cloud:<{cloud_w}}  {category:<{cat_w}}")

    print(f"\n  Total: {len(items)} templates")


def main():
    parser = argparse.ArgumentParser(description="Seed DynamoDB marketplace from template.yaml files")
    parser.add_argument(
        "--env",
        required=True,
        choices=["sandbox", "prod", "both"],
        help="Target environment",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be seeded without writing to DynamoDB",
    )
    args = parser.parse_args()

    if not TEMPLATES_DIR.exists():
        print(f"ERROR: Templates directory not found: {TEMPLATES_DIR}")
        sys.exit(1)

    # Find all template.yaml files
    template_files = sorted(TEMPLATES_DIR.rglob("template.yaml"))
    print(f"Found {len(template_files)} template.yaml files in {TEMPLATES_DIR}")

    # Parse all templates
    items = []
    for tf in template_files:
        rel = tf.relative_to(TEMPLATES_DIR)
        item = parse_template(tf)
        if item:
            items.append(item)
        else:
            print(f"  SKIP: {rel}")

    if not items:
        print("No valid templates found. Nothing to seed.")
        sys.exit(1)

    print(f"\nParsed {len(items)} valid templates")
    print_summary_table(items)

    # Seed target environments
    envs = ["sandbox", "prod"] if args.env == "both" else [args.env]
    for env in envs:
        seed_environment(env, items, dry_run=args.dry_run)

    print("\nDone.")


if __name__ == "__main__":
    main()
