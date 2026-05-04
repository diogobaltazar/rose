#!/bin/sh
mkdir -p /data
redis-server --daemonize yes --loglevel warning --appendonly yes --dir /data
exec uvicorn main:app --host 0.0.0.0 --port 8000
