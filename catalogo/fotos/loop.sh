#!/usr/bin/env bash
# Roda o pipeline de fotos em lotes até não sobrar grupo pendente.
#   nohup catalogo/fotos/loop.sh >> /tmp/fotos_carreiro.log 2>&1 &   # rodar em segundo plano
#   tail -f /tmp/fotos_carreiro.log                                  # acompanhar
#   pkill -INT -f catalogo/fotos/loop.sh; pkill -INT -f catalogo.fotos.executar   # parar
# Pode parar a qualquer momento: grupo interrompido continua pendente e é refeito.
set -u
cd "$(dirname "$0")/../.."
export TORCH_CPP_LOG_LEVEL=ERROR
export PYTHONUNBUFFERED=1
while true; do
  catalogo/.venv-fotos/bin/python -m catalogo.fotos.executar --limite 500
  rc=$?
  case $rc in
    0) sleep 5 ;;                                                    # lote ok, próximo
    4) echo "$(date '+%F %T') nada pendente: fim."; exit 0 ;;
    3) echo "$(date '+%F %T') DuckDuckGo bloqueando: pausa de 30 min."; sleep 1800 ;;
    *) echo "$(date '+%F %T') erro rc=$rc: parei."; exit "$rc" ;;
  esac
done
