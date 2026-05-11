import sqlite3

# Per-radio tables include a `radio_id` column (default 'a' for single-radio
# / backward-compat). Pi-shared tables (sensors, Pi health, external power,
# settings) stay un-keyed. Existing DBs are migrated in-place by the
# function-based migrations below — see _RADIO_ID_MIGRATIONS.

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS device_info (
    radio_id TEXT NOT NULL DEFAULT 'a',
    key      TEXT NOT NULL,
    value    TEXT NOT NULL,
    PRIMARY KEY (radio_id, key)
);

CREATE TABLE IF NOT EXISTS stats_core (
    ts          INTEGER NOT NULL,
    radio_id    TEXT NOT NULL DEFAULT 'a',
    battery_mv  INTEGER,
    uptime_secs INTEGER,
    errors      INTEGER,
    queue_len   INTEGER,
    PRIMARY KEY (ts, radio_id)
);

CREATE TABLE IF NOT EXISTS stats_radio (
    ts          INTEGER NOT NULL,
    radio_id    TEXT NOT NULL DEFAULT 'a',
    noise_floor REAL,
    tx_air_secs REAL,
    rx_air_secs REAL,
    last_rssi   REAL,
    last_snr    REAL,
    PRIMARY KEY (ts, radio_id)
);

CREATE TABLE IF NOT EXISTS stats_packets (
    ts          INTEGER NOT NULL,
    radio_id    TEXT NOT NULL DEFAULT 'a',
    recv_total  INTEGER,
    sent_total  INTEGER,
    recv_errors INTEGER,
    fwd_total   INTEGER,
    fwd_errors  INTEGER,
    direct_dups INTEGER,
    flood_dups  INTEGER,
    direct_tx   INTEGER,
    flood_tx    INTEGER,
    direct_rx   INTEGER,
    flood_rx    INTEGER,
    PRIMARY KEY (ts, radio_id)
);

CREATE TABLE IF NOT EXISTS stats_extpower (
    ts           INTEGER PRIMARY KEY,
    ch0_voltage  REAL,
    ch0_current  REAL,
    ch0_power    REAL,
    ch1_voltage  REAL,
    ch1_current  REAL,
    ch1_power    REAL,
    ch2_voltage  REAL,
    ch2_current  REAL,
    ch2_power    REAL
);

CREATE TABLE IF NOT EXISTS stats_pi_health (
    ts               INTEGER PRIMARY KEY,
    cpu_percent      REAL,
    load_1           REAL,
    load_5           REAL,
    load_15          REAL,
    mem_used_mb      REAL,
    mem_total_mb     REAL,
    mem_percent      REAL,
    swap_used_mb     REAL,
    swap_total_mb    REAL,
    cpu_temp         REAL,
    disk_used_gb     REAL,
    disk_total_gb    REAL,
    disk_percent     REAL,
    disk_read_bytes  INTEGER,
    disk_write_bytes INTEGER,
    net_bytes_sent   INTEGER,
    net_bytes_recv   INTEGER,
    uptime_secs      INTEGER,
    process_count    INTEGER
);

CREATE TABLE IF NOT EXISTS packet_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        INTEGER NOT NULL,
    radio_id  TEXT NOT NULL DEFAULT 'a',
    direction TEXT,
    pkt_type  INTEGER,
    route     TEXT,
    snr       REAL,
    rssi      REAL,
    score     REAL,
    hash      TEXT,
    raw_hex   TEXT
);

CREATE TABLE IF NOT EXISTS neighbors (
    pubkey_prefix TEXT NOT NULL,
    radio_id      TEXT NOT NULL DEFAULT 'a',
    name          TEXT,
    device_role   TEXT,
    last_seen     INTEGER,
    last_snr      REAL,
    last_rssi     REAL,
    lat           REAL,
    lon           REAL,
    PRIMARY KEY (pubkey_prefix, radio_id)
);

CREATE TABLE IF NOT EXISTS neighbor_sightings (
    ts            INTEGER NOT NULL,
    pubkey_prefix TEXT NOT NULL,
    radio_id      TEXT NOT NULL DEFAULT 'a',
    snr           REAL,
    rssi          REAL,
    PRIMARY KEY (ts, pubkey_prefix, radio_id)
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stats_sensor_power (
    ts          INTEGER PRIMARY KEY,
    ch0_voltage REAL,
    ch0_current REAL,
    ch0_power   REAL,
    ch1_voltage REAL,
    ch1_current REAL,
    ch1_power   REAL,
    ch2_voltage REAL,
    ch2_current REAL,
    ch2_power   REAL
);

CREATE TABLE IF NOT EXISTS stats_sensor_env (
    ts          INTEGER PRIMARY KEY,
    temperature REAL,
    humidity    REAL,
    pressure    REAL
);

CREATE TABLE IF NOT EXISTS stats_sensor_accel (
    ts       INTEGER PRIMARY KEY,
    vib_avg  REAL,
    vib_peak REAL,
    tilt_avg REAL,
    x_avg    REAL,
    y_avg    REAL,
    z_avg    REAL
);

CREATE TABLE IF NOT EXISTS sensor_lightning_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          INTEGER NOT NULL,
    event_type  INTEGER NOT NULL,
    distance_km REAL,
    energy      REAL
);

CREATE TABLE IF NOT EXISTS stats_disk_io (
    ts INTEGER NOT NULL,
    device TEXT NOT NULL,
    read_bytes INTEGER,
    write_bytes INTEGER,
    PRIMARY KEY (ts, device)
);

CREATE INDEX IF NOT EXISTS idx_packet_log_ts ON packet_log(ts);
-- idx_packet_log_radio_ts is created in _migrate_packet_log so it runs after
-- the radio_id column exists on legacy DBs.
CREATE INDEX IF NOT EXISTS idx_neighbor_sightings_ts ON neighbor_sightings(ts);
CREATE INDEX IF NOT EXISTS idx_lightning_events_ts ON sensor_lightning_events(ts);
CREATE INDEX IF NOT EXISTS idx_disk_io_ts ON stats_disk_io(ts);

CREATE TABLE IF NOT EXISTS stats_bq24074 (
    ts       INTEGER PRIMARY KEY,
    charging INTEGER,
    pgood    INTEGER
);
"""


MIGRATIONS = [
    "ALTER TABLE packet_log ADD COLUMN pkt_type INTEGER",
    "ALTER TABLE packet_log ADD COLUMN route TEXT",
    "ALTER TABLE neighbors ADD COLUMN device_role TEXT",
    "ALTER TABLE neighbors ADD COLUMN last_rssi REAL",
    "ALTER TABLE neighbor_sightings ADD COLUMN snr REAL",
    "ALTER TABLE neighbor_sightings ADD COLUMN rssi REAL",
    "ALTER TABLE packet_log ADD COLUMN raw_hex TEXT",
    "ALTER TABLE stats_packets ADD COLUMN flood_dups INTEGER",
    "ALTER TABLE stats_radio ADD COLUMN last_rssi REAL",
    "ALTER TABLE stats_radio ADD COLUMN last_snr REAL",
    "ALTER TABLE stats_packets ADD COLUMN direct_tx INTEGER",
    "ALTER TABLE stats_packets ADD COLUMN flood_tx INTEGER",
    "ALTER TABLE stats_packets ADD COLUMN direct_rx INTEGER",
    "ALTER TABLE stats_packets ADD COLUMN flood_rx INTEGER",
    "ALTER TABLE stats_sensor_power ADD COLUMN ch2_voltage REAL",
    "ALTER TABLE stats_sensor_power ADD COLUMN ch2_current REAL",
    "ALTER TABLE stats_sensor_power ADD COLUMN ch2_power REAL",
]


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def _rebuild_with_radio_id(conn: sqlite3.Connection, table: str, new_table_sql: str,
                            new_columns: list) -> None:
    """Rebuild `table` so it carries a radio_id column. Idempotent: skips if
    radio_id already exists. Existing rows backfill with radio_id='a'.

    new_columns must list every column in the rebuilt table in order. The
    'radio_id' entry is filled from the literal 'a'; every other column is
    copied straight from the old table by name, so it must exist there."""
    if _has_column(conn, table, "radio_id"):
        return
    new_table = f"{table}_v2"
    new_col_list = ", ".join(new_columns)
    select_expr = ", ".join("'a'" if c == "radio_id" else c for c in new_columns)
    conn.executescript(
        f"""
        BEGIN;
        {new_table_sql.replace(table, new_table, 1)};
        INSERT INTO {new_table} ({new_col_list})
            SELECT {select_expr} FROM {table};
        DROP TABLE {table};
        ALTER TABLE {new_table} RENAME TO {table};
        COMMIT;
        """
    )


def _migrate_device_info(conn: sqlite3.Connection) -> None:
    _rebuild_with_radio_id(
        conn,
        "device_info",
        """CREATE TABLE device_info (
            radio_id TEXT NOT NULL DEFAULT 'a',
            key      TEXT NOT NULL,
            value    TEXT NOT NULL,
            PRIMARY KEY (radio_id, key)
        )""",
        new_columns=["radio_id", "key", "value"],
    )


def _migrate_stats_core(conn: sqlite3.Connection) -> None:
    _rebuild_with_radio_id(
        conn,
        "stats_core",
        """CREATE TABLE stats_core (
            ts          INTEGER NOT NULL,
            radio_id    TEXT NOT NULL DEFAULT 'a',
            battery_mv  INTEGER,
            uptime_secs INTEGER,
            errors      INTEGER,
            queue_len   INTEGER,
            PRIMARY KEY (ts, radio_id)
        )""",
        new_columns=["ts", "radio_id", "battery_mv", "uptime_secs", "errors", "queue_len"],
    )


def _migrate_stats_radio(conn: sqlite3.Connection) -> None:
    _rebuild_with_radio_id(
        conn,
        "stats_radio",
        """CREATE TABLE stats_radio (
            ts          INTEGER NOT NULL,
            radio_id    TEXT NOT NULL DEFAULT 'a',
            noise_floor REAL,
            tx_air_secs REAL,
            rx_air_secs REAL,
            last_rssi   REAL,
            last_snr    REAL,
            PRIMARY KEY (ts, radio_id)
        )""",
        new_columns=["ts", "radio_id", "noise_floor", "tx_air_secs", "rx_air_secs", "last_rssi", "last_snr"],
    )


def _migrate_stats_packets(conn: sqlite3.Connection) -> None:
    _rebuild_with_radio_id(
        conn,
        "stats_packets",
        """CREATE TABLE stats_packets (
            ts          INTEGER NOT NULL,
            radio_id    TEXT NOT NULL DEFAULT 'a',
            recv_total  INTEGER,
            sent_total  INTEGER,
            recv_errors INTEGER,
            fwd_total   INTEGER,
            fwd_errors  INTEGER,
            direct_dups INTEGER,
            flood_dups  INTEGER,
            direct_tx   INTEGER,
            flood_tx    INTEGER,
            direct_rx   INTEGER,
            flood_rx    INTEGER,
            PRIMARY KEY (ts, radio_id)
        )""",
        new_columns=[
            "ts", "radio_id", "recv_total", "sent_total", "recv_errors", "fwd_total", "fwd_errors",
            "direct_dups", "flood_dups", "direct_tx", "flood_tx", "direct_rx", "flood_rx",
        ],
    )


def _migrate_neighbors(conn: sqlite3.Connection) -> None:
    _rebuild_with_radio_id(
        conn,
        "neighbors",
        """CREATE TABLE neighbors (
            pubkey_prefix TEXT NOT NULL,
            radio_id      TEXT NOT NULL DEFAULT 'a',
            name          TEXT,
            device_role   TEXT,
            last_seen     INTEGER,
            last_snr      REAL,
            last_rssi     REAL,
            lat           REAL,
            lon           REAL,
            PRIMARY KEY (pubkey_prefix, radio_id)
        )""",
        new_columns=["pubkey_prefix", "radio_id", "name", "device_role", "last_seen", "last_snr", "last_rssi", "lat", "lon"],
    )


def _migrate_neighbor_sightings(conn: sqlite3.Connection) -> None:
    _rebuild_with_radio_id(
        conn,
        "neighbor_sightings",
        """CREATE TABLE neighbor_sightings (
            ts            INTEGER NOT NULL,
            pubkey_prefix TEXT NOT NULL,
            radio_id      TEXT NOT NULL DEFAULT 'a',
            snr           REAL,
            rssi          REAL,
            PRIMARY KEY (ts, pubkey_prefix, radio_id)
        )""",
        new_columns=["ts", "pubkey_prefix", "radio_id", "snr", "rssi"],
    )


def _migrate_packet_log(conn: sqlite3.Connection) -> None:
    # packet_log has an AUTOINCREMENT id PK so we don't need a table rebuild —
    # a simple ADD COLUMN is enough. Index on (radio_id, ts) for per-radio queries.
    if not _has_column(conn, "packet_log", "radio_id"):
        conn.execute("ALTER TABLE packet_log ADD COLUMN radio_id TEXT NOT NULL DEFAULT 'a'")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_packet_log_radio_ts ON packet_log(radio_id, ts)")


_RADIO_ID_MIGRATIONS = [
    _migrate_device_info,
    _migrate_stats_core,
    _migrate_stats_radio,
    _migrate_stats_packets,
    _migrate_neighbors,
    _migrate_neighbor_sightings,
    _migrate_packet_log,
]


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(SCHEMA_SQL)
    for sql in MIGRATIONS:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # column already exists
    for migrate in _RADIO_ID_MIGRATIONS:
        migrate(conn)
    conn.commit()
    return conn
