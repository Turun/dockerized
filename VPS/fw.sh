ufw default deny incoming
ufw allow 80/tcp
ufw allow 443
ufw allow 10202/tcp
ufw enable

# for overview
ufw show added
ufw status verbose
