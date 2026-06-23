#!/bin/bash
# RAGFlow 12小时稳定性监控脚本
# 用法: bash stability_monitor.sh [持续时间秒] [间隔秒]
# 默认: 12小时(43200s), 每60秒采集一次

DURATION=${1:-43200}
INTERVAL=${2:-60}
OUTDIR="/mnt/c/Users/31326/Desktop/rag工单17/stability_data"
mkdir -p "$OUTDIR"

echo "=== RAGFlow 12h Stability Monitor ==="
echo "Duration: ${DURATION}s, Interval: ${INTERVAL}s"
echo "Start: $(date)"
echo ""

elapsed=0
while [ $elapsed -lt $DURATION ]; do
    timestamp=$(date +%s)
    datestr=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Memory stats
    mem=$(docker stats --no-stream docker-ragflow-cpu-1 --format '{{.MemUsage}}|{{.CPUPerc}}' 2>/dev/null)
    
    # Health check
    health=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:9380/api/v1/system/healthz 2>/dev/null)
    
    # GPU memory
    gpu_mem=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader 2>/dev/null || echo "N/A")
    
    # API response time (single quick request)
    TOKEN=$(cat "/mnt/c/Users/31326/Desktop/rag工单17/.jwt_token" 2>/dev/null)
    api_time=0
    if [ -n "$TOKEN" ]; then
        start_ns=$(date +%s%N)
        curl -s -X POST "http://localhost:9380/api/v1/chats/2f3f16ec662111f1b8890975c873e6bd/completions" \
          -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" \
          -d '{"question":"hi","stream":false}' -o /dev/null 2>/dev/null
        end_ns=$(date +%s%N)
        api_time=$(echo "scale=3; ($end_ns - $start_ns) / 1000000000" | bc)
    fi
    
    echo "$timestamp,$datestr,$mem,$health,$gpu_mem,$api_time" >> "$OUTDIR/monitor.csv"
    
    elapsed=$((elapsed + INTERVAL))
    hours=$((elapsed / 3600))
    mins=$(((elapsed % 3600) / 60))
    echo "[$datestr] ${hours}h${mins}m | Health:$health | API:${api_time}s | GPU:${gpu_mem}MiB | $mem"
    
    sleep $INTERVAL
done

echo ""
echo "=== Complete: $(date) ==="
echo "Data saved to $OUTDIR/monitor.csv"
