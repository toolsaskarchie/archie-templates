#!/bin/bash
# Install and configure MariaDB (AL2023-native; MySQL wire-compatible)
dnf update -y
# AL2023: mysql-server is not in base repos — use mariadb105-server (first-class dnf pkg, MySQL-compatible; matches wordpress.sh). AL2 EOS 2026-06-30.
dnf install -y mariadb105 mariadb105-server

# Start MariaDB
systemctl start mariadb
systemctl enable mariadb

# Wait until root can actually run a query — mysqladmin ping goes green during the
# first-start bootstrap, before root@localhost is usable, which races the hardening below.
for i in $(seq 1 30); do mysql -e "SELECT 1" >/dev/null 2>&1 && break; sleep 2; done

# Basic hardening in ONE passwordless session (fresh root = mysql_native_password, empty
# password; setting the password then reconnecting passwordless would lock out later
# statements). Anonymous users don't exist on AL2023 mariadb105 — DROP IF EXISTS is a safe no-op.
mysql -e "DROP USER IF EXISTS ''@'localhost'; ALTER USER 'root'@'localhost' IDENTIFIED BY 'ChangeMe123!'; FLUSH PRIVILEGES;"
