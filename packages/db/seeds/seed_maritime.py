"""
TradeFlow AI — Maritime Seed Data Generator (T-014)

Replaces the deleted CSV/Excel source files:
  - AIS_Data_Sample.csv          → ais_vessel_positions
  - Lineup_Data_Sample.csv       → port_lineup
  - Ownership_-_Website_Data_Sample.xlsx → vessel_ownership
  - Website_Vessel_Characteristics_Sample.xlsx → vessel_characteristics

Vessel names/voyages cross-referenced from docs/TradeFlow_GroundTruth_v5.2.json.

Usage:
    uv run python packages/db/seeds/seed_maritime.py
    # or with existing connection:
    uv run python packages/db/seeds/seed_maritime.py --db-url postgresql://postgres:postgres@localhost:5432/postgres
"""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta

import psycopg2
from faker import Faker

fake = Faker()

# ─────────────────────────────────────────────────────────────────────────────
# Ground truth vessels — cross-referenced from TradeFlow_GroundTruth_v5.2.json
# ─────────────────────────────────────────────────────────────────────────────
KNOWN_VESSELS = [
    {
        "name": "RIO DE LA PLATA",
        "voyage": "3208",
        "flag": "LR",
        "imo": "9400154",
        "mmsi": "538007842",
        "scac": "HLCU",
        "vessel_type": "Container Ship",
        "built_year": 2008,
        "trading_status": "Trdg",
        "owner": "Hapag-Lloyd AG",
    },
    {
        "name": "CAP VERDE",
        "voyage": "2304",
        "flag": "LR",
        "imo": "9312145",
        "mmsi": "538003754",
        "scac": "HLCU",
        "vessel_type": "Container Ship",
        "built_year": 2005,
        "trading_status": "Trdg",
        "owner": "Hapag-Lloyd AG",
    },
    {
        "name": "NMV MAERSK COPENHAGEN",
        "voyage": "246N",
        "flag": "DK",
        "imo": "9260956",
        "mmsi": "219001234",
        "scac": "MAEU",
        "vessel_type": "Container Ship",
        "built_year": 2003,
        "trading_status": "Trdg",
        "owner": "Maersk Line A/S",
    },
    {
        "name": "KMTC DUBAI",
        "voyage": "2105E",
        "flag": "KR",
        "imo": "9367527",
        "mmsi": "440187000",
        "scac": "EGLV",
        "vessel_type": "Container Ship",
        "built_year": 2007,
        "trading_status": "Trdg",
        "owner": "KMTC Line",
    },
    {
        "name": "CAPE NORVIEGA",
        "voyage": "0175-028S",
        "flag": "NO",
        "imo": "9398145",
        "mmsi": "258123456",
        "scac": "EGLV",
        "vessel_type": "Container Ship",
        "built_year": 2009,
        "trading_status": "Trdg",
        "owner": "Evergreen Marine Corporation",
    },
    {
        "name": "HANJIN ROTTERDAM",
        "voyage": "0011E",
        "flag": "KR",
        "imo": "9411204",
        "mmsi": "440384000",
        "scac": "EGLV",
        "vessel_type": "Container Ship",
        "built_year": 2009,
        "trading_status": "Trdg",
        "owner": "Evergreen Marine Corporation",
    },
    {
        "name": "GFS GISELLE",
        "voyage": "2304W",
        "flag": "PA",
        "imo": "9534218",
        "mmsi": "374123456",
        "scac": "CSLU",
        "vessel_type": "Container Ship",
        "built_year": 2011,
        "trading_status": "Trdg",
        "owner": "Cordelia Container Shipping Line",
    },
]

KNOWN_PORTS = [
    {"locode": "IDJKT", "name": "Jakarta", "country": "ID"},
    {"locode": "INMUN", "name": "Mundra", "country": "IN"},
    {"locode": "INNSA", "name": "Nhava Sheva", "country": "IN"},
    {"locode": "AEJEA", "name": "Jebel Ali", "country": "AE"},
    {"locode": "CNGZH", "name": "Guangzhou", "country": "CN"},
    {"locode": "CNSHK", "name": "Shekou", "country": "CN"},
    {"locode": "DEHAM", "name": "Hamburg", "country": "DE"},
    {"locode": "GBTIL", "name": "Tilbury", "country": "GB"},
    {"locode": "MYKUA", "name": "Kuantan", "country": "MY"},
    {"locode": "VNSGN", "name": "Ho Chi Minh City", "country": "VN"},
]


def generate_ais_positions(cursor: psycopg2.cursor) -> int:  # type: ignore[name-defined]
    """Seed ais_vessel_positions — 3 recent positions per known vessel."""
    inserted = 0
    for v in KNOWN_VESSELS:
        base_lat = random.uniform(-10, 35)
        base_lon = random.uniform(50, 130)
        for hours_ago in [1, 6, 24]:
            ts = datetime.utcnow() - timedelta(hours=hours_ago)
            cursor.execute(
                """
                INSERT INTO ais_vessel_positions
                    (imo, vessel_name, mmsi, latitude, longitude,
                     speed_knots, heading, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (imo, timestamp) DO NOTHING
                """,
                (
                    v["imo"],
                    v["name"],
                    v["mmsi"],
                    round(base_lat + random.uniform(-0.5, 0.5), 6),
                    round(base_lon + random.uniform(-0.5, 0.5), 6),
                    round(random.uniform(0, 20), 2),
                    random.randint(0, 359),
                    ts,
                ),
            )
            inserted += cursor.rowcount
    return inserted


def generate_vessel_characteristics(cursor: psycopg2.cursor) -> int:  # type: ignore[name-defined]
    """Seed vessel_characteristics from KNOWN_VESSELS + 13 extra synthetic."""
    inserted = 0
    for v in KNOWN_VESSELS:
        cursor.execute(
            """
            INSERT INTO vessel_characteristics
                (imo_number, vessel_name, call_sign, vessel_type_code,
                 flag_code, built_year, trading_status, registered_owner)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (imo_number) DO UPDATE SET
                trading_status = EXCLUDED.trading_status,
                registered_owner = EXCLUDED.registered_owner
            """,
            (
                v["imo"],
                v["name"],
                fake.lexify("????").upper(),
                "Container",
                v["flag"],
                v["built_year"],
                v["trading_status"],
                v["owner"],
            ),
        )
        inserted += cursor.rowcount

    # 13 synthetic vessels to pad to 20 total
    for _ in range(13):
        imo = str(random.randint(9000000, 9999999))
        cursor.execute(
            """
            INSERT INTO vessel_characteristics
                (imo_number, vessel_name, call_sign, vessel_type_code,
                 flag_code, built_year, trading_status, registered_owner)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (imo_number) DO NOTHING
            """,
            (
                imo,
                fake.last_name().upper() + " " + fake.last_name().upper(),
                fake.lexify("????").upper(),
                random.choice(["Container", "Bulk", "Tanker"]),
                random.choice(["SG", "PA", "LR", "MH", "BS"]),
                random.randint(1998, 2020),
                "Trdg",
                fake.company(),
            ),
        )
        inserted += cursor.rowcount

    return inserted


def generate_vessel_ownership(cursor: psycopg2.cursor) -> int:  # type: ignore[name-defined]
    """Seed vessel_ownership — 20 records matching known vessels."""
    inserted = 0
    for v in KNOWN_VESSELS:
        cursor.execute(
            """
            INSERT INTO vessel_ownership
                (imo_number, commercial_owner, commercial_owner_country,
                 effective_control, technical_manager, financial_owner, flag)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (
                v["imo"],
                v["owner"],
                fake.country(),
                v["owner"],
                fake.company() + " Ship Management",
                fake.company() + " Finance",
                v["flag"],
            ),
        )
        inserted += cursor.rowcount

    # Pad to 20 with synthetic
    for _ in range(13):
        imo = str(random.randint(9000000, 9999999))
        cursor.execute(
            """
            INSERT INTO vessel_ownership
                (imo_number, commercial_owner, commercial_owner_country,
                 effective_control, technical_manager, financial_owner, flag)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (
                imo,
                fake.company(),
                fake.country(),
                fake.company(),
                fake.company() + " Ship Management",
                fake.company() + " Finance",
                random.choice(["SG", "PA", "LR", "MH", "BS"]),
            ),
        )
        inserted += cursor.rowcount

    return inserted


def generate_port_lineup(cursor: psycopg2.cursor) -> int:  # type: ignore[name-defined]
    """Seed port_lineup covering IDJKT, INNSA, INMUN, AEJEA, CNGZH (30 rows)."""
    inserted = 0
    cdp_ports = ["IDJKT", "INNSA", "INMUN", "AEJEA", "CNGZH"]

    for v in KNOWN_VESSELS:
        for port_locode in random.sample(cdp_ports, k=min(4, len(cdp_ports))):
            port = next((p for p in KNOWN_PORTS if p["locode"] == port_locode), None)
            eta = datetime.utcnow() + timedelta(days=random.randint(1, 30))
            etd = eta + timedelta(days=random.randint(1, 3))
            cursor.execute(
                """
                INSERT INTO port_lineup
                    (imo, vessel_name, port_locode, port_name, country,
                     eta, etd, voyage_number, service_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    v["imo"],
                    v["name"],
                    port_locode,
                    port["name"] if port else port_locode,
                    port["country"] if port else "XX",
                    eta,
                    etd,
                    v["voyage"],
                    f"AX{random.randint(100, 999)}",
                ),
            )
            inserted += cursor.rowcount

    return inserted


def main(db_url: str) -> None:
    print(f"Connecting to {db_url[:40]}...")
    conn = psycopg2.connect(db_url)
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            print("Seeding ais_vessel_positions...")
            n = generate_ais_positions(cur)
            print(f"  → {n} rows inserted")

            print("Seeding vessel_characteristics...")
            n = generate_vessel_characteristics(cur)
            print(f"  → {n} rows inserted")

            print("Seeding vessel_ownership...")
            n = generate_vessel_ownership(cur)
            print(f"  → {n} rows inserted")

            print("Seeding port_lineup...")
            n = generate_port_lineup(cur)
            print(f"  → {n} rows inserted")

        conn.commit()
        print("✅ Maritime seed data committed successfully.")
    except Exception as exc:
        conn.rollback()
        print(f"❌ Seed failed, rolled back: {exc}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed maritime reference data")
    parser.add_argument(
        "--db-url",
        default="postgresql://postgres:postgres@localhost:5432/postgres",
        help="PostgreSQL connection string",
    )
    args = parser.parse_args()
    main(args.db_url)
