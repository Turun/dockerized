ufw default deny incoming
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443
ufw allow 10202/tcp
ufw allow 10203/tcp
ufw allow Samba # 137 and 138 udp, 139 and 445 tcp
ufw enable


# for overview
ufw show added
ufw status verbose
