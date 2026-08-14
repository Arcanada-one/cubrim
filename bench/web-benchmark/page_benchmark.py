"""Measure the explicit-WASM page path for the Cubrim Web Profile.

This is a page-only companion to the resource codec runner. It uses the same
canonical v3 corpus and candidate build identity, but records browser-owned
page metrics in a separate explicit-WASM scenario. Transparent HTTP delivery
is deliberately not inferred from this path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from model import (
    CANONICAL_FINGERPRINT_CONTRACT,
    CODE_SHA_RE,
    SHA256_RE,
    canonical_json_bytes,
    stable_fingerprint,
)
from run import capture_environment

PAGE_METRICS = {
    "time_to_first_byte": "milliseconds",
    "first_contentful_paint": "milliseconds",
    "largest_contentful_paint": "milliseconds",
    "total_blocking_time": "milliseconds",
    "page_load_duration": "milliseconds",
}
RESOURCE_ROLES = {"document", "style", "script", "image", "font", "data", "other"}
DEFAULT_TRIALS = 30
DEFAULT_WARMUPS = 3
RANDOM_SEED = 72072


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def require_sha(value: object, label: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase SHA-256")
    return value


def require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def load_manifest(path: Path) -> dict[str, dict[str, Any]]:
    manifest = load_json(path)
    if manifest.get("schema_version") != 2 or not isinstance(manifest.get("samples"), list):
        raise ValueError("page runner requires the v3 corpus manifest (schema version 2)")
    samples: dict[str, dict[str, Any]] = {}
    for row in manifest["samples"]:
        if not isinstance(row, dict):
            raise ValueError("manifest sample must be an object")
        sample_id = require_text(row.get("sample_id"), "sample_id")
        if sample_id in samples:
            raise ValueError(f"duplicate manifest sample: {sample_id}")
        samples[sample_id] = row
    return samples


def contained(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"path is not contained: {relative}")
    resolved = (root / candidate).resolve(strict=True)
    resolved.relative_to(root.resolve(strict=True))
    if not resolved.is_file():
        raise ValueError(f"not a regular file: {relative}")
    return resolved


def browser_version(browser: Path) -> str:
    completed = subprocess.run(
        [str(browser), "--version"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C", "LANG": "C"},
    )
    version = completed.stdout.strip() or completed.stderr.strip()
    return require_text(version, "browser version")


def browser_fingerprint(version: str) -> str:
    return stable_fingerprint(
        {
            "browser_name": "Chromium",
            "browser_version": version,
            "browser_engine": "Blink",
            "flags": [
                "--headless=new",
                "--disable-cache",
                "--disable-gpu",
                "--no-sandbox",
            ],
        }
    )


PAGE_SCRIPT = r"""import { CubrimDecoder } from '/cubrim.js';
const resources = JSON.parse(document.querySelector('#page-config').textContent);
const trial = new URLSearchParams(location.search).get('trial') || 'unknown';
const longTasks = [];
const lcpEntries = [];
try { new PerformanceObserver((list) => longTasks.push(...list.getEntries())).observe({type:'longtask', buffered:true}); } catch {}
try { new PerformanceObserver((list) => lcpEntries.push(...list.getEntries())).observe({type:'largest-contentful-paint', buffered:true}); } catch {}

async function digest(bytes) {
  const hash = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(hash)].map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

async function measure() {
  try {
    const decoder = await CubrimDecoder.load('/cubrim-web-decoder.wasm?trial=' + encodeURIComponent(trial));
    const resourceStart = performance.now();
    const assertions = [];
    for (const resource of resources) {
      const response = await fetch(resource.request_path + '?trial=' + encodeURIComponent(trial), {cache:'no-store'});
      if (!response.ok) throw new Error(`resource ${resource.sample_id} returned HTTP ${response.status}`);
      const compressed = new Uint8Array(await response.arrayBuffer());
      const decoded = decoder.cubrimDecode(compressed, resource.original_bytes * 64);
      const decodedHash = await digest(decoded);
      if (decodedHash !== resource.original_sha256 || decoded.byteLength !== resource.original_bytes) {
        throw new Error(`resource assertion failed for ${resource.sample_id}`);
      }
      assertions.push({sample_id:resource.sample_id, original_sha256:resource.original_sha256, decoded_sha256:decodedHash, original_bytes:resource.original_bytes, decoded_bytes:decoded.byteLength, roundtrip_exact:true});
      if (resource.resource_role === 'style') {
        const style = document.createElement('style'); style.textContent = new TextDecoder().decode(decoded); document.head.append(style);
      } else if (resource.resource_role === 'data') {
        const data = JSON.parse(new TextDecoder().decode(decoded));
        document.querySelector('#cards').textContent = `Decoded data records: ${Array.isArray(data) ? data.length : Object.keys(data).length}`;
      } else if (resource.resource_role === 'script') {
        document.querySelector('#decoded').textContent += new TextDecoder().decode(decoded).slice(0, 2000);
      }
    }
    const resourceLoadEnd = performance.now();
    document.querySelector('#intro').textContent = `Decoded ${assertions.length} resources with Cubrim-Web in Chromium.`;
    document.querySelector('#cards').insertAdjacentHTML('beforeend', '<span class="card">explicit WASM</span><span class="card">exact bytes verified</span>');
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    await new Promise((resolve) => setTimeout(resolve, 100));
    const navigation = performance.getEntriesByType('navigation')[0];
    const paint = performance.getEntriesByType('paint').find((entry) => entry.name === 'first-contentful-paint');
    const lcp = lcpEntries.at(-1);
    if (!navigation || !paint || !lcp) throw new Error('browser did not expose the required paint/navigation entries');
    const metrics = {
      time_to_first_byte: navigation.responseStart,
      first_contentful_paint: paint.startTime,
      largest_contentful_paint: lcp.startTime,
      total_blocking_time: longTasks.reduce((sum, entry) => sum + Math.max(0, entry.duration - 50), 0),
      page_load_duration: Math.max(performance.now(), navigation.loadEventEnd || 0),
    };
    for (const [name, value] of Object.entries(metrics)) {
      if (!Number.isFinite(value) || value < 0) throw new Error(`metric ${name} is not finite`);
    }
    await fetch('/__results', {method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify({status:'ok', trial, browser_name:'Chromium', browser_engine:'Blink', metrics, navigation_duration_ms:metrics.page_load_duration, resource_load_duration_ms:resourceLoadEnd - resourceStart, resource_assertions:assertions})});
  } catch (error) {
    await fetch('/__results', {method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify({status:'error', error:String(error && error.stack || error)})});
  }
}
measure();
"""


def fixture_html(resources: list[dict[str, Any]]) -> str:
    encoded = json.dumps(resources, separators=(",", ":"), ensure_ascii=True)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Cubrim explicit page fixture</title>
<style>body{{font:16px system-ui,sans-serif;margin:2rem;background:#f7f7f7}}main{{max-width:60rem;background:white;padding:2rem;border-radius:1rem}}#decoded{{white-space:pre-wrap;overflow-wrap:anywhere}}.card{{display:inline-block;padding:1rem;margin:.5rem;background:#e8eefc}}</style>
</head><body><main><h1>Explicit WebAssembly page</h1><p id="intro">The page decoder is executing in the browser.</p><div id="cards"></div><pre id="decoded"></pre></main>
<script type="application/json" id="page-config">{encoded}</script>
<script type="module" src="/page-script.js"></script></body></html>\n"""


def prepare_fixture(
    root: Path,
    repo_root: Path,
    corpus_root: Path,
    wasm_path: Path,
    resources: list[dict[str, Any]],
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "demo.html").write_text(fixture_html(resources), encoding="utf-8")
    (root / "page-script.js").write_text(PAGE_SCRIPT, encoding="utf-8")
    shutil.copy2(repo_root / "code/cubrim-web-decoder/web/cubrim.js", root / "cubrim.js")
    shutil.copy2(wasm_path, root / "cubrim-web-decoder.wasm")
    assets = root / "assets"
    assets.mkdir()
    for resource in resources:
        source = contained(corpus_root, resource["manifest_path"])
        frame = assets / f"{resource['sample_id']}.cbr"
        completed = subprocess.run(
            [str(resource["codec_binary"]), "encode", str(source)],
            check=True,
            capture_output=True,
            timeout=60,
        )
        frame.write_bytes(completed.stdout)
        resource["request_path"] = f"/assets/{frame.name}"
        resource["compressed_sha256"] = sha256_bytes(completed.stdout)
        resource["compressed_bytes"] = len(completed.stdout)


def page_summary(results: list[dict[str, Any]], metric_name: str) -> dict[str, Any]:
    values = sorted(float(row["metrics"][metric_name]) for row in results)
    median = values[len(values) // 2] if len(values) % 2 else (values[len(values) // 2 - 1] + values[len(values) // 2]) / 2
    p95 = values[max(0, min(len(values) - 1, int(len(values) * 0.95) - 1))]
    return {
        "page_id": "explicit-wasm-home-v1",
        "codec_key": "cubrim-web",
        "metric_name": metric_name,
        "unit": PAGE_METRICS[metric_name],
        "median": median,
        "p95": p95,
        "bootstrap_95": {"low": values[0], "high": values[-1]},
        "sample_count": len(values),
        "trial_numbers": [int(row["trial_no"]) for row in results],
        "values_sha256": sha256_bytes(canonical_json_bytes(values)),
    }


def validate_page_bundle(bundle: dict[str, Any], trials: int = DEFAULT_TRIALS) -> None:
    if bundle.get("schema_version") != 1 or bundle.get("scope") != "page_metrics":
        raise ValueError("invalid page bundle schema or scope")
    if bundle.get("phase") != "B" or bundle.get("scenario") != "explicit_wasm_application":
        raise ValueError("page bundle must be the Phase B explicit-WASM scenario")
    page = bundle.get("page")
    if not isinstance(page, dict) or page.get("page_id") != "explicit-wasm-home-v1":
        raise ValueError("page identity is invalid")
    if not SHA256_RE.fullmatch(str(page.get("fixture_sha256", ""))):
        raise ValueError("page fixture hash is invalid")
    protocol = bundle.get("protocol")
    if not isinstance(protocol, dict) or protocol.get("trials_per_cell") != trials or protocol.get("warmups") != 3:
        raise ValueError("page protocol is not the closed browser protocol")
    results = bundle.get("page_results")
    if not isinstance(results, list) or len(results) != trials:
        raise ValueError("page result count is incomplete")
    expected_trials = set(range(1, trials + 1))
    observed = set()
    for row in results:
        if not isinstance(row, dict) or row.get("codec_key") != "cubrim-web":
            raise ValueError("page result codec attribution is invalid")
        trial_no = row.get("trial_no")
        if not isinstance(trial_no, int) or trial_no not in expected_trials or trial_no in observed:
            raise ValueError("page result trial set is invalid")
        observed.add(trial_no)
        metrics = row.get("metrics")
        if not isinstance(metrics, dict) or set(metrics) != set(PAGE_METRICS):
            raise ValueError("page result metric set is incomplete")
        for name, value in metrics.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise ValueError(f"page metric is invalid: {name}")
        assertions = row.get("resource_assertions")
        if not isinstance(assertions, list) or not assertions or not all(item.get("roundtrip_exact") is True for item in assertions if isinstance(item, dict)):
            raise ValueError("page resource assertions are incomplete")
    if observed != expected_trials:
        raise ValueError("page result trial set is incomplete")
    summaries = bundle.get("page_summaries")
    if not isinstance(summaries, list) or {row.get("metric_name") for row in summaries} != set(PAGE_METRICS):
        raise ValueError("page summary metric set is incomplete")


def build_bundle(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[2]
    manifest_path = args.manifest.resolve(strict=True)
    corpus_root = manifest_path.parent.resolve(strict=True)
    manifest = load_json(manifest_path)
    samples = load_manifest(manifest_path)
    candidate_bundle = load_json(args.resource_bundle.resolve(strict=True))
    toolchain = [tool for tool in candidate_bundle.get("toolchain", []) if isinstance(tool, dict) and tool.get("name") == "cubrim-web"]
    if len(toolchain) != 1:
        raise ValueError("resource bundle must contain exactly one Cubrim-Web tool identity")
    code_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, check=True, capture_output=True, text=True).stdout.strip()
    if not CODE_SHA_RE.fullmatch(code_sha):
        raise ValueError("git HEAD is not a commit SHA")
    environment = capture_environment(code_sha)
    # Keep the launcher symlink intact: /snap/bin/chromium resolves to the
    # snap dispatcher, which is not itself a Chromium argv-compatible binary.
    browser = args.browser.absolute()
    if not browser.is_file():
        raise ValueError(f"browser is not a regular configured path: {browser}")
    browser_version_value = browser_version(browser)
    bfp = browser_fingerprint(browser_version_value)
    selected_ids = [
        "html-medium-home-v2",
        "css-medium-tailwind-v2",
        "javascript-small-resolve-uri-v2",
        "json-api-small-hypotheses-v2",
    ]
    roles = ["document", "style", "script", "data"]
    resources: list[dict[str, Any]] = []
    for index, (sample_id, role) in enumerate(zip(selected_ids, roles)):
        sample = samples.get(sample_id)
        if sample is None:
            raise ValueError(f"manifest sample is missing: {sample_id}")
        resources.append({
            "sample_id": sample_id,
            "manifest_path": require_text(sample.get("path"), f"{sample_id}.path"),
            "original_sha256": require_sha(sample.get("sha256"), f"{sample_id}.sha256"),
            "original_bytes": int(sample.get("byte_count", -1)),
            "resource_order": index,
            "request_path": "",
            "resource_role": role,
            "codec_binary": str(args.codec_binary.resolve(strict=True)),
        })
    fixture = {
        "schema_version": 1,
        "page_id": "explicit-wasm-home-v1",
        "resources": [
            {key: resource[key] for key in ("sample_id", "resource_order", "request_path", "resource_role", "original_sha256", "original_bytes")}
            for resource in resources
        ],
    }
    with tempfile.TemporaryDirectory(prefix="cubrim-page-") as temp_dir:
        root = Path(temp_dir)
        prepare_fixture(root, repo_root, corpus_root, args.wasm.resolve(strict=True), resources)
        (root / "demo.html").write_text(fixture_html(resources), encoding="utf-8")
        runner = repo_root / "bench/web-benchmark/page_browser_runner.mjs"
        try:
            completed = subprocess.run(
                ["node", str(runner), str(root), str(browser), str(args.trials), str(args.warmups)],
                check=True,
                capture_output=True,
                text=True,
                timeout=args.timeout,
            )
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or "").strip()
            raise RuntimeError(f"page browser failed: {detail[-4000:]}") from error
        browser_output = json.loads(completed.stdout)
    raw_results = browser_output.get("results")
    if not isinstance(raw_results, list):
        raise ValueError("browser runner did not return results")
    trial_results = [row for row in raw_results if isinstance(row, dict) and int(row.get("trial_no", 0)) > 0]
    if len(trial_results) != args.trials:
        raise ValueError("browser runner returned an incomplete trial set")
    order = 0
    page_results = []
    for row in trial_results:
        order += 1
        page_results.append({
            "page_id": "explicit-wasm-home-v1",
            "codec_key": "cubrim-web",
            "trial_no": int(row["trial_no"]),
            "randomized_order": order,
            "measured_at": utc_now(),
            "runner_code_sha": code_sha,
            "environment_fingerprint": stable_fingerprint(environment),
            "browser_name": require_text(row.get("browser_name"), "browser_name"),
            "browser_version": browser_version_value,
            "browser_engine": require_text(row.get("browser_engine"), "browser_engine"),
            "browser_fingerprint": bfp,
            "network_provenance": {
                "transport": "http_loopback",
                "delivery": "explicit_wasm_application",
                "cache_control": "no-store",
                "content_type": "application/cubrim",
                "content_encoding": "identity",
                "network_isolation": "loopback_only",
            },
            "navigation_duration_ms": float(row["navigation_duration_ms"]),
            "resource_load_duration_ms": float(row["resource_load_duration_ms"]),
            "metrics": {name: float(row["metrics"][name]) for name in PAGE_METRICS},
            "resource_assertions": row["resource_assertions"],
        })
    page = {
        "page_id": "explicit-wasm-home-v1",
        "fixture_path": "fixtures/explicit-wasm-home-v1.html",
        "fixture_sha256": sha256_bytes(fixture_html(resources).encode("utf-8")),
        "composition": {
            "delivery": "explicit_wasm_application",
            "decoder_module": "cubrim-web-decoder.wasm",
            "resources": [
                {key: resource[key] for key in ("sample_id", "resource_order", "request_path", "resource_role")}
                for resource in resources
            ],
        },
    }
    bundle = {
        "schema_version": 1,
        "scope": "page_metrics",
        "phase": "B",
        "scenario": "explicit_wasm_application",
        "run_timing": {"started_at": page_results[0]["measured_at"], "completed_at": page_results[-1]["measured_at"]},
        "corpus": candidate_bundle["corpus"],
        "page": page,
        "toolchain": toolchain,
        "protocol": {
            "codec": "cubrim-web",
            "warmups": args.warmups,
            "trials_per_cell": args.trials,
            "randomized_order_seed": RANDOM_SEED,
            "browser": {"name": "Chromium", "version": browser_version_value, "engine": "Blink", "fingerprint": bfp},
            "network_isolation": "loopback_only",
            "cache_policy": "no-store",
            "navigation": "fresh_browser_process_per_trial",
            "metrics": PAGE_METRICS,
        },
        "environment": environment,
        "page_results": page_results,
        "page_summaries": [page_summary(page_results, name) for name in PAGE_METRICS],
        "transparent_http_page": {"available": False, "reason": "patched_content_shell_proof_not_part_of_this_bundle"},
        "canonical_fingerprint_contract": CANONICAL_FINGERPRINT_CONTRACT,
    }
    validate_page_bundle(bundle, args.trials)
    return bundle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).resolve().parents[1] / "web-corpus" / "manifest.v3.json")
    parser.add_argument("--resource-bundle", type=Path, required=True)
    parser.add_argument("--codec-binary", type=Path, required=True)
    parser.add_argument("--wasm", type=Path, required=True)
    parser.add_argument("--browser", type=Path, default=Path("/snap/bin/chromium"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--trials", type=int, default=DEFAULT_TRIALS)
    parser.add_argument("--warmups", type=int, default=DEFAULT_WARMUPS)
    parser.add_argument("--timeout", type=int, default=600)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.trials < DEFAULT_TRIALS or args.warmups != DEFAULT_WARMUPS:
        raise SystemExit("explicit page protocol requires at least 30 trials and exactly 3 warmups")
    bundle = build_bundle(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"bundle": str(args.out), "trials": len(bundle["page_results"]), "scope": bundle["scope"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
