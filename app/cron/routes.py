import json
import os
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template
from app.url_health_test import run_health_check

cron_bp = Blueprint("cron", __name__)

REPORT_PATH = os.path.join(os.path.dirname(__file__), "health_report.json")

def save_report(total, flagged):
    report = {
        "run_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "total_checked": total,
        "total_flagged": len(flagged),
        "flagged_urls": flagged
    }
    with open(REPORT_PATH, "w") as f:
        json.dump(report, f)

def load_report():
    if not os.path.exists(REPORT_PATH):
        return None
    with open(REPORT_PATH, "r") as f:
        return json.load(f)

@cron_bp.route("/cron/url-health", methods=["GET"])
def url_health_cron():
    cron_secret = os.environ.get("CRON_SECRET")
    if cron_secret:
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {cron_secret}":
            return jsonify({"error": "Unauthorized"}), 401

    total, flagged = run_health_check()
    save_report(total, flagged)
    return jsonify({"checked": total, "flagged": len(flagged)}), 200

@cron_bp.route("/url-health-status", methods=["GET"])
def url_health_status():
    report = load_report()
    return render_template("url_health_report.html", report=report)