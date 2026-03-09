#!/bin/bash
# Script per avviare il debug manualmente senza VS Code discovery

cd /home/ag/Desktop/d/Documenti/Lavoro/RM1/Flagship/SW/model4italy/m4i_package

echo "Avvio debug su porta 5678..."
echo "In VS Code: Run > Attach to Process > localhost:5678"
echo ""

/usr/local/bin/python3 -m debugpy --listen 0.0.0.0:5678 --wait-for-client model4italy.py run -p params_eur2_rt_offline.json
