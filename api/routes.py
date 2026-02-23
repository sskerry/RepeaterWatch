from flask import Blueprint, jsonify, request

from database import models

api = Blueprint("api", __name__, url_prefix="/api/v1")


def _hours():
    try:
        return int(request.args.get("hours", 24))
    except (TypeError, ValueError):
        return 24


@api.route("/device")
def device_info():
    info = models.get_device_info()
    core = models.query_stats_core(hours=1)
    uptime = core[-1]["uptime_secs"] if core else None
    pk = info.get("public_key", "")
    # pubkey_prefix: first 4 hex chars (2 bytes) for map label
    pubkey_prefix = pk[:4].upper() if pk else ""
    lat = None
    lon = None
    try:
        lat = float(info["lat"]) if "lat" in info else None
        lon = float(info["lon"]) if "lon" in info else None
    except (ValueError, TypeError):
        pass
    return jsonify({
        "name": info.get("name", "Unknown"),
        "firmware": info.get("firmware", "Unknown"),
        "board": info.get("board", "Unknown"),
        "radio_config": info.get("radio_config", "Unknown"),
        "public_key": pk,
        "pubkey_prefix": pubkey_prefix,
        "lat": lat,
        "lon": lon,
        "uptime_secs": uptime,
    })


@api.route("/stats/battery")
def stats_battery():
    rows = models.query_stats_core(_hours())
    return jsonify({
        "timestamps": [r["ts"] for r in rows],
        "battery_mv": [r["battery_mv"] for r in rows],
    })


@api.route("/stats/radio")
def stats_radio():
    rows = models.query_stats_radio(_hours())
    return jsonify({
        "timestamps": [r["ts"] for r in rows],
        "noise_floor": [r["noise_floor"] for r in rows],
        "tx_air_secs": [r["tx_air_secs"] for r in rows],
        "rx_air_secs": [r["rx_air_secs"] for r in rows],
    })


@api.route("/stats/packets")
def stats_packets():
    rows = models.query_stats_packets(_hours())
    return jsonify({
        "timestamps": [r["ts"] for r in rows],
        "recv_total": [r["recv_total"] for r in rows],
        "sent_total": [r["sent_total"] for r in rows],
        "recv_errors": [r["recv_errors"] for r in rows],
        "fwd_total": [r["fwd_total"] for r in rows],
        "fwd_errors": [r["fwd_errors"] for r in rows],
        "direct_dups": [r["direct_dups"] for r in rows],
    })


@api.route("/stats/power")
def stats_power():
    rows = models.query_stats_extpower(_hours())
    return jsonify({
        "timestamps": [r["ts"] for r in rows],
        "ch0_voltage": [r["ch0_voltage"] for r in rows],
        "ch0_current": [r["ch0_current"] for r in rows],
        "ch0_power": [r["ch0_power"] for r in rows],
        "ch1_voltage": [r["ch1_voltage"] for r in rows],
        "ch1_current": [r["ch1_current"] for r in rows],
        "ch1_power": [r["ch1_power"] for r in rows],
        "ch2_voltage": [r["ch2_voltage"] for r in rows],
        "ch2_current": [r["ch2_current"] for r in rows],
        "ch2_power": [r["ch2_power"] for r in rows],
    })


@api.route("/stats/airtime")
def stats_airtime():
    rows = models.query_airtime(_hours())
    return jsonify({
        "timestamps": [r["ts"] for r in rows],
        "tx_pct": [r["tx_pct"] for r in rows],
        "rx_pct": [r["rx_pct"] for r in rows],
    })


@api.route("/packets/activity")
def packets_activity():
    h = _hours()
    bucket = request.args.get("bucket_minutes", 15, type=int)
    rows = models.query_packets_activity(h, bucket)
    dups = models.query_packet_dups(h)
    dup_by_ts = {}
    for d in dups:
        dup_by_ts[d["ts"]] = d
    dup_timestamps = sorted(dup_by_ts.keys())
    def find_dups(bucket_ts):
        dd = 0
        fd = 0
        for dts in dup_timestamps:
            if dts <= bucket_ts:
                dd = dup_by_ts[dts]["direct_dups"]
                fd = dup_by_ts[dts]["flood_dups"]
            else:
                break
        return dd, fd
    direct_dups_list = []
    flood_dups_list = []
    for r in rows:
        dd, fd = find_dups(r["bucket"])
        direct_dups_list.append(dd)
        flood_dups_list.append(fd)
    return jsonify({
        "timestamps": [r["bucket"] for r in rows],
        "tx_direct": [r["tx_direct"] for r in rows],
        "tx_flood": [r["tx_flood"] for r in rows],
        "rx_direct": [r["rx_direct"] for r in rows],
        "rx_flood": [r["rx_flood"] for r in rows],
        "direct_dups": direct_dups_list,
        "flood_dups": flood_dups_list,
        "total": [r["total"] for r in rows],
    })


@api.route("/packets/recent")
def packets_recent():
    limit = request.args.get("limit", 50, type=int)
    rows = models.query_packets_recent(limit)
    return jsonify(rows)


@api.route("/neighbors")
def neighbors():
    rows = models.query_neighbors()
    return jsonify(rows)


@api.route("/neighbors/history")
def neighbors_history():
    rows = models.query_neighbor_history(_hours())
    return jsonify({
        "timestamps": [r["ts"] for r in rows],
        "count": [r["count"] for r in rows],
    })


@api.route("/status")
def status():
    from collector.stats_poller import StatsPoller
    from flask import current_app
    poller = current_app.config.get("poller")
    poller_status = poller.status if poller else {"running": False}
    return jsonify({
        **poller_status,
        "db_size_bytes": models.db_size_bytes(),
    })
