"""User behavior for the Google-authenticated analyzer's operational store."""
import json
import time
from datetime import datetime, timezone

from .admin_insights import init
from .admin_metrics import database


def funnel(days):
    cutoff = time.time() - days * 86400
    with database() as db:
        init(db)
        counts = db.execute("""
            WITH visits AS (
                SELECT visitor, MIN(created) AS first_seen FROM ops_events
                WHERE action = 'visit' AND created >= ? GROUP BY visitor
            ), tasks AS (
                SELECT visits.visitor, reports.id, reports.state, ops_quality.finished
                FROM visits
                JOIN ops_journey AS started ON started.visitor = visits.visitor
                     AND started.action = 'analysis_started' AND started.created >= visits.first_seen
                JOIN reports ON reports.id = started.task AND reports.state != 'deleted'
                LEFT JOIN ops_quality ON ops_quality.task = reports.id
            )
            SELECT (SELECT COUNT(*) FROM visits),
                   COUNT(DISTINCT tasks.visitor),
                   COUNT(DISTINCT CASE WHEN tasks.state = 'completed' THEN tasks.visitor END),
                   COUNT(DISTINCT CASE WHEN tasks.state = 'completed' AND EXISTS (
                       SELECT 1 FROM ops_journey AS viewed
                       WHERE viewed.action = 'result_viewed' AND viewed.visitor = tasks.visitor
                         AND viewed.task = tasks.id AND viewed.created >= tasks.finished
                   ) THEN tasks.visitor END)
            FROM tasks
        """, (cutoff,)).fetchone()
    labels = ("Visitors", "Started analysis", "Completed analysis", "Viewed result")
    return [{"label": label, "count": count} for label, count in zip(labels, counts)]


def stream(days, limit, offset, action):
    cutoff = time.time() - days * 86400
    query = """
        WITH engine_reports AS (
            SELECT * FROM reports
            WHERE (owner LIKE 'gefei:%' OR owner LIKE 'gefei-staging:%') AND state != 'deleted'
        ), behavior AS (
            SELECT action, user_id, task, created, details
            FROM ops_journey
            WHERE action IN ('visit', 'file_selected', 'result_viewed', 'comparison_viewed')
            UNION ALL
            SELECT 'analysis_started', owner, id, created, '{}'
            FROM engine_reports
            UNION ALL
            SELECT CASE WHEN state = 'completed' THEN 'analysis_completed' ELSE 'analysis_failed' END,
                   owner, id, finished, '{}'
            FROM engine_reports JOIN ops_quality ON ops_quality.task = engine_reports.id
            WHERE state IN ('completed', 'failed')
        )
    """
    filters = "WHERE created >= ? AND (? IS NULL OR action = ?)"
    args = (cutoff, action, action)
    with database() as db:
        init(db)
        count = db.execute(query + f"SELECT COUNT(*) FROM behavior {filters}", args).fetchone()[0]
        rows = db.execute(query + f"""
            SELECT * FROM behavior {filters}
            ORDER BY created DESC, task, action LIMIT ? OFFSET ?
        """, (*args, limit, offset)).fetchall()

    logs = []
    for row in rows:
        details = json.loads(row["details"])
        if row["task"]:
            details["task"] = row["task"]
        logs.append({
            "action": row["action"], "user_id": row["user_id"], "details": details,
            "created_at": datetime.fromtimestamp(row["created"], timezone.utc).isoformat(),
        })
    return {"logs": logs, "count": count}
