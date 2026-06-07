"""
notifications.py — Backend-generated UI notifications, persisted in MongoDB.

This module is the single writer for in-app notifications shown in the React UI
(notification bell + toast). It is UI-only and NEVER sends email: critical email
alerts remain owned by the existing alert module and are completely unchanged.
For events that already trigger an email alert, that alert path also calls
create_notification(...) so the same event surfaces in the UI — the email
behaviour itself is untouched.

Design notes:
  * Every call is wrapped in try/except and is a no-op if the module has not been
    initialised, so notification creation can be safely added next to control,
    sensor and decision logic without ever being able to break it.
  * Duplicate/spam suppression is handled with an optional dedup_key plus a
    cooldown window (dedup_window_sec).
"""

import datetime
import threading

from utils.utils import _CUSTOM_PRINT_FUNC

_mongo = None
_id_lock = threading.Lock()
_counter = 0

VALID_SEVERITY = ('info', 'warning', 'critical')
VALID_CATEGORY = ('workflow', 'sensor', 'system')


def init(mongo_db_handler_obj):
    """Wire the MongoDB handler. Called once at startup."""
    global _mongo
    _mongo = mongo_db_handler_obj
    _CUSTOM_PRINT_FUNC("[Notifications] initialised")


def _next_id() -> str:
    """Monotonic, collision-resistant notification id (string)."""
    global _counter
    with _id_lock:
        _counter += 1
        return f"ntf{int(datetime.datetime.now().timestamp() * 1000)}{_counter}"


def create_notification(
    type, severity, title, message,
    *, category="workflow", link=None, meta=None,
    dedup_key=None, dedup_window_sec=0, already_emailed=False,
) -> bool:
    """Create one UI notification.

    Returns True if a notification was inserted, False if it was skipped
    (duplicate within the cooldown window) or failed. Never raises and never
    sends email.

    Args:
        type:     short machine string, e.g. "approval_required".
        severity: "info" | "warning" | "critical".
        title:    short headline shown in the bell/toast.
        message:  one-sentence description.
        category: "workflow" | "sensor" | "system".
        link:     optional UI page id to deep-link to ("layer3", "ai-advisor", …).
        meta:     optional dict of context (decision_id, rec_id, sensor_id, …).
        dedup_key:        if set with dedup_window_sec, suppresses repeats.
        dedup_window_sec: cooldown window in seconds for dedup_key.
        already_emailed:  record that this event also sent an email (no email here).
    """
    if _mongo is None:
        return False
    if severity not in VALID_SEVERITY:
        severity = 'info'
    if category not in VALID_CATEGORY:
        category = 'workflow'
    try:
        # Spam / duplicate guard
        if dedup_key and dedup_window_sec and dedup_window_sec > 0:
            if _mongo.get_recent_notification(dedup_key, dedup_window_sec):
                return False

        doc = {
            'notification_id': _next_id(),
            'type':       type,
            'category':   category,
            'severity':   severity,
            'title':      title,
            'message':    message,
            'link':       link,
            'meta':       dict(meta) if meta else {},
            'dedup_key':  dedup_key,
            'read':       False,
            'created_at': datetime.datetime.now().isoformat(),
        }
        if already_emailed:
            doc['meta']['emailed'] = True

        return bool(_mongo.insert_notification(doc))
    except Exception as e:
        _CUSTOM_PRINT_FUNC(f"[Notifications] Error creating notification: {e}")
        return False
