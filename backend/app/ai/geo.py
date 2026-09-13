"""Pure geographic helpers (haversine distance, nearest-neighbor ordering).

No imports from the ai package — shared by the routing agent and the
optimize_route tool handler without import cycles.
"""

import math

AVG_SPEED_MPH = 55.0
MPG = 6.5
DIESEL_USD_PER_GAL = 3.80
COST_USD_PER_MILE = 1.75


def haversine_miles(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance in miles. Returns 0.0 when coords are missing."""
    if None in (lat1, lon1, lat2, lon2):
        return 0.0
    r = 3958.8  # earth radius in miles
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def trip_costs(miles: float) -> dict:
    miles = round(miles, 2)
    minutes = round(miles / AVG_SPEED_MPH * 60, 1)
    fuel_usd = round(miles / MPG * DIESEL_USD_PER_GAL, 2)
    cost_usd = round(miles * COST_USD_PER_MILE, 2)
    return {"miles": miles, "minutes": minutes,
            "fuel_usd": fuel_usd, "cost_usd": cost_usd}


def total_miles(points: list[dict], order: list[int] | None = None) -> float:
    order = order if order is not None else list(range(len(points)))
    miles = 0.0
    for a, b in zip(order, order[1:]):
        pa, pb = points[a], points[b]
        miles += haversine_miles(pa.get("lat"), pa.get("lng"),
                                 pb.get("lat"), pb.get("lng"))
    return miles


def nearest_neighbor_order(points: list[dict]) -> list[int]:
    """Visit order starting at point 0 (origin), then greedy nearest."""
    n = len(points)
    if n <= 2:
        return list(range(n))
    unvisited = set(range(1, n))
    order = [0]
    while unvisited:
        last = points[order[-1]]
        nxt = min(
            unvisited,
            key=lambda i: haversine_miles(
                last.get("lat"), last.get("lng"),
                points[i].get("lat"), points[i].get("lng"),
            ),
        )
        order.append(nxt)
        unvisited.remove(nxt)
    return order
