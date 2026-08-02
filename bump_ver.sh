#!/bin/bash
cd /home1/ikymximy/LinkLynk
V=$(date +%s)
sed -i -E "s/app\.js\?v=[0-9]+/app.js?v=$V/" index.html
echo "app.js?v=$V"
