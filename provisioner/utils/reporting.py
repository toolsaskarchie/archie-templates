import os
import json
import time
import boto3
from datetime import datetime, UTC
from typing import Dict, Any, List

class DeploymentReporter:
    """
    Utility to generate and store detailed deployment reports.
    """
    
    def __init__(self, bucket_name: str = None):
        self.bucket_name = bucket_name or os.environ.get('REPORTS_BUCKET')
        self.s3_client = boto3.client('s3')
        
    def generate_markdown_report(self, 
                                deployment_context: Dict[str, Any], 
                                results: Dict[str, Any],
                                stack_state: Dict[str, Any] = None) -> str:
        """
        Generate a professional Markdown report.
        """
        template_name = deployment_context.get('template_name', 'Unknown')
        stack_name = deployment_context.get('stack_name', 'Unknown')
        start_time = results.get('started_at', time.time())
        end_time = results.get('completed_at', time.time())
        duration = end_time - start_time
        
        report = []
        report.append(f"# Deployment Report: {stack_name}")
        report.append(f"**Template:** {template_name}")
        report.append(f"**Status:** {'✅ SUCCESS' if results.get('success') else '❌ FAILED'}")
        report.append(f"**Timestamp:** {datetime.fromtimestamp(end_time, UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        report.append(f"**Duration:** {duration:.2f} seconds")
        report.append("")
        
        report.append("## 📊 Deployment Summary")
        report.append(f"- **Total Resources Managed:** {len(results.get('resources', []))}")
        report.append(f"- **Account ID:** {results.get('deployed_account_id', 'N/A')}")
        report.append(f"- **Region:** {deployment_context.get('region', 'N/A')}")
        report.append("")
        
        # Identify Gaps (Non-compliance)
        gaps = []
        config = deployment_context.get('config', {}).get('parameters', {})
        outputs = results.get('outputs', {})
        
        comparison_keys = sorted(set(config.keys()) | set(outputs.keys()))
        comparison_data = []
        
        for key in comparison_keys:
            req_val = config.get(key, "-")
            actual_val = outputs.get(key, "-")
            
            # Comparison logic
            is_match = False
            if req_val == "-" or actual_val == "-":
                status = "INFO"
            elif str(req_val).lower() == str(actual_val).lower():
                status = "COMPLIANT"
                is_match = True
            else:
                status = "NON-COMPLIANT"
                gaps.append({'param': key, 'expected': req_val, 'actual': actual_val})
            
            comparison_data.append({
                'key': key,
                'expected': req_val,
                'actual': actual_val,
                'status': status
            })

        # 1. Compliance & Drift Summary
        report.append("## 🛡️ Compliance & Drift Summary")
        if not gaps:
            report.append("✅ **100% Compliant**: All requested configuration parameters match the deployed infrastructure.")
        else:
            report.append(f"⚠️ **{len(gaps)} Configuration Gaps Detected**: The following parameters do not match the requested intent.")
            report.append("")
            report.append("| Parameter | Intent (Requested) | Actual (Deployed) | Remediation |")
            report.append("|-----------|-------------------|------------------|-------------|")
            for gap in gaps:
                report.append(f"| {gap['param']} | `{gap['expected']}` | `{gap['actual']}` | Manual review required |")
        report.append("")

        # 2. Configuration Comparison Table
        report.append("## ⚙️ Detailed Comparison")
        report.append("| Parameter | Requested | Deployed | Status |")
        report.append("|-----------|-----------|----------|--------|")
        
        for item in comparison_data:
            status_icon = "✅" if item['status'] == "COMPLIANT" else ("⚠️" if item['status'] == "NON-COMPLIANT" else "ℹ️")
            report.append(f"| {item['key']} | `{item['expected']}` | `{item['actual']}` | {status_icon} {item['status']} |")
        report.append("")
        
        # 2. Detailed Resource Inventory (with properties)
        report.append("## 🏗️ Deep Resource Inventory")
        resources = results.get('resources', [])
        
        if not resources:
            report.append("_No detailed resource information available._")
        else:
            for res in resources:
                res_name = res.get('name', 'Unknown')
                res_type = res.get('type', 'Unknown')
                report.append(f"### {res_name}")
                report.append(f"- **Type:** `{res_type}`")
                report.append(f"- **Service:** {res.get('service', 'N/A')}")
                report.append(f"- **Status:** {res.get('status', 'N/A')}")
                
                # If we have the full stack state, we can extract details for this resource
                if stack_state:
                    res_details = self._find_resource_in_state(stack_state, res_name, res_type)
                    if res_details:
                        report.append("  - **Applied Properties:**")
                        inputs = res_details.get('inputs', {})
                        for k, v in inputs.items():
                            if k not in ['__defaults', 'tags']: # Filter noise
                                report.append(f"    - `{k}`: {v}")
                
        report.append("")
        report.append("---")
        report.append(f"_Generated by Archie Automation Engine v2.0_")
        
        return "\n".join(report)

    def _find_resource_in_state(self, stack_state: Dict[str, Any], name: str, type_str: str) -> Dict[str, Any]:
        """Find a resource by name and type in the Pulumi stack state JSON."""
        deployment = stack_state.get('deployment', {})
        resources = deployment.get('resources', [])
        for res in resources:
            # Pulumi names in state might match the URN parts
            # URN format: urn:pulumi:stack::project::type::name
            urn = res.get('urn', '')
            if name in urn and type_str in urn:
                return res
        return None

    def upload_report(self, report_md: str, deployment_id: str) -> str:
        """
        Upload report to S3 and return a signed URL.
        """
        if not self.bucket_name:
            print("[REPORTER] ❌ No bucket name provided, skipping upload.")
            return None
        
        print(f"[REPORTER] Uploading to bucket: {self.bucket_name}")
        key = f"reports/{deployment_id}/deployment-report.md"
        print(f"[REPORTER] S3 key: {key}")
        
        try:
            print(f"[REPORTER] Putting object to S3...")
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=report_md.encode('utf-8'),
                ContentType='text/markdown'
            )
            print(f"[REPORTER] ✅ Object uploaded successfully")
            
            # Generate signed URL (valid for 7 days)
            print(f"[REPORTER] Generating presigned URL...")
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=604800 
            )
            print(f"[REPORTER] ✅ Presigned URL generated: {url[:100]}...")
            return url
        except Exception as e:
            import traceback
            print(f"[REPORTER] ❌ Failed to upload report: {e}")
            print(f"[REPORTER] Traceback: {traceback.format_exc()}")
            return None

def generate_deployment_report(deployment_context: Dict[str, Any], 
                                results: Dict[str, Any], 
                                stack_state: Dict[str, Any] = None) -> str:
    """Helper function to generate and upload a report."""
    try:
        # Default bucket based on environment - check both REPORTS_BUCKET and ARTIFACTS_BUCKET
        default_bucket = (
            os.environ.get('REPORTS_BUCKET') or 
            os.environ.get('ARTIFACTS_BUCKET') or 
            'newarchie-deployment-artifacts-sandbox-use1'
        )
        print(f"[REPORTER] Using bucket: {default_bucket}")
        print(f"[REPORTER] REPORTS_BUCKET={os.environ.get('REPORTS_BUCKET')}, ARTIFACTS_BUCKET={os.environ.get('ARTIFACTS_BUCKET')}")
        
        reporter = DeploymentReporter(bucket_name=default_bucket)
        print(f"[REPORTER] DeploymentReporter initialized")
        
        report_md = reporter.generate_markdown_report(deployment_context, results, stack_state)
        print(f"[REPORTER] Generated markdown report ({len(report_md)} chars)")
        
        deployment_id = deployment_context.get('deployment_id', str(int(time.time())))
        print(f"[REPORTER] Uploading report for deployment_id={deployment_id}")
        
        report_url = reporter.upload_report(report_md, deployment_id)
        print(f"[REPORTER] Upload complete, URL: {report_url}")
        
        return report_url
    except Exception as e:
        import traceback
        print(f"[REPORTER] ❌ Error in generate_deployment_report: {e}")
        print(f"[REPORTER] Traceback: {traceback.format_exc()}")
        return None
