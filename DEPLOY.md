## Manual Release

Initial server setup is done once. Afterwards, every release only needs:

```bash
ssh root@172.16.62.135
cd /opt/dingtalk_msg
./deploy.sh
```

## First-Time Setup Summary

1. Clone the repository to `/opt/dingtalk_msg`
2. Copy `.env.example` to `.env` and fill runtime secrets
3. Install Python dependencies and Playwright Chromium
4. Install `dingtalk-msg.service`
5. Enable and start the service

## Runtime Environment Variables

Required values in `.env`:

```bash
REPORT_BASE_URL=http://your-server-ip:8765
UPLOAD_SFTP_HOST=172.16.62.135
UPLOAD_SFTP_PORT=22
UPLOAD_SFTP_USER=root
UPLOAD_SFTP_PASS=your-password
UPLOAD_REMOTE_DIR=/home/imgs
UPLOAD_HTTP_BASE=http://your-public-host/imgs
```

Optional values:

```bash
GITHUB_TOKEN=
GITHUB_REPO=
```
