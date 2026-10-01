#!/bin/bash
# PostgreSQL 首次初始化时启用 vector 扩展（pgvector）
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
EOSQL
