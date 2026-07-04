#!/bin/bash
# Install Node.js and PM2
dnf update -y
# AL2023: dnf (no amazon-linux-extras; AL2 EOS 2026-06-30). nodesource registers a dnf-compatible repo. LIVE-TEST nodesource on AL2023.
curl -fsSL https://rpm.nodesource.com/setup_18.x | bash -
dnf install -y nodejs
npm install -g pm2

# Create sample app
mkdir -p /opt/app
cat > /opt/app/server.js << 'EOF'
const http = require('http');
const server = http.createServer((req, res) => {
  res.writeHead(200, {'Content-Type': 'text/html'});
  res.end('<h1>Node.js Server Running!</h1><p>Deployed by Archie</p>');
});
server.listen(3000, () => console.log('Server running on port 3000'));
EOF

# Start with PM2
cd /opt/app
pm2 start server.js
pm2 startup
pm2 save
