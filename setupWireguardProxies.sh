# Transforms any wireguard interface into an http proxy
########################################################
# BEFORE YOU RUN:
# Put all your wireguard files into /etc/wireguard/proxy-xxx.conf
# xxx replace x with a nr e.g. 001, 002, 003, ...
########################################################
# Auto Configures for each wireguard proxy-xxx.conf file 
#    - tinyproxy-xxx.conf tinyproxy-xxx.service and user
#    - starts wireguard interface and tinyproxy service
#    - sets routing tables
# On success you will have two different IPs
#    - curl -x 127.0.0.1:18080 https://api.ipify.org/
#    - curl https://api.ipify.org/

if [ "$EUID" -ne 0 ]; then
    echo "Must be run as sudo"; exit 1
fi

for conf in /etc/wireguard/proxy-*.conf; do
    filename=$(basename "$conf")
    interface=${filename%.conf}
    nr=${interface#proxy-}
    port="$((18080 + 10#$nr - 1))"

    # savety checks
    grep -q '^DNS' "$conf" && { echo "Remove DNS line from $conf"; exit 1; }
    grep -q '^Table\s*=\s*off' "$conf" || { echo "Insert Table = off under [Interface] in $conf"; exit 1; }

    echo "Setting up wireguard $interface"
    wg show "$interface" &> /dev/null || wg-quick up "$interface" 

    echo "Setting up tinyproxy-$nr"
    id tinyproxy-$nr &> /dev/null || useradd --system --no-create-home --shell /usr/sbin/nologin tinyproxy-$nr
    uid=$(id -u "tinyproxy-$nr")

    echo "Configuring tinyproxy-$nr.conf (Port $port)"
    tee "/etc/tinyproxy/tinyproxy-$nr.conf" > /dev/null <<EOF
User tinyproxy-$nr
Group tinyproxy-$nr
Port $port

Timeout 600
DefaultErrorFile "/usr/share/tinyproxy/default.html"
LogLevel Info
MaxClients 200

MinSpareServers 20 
MaxSpareServers 100 
StartServers 30 

MaxRequestsPerChild 0

Allow 127.0.0.1
Allow 172.17.0.0/16

ViaProxyName "tinyproxy"

ConnectPort 443
ConnectPort 563
EOF

    echo "Configuring tinyproxy-$nr.service"
    tee "/etc/systemd/system/tinyproxy-$nr.service" > /dev/null <<EOF
[Unit]
Description=Tinyproxy $nr
After=network.target

[Service]
Type=simple
User=tinyproxy-$nr
ExecStart=/usr/bin/tinyproxy -d -c /etc/tinyproxy/tinyproxy-$nr.conf
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable --now "tinyproxy-$nr.service"

    table=$((100 + 10#$nr - 1))
    echo "Setting routes for proxy $nr → UID $uid Routing Table $table"

    ip rule add uidrange "$uid-$uid" table "$table"
    ip route replace default dev "proxy-$nr" table "$table"
    ip route replace 172.17.0.0/16 dev docker0 table "$table"
done
