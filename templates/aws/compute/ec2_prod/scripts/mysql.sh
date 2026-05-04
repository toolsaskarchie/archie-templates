#!/bin/bash
# Install and configure MySQL 8.0
yum update -y
yum install mysql-server -y

# Start MySQL
systemctl start mysqld
systemctl enable mysqld

# Secure installation (basic)
mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED BY 'ChangeMe123!';"
mysql -e "DELETE FROM mysql.user WHERE User='';"
mysql -e "FLUSH PRIVILEGES;"
