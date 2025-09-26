#!/bin/bash

# Install Redis
echo "Installing Redis..."
sudo apt update
sudo apt install -y redis-server

# Start and enable Redis service
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Verify Redis is running
redis_status=$(sudo systemctl is-active redis-server)
if [ "$redis_status" != "active" ]; then
  echo "Error: Redis failed to start."
  exit 1
fi
echo "Redis is running."

# Install Caddy (if not installed)
echo "Installing Caddy..."
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo apt-key add -
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/deb/debian/caddy.list' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install -y caddy

# Set up Caddy configuration
echo "Configuring Caddy..."
sudo tee /etc/caddy/Caddyfile > /dev/null <<EOL
{
  order before rewrite
}

localhost:9443 {
  cache {
    type redis
    endpoint 127.0.0.1:6379
    key_prefix my_cache
    default_ttl 600s
  }

  encode gzip zstd brotli

  reverse_proxy http://localhost {
    header_up Host {host}
    header_up X-Real-IP {remote}
    header_up X-Forwarded-For {remote}
    header_up X-Forwarded-Proto {scheme}
  }

  file_server
}
EOL

# Restart Caddy to apply configuration
echo "Restarting Caddy..."
sudo systemctl restart caddy

echo "Setup complete! Redis and Caddy are now running."
