#!/usr/bin/env python3
"""Profile JSONB property sizes across all .trug.json files.

Resolves Unknown 3 (TOAST risk) for the PostgreSQL adapter by measuring
the serialized byte size of every node's `properties` field across all
TRUGs in the repository.

Usage:
    python TRUGS_STORE/scripts/profile_property_sizes.py [REPO_ROOT]

Output:
    - Human-readable summary to stdout
    - JSON results to TRUGS_STORE/scripts/results/property_size_profile.json
"""

import json
import os
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List


TOAST_THRESHOLD = 2048  # ~2KB PostgreSQL TOAST threshold

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".claude"}


def find_trug_files(root: Path) -> List[Path]:
    """Find all .trug.json files, excluding zzz_* and skip dirs."""
    trug_files = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip hidden/vendor dirs
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and not d.startswith("zzz_")
        ]
        # Skip zzz_ paths
        if "/zzz_" in dirpath or dirpath.endswith("/zzz_") or os.path.basename(dirpath).startswith("zzz_"):
            continue
        for fname in filenames:
            if fname.endswith(".trug.json") and not fname.startswith("zzz_"):
                trug_files.append(Path(dirpath) / fname)
    return sorted(trug_files)


def measure_properties(trug_path: Path) -> List[Dict[str, Any]]:
    """Measure serialized byte size of each node's properties field."""
    results = []
    try:
        with open(trug_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  WARN: Skipping {trug_path}: {e}", file=sys.stderr)
        return results

    nodes = data.get("nodes", [])
    for node in nodes:
        props = node.get("properties", {})
        serialized = json.dumps(props, ensure_ascii=False, separators=(",", ":"))
        byte_size = len(serialized.encode("utf-8"))
        results.append({
            "file": str(trug_path),
            "node_id": node.get("id", "<no-id>"),
            "node_type": node.get("type", "<no-type>"),
            "byte_size": byte_size,
        })
    return results


def compute_percentile(sorted_values: List[int], p: float) -> int:
    """Compute percentile from sorted list."""
    if not sorted_values:
        return 0
    k = (len(sorted_values) - 1) * (p / 100.0)
    f = int(k)
    c = f + 1
    if c >= len(sorted_values):
        return sorted_values[-1]
    return int(sorted_values[f] + (k - f) * (sorted_values[c] - sorted_values[f]))


def compute_stats(measurements: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute distribution statistics."""
    sizes = sorted(m["byte_size"] for m in measurements)
    if not sizes:
        return {"count": 0}

    return {
        "count": len(sizes),
        "min": sizes[0],
        "max": sizes[-1],
        "mean": round(statistics.mean(sizes), 1),
        "median": round(statistics.median(sizes), 1),
        "p90": compute_percentile(sizes, 90),
        "p95": compute_percentile(sizes, 95),
        "p99": compute_percentile(sizes, 99),
    }


def find_oversized(measurements: List[Dict[str, Any]], threshold: int = TOAST_THRESHOLD) -> List[Dict[str, Any]]:
    """Find nodes with properties exceeding the threshold."""
    return [m for m in measurements if m["byte_size"] > threshold]


def main():
    repo_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    repo_root = repo_root.resolve()

    script_dir = Path(__file__).parent.resolve()
    results_dir = script_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    output_path = results_dir / "property_size_profile.json"

    # Find all TRUG files
    trug_files = find_trug_files(repo_root)
    print(f"Found {len(trug_files)} .trug.json files")

    # Measure all properties
    all_measurements: List[Dict[str, Any]] = []
    for trug_file in trug_files:
        rel = trug_file.relative_to(repo_root)
        measurements = measure_properties(trug_file)
        # Store relative paths
        for m in measurements:
            m["file"] = str(rel)
        all_measurements.extend(measurements)

    print(f"Profiled {len(all_measurements)} nodes across {len(trug_files)} TRUGs")

    # Compute stats
    stats = compute_stats(all_measurements)
    oversized = find_oversized(all_measurements)

    # Determine verdict
    if stats.get("count", 0) == 0:
        verdict = "NO_DATA"
    elif stats["p99"] < TOAST_THRESHOLD:
        verdict = "GO"
    else:
        verdict = "NO_GO"

    # Build results
    results = {
        "toast_threshold_bytes": TOAST_THRESHOLD,
        "trugs_scanned": len(trug_files),
        "nodes_profiled": len(all_measurements),
        "statistics": stats,
        "verdict": verdict,
        "oversized_nodes": oversized,
    }

    # Save JSON
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Results saved to {output_path}")

    # Print human-readable summary
    print()
    print("=" * 60)
    print("JSONB Property Size Profile — Summary")
    print("=" * 60)
    print(f"  TRUGs scanned:   {len(trug_files)}")
    print(f"  Nodes profiled:  {len(all_measurements)}")
    print()
    if stats.get("count", 0) > 0:
        print("  Size Distribution (bytes):")
        print(f"    Min:    {stats['min']:>8,}")
        print(f"    Median: {stats['median']:>8,.1f}")
        print(f"    Mean:   {stats['mean']:>8,.1f}")
        print(f"    P90:    {stats['p90']:>8,}")
        print(f"    P95:    {stats['p95']:>8,}")
        print(f"    P99:    {stats['p99']:>8,}")
        print(f"    Max:    {stats['max']:>8,}")
        print()
        print(f"  TOAST threshold: {TOAST_THRESHOLD:,} bytes")
        print(f"  Nodes > threshold: {len(oversized)}")
        if oversized:
            print()
            print("  Oversized nodes:")
            for node in sorted(oversized, key=lambda x: -x["byte_size"]):
                print(f"    {node['byte_size']:>6,} bytes  {node['file']}  [{node['node_id']}]")
        print()
        print(f"  VERDICT: {verdict}")
        if verdict == "GO":
            print("  → P99 < 2KB. TOAST is a non-issue. Proceed with standard JSONB column.")
        else:
            print("  → P99 >= 2KB. Consider property normalization or EXTERNAL storage strategy.")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
