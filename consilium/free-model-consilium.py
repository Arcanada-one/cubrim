#!/usr/bin/env python3
"""Cubrim free-model consilium: 3 free members (OpenRouter) give opinions,
DeepSeek head synthesizes. JSON repaired via arcanada-output-guard."""
import sys, os, json, time, concurrent.futures as cf, urllib.request, urllib.error
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "og-venv/lib"))
try:
    from output_guard import repair
except Exception:
    repair = None

OR_KEY = open(os.path.expanduser("~/arcanada/config/credentials/Openrouter.md")).read()
import re
OR_KEY = re.search(r"sk-or-v1-[A-Za-z0-9-]+", OR_KEY).group(0)
DS_KEY = re.search(r"sk-[A-Za-z0-9]{20,}", open(os.path.expanduser("~/arcanada/config/credentials/Deepseek.md")).read()).group(0)

MEMBERS = [
    ("gpt-oss-120b",  "https://openrouter.ai/api/v1/messages", OR_KEY, "openai/gpt-oss-120b:free"),
    ("gemma-4-31b",   "https://openrouter.ai/api/v1/messages", OR_KEY, "google/gemma-4-31b-it:free"),
    ("nemotron-120b", "https://openrouter.ai/api/v1/messages", OR_KEY, "nvidia/nemotron-3-super-120b-a12b:free"),
]
HEAD = ("deepseek-v4", "https://api.deepseek.com/anthropic/v1/messages", DS_KEY, "deepseek-chat")

def call(url, key, model, prompt, max_tokens=600, retries=2):
    body = json.dumps({"model": model, "max_tokens": max_tokens,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    for attempt in range(retries+1):
        try:
            req = urllib.request.Request(url, data=body, headers={
                "Authorization": f"Bearer {key}", "content-type": "application/json",
                "anthropic-version": "2023-06-01"})
            raw = urllib.request.urlopen(req, timeout=70).read().decode()
            d = json.loads(raw)
            txt = " ".join(b.get("text","") for b in d.get("content",[]) if b.get("type")=="text")
            if txt.strip(): return txt.strip()
            return "[empty/thinking-only]"
        except urllib.error.HTTPError as e:
            err = e.read().decode()[:120]
            if e.code == 429 and attempt < retries:
                time.sleep(20); continue
            return f"[HTTP{e.code}: {err}]"
        except Exception as e:
            return f"[err: {str(e)[:80]}]"

def ask_members(question):
    out = {}
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(call, url, key, model, question): name for name,url,key,model in MEMBERS}
        for f in cf.as_completed(futs):
            out[futs[f]] = f.result()
    return out

def synthesize(question, opinions):
    blob = "\n\n".join(f"### Member {n}:\n{t}" for n,t in opinions.items())
    prompt = (f"You are the HEAD of a compression-research consilium. Question posed to members:\n\n{question}\n\n"
              f"Member opinions:\n\n{blob}\n\n"
              "Synthesize: (1) which proposal is strongest and WHY (non-subsumability + realistic ceiling), "
              "(2) flag any fabricated/overclaimed numbers, (3) give ONE final ranked recommendation for the implementer "
              "to spike-test first. Be concise and honest. Discount unverifiable ceilings.")
    return call(*HEAD[1:], prompt, max_tokens=800)

if __name__ == "__main__":
    q = sys.stdin.read().strip()
    print("=== ASKING 3 FREE MEMBERS (parallel) ===", flush=True)
    ops = ask_members(q)
    for n,t in ops.items():
        print(f"\n----- {n} -----\n{t[:500]}", flush=True)
    print("\n\n=== DEEPSEEK HEAD SYNTHESIS ===", flush=True)
    print(synthesize(q, ops), flush=True)
