#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESULT_DIR="${ROOT_DIR}/jmeter/results"
DASHBOARD_DIR="${RESULT_DIR}/dashboard"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-5010}"
PROTOCOL="${PROTOCOL:-http}"
USERS="${USERS:-20}"
RAMP_UP="${RAMP_UP:-20}"
LOOPS="${LOOPS:-10}"
TOP_K="${TOP_K:-5}"
SLA_MS="${SLA_MS:-3000}"
CONNECT_TIMEOUT="${CONNECT_TIMEOUT:-5000}"
RESPONSE_TIMEOUT="${RESPONSE_TIMEOUT:-15000}"
QUERY_FILE="${QUERY_FILE:-${ROOT_DIR}/jmeter/hybrid_retrieval_queries.csv}"
PLAN_FILE="${PLAN_FILE:-${ROOT_DIR}/jmeter/hybrid_retrieval_test_plan.jmx}"
JTL_FILE="${JTL_FILE:-${RESULT_DIR}/hybrid_retrieval.jtl}"

mkdir -p "${RESULT_DIR}"
rm -rf "${DASHBOARD_DIR}"
rm -f "${JTL_FILE}"

echo "Running JMeter against ${PROTOCOL}://${HOST}:${PORT}/api/retrieval/search"
echo "Users=${USERS} RampUp=${RAMP_UP} Loops=${LOOPS} TopK=${TOP_K}"

jmeter -n \
  -t "${PLAN_FILE}" \
  -l "${JTL_FILE}" \
  -e \
  -o "${DASHBOARD_DIR}" \
  -JHOST="${HOST}" \
  -JPORT="${PORT}" \
  -JPROTOCOL="${PROTOCOL}" \
  -JUSERS="${USERS}" \
  -JRAMP_UP="${RAMP_UP}" \
  -JLOOPS="${LOOPS}" \
  -JTOP_K="${TOP_K}" \
  -JSLA_MS="${SLA_MS}" \
  -JCONNECT_TIMEOUT="${CONNECT_TIMEOUT}" \
  -JRESPONSE_TIMEOUT="${RESPONSE_TIMEOUT}" \
  -JQUERY_FILE="${QUERY_FILE}" \
  -Jsample_variables=hit_count,total_ms,lexical_ms,vector_ms,fusion_ms,rerank_ms

echo
echo "JTL: ${JTL_FILE}"
echo "Dashboard: ${DASHBOARD_DIR}/index.html"
echo "Analyze: python3 ${ROOT_DIR}/jmeter/analyze_results.py ${JTL_FILE}"
