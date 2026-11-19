#!/bin/sh
# Keep the container alive without named, so the watchdog and Ansible own its lifecycle.
mkdir -p /var/log/named && chown bind:bind /var/log/named && touch /var/log/named/named.log && chown bind:bind /var/log/named/named.log
tail -F /var/log/named/named.log &
exec sleep infinity
