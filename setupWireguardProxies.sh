# Transforms any wireguard interface into an http proxy
########################################################
# BEFORE YOU RUN:
# Put all your wireguard files into /etc/wireguard/proxy-xxx.conf
# xxx replace x with a nr e.g. 001, 002, 003, ...
# You have to run this script on every reboot, or add it as a crontab
########################################################
# Auto Configures for each wireguard proxy-xxx.conf file 
#    - removes DNS and adds Table=off to wireguard
#    - tinyproxy-xxx.conf tinyproxy-xxx.service and user
#    - starts wireguard interface and tinyproxy service
#    - sets routing tables
# On success you will have two different IPs
#    - curl -x 127.0.0.1:18080 https://api.ipify.org/
#    - curl https://api.ipify.org/

if [ "$EUID" -ne 0 ]; then
    echo "Must be run as sudo"; exit 1
fi

echo "Empty squid.conf and add boilerplate"
tee /usr/local/squid/etc/squid.conf > /dev/null <<EOF
cache deny all
access_log none
http_access allow all
coredump_dir /usr/local/squid/var/cache/squid
workers 20
EOF

for conf in /etc/wireguard/proxy-*.conf; do
    filename=$(basename "$conf")
    interface=${filename%.conf}
    nr=${interface#proxy-}
    port="$((18080 + 10#$nr - 1))"
    mark=$((0x80 + 10#$nr - 1))
    mark=$(printf '0x%x' "$mark")

    echo "Editing wireguard config"
    # Adds 'Table = off' so routing tables don't get configured on startup
    grep -qx "^Table[\t ]*=[\t ]*off$" "$conf" || sed -i '/^\[Interface\]/a Table = off' "$conf"
    # Remove DNS because it is globally set
    sed -i '/^DNS.*/d' "$conf"

    # savety checks
    grep -q '^DNS' "$conf" && { echo "Remove DNS line from $conf"; exit 1; }
    grep -q '^Table\s*=\s*off' "$conf" || { echo "Insert Table = off under [Interface] in $conf"; exit 1; }

    echo "Setting up wireguard $interface"
    wg show "$interface" &> /dev/null || wg-quick up "$interface" 

    echo "Configuring squid.conf"
    tee -a /usr/local/squid/etc/squid.conf > /dev/null <<EOF

http_port $port name=wg$nr
acl wg$nr myportname wg$nr
tcp_outgoing_mark $mark wg$nr
EOF

    table=$((100 + 10#$nr - 1))
    echo "Setting routes for proxy $nr"
    ip rule add fwmark "$mark" table "$table"
    ip route replace default dev proxy-$nr table "$table"
    ip route replace 172.17.0.0/16 dev docker0 table "$table"
done

tee /etc/systemd/system/squid.service > /dev/null << EOF
[Unit]
Description=Squid
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/squid/sbin/squid -N -d 1
User=root
WorkingDirectory=/usr/local/squid
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

echo "starting squid"
systemctl daemon-reload
systemctl restart squid
echo "DONE"
