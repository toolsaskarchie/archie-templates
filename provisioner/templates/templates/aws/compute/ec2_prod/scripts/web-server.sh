#!/bin/bash
# Install and configure Nginx web server with embedded Archie Static Website
set -e  # Exit on error

echo "=== Starting Web Server Setup ==="

# Wait for network to be ready (important for NAT Gateway scenarios)
echo "Waiting for network connectivity..."
timeout=60
counter=0
while ! curl -s --connect-timeout 5 https://amazonlinux-2-repos-us-east-1.s3.dualstack.us-east-1.amazonaws.com/ > /dev/null; do
    if [ $counter -ge $timeout ]; then
        echo "Network timeout reached, continuing anyway..."
        break
    fi
    echo "Waiting for network... ($counter/$timeout)"
    sleep 5
    counter=$((counter + 5))
done

# Install Nginx with retry logic
echo "Installing Nginx..."
max_retries=3
retry_count=0
while [ $retry_count -lt $max_retries ]; do
    if yum update -y && amazon-linux-extras install nginx1 -y; then
        echo "✓ Nginx installed successfully"
        break
    else
        retry_count=$((retry_count + 1))
        echo "⚠ Installation failed, retry $retry_count/$max_retries"
        if [ $retry_count -lt $max_retries ]; then
            sleep 10
        fi
    fi
done

if [ $retry_count -eq $max_retries ]; then
    echo "❌ Failed to install Nginx after $max_retries attempts"
    exit 1
fi

# Get deployment information from config (passed from frontend)
PROJECT_NAME="{PROJECT_NAME}"
ENVIRONMENT="{ENVIRONMENT}"
STACK_NAME="{STACK_NAME}"
TEMPLATE_NAME="{TEMPLATE_NAME}"

# Get real-time metadata using IMDSv2
echo "Retrieving instance metadata..."
TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" -s)
INSTANCE_ID=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/instance-id)
PUBLIC_IP=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/public-ipv4)
PRIVATE_IP=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/local-ipv4)
AVAILABILITY_ZONE=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/placement/availability-zone)
REGION=$(echo "${AVAILABILITY_ZONE}" | sed 's/[a-z]$//')
INSTANCE_TYPE=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/instance-type)
AMI_ID=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/ami-id)
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S UTC')

# Download the website files from S3 bucket
echo "Downloading website template..."
cd /usr/share/nginx/html

# Download all website files (using wget since bucket is public)
wget -O index.html https://archie-static-website-source-prod.s3.amazonaws.com/index-aws.html
wget -O styles.css https://archie-static-website-source-prod.s3.amazonaws.com/styles.css
wget -O archie-logo.png https://archie-static-website-source-prod.s3.amazonaws.com/archie-logo.png

# Replace placeholders with actual values (use | delimiter to avoid issues with / in values)
# Note: curly braces escaped for Python format() in config.py
sed -i "s|{{PROJECT_NAME}}|${PROJECT_NAME}|g" index.html
sed -i "s|{{ENVIRONMENT}}|${ENVIRONMENT}|g" index.html
sed -i "s|{{STACK_NAME}}|${STACK_NAME}|g" index.html
sed -i "s|{{TEMPLATE_NAME}}|${TEMPLATE_NAME}|g" index.html
sed -i "s|{{INSTANCE_ID}}|${INSTANCE_ID}|g" index.html
sed -i "s|{{INSTANCE_TYPE}}|${INSTANCE_TYPE}|g" index.html
sed -i "s|{{PUBLIC_IP}}|${PUBLIC_IP}|g" index.html
sed -i "s|{{PRIVATE_IP}}|${PRIVATE_IP}|g" index.html
sed -i "s|{{AVAILABILITY_ZONE}}|${AVAILABILITY_ZONE}|g" index.html
sed -i "s|{{AMI_ID}}|${AMI_ID}|g" index.html
sed -i "s|{{REGION}}|${REGION}|g" index.html
sed -i "s|{{TIMESTAMP}}|${TIMESTAMP}|g" index.html

# Get load balancer information (don't fail script if AWS CLI calls fail)
# Note: AWS CLI might not be installed on all AMIs, but we'll try for ALB DNS display
ALB_DNS=$(aws elbv2 describe-load-balancers --region ${REGION} --query 'LoadBalancers[?contains(LoadBalancerName, `'"${STACK_NAME}"'`)].DNSName' --output text 2>/dev/null || echo "N/A")
TARGET_GROUP=$(aws elbv2 describe-target-groups --region ${REGION} --query 'TargetGroups[?contains(TargetGroupName, `'"${STACK_NAME}"'`)].TargetGroupArn' --output text 2>/dev/null || echo "N/A")

# Add load balancing info to HTML
sed -i "s|{{ALB_DNS}}|${ALB_DNS}|g" index.html
sed -i "s|{{TARGET_GROUP}}|${TARGET_GROUP}|g" index.html

# Set proper permissions
chown -R nginx:nginx /usr/share/nginx/html
chmod -R 755 /usr/share/nginx/html

# Start Nginx
echo "Starting Nginx..."
systemctl start nginx
systemctl enable nginx

echo "=== Web Server Setup Complete ==="
echo "Instance ID: ${INSTANCE_ID}"
echo "Public IP: ${PUBLIC_IP}"
echo "Website URL: http://${PUBLIC_IP}"
echo "Status: Nginx is running and serving content"
