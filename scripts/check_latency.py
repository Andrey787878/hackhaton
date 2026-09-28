"""Measure sequential local API latency for a reproducible smoke check."""
import argparse
import math
from time import perf_counter
from urllib.request import urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="Обычный GET-маршрут API")
    parser.add_argument("--requests", type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.requests <= 10000:
        parser.error("--requests должен быть от 1 до 10000")
    samples = []
    for _ in range(args.requests):
        start = perf_counter()
        with urlopen(args.url, timeout=5) as response:
            if response.status != 200:
                raise RuntimeError(f"HTTP {response.status}")
            response.read()
        samples.append((perf_counter() - start) * 1000)
    samples.sort()
    p95 = samples[math.ceil(0.95 * len(samples)) - 1]
    print(f"n={len(samples)} p95={p95:.1f} ms max={samples[-1]:.1f} ms")


if __name__ == "__main__":
    main()
