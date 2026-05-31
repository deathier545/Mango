#!/usr/bin/env python3
import sys
steps = [
    ("onnxruntime", lambda: __import__("onnxruntime")),
    ("torch", lambda: __import__("torch")),
    ("openwakeword", lambda: __import__("openwakeword")),
    ("train", lambda: __import__("openwakeword.train")),
]
for name, fn in steps:
    print(f"import {name}...", flush=True)
    fn()
    print(f"  {name} OK", flush=True)
print("all OK")
