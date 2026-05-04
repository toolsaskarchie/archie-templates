#!/bin/bash
# Install LAMP stack and WordPress
yum update -y
amazon-linux-extras install php7.4 mariadb10.5 -y
yum install httpd -y

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
