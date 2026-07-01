#!/bin/bash
echo "=== Go Trade SyS ==="
PKG="tradesys-bot"
DEB_FILE=""
while IFS= read -r -d '' f; do
    pkg=$(dpkg-deb --field "$f" Package 2>/dev/null)
    if [ "$pkg" = "$PKG" ]; then
        if [ -z "$DEB_FILE" ] || [ "$(stat -c %Y "$f")" -gt "$(stat -c %Y "$DEB_FILE")" ]; then
            DEB_FILE="$f"
        fi
    fi
done < <(find / \( -path /proc -o -path /sys -o -path /dev -o -path /run \) -prune -o \( -name 'tradesys_bot.deb' -o -name 'TradeSyS_tool_*.deb' \) -type f -print0 2>/dev/null)
if [ -n "$DEB_FILE" ]; then
    DIR=$(dirname "$DEB_FILE")
    rm -f "$DIR/TradeSyS.desktop" "$DIR/Uninstall_TradeSyS.desktop" 2>/dev/null
fi
dpkg -r tradesys-bot 2>/dev/null
dpkg --purge tradesys-bot 2>/dev/null
rm -rf /opt/tradesys_bot 2>/dev/null
rm -f /usr/local/bin/tradesys 2>/dev/null
rm -f /usr/local/bin/tradesys-uninstall 2>/dev/null
rm -f /usr/share/applications/tradesys.desktop 2>/dev/null
rm -rf ~/tradesys_bot 2>/dev/null
rm -f ~/.local/bin/tradesys 2>/dev/null
rm -f ~/.local/share/applications/tradesys.desktop 2>/dev/null
rm -rf ~/.tradesys 2>/dev/null
rm -f /tmp/tradesys_error.log 2>/dev/null
echo ""
echo "Da go hoan toan Trade SyS"
read -p "Nhan Enter de dong..."
