#!/usr/bin/env python3
"""H-41 fixed-interval corpus generator (Prometheus 15s scrape + Intel-Berkeley-Lab 31s
sensor formats; deterministic LCG). For the DoubleDelta spike. Output dir = argv[1]."""
import sys, os
FI=sys.argv[1] if len(sys.argv)>1 else "fixedinterval"; os.makedirs(FI, exist_ok=True)
st=0x9E3779B97F4A7C15
def nx(m):
    global st; st=(st*6364136223846793005+1)&0xFFFFFFFFFFFFFFFF; return (st>>33)%m
rows=["timestamp,cpu_usage,mem_bytes,requests_total"]; ts=1700000000; cpu=2350; mem=512000000; req=0
for i in range(8000):
    ts+=15; cpu+=nx(11)-5; mem+=nx(20001)-10000; req+=nx(50)
    rows.append(f"{ts},{cpu/100:.2f},{mem},{req}")
open(f"{FI}/prometheus_metrics.csv","wb").write(("\n".join(rows)+"\n").encode())
rows=["epoch,moteid,temperature,humidity,light,voltage"]; ep=1000; t=1922; h=3789; l=4520; v=274
for i in range(8000):
    ep+=31; t+=nx(7)-3; h+=nx(7)-3; l+=nx(11)-5; v+=nx(3)-1
    rows.append(f"{ep},1,{t/100:.2f},{h/100:.2f},{l/100:.2f},{v/100:.2f}")
open(f"{FI}/sensor_berkeley.csv","wb").write(("\n".join(rows)+"\n").encode())
print(f"wrote prometheus_metrics.csv + sensor_berkeley.csv to {FI}")
