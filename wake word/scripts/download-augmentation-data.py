#!/usr/bin/env python3
"""Ensure augmentation data dirs exist. MIT/FMA optional (training works without them)."""
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT)

for d in ("data/mit_rirs", "data/fma"):
    os.makedirs(d, exist_ok=True)
    n = len([f for f in os.listdir(d) if f.endswith(".wav")])
    print(f"{d}: {n} wav files")

print("Augmentation dirs ready (empty RIR/background is OK for training).")
