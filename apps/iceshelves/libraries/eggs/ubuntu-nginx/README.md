# Ubuntu Nginx Web Server

Production-ready Nginx web server on Ubuntu 24.04 LTS with SSL/TLS support via Certbot.

## Features
- Nginx (latest from Ubuntu repositories)
- Certbot for Let's Encrypt SSL certificates
- Custom welcome page
- Firewall configured for HTTP/HTTPS

## Default Configuration
- **Webroot**: /var/www/html
- **Nginx Config**: /etc/nginx
- **Ports**: 80 (HTTP), 443 (HTTPS)

## Post-Deployment
1. Access web server at http://[instance-ip]
2. Configure SSL: `sudo certbot --nginx -d your-domain.com`
3. Add your website content to /var/www/html

## Version
1.0.0 - Ubuntu 24.04 LTS
