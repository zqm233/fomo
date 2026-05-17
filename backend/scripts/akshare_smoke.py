"""
AkShare 新浪美股日线冒烟测试（与线上 services.market 一致：仅 stock_us_daily）。

用法（在 backend/ 目录）:
    uv run python scripts/akshare_smoke.py
    uv run python scripts/akshare_smoke.py --hist AAPL
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.market import exception_log_detail, without_proxy_env  # noqa: E402


def _dns_ipv4_line(name: str) -> str | None:
    try:
        r = subprocess.run(
            ["dscacheutil", "-q", "host", "-a", "name", name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for ln in r.stdout.splitlines():
            if "ip_address:" in ln:
                return ln.split("ip_address:", 1)[1].strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _print_dns(name: str) -> str | None:
    ip = _dns_ipv4_line(name)
    if ip:
        print(f"  DNS {name}: ip_address: {ip}")
    else:
        print(f"  DNS {name}: (无结果)")
    return ip


def main() -> None:
    try:
        sys.stdout.reconfigure(line_buffering=True)  # noqa: SLF001
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="AkShare Sina US daily smoke test")
    parser.add_argument(
        "--hist",
        metavar="SYM",
        default="AAPL",
        help="ticker for stock_us_daily (default AAPL)",
    )
    args = parser.parse_args()
    sym = args.hist.strip().upper()

    print("── 环境快照 ──")
    _print_dns("finance.sina.com.cn")

    print(f"\n── stock_us_daily（新浪）{sym}──")
    try:
        import akshare as ak

        with without_proxy_env():
            df = ak.stock_us_daily(symbol=sym, adjust="qfq")
        if df is None or df.empty:
            print("  FAIL empty dataframe")
        else:
            print(f"  OK rows={len(df)} columns={list(df.columns)}")
            print(df.tail(3).to_string())
    except Exception as e:
        print("  FAIL", exception_log_detail(e))

    print("\n完成。")


if __name__ == "__main__":
    main()
