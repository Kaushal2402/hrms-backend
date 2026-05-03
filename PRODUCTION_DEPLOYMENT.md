# HRMS Production Deployment Guide

This guide provides a step-by-step walkthrough to deploy the HRMS project to a production server (Ubuntu/Linux) from scratch.

---

## 1. System Requirements

- **Operating System**: Ubuntu 22.04 LTS (Recommended)
- **Python**: 3.10 or higher
- **Node.js**: 18.x or higher
- **Database**: MySQL 8.0 or higher
- **Web Server**: Nginx
- **Process Manager**: PM2

---

## 2. Server Preparation

Update the system and install essential packages:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv mysql-server nginx git curl
```

Install PM2 globally for process management:
```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
sudo npm install -g pm2
```

---

## 3. Database Setup

1. Log into MySQL:
   ```bash
   sudo mysql -u root
   ```

2. Create the database and user:
   ```sql
   CREATE DATABASE hrm CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'hrm_user'@'localhost' IDENTIFIED BY 'your_secure_password';
   GRANT ALL PRIVILEGES ON hrm.* TO 'hrm_user'@'localhost';
   FLUSH PRIVILEGES;
   EXIT;
   ```

---

## 4. Backend Deployment

1. Clone and enter the directory:
   ```bash
   git clone <your-repo-url> /var/www/hrm-backend
   cd /var/www/hrm-backend
   ```

2. Set up virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. Configure Environment Variables:
   Create a `.env` file in the root:
   ```env
   PROJECT_NAME="HRMS Production"
   MYSQL_SERVER="localhost"
   MYSQL_USER="hrm_user"
   MYSQL_PASSWORD="your_secure_password"
   MYSQL_DB="hrm"
   MYSQL_PORT="3306"
   SECRET_KEY="your-super-secret-key"
   ALGORITHM="HS256"
   EMAILS_FROM_EMAIL="support@yourdomain.com"
   SERVER_HOST="https://api.yourdomain.com"
   ```

4. Run Database Migrations:
   ```bash
   alembic upgrade head
   ```

5. Run Production Seeders:
   ```bash
   python3 seed_production_data.py
   ```

6. Start Backend with PM2:
   ```bash
   pm2 start "uvicorn app.main:app --host 0.0.0.0 --port 8000" --name hrm-backend
   ```

---

## 5. Frontend Deployment

1. Clone and enter the frontend directory:
   ```bash
   git clone <your-repo-url> /var/www/hrm-frontend
   cd /var/www/hrm-frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Create production `.env`:
   ```env
   VITE_API_BASE_URL=https://api.yourdomain.com/api/v1
   ```

4. Build the project:
   ```bash
   npm run build
   ```
   *This creates a `dist` folder.*

---

## 6. Nginx Configuration

Create a new Nginx config:
`sudo nano /etc/nginx/sites-available/hrm`

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    # Frontend Static Files
    location / {
        root /var/www/hrm-frontend/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # Backend API Reverse Proxy
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Enable the site and restart Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/hrm /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 7. Security (SSL)

Use Certbot to enable HTTPS:
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d api.yourdomain.com
```

---

## 8. Summary Checklist

- [ ] Database created and user granted permissions.
- [ ] Backend dependencies installed and `.env` configured.
- [ ] Database migrations (`alembic upgrade head`) finished.
- [ ] Seeders (`seed_production_data.py`) executed.
- [ ] Frontend build (`npm run build`) completed.
- [ ] Nginx configured for both Frontend and Reverse Proxy.
- [ ] HTTPS/SSL certificates installed.
