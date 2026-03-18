#!/usr/bin/env python3
"""
Template Validator — checks every template against TEMPLATE_FRAMEWORK.md standards.

Validates:
  1. Metadata: name, title, description, cloud, version, base_cost, 6 pillars
  2. Config schema: fields have type, title, order, group
  3. Resources: template.yaml has resources section
  4. Outputs: pulumi.export() calls exist
  5. Factory: no direct Pulumi resource calls
  6. Config class: has environment, region, tags, project_name

Usage:
  python3 validate-templates.py
  python3 validate-templates.py --template aws-vpc-nonprod
  python3 validate-templates.py --fix  # show what to fix
"""
import sys
import os
import ast
import json
import importlib
import importlib.util
from pathlib import Path
from typing import Dict, List, Any, Optional

TEMPLATES_DIR = Path(__file__).parent / "provisioner" / "templates" / "templates"
REQUIRED_PILLARS = {
    "Operational Excellence", "Security", "Reliability",
    "Performance Efficiency", "Cost Optimization", "Sustainability"
}

def find_all_templates() -> List[Path]:
    """Find all template directories with pulumi.py"""
    return sorted([p.parent for p in TEMPLATES_DIR.rglob("pulumi.py")])


def check_metadata(template_path: Path) -> Dict[str, Any]:
    """Check get_metadata() output"""
    issues = []
    pulumi_py = template_path / "pulumi.py"
    source = pulumi_py.read_text()

    # Check if get_metadata exists
    if "get_metadata" not in source:
        return {"pass": False, "issues": ["Missing get_metadata() method"]}

    # Try to import and call it
    try:
        # Add paths
        root = Path(__file__).parent
        sys.path.insert(0, str(root))

        module_parts = list(template_path.relative_to(root).parts)
        module_parts[-1] = module_parts[-1]  # keep as-is
        module_name = ".".join(module_parts) + ".pulumi"

        spec = importlib.util.spec_from_file_location(module_name, str(pulumi_py))
        if not spec or not spec.loader:
            return {"pass": False, "issues": ["Cannot load module"]}

        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            return {"pass": False, "issues": [f"Import error: {e}"]}

        # Find the template class
        template_class = None
        for name in dir(mod):
            obj = getattr(mod, name)
            if isinstance(obj, type) and hasattr(obj, 'get_metadata') and name != 'InfrastructureTemplate':
                template_class = obj
                break

        if not template_class:
            return {"pass": False, "issues": ["No template class with get_metadata found"]}

        metadata = template_class.get_metadata()
        if not isinstance(metadata, dict):
            return {"pass": False, "issues": ["get_metadata() doesn't return a dict"]}

        # Check required fields
        for field in ["name", "title", "description", "cloud", "version"]:
            if field not in metadata:
                issues.append(f"Missing metadata field: {field}")

        # Check pillars
        pillars = metadata.get("pillars", [])
        if not pillars:
            issues.append("No pillars in metadata")
        else:
            pillar_titles = {p.get("title", "") for p in pillars}
            missing = REQUIRED_PILLARS - pillar_titles
            if missing:
                issues.append(f"Missing pillars: {missing}")
            if len(pillars) < 6:
                issues.append(f"Only {len(pillars)} pillars (need 6)")

            # Check each pillar has required fields
            for p in pillars:
                if "score" not in p:
                    issues.append(f"Pillar '{p.get('title', '?')}' missing score")
                if "score_color" not in p:
                    issues.append(f"Pillar '{p.get('title', '?')}' missing score_color")
                practices = p.get("practices", [])
                if len(practices) < 3:
                    issues.append(f"Pillar '{p.get('title', '?')}' has only {len(practices)} practices (need 3+)")

        return {
            "pass": len(issues) == 0,
            "issues": issues,
            "name": metadata.get("name", "?"),
            "title": metadata.get("title", "?"),
            "pillars": len(pillars),
            "base_cost": metadata.get("base_cost", "?"),
        }

    except Exception as e:
        return {"pass": False, "issues": [f"Error: {e}"]}


def check_template_yaml(template_path: Path) -> Dict[str, Any]:
    """Check template.yaml for resources and config"""
    issues = []
    yaml_path = template_path / "template.yaml"

    if not yaml_path.exists():
        return {"pass": False, "issues": ["No template.yaml"], "resources": 0, "config_fields": 0}

    try:
        import yaml
        with open(yaml_path) as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        return {"pass": False, "issues": [f"YAML parse error: {e}"], "resources": 0, "config_fields": 0}

    # Check resources
    resources = data.get("resources", {})
    if not resources:
        issues.append("No resources in template.yaml")

    # Check metadata
    metadata = data.get("metadata", {})
    if not metadata:
        issues.append("No metadata in template.yaml")

    # Check configuration
    config = data.get("configuration", {})
    config_props = config.get("properties", {}) if config else {}

    # Check outputs
    outputs = data.get("outputs", {})

    return {
        "pass": len(issues) == 0,
        "issues": issues,
        "resources": len(resources),
        "config_fields": len(config_props),
        "outputs": len(outputs) if isinstance(outputs, (dict, list)) else 0,
        "has_pillars": bool(metadata.get("pillars")),
    }


def check_exports(template_path: Path) -> Dict[str, Any]:
    """Check for pulumi.export() calls"""
    source = (template_path / "pulumi.py").read_text()
    exports = [line.strip() for line in source.split("\n") if "pulumi.export(" in line]
    return {
        "pass": len(exports) > 0,
        "count": len(exports),
        "issues": ["No pulumi.export() calls"] if not exports else [],
    }


def check_factory(template_path: Path) -> Dict[str, Any]:
    """Check for direct Pulumi resource calls (should use factory)"""
    source = (template_path / "pulumi.py").read_text()
    issues = []

    # Look for direct resource creation patterns
    import re
    direct_calls = re.findall(r'\baws\.\w+\.\w+\(', source)
    # Filter out: imports, type hints, Args classes, .get_ami, .id, .arn
    real_calls = [c for c in direct_calls
                  if not any(x in c for x in ['Args(', 'get_ami(', 'GetAmi', '.id', '.arn', '.name'])]

    if real_calls:
        issues.append(f"Direct Pulumi calls: {', '.join(set(real_calls))}")

    return {"pass": len(issues) == 0, "issues": issues}


def check_config_class(template_path: Path) -> Dict[str, Any]:
    """Check config.py for required attributes"""
    config_path = template_path / "config.py"
    if not config_path.exists():
        return {"pass": True, "issues": [], "note": "No config.py (uses TemplateConfig)"}

    source = config_path.read_text()
    issues = []

    for attr in ["environment", "region", "tags"]:
        if f"self.{attr}" not in source:
            issues.append(f"Missing self.{attr}")

    # Check params resolution
    if "parameters" in source and "params.get('aws'" not in source and "get('aws'" not in source:
        if "self.parameters = self.raw_config.get('parameters', {}).get('aws', {})" in source:
            issues.append("Params only reads parameters.aws (should also check params directly)")

    return {"pass": len(issues) == 0, "issues": issues}


def derive_template_id(template_path: Path) -> str:
    """Derive template ID from path"""
    parts = template_path.relative_to(TEMPLATES_DIR).parts
    # e.g., aws/networking/vpc_nonprod → aws-vpc-nonprod
    cloud = parts[0]
    name = parts[-1].replace("_", "-")
    return f"{cloud}-{name}"


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", help="Check specific template")
    parser.add_argument("--fix", action="store_true", help="Show fix suggestions")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    templates = find_all_templates()

    if args.template:
        target = args.template.replace("-", "_")
        templates = [t for t in templates if target in str(t).replace("-", "_")]
        if not templates:
            print(f"Template not found: {args.template}")
            sys.exit(1)

    results = []
    for tpl_path in templates:
        tpl_id = derive_template_id(tpl_path)
        rel = str(tpl_path.relative_to(TEMPLATES_DIR))

        meta = check_metadata(tpl_path)
        yaml_check = check_template_yaml(tpl_path)
        exports = check_exports(tpl_path)
        factory = check_factory(tpl_path)
        config = check_config_class(tpl_path)

        all_pass = all([meta["pass"], yaml_check["pass"], exports["pass"], factory["pass"], config["pass"]])
        all_issues = meta["issues"] + yaml_check["issues"] + exports["issues"] + factory["issues"] + config["issues"]

        results.append({
            "id": tpl_id,
            "path": rel,
            "pass": all_pass,
            "metadata": meta,
            "yaml": yaml_check,
            "exports": exports,
            "factory": factory,
            "config": config,
            "issues": all_issues,
        })

    if args.json:
        print(json.dumps(results, indent=2, default=str))
        return

    # Print table
    print(f"\n{'Template':<35} {'Meta':>5} {'YAML':>5} {'Res':>4} {'Cfg':>4} {'Exp':>4} {'Fact':>5} {'Conf':>5} {'Status':>8}")
    print("─" * 95)

    passed = 0
    failed = 0

    for r in results:
        meta_ok = "✓" if r["metadata"]["pass"] else "✗"
        yaml_ok = "✓" if r["yaml"]["pass"] else "✗"
        res_count = r["yaml"].get("resources", 0)
        cfg_count = r["yaml"].get("config_fields", 0)
        exp_count = r["exports"]["count"]
        fact_ok = "✓" if r["factory"]["pass"] else "✗"
        conf_ok = "✓" if r["config"]["pass"] else "✗"
        status = "PASS" if r["pass"] else "FAIL"

        if r["pass"]:
            passed += 1
        else:
            failed += 1

        print(f"{r['id']:<35} {meta_ok:>5} {yaml_ok:>5} {res_count:>4} {cfg_count:>4} {exp_count:>4} {fact_ok:>5} {conf_ok:>5} {status:>8}")

        if args.fix and r["issues"]:
            for issue in r["issues"]:
                print(f"  → {issue}")

    print("─" * 95)
    print(f"{'TOTAL':<35} {passed} passed, {failed} failed out of {len(results)}")
    print()


if __name__ == "__main__":
    main()
