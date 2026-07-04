#!/bin/bash
# Install LAMP stack and WordPress
dnf update -y
# AL2023: php + mariadb105 are first-class dnf packages (no amazon-linux-extras; AL2 EOS 2026-06-30)
dnf install -y php php-mysqlnd mariadb105 mariadb105-server
dnf install -y httpd

# Install WordPress
cd /var/www/html
wget https://wordpress.org/latest.tar.gz
tar -xzf latest.tar.gz
mv wordpress/* .
rm -rf wordpress latest.tar.gz

# Configure permissions
chown -R apache:apache /var/www/html
chmod -R 755 /var/www/html

# Start services
systemctl start httpd
systemctl enable httpd
systemctl start mariadb
systemctl enable mariadb
