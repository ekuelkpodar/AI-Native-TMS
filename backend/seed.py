#!/usr/bin/env python3
"""Idempotent demo-data seeder for the AI-Native TMS backend.

Usage:
    python seed.py            # seed once; exits 0 with "already seeded" if the
                             # demo org exists
    python seed.py --reset    # drop all tables, recreate, then reseed
    python seed.py --force    # seed even if the demo org already exists
                             # (appends; use --reset for a clean re-seed)

Only stdlib + sqlalchemy + the app's own models/database/security are used.
Every timestamp is relative to "now" so delays, expiries and exceptions look
live whenever the seed runs. Data generation is deterministic (seeded RNG).

Run from the backend/ directory:
    cd backend && python seed.py
"""

import math
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from app import models  # noqa: E402  (register all models on Base)
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.security import hash_password  # noqa: E402

DEMO_SLUG = "demo"
DEMO_PASSWORD = "Demo1234!"

rng = random.Random(42)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Geography helpers
# ---------------------------------------------------------------------------

CITIES = {
    "Atlanta":      {"state": "GA", "zip": "30303", "lat": 33.7490, "lng": -84.3880},
    "Dallas":       {"state": "TX", "zip": "75201", "lat": 32.7767, "lng": -96.7970},
    "Chicago":      {"state": "IL", "zip": "60601", "lat": 41.8781, "lng": -87.6298},
    "Los Angeles":  {"state": "CA", "zip": "90013", "lat": 34.0522, "lng": -118.2437},
    "Phoenix":      {"state": "AZ", "zip": "85003", "lat": 33.4484, "lng": -112.0740},
    "Seattle":      {"state": "WA", "zip": "98101", "lat": 47.6062, "lng": -122.3321},
    "Denver":       {"state": "CO", "zip": "80202", "lat": 39.7392, "lng": -104.9903},
    "Miami":        {"state": "FL", "zip": "33128", "lat": 25.7617, "lng": -80.1918},
    "Houston":      {"state": "TX", "zip": "77002", "lat": 29.7604, "lng": -95.3698},
    "Memphis":      {"state": "TN", "zip": "38103", "lat": 35.1495, "lng": -90.0490},
    "Nashville":    {"state": "TN", "zip": "37203", "lat": 36.1627, "lng": -86.7816},
    "Kansas City":  {"state": "MO", "zip": "64106", "lat": 39.0997, "lng": -94.5786},
    "Columbus":     {"state": "OH", "zip": "43215", "lat": 39.9612, "lng": -82.9988},
    "Charlotte":    {"state": "NC", "zip": "28202", "lat": 35.2271, "lng": -80.8431},
    "Indianapolis": {"state": "IN", "zip": "46204", "lat": 39.7684, "lng": -86.1581},
    "Louisville":   {"state": "KY", "zip": "40202", "lat": 38.2527, "lng": -85.7585},
    "Omaha":        {"state": "NE", "zip": "68102", "lat": 41.2565, "lng": -95.9345},
    "Salt Lake City": {"state": "UT", "zip": "84101", "lat": 40.7608, "lng": -111.8910},
    "El Paso":      {"state": "TX", "zip": "79901", "lat": 31.7619, "lng": -106.4850},
    "Jacksonville": {"state": "FL", "zip": "32202", "lat": 30.3322, "lng": -81.6557},
}

LANES = [
    ("Atlanta", "Dallas"), ("Chicago", "Atlanta"), ("Los Angeles", "Phoenix"),
    ("Seattle", "Denver"), ("Miami", "Atlanta"), ("Houston", "Memphis"),
    ("Nashville", "Kansas City"), ("Columbus", "Charlotte"),
    ("Chicago", "Dallas"), ("Los Angeles", "Dallas"), ("Atlanta", "Charlotte"),
    ("Seattle", "Salt Lake City"), ("Omaha", "Kansas City"),
    ("Denver", "El Paso"), ("Indianapolis", "Louisville"),
    ("Atlanta", "Jacksonville"), ("Dallas", "El Paso"), ("Houston", "Atlanta"),
]


def haversine_miles(lat1, lng1, lat2, lng2) -> float:
    r = 3958.8  # earth radius in miles
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def lane_distance(origin_name: str, dest_name: str) -> float:
    o, d = CITIES[origin_name], CITIES[dest_name]
    return round(haversine_miles(o["lat"], o["lng"], d["lat"], d["lng"]) * 1.2, 1)


def city_point(name: str) -> dict:
    c = CITIES[name]
    return {"city": name, "state": c["state"], "zip": c["zip"],
            "lat": c["lat"], "lng": c["lng"]}


# ---------------------------------------------------------------------------
# Static reference data
# ---------------------------------------------------------------------------

CUSTOMER_DEFS = [
    ("Blue Ridge Foods Distributors", "Marcus Webb", "logistics@blueridgefoods.com",
     "(404) 555-0147", "1200 Peachtree Industrial Blvd", "Atlanta", "GA", "30341",
     250000.0, "Net 30"),
    ("Palmetto Paper & Packaging", "Dana Whitaker", "shipping@palmettopaper.com",
     "(704) 555-0182", "8800 Packaging Way", "Charlotte", "NC", "28273",
     175000.0, "Net 30"),
    ("Lone Star Beverage Co", "Rick Delgado", "transport@lonestarbev.com",
     "(214) 555-0119", "4500 Distribution Dr", "Dallas", "TX", "75236",
     300000.0, "Net 15"),
    ("Windy City Furniture Mart", "Priya Nair", "freight@windycityfurniture.com",
     "(312) 555-0163", "2200 W Fulton Market", "Chicago", "IL", "60612",
     150000.0, "Net 30"),
    ("Gulf Coast Plastics", "Tom Beaumont", "logistics@gulfcoastplastics.com",
     "(713) 555-0128", "7900 Resin Blvd", "Houston", "TX", "77041",
     200000.0, "Net 45"),
    ("Sunshine Produce Wholesale", "Maria Santos", "dispatch@sunshineproduce.com",
     "(305) 555-0175", "3300 NW 36th St", "Miami", "FL", "33142",
     125000.0, "Net 15"),
    ("Cascade Building Supply", "Greg Hollis", "freight@cascadebuilding.com",
     "(206) 555-0139", "14500 NE 95th St", "Seattle", "WA", "98052",
     180000.0, "Net 30"),
    ("Rocky Mountain Apparel", "Jen Kowalski", "supplychain@rmapparel.com",
     "(303) 555-0154", "5600 E 40th Cir", "Denver", "CO", "80216",
     140000.0, "Net 30"),
    ("Desert Sun Electronics", "Alan Reyes", "logistics@desertsunelec.com",
     "(602) 555-0122", "2323 W Dunlap Ave", "Phoenix", "AZ", "85021",
     225000.0, "Net 30"),
    ("Golden State Auto Parts", "Ken Watanabe", "shipping@gsautoparts.com",
     "(323) 555-0188", "6100 S Alameda St", "Los Angeles", "CA", "90001",
     190000.0, "Net 45"),
    ("Volunteer State Textiles", "Beth Carpenter", "traffic@vstextiles.com",
     "(615) 555-0144", "900 Textile Mill Rd", "Nashville", "TN", "37210",
     110000.0, "Net 30"),
    ("Heartland Grain & Feed", "Doug Pritchard", "dispatch@heartlandgrain.com",
     "(402) 555-0111", "4700 Grain Elevator Rd", "Omaha", "NE", "68127",
     160000.0, "Net 30"),
]

CARRIER_DEFS = [
    # (legal_name, dba, home city, equipment types, service area states)
    ("BlueLine Transport LLC", "BlueLine", "Atlanta", ["dry_van", "reefer"],
     ["GA", "TN", "NC", "SC", "FL", "AL"]),
    ("Southern Freightways Inc", None, "Charlotte", ["dry_van", "flatbed"],
     ["NC", "SC", "GA", "TN", "VA"]),
    ("Lone Star Logistics LLC", "Lone Star", "Dallas", ["dry_van"],
     ["TX", "OK", "LA", "AR", "NM"]),
    ("Windy City Haulers Inc", None, "Chicago", ["dry_van", "box_truck"],
     ["IL", "IN", "WI", "MI", "OH"]),
    ("Gulf Coast Carriers LLC", "GCC", "Houston", ["dry_van", "tanker"],
     ["TX", "LA", "MS", "AL"]),
    ("Sunshine State Transport", None, "Miami", ["dry_van", "reefer"],
     ["FL", "GA", "SC"]),
    ("Cascade Express LLC", None, "Seattle", ["dry_van", "reefer"],
     ["WA", "OR", "ID", "CA"]),
    ("Rocky Mountain Freight", None, "Denver", ["dry_van", "flatbed", "step_deck"],
     ["CO", "WY", "UT", "NM", "KS"]),
    ("Desert Ridge Trucking", None, "Phoenix", ["dry_van", "flatbed"],
     ["AZ", "CA", "NV", "NM", "TX"]),
    ("Golden State Carriers", None, "Los Angeles", ["dry_van", "reefer"],
     ["CA", "AZ", "NV", "OR"]),
    ("Volunteer Express Inc", None, "Nashville", ["dry_van"],
     ["TN", "KY", "AL", "GA", "MS"]),
    ("Heartland Haul LLC", None, "Omaha", ["dry_van", "flatbed"],
     ["NE", "IA", "KS", "MO", "SD"]),
    ("Iron Horse Freight LLC", None, "Kansas City", ["dry_van"],
     ["MO", "KS", "OK", "AR", "TN"]),
    ("Red River Logistics", None, "Dallas", ["flatbed", "step_deck"],
     ["TX", "OK", "AR", "LA"]),
    ("Bayou Line Transport", None, "Houston", ["dry_van", "reefer"],
     ["TX", "LA", "MS"]),
    ("Magnolia Freight Co", None, "Memphis", ["dry_van"],
     ["TN", "MS", "AR", "AL"]),
    ("Keystone Carrier Group", None, "Columbus", ["dry_van", "box_truck"],
     ["OH", "PA", "IN", "KY"]),
    ("Bluegrass Transport LLC", None, "Louisville", ["dry_van"],
     ["KY", "TN", "IN", "OH"]),
    ("Palmetto Line Inc", None, "Jacksonville", ["dry_van", "reefer"],
     ["FL", "GA", "SC", "NC"]),
    ("Evergreen Freight LLC", None, "Seattle", ["flatbed", "step_deck"],
     ["WA", "OR", "CA", "ID"]),
    ("Copper Canyon Carriers", None, "El Paso", ["dry_van", "flatbed"],
     ["TX", "NM", "AZ"]),
    ("Sierra Pacific Logistics", None, "Salt Lake City", ["dry_van", "reefer"],
     ["UT", "CO", "NV", "ID", "WY"]),
    ("Lake Effect Transport", None, "Chicago", ["dry_van"],
     ["IL", "WI", "MI", "IN"]),
    ("Prairie Wind Carriers", None, "Omaha", ["dry_van"],
     ["NE", "IA", "SD", "KS", "MO"]),
    ("Delta South Freight", None, "Memphis", ["dry_van", "reefer"],
     ["TN", "MS", "AR", "LA", "AL"]),
    ("Appalachian Haul Inc", None, "Charlotte", ["flatbed", "step_deck"],
     ["NC", "SC", "TN", "GA", "VA"]),
    ("Sunbelt Express LLC", None, "Atlanta", ["dry_van"],
     ["GA", "FL", "AL", "TN", "SC"]),
    ("Summit Point Logistics", None, "Denver", ["dry_van", "reefer"],
     ["CO", "UT", "WY", "NM"]),
]

FIRST_NAMES = ["James", "Maria", "Robert", "Lisa", "Michael", "Sarah", "David",
               "Jennifer", "Chris", "Angela", "Kevin", "Michelle", "Brian",
               "Stephanie", "Jason", "Nicole", "Anthony", "Rachel", "Steven",
               "Tanya", "Marcus", "Elena", "Derek", "Priya", "Tom", "Aisha",
               "Carlos", "Denise", "Victor", "Hannah", "Sam", "Olivia",
               "Jamal", "Karen", "Paul", "Rita", "Eddie", "Monica", "Ray",
               "Diane", "Frank", "Nadia", "George", "Tina", "Henry"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
              "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez",
              "Lopez", "Gonzalez", "Wilson", "Anderson", "Taylor", "Thomas",
              "Moore", "Jackson", "Martin", "Lee", "Walker", "Hall",
              "Young", "King", "Wright", "Scott", "Green", "Baker", "Adams",
              "Nelson", "Carter", "Mitchell", "Perez", "Roberts", "Turner"]

COMMODITIES = [
    ("dry_van", "Bottled water", 40000, 26, 1500),
    ("dry_van", "Paper products", 38500, 24, 1200),
    ("dry_van", "Furniture", 22000, 20, 900),
    ("dry_van", "Auto parts", 30000, 22, 1100),
    ("dry_van", "Canned goods", 42000, 26, 1600),
    ("dry_van", "Office supplies", 18000, 18, 800),
    ("dry_van", "Apparel", 15000, 22, 700),
    ("dry_van", "Electronics", 12000, 16, 600),
    ("dry_van", "Tires", 36000, 24, 950),
    ("dry_van", "Cereal products", 30000, 26, 1300),
    ("dry_van", "Cleaning supplies", 26000, 24, 1000),
    ("dry_van", "Plastic resin", 44000, 26, 1700),
    ("reefer", "Frozen chicken", 40000, 26, 1450),
    ("reefer", "Fresh produce", 38000, 26, 1400),
    ("reefer", "Dairy products", 36000, 24, 1200),
    ("reefer", "Pharmaceuticals", 14000, 18, 650),
    ("flatbed", "Building materials", 42000, 0, 1100),
    ("flatbed", "Steel coils", 44000, 0, 900),
    ("flatbed", "HVAC equipment", 24000, 0, 700),
    ("step_deck", "Machinery", 38000, 0, 850),
    ("box_truck", "Parcel freight", 9000, 10, 400),
]

PER_MILE = {
    "dry_van": (2.05, 2.80), "reefer": (2.35, 3.15), "flatbed": (2.25, 3.05),
    "step_deck": (2.40, 3.20), "box_truck": (1.60, 2.20),
}

USER_DEFS = [
    ("admin@demo.tms", "Ava Mitchell", "admin", None, None, None),
    ("broker@demo.tms", "Brian Torres", "broker", None, None, None),
    ("dispatcher@demo.tms", "Dana Whitfield", "dispatcher", None, None, None),
    ("carrier@demo.tms", "Carlos Vega", "carrier", "carrier", None, None),
    ("driver@demo.tms", "Derek Nolan", "driver", None, "driver", None),
    ("shipper@demo.tms", "Sara Hensley", "shipper", None, None, "customer"),
    ("finance@demo.tms", "Fiona Clarke", "finance", None, None, None),
    ("ops@demo.tms", "Omar Reyes", "ops_manager", None, None, None),
]

AI_AGENT_DEFS = [
    ("Dispatch Agent", 2, "medium",
     ["match_carriers", "assign_load", "send_communication"],
     ["loads:write", "dispatch:write", "communications:write"]),
    ("Routing Agent", 2, "low",
     ["optimize_route", "geocode", "lane_stats"],
     ["loads:read", "lanes:read"]),
    ("Carrier Agent", 2, "medium",
     ["score_carrier", "tender_load", "send_communication"],
     ["carriers:read", "loads:write", "communications:write"]),
    ("Customer Service Agent", 1, "low",
     ["load_status_lookup", "send_communication"],
     ["loads:read", "communications:write"]),
    ("Exception Agent", 2, "medium",
     ["detect_exceptions", "create_exception", "notify_ops"],
     ["exceptions:*", "notifications:write"]),
    ("Pricing Agent", 1, "medium",
     ["quote_rate", "lane_stats"],
     ["rates:read", "lanes:read"]),
    ("Finance Agent", 1, "medium",
     ["draft_invoice", "validate_pod", "payment_lookup"],
     ["invoices:write", "documents:read"]),
    ("Compliance Agent", 2, "high",
     ["check_insurance", "check_authority", "block_carrier"],
     ["carriers:read", "carriers:write"]),
    ("Operations Analyst Agent", 1, "low",
     ["analytics_read", "forecast"],
     ["analytics:read"]),
]

INTEGRATION_PROVIDERS = [
    "maps", "eld_samsara", "eld_motive", "project44", "fourkites", "dat",
    "truckstop", "quickbooks", "stripe", "twilio", "sendgrid", "openai",
    "anthropic",
]


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def seed_org(db):
    return models.Organization(
        name="Demo Logistics Co",
        slug=DEMO_SLUG,
        plan="professional",
        settings={"currency": "USD", "timezone": "America/Chicago",
                  "default_payment_terms": "Net 30"},
    )


def seed_customers(db, org_id):
    customers = []
    for (name, contact, email, phone, street, city, state, zipc,
         credit_limit, terms) in CUSTOMER_DEFS:
        customers.append(models.Customer(
            org_id=org_id, name=name, contact_name=contact, email=email,
            phone=phone, street=street, city=city, state=state, zip=zipc,
            country="USA", credit_limit=credit_limit, payment_terms=terms,
            notes=f"Seeded demo account for {name}."))
    db.add_all(customers)
    db.flush()
    return customers


def seed_carriers(db, org_id):
    carriers = []
    mc = rng.sample(range(100000, 999999), len(CARRIER_DEFS))
    for i, (legal, dba, home_city, equipment, areas) in enumerate(CARRIER_DEFS):
        c = CITIES[home_city]
        # Two carriers are expired (insurance lapsed), three are warnings.
        if i in (12, 25):  # Iron Horse, Delta South
            compliance, ins = "expired", utcnow().date() - timedelta(days=rng.randint(10, 120))
            authority, safety = "inactive", "conditional"
            score = round(rng.uniform(62, 74), 1)
        elif i in (4, 17, 22):  # Gulf Coast, Bluegrass, Lake Effect
            compliance, ins = "warning", utcnow().date() + timedelta(days=rng.randint(5, 45))
            authority, safety = "active", "satisfactory"
            score = round(rng.uniform(78, 86), 1)
        else:
            compliance, ins = "compliant", utcnow().date() + timedelta(days=rng.randint(90, 400))
            authority, safety = "active", rng.choice(["satisfactory"] * 8 + ["excellent"])
            score = round(rng.uniform(82, 98), 1)
        on_time = round(rng.uniform(78, 99.5), 1)
        accept = round(rng.uniform(70, 99), 1)
        carriers.append(models.Carrier(
            org_id=org_id, legal_name=legal, dba=dba,
            mc_number=f"MC-{mc[i]}", dot_number=str(rng.randint(1000000, 3999999)),
            street=f"{rng.randint(100, 9900)} {rng.choice(['Industrial', 'Freight', 'Logistics', 'Depot'])} {rng.choice(['Pkwy', 'Blvd', 'Dr', 'Ave'])}",
            city=home_city, state=c["state"], zip=c["zip"],
            phone=f"({rng.randint(200, 989)}) 555-{rng.randint(1000, 9999):04d}",
            email=f"dispatch@{legal.lower().replace(' ', '').replace(',', '')[:18]}.com",
            equipment_types=equipment, service_areas=areas,
            lanes=[{"origin": f"{a}, {CITIES[a]['state']}",
                    "dest": f"{b}, {CITIES[b]['state']}"}
                   for a, b in rng.sample(LANES, k=min(6, len(LANES)))],
            insurance_expiry=ins, authority_status=authority,
            compliance_status=compliance, safety_rating=safety,
            performance_score=score, on_time_pct=on_time,
            acceptance_rate=accept,
            claims_count=rng.randint(0, 6) if score < 90 else rng.randint(0, 2),
            cancellations_count=rng.randint(0, 8) if score < 85 else rng.randint(0, 2),
            total_revenue=round(rng.uniform(120000, 2800000), 2),
            notes=f"{legal} — seeded demo carrier. {'DO NOT DISPATCH: insurance expired.' if compliance == 'expired' else ''}"))
    db.add_all(carriers)
    db.flush()
    return carriers


def seed_drivers(db, org_id, carriers):
    drivers = []
    used_names = set()
    statuses = (["available"] * 14 + ["in_transit"] * 8 + ["assigned"] * 6
                + ["en_route"] * 4 + ["off_duty"] * 5 + ["at_pickup"] * 2
                + ["at_delivery"] * 2 + ["unavailable"] * 4)
    city_names = list(CITIES)
    for i in range(45):
        name = f"{FIRST_NAMES[i % len(FIRST_NAMES)]} {LAST_NAMES[(i * 7) % len(LAST_NAMES)]}"
        while name in used_names:  # keep names unique
            name += " Jr."
        used_names.add(name)
        city = rng.choice(city_names)
        carrier = carriers[i % len(carriers)]
        email_local = (name.lower().split()[0][0] + name.lower().split()[-1]).replace(" ", "")
        drivers.append(models.Driver(
            org_id=org_id, carrier_id=carrier.id, full_name=name,
            phone=f"({rng.randint(200, 989)}) 555-{rng.randint(1000, 9999):04d}",
            email=f"{email_local}@example.com",
            license_number=f"{CITIES[city]['state']}-{rng.randint(1000000, 9999999)}",
            license_expiry=utcnow().date() + timedelta(days=rng.randint(200, 1500)),
            status=statuses[i % len(statuses)],
            current_location={"lat": round(CITIES[city]["lat"] + rng.uniform(-0.3, 0.3), 4),
                              "lng": round(CITIES[city]["lng"] + rng.uniform(-0.3, 0.3), 4),
                              "city": city, "state": CITIES[city]["state"]},
            hours_available=round(rng.uniform(0, 70), 1),
            performance_score=round(rng.uniform(70, 99), 1)))
    db.add_all(drivers)
    db.flush()
    return drivers


def seed_vehicles(db, org_id):
    vehicles = []
    truck_specs = [("Freightliner", "Cascadia"), ("Peterbilt", "579"),
                   ("Kenworth", "T680"), ("Volvo", "VNL 760"),
                   ("International", "LT625")]
    trailer_specs = [("Utility", "4000D-X"), ("Wabash", "DuraPlate"),
                     ("Great Dane", "Champion")]
    city_names = list(CITIES)
    for i in range(35):
        if i < 22:
            vtype, prefix = "truck", "T"
            make, model = truck_specs[i % len(truck_specs)]
            capacity = 45000.0
        elif i < 32:
            vtype, prefix = "trailer", "TR"
            make, model = trailer_specs[(i - 22) % len(trailer_specs)]
            capacity = 45000.0
        else:
            vtype, prefix = "van", "V"
            make, model = "Ford", "Transit"
            capacity = 9000.0
        city = rng.choice(city_names)
        avail = rng.choices(["available", "assigned", "maintenance", "out_of_service"],
                            weights=[55, 30, 10, 5])[0]
        vehicles.append(models.Vehicle(
            org_id=org_id,
            vin="".join(rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ0123456789") for _ in range(17)),
            unit_number=f"{prefix}-{101 + i}",
            license_plate=f"{rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}{rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}{rng.randint(1000, 9999)}",
            make=make, model=model, year=rng.randint(2018, 2025),
            vehicle_type=vtype, capacity_lbs=capacity,
            mileage=round(rng.uniform(45000, 620000), 1),
            current_location={"lat": round(CITIES[city]["lat"] + rng.uniform(-0.4, 0.4), 4),
                              "lng": round(CITIES[city]["lng"] + rng.uniform(-0.4, 0.4), 4),
                              "city": city, "state": CITIES[city]["state"]},
            availability_status=avail,
            maintenance_status=rng.choice(["good"] * 7 + ["due_soon", "overdue"]),
            insurance_expiry=utcnow().date() + timedelta(days=rng.randint(60, 400))))
    db.add_all(vehicles)
    db.flush()
    return vehicles

def seed_loads(db, org_id, customers, carriers, drivers, vehicles):
    """120 loads across the lane network with a realistic status mix."""
    plan = ([("available", 25), ("assigned", 8), ("dispatched", 7),
             ("in_transit", 20), ("delivered", 22), ("pod_received", 18),
             ("invoiced", 6), ("paid", 4), ("quoted", 3), ("tendered", 3),
             ("cancelled", 4)])
    compliant = [c for c in carriers if c.compliance_status == "compliant"]
    trucks = [v for v in vehicles if v.vehicle_type == "truck"]
    now = utcnow()
    loads = []
    delayed_loads = []
    idx = 0
    for status, count in plan:
        for _ in range(count):
            idx += 1
            lane = rng.choice(LANES)
            if rng.random() < 0.35:
                lane = (lane[1], lane[0])
            origin_name, dest_name = lane
            origin, dest = city_point(origin_name), city_point(dest_name)
            distance = lane_distance(origin_name, dest_name)
            equip, commodity, weight, pallets, pieces = rng.choice(COMMODITIES)
            lo, hi = PER_MILE[equip]
            customer_rate = round(distance * rng.uniform(lo, hi) + rng.uniform(0, 150), 2)
            # one deliberately thin-margin load for the margin-anomaly demo
            margin_target = 0.06 if idx == 7 else rng.uniform(0.10, 0.24)
            carrier_rate = round(customer_rate * (1 - margin_target), 2)

            # -- timeline by status -------------------------------------
            if status == "available":
                pickup = now + timedelta(days=rng.randint(1, 5), hours=rng.randint(0, 12))
                delivery = pickup + timedelta(days=rng.randint(1, 4))
                created = now - timedelta(days=rng.randint(0, 6))
                carrier = driver = vehicle = None
            elif status in ("assigned", "dispatched"):
                pickup = now + timedelta(days=rng.randint(-1, 2), hours=rng.randint(0, 12))
                delivery = pickup + timedelta(days=rng.randint(1, 4))
                created = now - timedelta(days=rng.randint(1, 10))
                carrier, driver, vehicle = _pick_capacity(compliant, drivers, trucks)
            elif status == "in_transit":
                transit_days = rng.randint(1, 5)
                pickup = now - timedelta(days=transit_days)
                delayed = len(delayed_loads) < 5 and rng.random() < 0.35
                if delayed:
                    delivery = now - timedelta(hours=rng.randint(2, 30))  # at-risk
                    delayed_loads.append(idx)
                else:
                    delivery = now + timedelta(days=rng.randint(0, 3))
                created = pickup - timedelta(days=rng.randint(1, 8))
                carrier, driver, vehicle = _pick_capacity(compliant, drivers, trucks)
            elif status in ("delivered", "pod_received", "invoiced", "paid"):
                transit_days = rng.randint(2, 6)
                delivery = now - timedelta(days=rng.randint(1, 25))
                pickup = delivery - timedelta(days=transit_days)
                created = pickup - timedelta(days=rng.randint(1, 9))
                carrier, driver, vehicle = _pick_capacity(compliant, drivers, trucks)
            elif status in ("quoted", "tendered"):
                pickup = now + timedelta(days=rng.randint(2, 9))
                delivery = pickup + timedelta(days=rng.randint(1, 4))
                created = now - timedelta(days=rng.randint(0, 4))
                carrier = driver = vehicle = None
            else:  # cancelled
                pickup = now - timedelta(days=rng.randint(1, 20))
                delivery = pickup + timedelta(days=rng.randint(1, 4))
                created = pickup - timedelta(days=rng.randint(1, 6))
                carrier = driver = vehicle = None

            load = models.Load(
                org_id=org_id,
                load_number=f"LD-{10000 + idx}",
                reference_number=f"CUST-{rng.randint(100000, 999999)}",
                customer_id=rng.choice(customers).id,
                carrier_id=carrier.id if carrier else None,
                driver_id=driver.id if driver else None,
                vehicle_id=vehicle.id if vehicle else None,
                origin=origin, destination=dest,
                pickup_datetime=pickup, delivery_datetime=delivery,
                equipment_type=equip, commodity=commodity,
                weight_lbs=float(weight), pallets=pallets, pieces=pieces,
                customer_rate=customer_rate, carrier_rate=carrier_rate,
                distance_miles=distance,
                hazmat=(commodity == "Cleaning supplies"),
                temp_min=-10.0 if equip == "reefer" else None,
                temp_max=34.0 if equip == "reefer" else None,
                status=status,
                notes=(f"Cancelled by shipper — duplicate of LD-{10000 + idx - 3}."
                       if status == "cancelled" else None),
                created_at=created, updated_at=created)
            loads.append(load)
            # driver status follows the newest load assigned to them
            if driver and status in ("in_transit", "dispatched", "assigned"):
                driver.status = {"in_transit": "in_transit",
                                 "dispatched": "en_route",
                                 "assigned": "assigned"}[status]
                driver.current_location = {
                    "lat": round(origin["lat"] + rng.uniform(-0.5, 0.5), 4),
                    "lng": round(origin["lng"] + rng.uniform(-0.5, 0.5), 4),
                    "city": origin_name, "state": origin["state"]}
            if vehicle and status in ("in_transit", "dispatched", "assigned"):
                vehicle.availability_status = "assigned"
    db.add_all(loads)
    db.flush()
    delayed = [l for l in loads if l.load_number in
               {f"LD-{10000 + i}" for i in delayed_loads}]
    return loads, delayed


def _pick_capacity(compliant, drivers, trucks):
    """Pick a carrier + one of its drivers + an available truck."""
    carrier = rng.choice(compliant)
    cand = [d for d in drivers if d.carrier_id == carrier.id]
    driver = rng.choice(cand) if cand else rng.choice(drivers)
    truck = rng.choice(trucks) if trucks else None
    return carrier, driver, truck


def seed_stops(db, loads):
    """8 multi-stop loads: 4 with 3 stops, 4 with 4 stops."""
    chosen = rng.sample([l for l in loads if l.status in
                         ("in_transit", "dispatched", "delivered")], 8)
    stops = []
    for j, load in enumerate(chosen):
        origin, dest = load.origin, load.destination
        mid_names = rng.sample([n for n in CITIES if n not in
                                (origin["city"], dest["city"])],
                               2 if j < 4 else 3)
        if j < 4:  # pickup -> delivery -> delivery
            defs = [("pickup", origin, 0), ("delivery", city_point(mid_names[0]), 1),
                    ("delivery", dest, 2)]
        else:  # pickup -> pickup -> delivery -> delivery
            defs = [("pickup", origin, 0), ("pickup", city_point(mid_names[0]), 1),
                    ("delivery", city_point(mid_names[1]), 2),
                    ("delivery", city_point(mid_names[2]), 3)]
        for stop_type, loc, seq in defs:
            base = load.pickup_datetime if stop_type == "pickup" else load.delivery_datetime
            appt = (base + timedelta(hours=seq * 20)) if base else None
            status = ("completed" if load.status in ("delivered", "pod_received",
                                                     "invoiced", "paid")
                      else ("pending" if seq > 1 else "arrived"))
            stops.append(models.Stop(
                load_id=load.id, sequence=seq, stop_type=stop_type,
                location={**loc, "address":
                          f"{rng.randint(100, 9900)} Freight Way, {loc['city']}, {loc['state']} {loc['zip']}"},
                appointment_start=appt,
                appointment_end=(appt + timedelta(hours=2)) if appt else None,
                status=status,
                notes="Multi-stop leg — seeded demo data."))
    db.add_all(stops)
    db.flush()
    return stops


def seed_tracking(db, org_id, loads):
    """5-8 GPS pings per in-transit load along its lane, plus history pings."""
    now = utcnow()
    events = []
    transit = [l for l in loads if l.status == "in_transit"]
    history = rng.sample([l for l in loads if l.status in
                          ("delivered", "pod_received", "invoiced", "paid")], 10)
    for load in transit + history:
        o, d = load.origin, load.destination
        n = rng.randint(5, 8) if load.status == "in_transit" else rng.randint(3, 4)
        start = load.pickup_datetime or (now - timedelta(days=3))
        for k in range(n):
            frac = (k + 1) / (n + 1)
            jitter = lambda: rng.uniform(-0.35, 0.35)
            recorded = start + timedelta(hours=k * rng.uniform(4, 9))
            if recorded > now:
                recorded = now - timedelta(minutes=rng.randint(5, 60))
            events.append(models.TrackingEvent(
                org_id=org_id, load_id=load.id, event_type="position",
                lat=round(o["lat"] + (d["lat"] - o["lat"]) * frac + jitter(), 4),
                lng=round(o["lng"] + (d["lng"] - o["lng"]) * frac + jitter(), 4),
                city=None, speed_mph=round(rng.uniform(52, 70), 1),
                recorded_at=recorded,
                meta={"source": "eld_samsara_mock", "heading": rng.randint(0, 359)}))
    db.add_all(events)
    db.flush()
    return events

def seed_exceptions(db, org_id, loads, delayed_loads, users):
    """23 exceptions across the taxonomy; 8 already resolved with history."""
    now = utcnow()
    ops = next(u for u in users if u.role == "ops_manager")
    dispatcher = next(u for u in users if u.role == "dispatcher")
    made = []

    def add(load, etype, severity, title, desc, action, detected,
            status="open", resolution=None, resolved=None, owner=None):
        exc = models.Exception(
            org_id=org_id, load_id=load.id if load else None,
            exception_type=etype, severity=severity, title=title,
            description=desc, detected_at=detected,
            recommended_action=action,
            owner_user_id=(owner or dispatcher).id,
            status=status, resolution=resolution, resolved_at=resolved,
            history=[
                {"ts": detected.isoformat(), "by": "Exception Agent",
                 "note": f"Detected via telemetry: {etype}."},
                ({"ts": (resolved or now).isoformat(),
                  "by": owner.full_name if owner else dispatcher.full_name,
                  "note": f"Status -> {status}: {resolution or 'acknowledged.'}"}
                 if status != "open" else None),
            ])
        exc.history = [h for h in exc.history if h]
        made.append(exc)

    # late deliveries on the at-risk in-transit loads
    for i, load in enumerate(delayed_loads):
        overdue_h = int((now - load.delivery_datetime).total_seconds() // 3600)
        add(load, "late_delivery", "critical" if i < 2 else "high",
            f"Load {load.load_number} is {overdue_h}h past delivery appointment",
            f"Appointment was {load.delivery_datetime:%b %d %H:%M}; load still shows "
            f"in-transit on lane {load.origin['city']} -> {load.destination['city']}.",
            "Contact driver for updated ETA; reassign if ETA slips beyond customer tolerance.",
            load.delivery_datetime + timedelta(hours=1))

    # late pickups
    for load in rng.sample([l for l in loads if l.status in ("dispatched", "assigned")], 3):
        add(load, "late_pickup", "medium",
            f"Late pickup on load {load.load_number}",
            f"Driver had not arrived at {load.origin['city']} pickup 45 minutes after "
            f"the {load.pickup_datetime:%H:%M} appointment.",
            "Confirm driver status; tender to backup carrier if unresponsive.",
            now - timedelta(hours=rng.randint(2, 10)))

    # POD missing on older delivered loads
    for load in rng.sample([l for l in loads if l.status == "delivered"
                           and (now - l.delivery_datetime).days >= 2], 4):
        add(load, "pod_missing", "medium",
            f"POD not received for {load.load_number}",
            f"Delivered {(now - load.delivery_datetime).days} days ago; no proof of "
            "delivery on file — invoicing is blocked.",
            "Request signed POD from driver/carrier; escalate after 72h.",
            now - timedelta(days=rng.randint(1, 4)))

    # margin anomalies (includes the deliberately thin-margin load LD-10007)
    thin = next(l for l in loads if l.load_number == "LD-10007")
    add(thin, "margin_anomaly", "high",
        f"Margin on {thin.load_number} is {thin.margin_pct:.1f}% — below 10% floor",
        f"Customer rate ${thin.customer_rate:,.2f} vs carrier rate "
        f"${thin.carrier_rate:,.2f} on {thin.origin['city']} -> {thin.destination['city']}.",
        "Re-rate with carrier or renegotiate accessorials before dispatch.",
        now - timedelta(hours=5))
    for load in rng.sample([l for l in loads if l.status in ("assigned", "dispatched")
                           and l.id != thin.id], 2):
        add(load, "margin_anomaly", "medium",
            f"Thin margin ({load.margin_pct:.1f}%) on {load.load_number}",
            "Spot rate moved against the quoted customer rate after tender.",
            "Review lane pricing; adjust carrier pay or add fuel surcharge.",
            now - timedelta(hours=rng.randint(3, 20)))

    # document / misc
    for load in rng.sample([l for l in loads if l.status == "in_transit"], 3):
        add(load, "document_missing", rng.choice(["low", "medium"]),
            f"Missing paperwork on {load.load_number}",
            "BOL image uploaded but unreadable; rate confirmation not yet signed by carrier.",
            "Re-request documents from carrier before delivery.",
            now - timedelta(hours=rng.randint(4, 30)))
    # carrier issues on open lanes
    for load in rng.sample([l for l in loads if l.status in ("available", "tendered")], 2):
        add(load, "carrier_cancellation", "high",
            f"Carrier cancelled tender for {load.load_number}",
            "Carrier reported equipment breakdown and returned the tender 6 hours "
            "before pickup.",
            "Re-tender to next-best carriers from AI match list immediately.",
            now - timedelta(hours=rng.randint(1, 12)))

    # route deviation + missed appointment
    dev_load = rng.choice([l for l in loads if l.status == "in_transit"
                           and l.delivery_datetime >= now])
    add(dev_load, "route_deviation", "medium",
        f"Route deviation on {dev_load.load_number}",
        "ELD pings show the truck 28 miles off the planned corridor near a "
        "weigh-station bypass route.",
        "Verify with driver; flag carrier if unexplained.",
        now - timedelta(hours=rng.randint(2, 8)))
    miss_load = rng.choice([l for l in loads if l.status in ("dispatched", "at_pickup")
                            ]) if any(l.status in ("dispatched",) for l in loads) else None
    if miss_load is None:
        miss_load = rng.choice([l for l in loads if l.status == "dispatched"])
    add(miss_load, "missed_appointment", "high",
        f"Missed pickup appointment — {miss_load.load_number}",
        f"Driver missed the {miss_load.pickup_datetime:%H:%M} pickup window at "
        f"{miss_load.origin['city']}; receiver rescheduled to tomorrow.",
        "Recover with team driver or re-tender; update customer ETA.",
        now - timedelta(hours=rng.randint(1, 6)))

    # resolve 8 of them with realistic history
    for exc in rng.sample(made, 8):
        resolved_at = now - timedelta(hours=rng.randint(1, 48))
        exc.status = "resolved"
        exc.resolved_at = resolved_at
        exc.resolution = rng.choice([
            "Driver provided updated ETA; customer accepted revised appointment.",
            "POD received from driver and attached to load documents.",
            "Carrier re-rated; margin restored to 14.2%.",
            "Re-tendered to backup carrier at equal cost.",
            "Documents re-uploaded and verified."])
        exc.history.append({"ts": resolved_at.isoformat(), "by": ops.full_name,
                            "note": f"Resolved: {exc.resolution}"})
    # acknowledge 3 more
    for exc in rng.sample([e for e in made if e.status == "open"], 3):
        exc.status = "acknowledged"
        exc.history.append({"ts": now.isoformat(), "by": dispatcher.full_name,
                            "note": "Acknowledged — working with carrier on recovery plan."})

    db.add_all(made)
    db.flush()
    return made


def seed_invoices(db, org_id, loads):
    """40 invoices linked to delivered/pod_received/invoiced/paid loads."""
    now = utcnow()
    invoices, payments = [], []
    targets = ([l for l in loads if l.status == "invoiced"]
               + [l for l in loads if l.status == "paid"]
               + rng.sample([l for l in loads if l.status == "pod_received"], 18)
               + rng.sample([l for l in loads if l.status == "delivered"], 16))
    for i, load in enumerate(targets[:40]):
        subtotal = load.customer_rate
        if load.status == "invoiced":
            status, issued = "issued", now - timedelta(days=rng.randint(1, 10))
        elif load.status == "paid":
            status, issued = "paid", now - timedelta(days=rng.randint(20, 45))
        else:
            status = rng.choice(["issued", "overdue", "draft", "paid"])
            issued = now - timedelta(days=rng.randint(1, 50))
            if status == "overdue":
                issued = now - timedelta(days=rng.randint(35, 70))
        due = issued.date() + timedelta(days=30)
        total = round(subtotal, 2)
        inv = models.Invoice(
            org_id=org_id, invoice_number=f"INV-{5001 + i}",
            customer_id=load.customer_id, load_id=load.id,
            issue_date=issued.date(), due_date=due,
            line_items=[
                {"description": f"Linehaul — {load.origin['city']}, {load.origin['state']} "
                                f"to {load.destination['city']}, {load.destination['state']} "
                                f"({load.load_number}, {load.equipment_type})",
                 "quantity": 1, "rate": round(subtotal, 2), "amount": round(subtotal, 2)},
                {"description": "Fuel surcharge", "quantity": 1,
                 "rate": 0.0, "amount": 0.0}],
            subtotal=round(subtotal, 2), tax=0.0, total=total,
            amount_paid=(total if status == "paid" else 0.0),
            status=status,
            notes="Seeded demo invoice.",
            created_at=issued, updated_at=issued)
        invoices.append(inv)
        if status == "paid":
            payments.append((inv, total, issued))
    db.add_all(invoices)
    db.flush()
    # invoice ids are only populated after the flush above
    db.add_all([models.Payment(
        org_id=org_id, invoice_id=inv.id, amount=total,
        method=rng.choice(["ACH", "wire", "check"]),
        reference=f"PAY-{9000 + i}",
        paid_at=issued + timedelta(days=rng.randint(5, 28)))
        for i, (inv, total, issued) in enumerate(payments)])
    db.flush()
    return invoices


def _write_seed_file(seed_dir: Path, filename: str, content: str) -> Path:
    path = seed_dir / filename
    path.write_text(content)
    return path


def seed_documents(db, org_id, loads, carriers, users):
    """Realistic text BOL / POD / rate-confirmation files under storage/seed/."""
    seed_dir = BACKEND_DIR / "storage" / "seed"
    seed_dir.mkdir(parents=True, exist_ok=True)
    uploader = next(u for u in users if u.role == "dispatcher")
    docs = []

    def add_doc(entity_type, entity_id, doc_type, filename, content, meta):
        path = _write_seed_file(seed_dir, filename, content)
        docs.append(models.Document(
            org_id=org_id, entity_type=entity_type, entity_id=entity_id,
            doc_type=doc_type, filename=filename, content_type="text/plain",
            size_bytes=path.stat().st_size,
            storage_path=str(Path("storage") / "seed" / filename),
            doc_metadata=meta, version=1, uploaded_by=uploader.id))

    delivered = [l for l in loads if l.status in ("delivered", "pod_received",
                                                 "invoiced", "paid")]
    for i, load in enumerate(delivered[:5]):
        carr = next((c for c in carriers if c.id == load.carrier_id), None)
        carrier_name = carr.legal_name if carr else "Unknown Carrier"
        add_doc("load", load.id, "bol", f"BOL-{load.load_number}.txt", f"""\
STRAIGHT BILL OF LADING — Demo Logistics Co (broker)
Load No:        {load.load_number}
Date:           {load.pickup_datetime:%Y-%m-%d}
Shipper:        {load.origin['city']}, {load.origin['state']} {load.origin['zip']}
Consignee:      {load.destination['city']}, {load.destination['state']} {load.destination['zip']}
Carrier:        {carrier_name}
Equipment:      {load.equipment_type}   Seal No: {100000 + i}
Pieces:         {load.pallets} pallets / {load.pieces} pcs
Weight:         {load.weight_lbs:,.0f} lbs
Commodity:      {load.commodity}
Freight terms:  Prepaid — collect from broker per rate confirmation.
Shipper certifies the goods are properly described, packaged and marked.
""", {"load_number": load.load_number, "seal": str(100000 + i)})

    for i, load in enumerate(delivered[5:9]):
        add_doc("load", load.id, "pod", f"POD-{load.load_number}.txt", f"""\
PROOF OF DELIVERY — Demo Logistics Co
Load No:        {load.load_number}
Delivered:      {load.delivery_datetime:%Y-%m-%d %H:%M}
Location:       {load.destination['city']}, {load.destination['state']} {load.destination['zip']}
Pieces:         {load.pallets} pallets — received in apparent good condition
Received by:    {rng.choice(['J. Ortiz', 'M. Chen', 'R. Patel', 'S. Brooks'])} (dock {rng.randint(1, 24)})
Signature:      /s/ on file — ELD geofence confirmed at delivery
Notes:          No exceptions reported at delivery.
""", {"load_number": load.load_number, "received_by": "dock staff"})

    active = [l for l in loads if l.status in ("available", "assigned", "tendered")]
    for load in active[:4]:
        carr = next((c for c in carriers if c.id == load.carrier_id), None)
        carrier_name = carr.legal_name if carr else "TBD — tender pending"
        fsc = round(load.carrier_rate * 0.12, 2)
        add_doc("load", load.id, "rate_confirmation",
                f"RATECON-{load.load_number}.txt", f"""\
RATE CONFIRMATION — Demo Logistics Co
Date:           {utcnow():%Y-%m-%d}
Carrier:        {carrier_name}
Load No:        {load.load_number}
Lane:           {load.origin['city']}, {load.origin['state']} -> {load.destination['city']}, {load.destination['state']} ({load.distance_miles:,.0f} mi)
Pickup:         {load.pickup_datetime:%Y-%m-%d %H:%M}     Delivery: {load.delivery_datetime:%Y-%m-%d %H:%M}
Equipment:      {load.equipment_type}   Commodity: {load.commodity}
Weight:         {load.weight_lbs:,.0f} lbs / {load.pallets} pallets
Linehaul:       ${load.carrier_rate - fsc:,.2f}
Fuel surcharge: ${fsc:,.2f}
Total carrier pay: ${load.carrier_rate:,.2f}
Terms: detention $75/hr after 2h; TONU $250; carrier must check in via ELD.
""", {"load_number": load.load_number, "total_carrier_pay": load.carrier_rate})

    for carrier in carriers[:2]:
        add_doc("carrier", carrier.id, "insurance",
                f"COI-{carrier.mc_number.replace('-', '')}.txt", f"""\
CERTIFICATE OF LIABILITY INSURANCE (summary)
Insured:        {carrier.legal_name}
MC:             {carrier.mc_number}   DOT: {carrier.dot_number}
Auto liability: $1,000,000 per occurrence
Cargo:          $100,000 per occurrence
General liab.:  $1,000,000
Policy period:  {utcnow().date() - timedelta(days=200)} to {carrier.insurance_expiry}
Certificate holder: Demo Logistics Co, Atlanta GA
""", {"mc_number": carrier.mc_number,
      "expiry": str(carrier.insurance_expiry)})
    db.add_all(docs)
    db.flush()
    return docs


def seed_communications(db, org_id, loads, customers, carriers, users):
    """A few realistic threads: load ops, customer quoting, carrier tender."""
    now = utcnow()
    dispatcher = next(u for u in users if u.role == "dispatcher")
    broker = next(u for u in users if u.role == "broker")
    msgs = []

    delayed = next(l for l in loads if l.status == "in_transit"
                   and l.delivery_datetime < now)
    msgs += [
        ("load", delayed.id, "sms", "out", "Dana Whitfield (dispatch)",
         f"Driver of {delayed.load_number}",
         None, f"Hi — checking status on {delayed.load_number}. Appointment in "
               f"{delayed.destination['city']} was {delayed.delivery_datetime:%H:%M} "
               "and we are showing you 40 mi out. Please confirm ETA.",
         now - timedelta(hours=3)),
        ("load", delayed.id, "sms", "in", "Driver", "Dispatch",
         None, "Stuck at receiver, dock backed up. Rolling in 30. New ETA 1 hr.",
         now - timedelta(hours=2, minutes=40)),
        ("load", delayed.id, "in_app", "out", "Dana Whitfield (dispatch)", "Ops",
         "ETA update", f"Driver for {delayed.load_number} reports receiver dock "
                       "congestion; revised ETA ~1h past appointment. Customer notified.",
         now - timedelta(hours=2, minutes=20)),
    ]

    cust = customers[2]  # Lone Star Beverage
    quoted = next(l for l in loads if l.status == "quoted")
    msgs += [
        ("customer", cust.id, "email", "out", "Brian Torres (broker)",
         f"{cust.contact_name} <{cust.email}>", f"Spot quote — {quoted.load_number}",
         f"Hi {cust.contact_name.split()[0]},\n\nQuoted ${quoted.customer_rate:,.2f} all-in "
         f"for {quoted.origin['city']} -> {quoted.destination['city']} "
         f"({quoted.distance_miles:,.0f} mi), {quoted.equipment_type}, "
         f"pickup {quoted.pickup_datetime:%b %d}. Capacity is tight this week — "
         "quote good for 24h.\n\nThanks,\nBrian",
         now - timedelta(days=1, hours=5)),
        ("customer", cust.id, "email", "in", f"{cust.contact_name} <{cust.email}>",
         "Brian Torres (broker)", f"Re: Spot quote — {quoted.load_number}",
         "Brian — approved, please book it. Same receiver notes as last time.",
         now - timedelta(days=1, hours=2)),
    ]

    carrier = carriers[0]
    tender = next(l for l in loads if l.status == "tendered")
    msgs += [
        ("carrier", carrier.id, "email", "out", "Dana Whitfield (dispatch)",
         carrier.email, f"Tender offer — {tender.load_number}",
         f"Offering {tender.load_number}: {tender.origin['city']} -> "
         f"{tender.destination['city']}, ${tender.carrier_rate:,.2f} all-in, "
         f"pickup {tender.pickup_datetime:%b %d %H:%M}. Please accept within 2h.",
         now - timedelta(hours=6)),
        ("carrier", carrier.id, "email", "in", carrier.email,
         "Dana Whitfield (dispatch)", f"Re: Tender offer — {tender.load_number}",
         "Accepted. Truck assigned, driver will check in on arrival.",
         now - timedelta(hours=4)),
    ]

    rows = [models.Communication(
        org_id=org_id, thread_type=t, thread_id=tid, channel=ch, direction=d,
        sender=s, recipient=r, subject=subj, body=body,
        created_by=dispatcher.id if t == "load" else broker.id,
        sent_at=sent, created_at=sent) for t, tid, ch, d, s, r, subj, body, sent in msgs]
    db.add_all(rows)
    db.flush()
    return rows

def seed_users(db, org_id, carriers, drivers, customers):
    pw = hash_password(DEMO_PASSWORD)
    link = {"carrier": carriers[0].id, "driver": drivers[0].id,
            "customer": customers[0].id}
    users = []
    for email, name, role, lk_carrier, lk_driver, lk_customer in USER_DEFS:
        users.append(models.User(
            org_id=org_id, email=email, password_hash=pw, full_name=name,
            role=role,
            carrier_id=link["carrier"] if lk_carrier else None,
            driver_id=link["driver"] if lk_driver else None,
            customer_id=link["customer"] if lk_customer else None))
    db.add_all(users)
    db.flush()
    return users


def seed_automation_rules(db, org_id):
    rules = [
        models.AutomationRule(
            org_id=org_id,
            name="Delay over 30 minutes — exception + notify",
            event_name="SHIPMENT_DELAYED",
            conditions={"delay_minutes": {"gt": 30}},
            actions=[
                {"type": "create_exception",
                 "params": {"exception_type": "late_delivery", "severity": "high"}},
                {"type": "create_notification",
                 "params": {"type": "delay", "title": "Shipment delayed over 30 min"}},
                {"type": "trigger_agent",
                 "params": {"agent": "Exception Agent", "task_type": "evaluate_delay"}}]),
        models.AutomationRule(
            org_id=org_id,
            name="POD uploaded — validate, invoice, notify",
            event_name="POD_UPLOADED",
            conditions={},
            actions=[
                {"type": "trigger_agent",
                 "params": {"agent": "Finance Agent", "task_type": "validate_pod"}},
                {"type": "update_load_status",
                 "params": {"status": "pod_received"}},
                {"type": "create_notification",
                 "params": {"type": "document",
                            "title": "POD validated — invoice drafted"}}]),
        models.AutomationRule(
            org_id=org_id,
            name="Margin under 10% — notify ops",
            event_name="LOAD_CREATED",
            conditions={"margin_pct": {"lt": 10}},
            actions=[
                {"type": "create_notification",
                 "params": {"type": "info",
                            "title": "Low-margin load needs review",
                            "recipient_role": "ops_manager"}}]),
    ]
    db.add_all(rules)
    db.flush()
    return rules


def seed_policies(db, org_id):
    policies = [
        models.Policy(
            org_id=org_id, name="Block low-score carriers",
            description="Deny carrier assignment when the carrier score is below 80.",
            rule={"conditions": [
                {"field": "carrier_score", "op": "<", "value": 80},
                {"field": "action", "op": "==", "value": "assign"}],
                "effect": "deny"},
            priority=100),
        models.Policy(
            org_id=org_id, name="Price changes need approval",
            description="Rate changes over $500 require human approval.",
            rule={"conditions": [
                {"field": "action", "op": "==", "value": "rate_update"},
                {"field": "payload.amount", "op": ">", "value": 500}],
                "effect": "require_approval"},
            priority=90),
        models.Policy(
            org_id=org_id, name="High-value loads need approval",
            description="Loads valued over $10,000 require human approval.",
            rule={"conditions": [
                {"field": "load_value", "op": ">", "value": 10000}],
                "effect": "require_approval"},
            priority=80),
    ]
    db.add_all(policies)
    db.flush()
    return policies


def seed_ai_agents(db, org_id):
    agents = [models.AIAgent(
        org_id=org_id, name=name, version="1.0", model="mock-heuristic-v1",
        tools=tools, permissions=perms, status="active", owner="Platform",
        risk_level=risk, autonomy_level=autonomy,
        config={"provider": "mock", "explainable": True})
        for name, autonomy, risk, tools, perms in AI_AGENT_DEFS]
    db.add_all(agents)
    db.flush()
    return agents


def seed_feature_flags(db, org_id):
    flags = [
        models.FeatureFlag(org_id=org_id, key="carrier_score_weights", enabled=True,
                           config={"rate_competitiveness": 0.30, "on_time": 0.25,
                                   "acceptance": 0.15, "lane_history": 0.15,
                                   "compliance": 0.10, "equipment_match": 0.05}),
        models.FeatureFlag(org_id=org_id, key="ai_agents", enabled=True),
        models.FeatureFlag(org_id=org_id, key="advanced_analytics", enabled=True),
        models.FeatureFlag(org_id=org_id, key="forecasting", enabled=True),
        models.FeatureFlag(org_id=org_id, key="autonomous_dispatch", enabled=False),
        models.FeatureFlag(org_id=org_id, key="ai_monthly_budget_usd", enabled=True,
                           config={"amount_usd": 500}),
    ]
    db.add_all(flags)
    db.flush()
    return flags


def seed_integrations(db, org_id):
    rows = [models.Integration(org_id=org_id, provider=p, status="mock",
                               config={"mode": "mock",
                                       "note": "Seeded mock adapter — no real credentials."})
            for p in INTEGRATION_PROVIDERS]
    db.add_all(rows)
    db.flush()
    return rows


def seed_governance(db, org_id, users, loads, delayed_loads):
    """1 pending approval + 2 decided ones, 3 ai_actions, notifications, forecasts."""
    now = utcnow()
    admin = next(u for u in users if u.role == "admin")
    dispatcher = next(u for u in users if u.role == "dispatcher")
    delayed = delayed_loads[0]
    old_carrier = next(c for c in db.query(models.Carrier).filter_by(org_id=org_id).all()
                       if c.id == delayed.carrier_id)
    alt = next(c for c in db.query(models.Carrier).filter_by(org_id=org_id).all()
               if c.id != delayed.carrier_id and c.compliance_status == "compliant"
               and c.performance_score and c.performance_score > 90)

    pending = models.Approval(
        org_id=org_id, agent_name="Dispatch Agent", action_type="reassign_carrier",
        entity_type="load", entity_id=delayed.id,
        payload={"old_carrier_id": delayed.carrier_id,
                 "new_carrier_id": alt.id,
                 "reason": f"Load {delayed.load_number} is past its delivery "
                           f"appointment; {alt.legal_name} has a truck 60 mi away "
                           "and a 96+ on-time score on this lane."},
        reason=f"AI-proposed carrier reassignment for at-risk load {delayed.load_number}.",
        risk_level="medium", required_role="dispatcher", status="pending",
        requested_by=admin.id)
    approved = models.Approval(
        org_id=org_id, agent_name="Routing Agent", action_type="optimize_route",
        entity_type="load", entity_id=loads[3].id,
        payload={"saved_miles": 42, "saved_minutes": 55},
        reason="Route optimization saves 42 miles.", risk_level="low",
        required_role="dispatcher", status="approved",
        requested_by=admin.id, decided_by=dispatcher.id,
        decided_at=now - timedelta(hours=5))
    rejected = models.Approval(
        org_id=org_id, agent_name="Pricing Agent", action_type="bulk_reprice",
        entity_type="lane", entity_id=None,
        payload={"lane": "Atlanta, GA -> Dallas, TX", "adjustment_pct": -8},
        reason="Across-the-board 8% cut is too aggressive before peak season.",
        risk_level="high", required_role="admin", status="rejected",
        requested_by=admin.id, decided_by=admin.id,
        decided_at=now - timedelta(days=1))
    db.add_all([pending, approved, rejected])
    db.flush()

    agents = {a.name: a for a in db.query(models.AIAgent).filter_by(org_id=org_id)}
    actions = [
        models.AIAction(
            org_id=org_id, agent_id=agents["Pricing Agent"].id,
            agent_name="Pricing Agent", action_type="quote_rate",
            entity_type="load", entity_id=loads[10].id,
            input={"load_id": loads[10].id, "lane": "Chicago, IL -> Dallas, TX"},
            output={"customer_rate": loads[10].customer_rate,
                    "carrier_rate": loads[10].carrier_rate,
                    "margin_pct": round(loads[10].margin_pct, 1)},
            decision="auto",
            result={"status": "executed", "note": "Quote returned to broker UI."}),
        models.AIAction(
            org_id=org_id, agent_id=agents["Routing Agent"].id,
            agent_name="Routing Agent", action_type="optimize_route",
            entity_type="load", entity_id=loads[3].id,
            input={"load_id": loads[3].id},
            output={"saved_miles": 42, "saved_minutes": 55},
            decision="approved", approval_id=approved.id,
            result={"status": "executed", "note": "Optimized route applied to load."}),
        models.AIAction(
            org_id=org_id, agent_id=agents["Pricing Agent"].id,
            agent_name="Pricing Agent", action_type="bulk_reprice",
            entity_type="lane", entity_id=None,
            input={"lane": "Atlanta, GA -> Dallas, TX", "adjustment_pct": -8},
            output=None, decision="denied", approval_id=rejected.id,
            result={"status": "blocked",
                    "note": "Rejected by admin — no changes applied."}),
    ]
    db.add_all(actions)

    notifications = [
        models.Notification(org_id=org_id, user_id=dispatcher.id, type="delay",
                            title=f"Load {delayed.load_number} is past its appointment",
                            body="At-risk delivery — review the pending carrier "
                                 "reassignment approval.",
                            entity_type="load", entity_id=delayed.id),
        models.Notification(org_id=org_id, user_id=dispatcher.id, type="approval",
                            title="Approval requested: carrier reassignment",
                            body="Dispatch Agent proposed reassigning an at-risk load.",
                            entity_type="approval", entity_id=pending.id),
        models.Notification(org_id=org_id, user_id=admin.id, type="ai_recommendation",
                            title="3 carriers match the new Atlanta → Dallas tender",
                            body="Carrier Agent ranked matches with explanations.",
                            entity_type="load", entity_id=loads[0].id),
        models.Notification(org_id=org_id, user_id=dispatcher.id, type="exception",
                            title="New exception: margin below 10% floor",
                            body="Load LD-10007 margin is 6.0% — review before dispatch.",
                            entity_type="exception", entity_id=None, is_read=True),
        models.Notification(org_id=org_id, user_id=dispatcher.id, type="assignment",
                            title="Driver assigned to LD-10030",
                            body="Driver accepted the assignment via ELD.",
                            entity_type="load", entity_id=loads[29].id, is_read=True),
        models.Notification(org_id=org_id, user_id=None, type="info",
                            title="Nightly forecast refresh complete",
                            body="Volume and lane-pricing forecasts updated.",
                            entity_type=None, entity_id=None, is_read=True),
    ]
    db.add_all(notifications)

    forecasts = [
        models.Forecast(org_id=org_id, forecast_type="volume",
                        period_start=now.date() + timedelta(days=1),
                        period_end=now.date() + timedelta(days=30),
                        values={"weeks": [
                            {"week": 1, "loads": 118}, {"week": 2, "loads": 126},
                            {"week": 3, "loads": 134}, {"week": 4, "loads": 129}],
                            "trend": "+6.2% vs prior 30 days"},
                        confidence=0.78),
        models.Forecast(org_id=org_id, forecast_type="lane_pricing",
                        period_start=now.date() + timedelta(days=1),
                        period_end=now.date() + timedelta(days=90),
                        values={"lanes": [
                            {"lane": "Atlanta, GA -> Dallas, TX",
                             "current_per_mile": 2.42, "forecast_per_mile": 2.51},
                            {"lane": "Chicago, IL -> Atlanta, GA",
                             "current_per_mile": 2.38, "forecast_per_mile": 2.44},
                            {"lane": "Los Angeles, CA -> Phoenix, AZ",
                             "current_per_mile": 2.66, "forecast_per_mile": 2.72}]},
                        confidence=0.71),
    ]
    db.add_all(forecasts)
    db.flush()
    return pending


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    reset = "--reset" in argv
    force = "--force" in argv

    if reset:
        print("Dropping all tables...")
        Base.metadata.drop_all(bind=engine)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = db.query(models.Organization).filter_by(slug=DEMO_SLUG).first()
        if existing and not (reset or force):
            print("already seeded")
            return 0

        org = seed_org(db)
        db.add(org)
        db.flush()

        customers = seed_customers(db, org.id)
        carriers = seed_carriers(db, org.id)
        drivers = seed_drivers(db, org.id, carriers)
        vehicles = seed_vehicles(db, org.id)
        users = seed_users(db, org.id, carriers, drivers, customers)
        loads, delayed_loads = seed_loads(db, org.id, customers, carriers,
                                          drivers, vehicles)
        seed_stops(db, loads)
        seed_tracking(db, org.id, loads)
        seed_exceptions(db, org.id, loads, delayed_loads, users)
        seed_invoices(db, org.id, loads)
        seed_documents(db, org.id, loads, carriers, users)
        seed_communications(db, org.id, loads, customers, carriers, users)
        seed_automation_rules(db, org.id)
        seed_policies(db, org.id)
        seed_ai_agents(db, org.id)
        seed_feature_flags(db, org.id)
        seed_integrations(db, org.id)
        seed_governance(db, org.id, users, loads, delayed_loads)

        db.commit()
        counts = {
            "users": db.query(models.User).count(),
            "customers": db.query(models.Customer).count(),
            "carriers": db.query(models.Carrier).count(),
            "drivers": db.query(models.Driver).count(),
            "vehicles": db.query(models.Vehicle).count(),
            "loads": db.query(models.Load).count(),
            "stops": db.query(models.Stop).count(),
            "tracking_events": db.query(models.TrackingEvent).count(),
            "exceptions": db.query(models.Exception).count(),
            "invoices": db.query(models.Invoice).count(),
            "payments": db.query(models.Payment).count(),
            "documents": db.query(models.Document).count(),
            "communications": db.query(models.Communication).count(),
            "automation_rules": db.query(models.AutomationRule).count(),
            "policies": db.query(models.Policy).count(),
            "ai_agents": db.query(models.AIAgent).count(),
            "feature_flags": db.query(models.FeatureFlag).count(),
            "integrations": db.query(models.Integration).count(),
            "approvals": db.query(models.Approval).count(),
            "ai_actions": db.query(models.AIAction).count(),
            "notifications": db.query(models.Notification).count(),
            "forecasts": db.query(models.Forecast).count(),
        }
        print("Seed complete:")
        for k, v in counts.items():
            print(f"  {k:17s} {v}")
        print("Demo login: admin@demo.tms / Demo1234!")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
