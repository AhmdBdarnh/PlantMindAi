"""
telegram_alerts.py — Email notification system for PlantMind AI.

Sends alert emails when abnormal events occur in sensors, actuators, or the
backend system.  (The module keeps its original name so the rest of the
codebase — which imports `send_telegram_alert` and the `alert_*` helpers —
keeps working unchanged.  Internally it now delivers email instead of Telegram.)

Configuration (from .env):
    ALERT_EMAIL_FROM=your_sender@gmail.com        # Gmail account that SENDS the alerts
    ALERT_EMAIL_APP_PASSWORD=xxxxxxxxxxxxxxxx      # 16-char Gmail App Password (NOT the login password)
    ALERT_EMAIL_TO=ahmds3b@gmail.com               # recipient (default already set)
    SMTP_HOST=smtp.gmail.com                        # optional override
    SMTP_PORT=587                                   # optional override (587 = STARTTLS)

All logic is here — other files only call the helper functions.
"""

import os
import time
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# ── Configuration ─────────────────────────────────────────────────────────────

SMTP_HOST                = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT                = int(os.getenv('SMTP_PORT', '587'))
ALERT_EMAIL_FROM         = os.getenv('ALERT_EMAIL_FROM', '').strip()
# Gmail shows App Passwords grouped with spaces (e.g. "aflj ueqj tdve lcwy");
# strip all whitespace so login works whether or not the spaces are kept.
ALERT_EMAIL_APP_PASSWORD = os.getenv('ALERT_EMAIL_APP_PASSWORD', '').replace(' ', '')
ALERT_EMAIL_TO           = os.getenv('ALERT_EMAIL_TO', 'ahmds3b@gmail.com').strip()

# Email is only active when a sender account + app password are configured.
EMAIL_ENABLED = bool(ALERT_EMAIL_FROM and ALERT_EMAIL_APP_PASSWORD)

# ── Cooldown settings ─────────────────────────────────────────────────────────
# Same alert will not be re-sent until the cooldown expires.

COOLDOWN_SEC = {
    'INFO':     1800,   # 30 minutes
    'WARNING':   600,   # 10 minutes
    'CRITICAL':  120,   #  2 minutes
    'DANGER':    120,   #  2 minutes
}

# ── Internal cooldown state ───────────────────────────────────────────────────

_cooldown_lock = threading.Lock()
_last_sent: dict = {}   # alert_key → timestamp (float)


# ── Core send function ────────────────────────────────────────────────────────

def send_telegram_alert(
    title:           str,
    message:         str,
    severity:        str  = "WARNING",
    component:       str  = None,
    current_value          = None,
    allowed_range:   str  = None,
    action_taken:    str  = None,
    recommendation:  str  = None,
    data:            dict = None,
) -> bool:
    """
    Send an alert EMAIL with cooldown and full error handling.

    (Name kept as `send_telegram_alert` for backward compatibility — it now
    delivers email instead of a Telegram message.)

    Returns True if the email was dispatched, False if skipped (cooldown /
    disabled) or failed.  The backend will NEVER crash if email sending fails.
    """
    # UI notification (bell/toast) — UI only, independent of email, never raises.
    # Its own dedup window mirrors the email cooldown to avoid spam.
    try:
        import notifications
        notifications.create_notification(
            'sensor_warning',
            'critical' if severity.upper() in ('CRITICAL', 'DANGER') else 'warning',
            title, message,
            category='sensor', link='dashboard',
            meta={'component': component, 'value': current_value},
            dedup_key=f"sensor:{title}|{component or ''}",
            dedup_window_sec=COOLDOWN_SEC.get(severity.upper(), 600),
            already_emailed=EMAIL_ENABLED,
        )
    except Exception as _ntf_err:
        print(f"[Notifications] sensor alert skipped: {_ntf_err}")

    if not EMAIL_ENABLED:
        print(f"[Email] DISABLED (set ALERT_EMAIL_FROM + ALERT_EMAIL_APP_PASSWORD in .env). "
              f"Would send [{severity}] {title}: {message}")
        return False

    alert_key = f"{title}|{component or ''}"
    cooldown  = COOLDOWN_SEC.get(severity.upper(), 600)

    with _cooldown_lock:
        last = _last_sent.get(alert_key, 0)
        if (time.time() - last) < cooldown:
            return False   # still on cooldown — skip silently
        _last_sent[alert_key] = time.time()

    subject = _build_subject(title, severity)
    body    = _build_message(
        title, message, severity, component,
        current_value, allowed_range, action_taken, recommendation, data,
    )

    # Send in a background thread so a slow SMTP handshake never blocks the
    # control loops. The cooldown above is already recorded synchronously.
    threading.Thread(
        target=_send_email_safe,
        args=(subject, body, severity, title),
        daemon=True,
        name='EmailAlert',
    ).start()
    return True


# Backward/forward-compatible aliases — same behavior, clearer name.
def send_email_alert(*args, **kwargs) -> bool:
    return send_telegram_alert(*args, **kwargs)


def send_alert(*args, **kwargs) -> bool:
    return send_telegram_alert(*args, **kwargs)


def _send_email_safe(subject: str, body: str, severity: str, title: str) -> None:
    """Open an SMTP connection and deliver one email. Never raises."""
    try:
        msg = MIMEMultipart()
        msg['From']    = ALERT_EMAIL_FROM
        msg['To']      = ALERT_EMAIL_TO
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(ALERT_EMAIL_FROM, ALERT_EMAIL_APP_PASSWORD)
            server.sendmail(ALERT_EMAIL_FROM, [ALERT_EMAIL_TO], msg.as_string())

        print(f"[Email] Sent [{severity}] {title} → {ALERT_EMAIL_TO}")
    except Exception as e:
        print(f"[Email] ERROR (backend continues): {e}")


def _build_subject(title: str, severity: str) -> str:
    icons = {'INFO': 'ℹ️', 'WARNING': '⚠️', 'CRITICAL': '🚨', 'DANGER': '🔴'}
    icon  = icons.get(severity.upper(), '⚠️')
    return f"{icon} PlantMind AI [{severity.upper()}] — {title}"


def _build_message(
    title, message, severity, component,
    current_value, allowed_range, action_taken, recommendation, data,
) -> str:
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    lines = [
        "PlantMind AI Alert",
        "==================",
        "",
        f"Title:      {title}",
        f"Severity:   {severity.upper()}",
        f"Time:       {ts}",
    ]
    if component:
        lines.append(f"Component:  {component}")
    lines.append(f"Problem:    {message}")
    if current_value is not None:
        lines.append(f"Current Value:  {current_value}")
    if allowed_range:
        lines.append(f"Allowed Range:  {allowed_range}")
    if action_taken:
        lines.append(f"Action Taken:   {action_taken}")
    if recommendation:
        lines.append(f"Recommendation: {recommendation}")
    if data:
        lines.append("")
        lines.append("Details:")
        for k, v in data.items():
            lines.append(f"  - {k}: {v}")

    lines.append("")
    lines.append("—")
    lines.append("This is an automated message from your PlantMind AI greenhouse system.")
    return "\n".join(lines)


# ── Helper functions — called from other modules ──────────────────────────────

def alert_sensor_error(sensor_name: str, value, reason: str = "Invalid reading"):
    send_telegram_alert(
        title         = "Sensor Error",
        message       = reason,
        severity      = "WARNING",
        component     = sensor_name,
        current_value = str(value),
        action_taken  = "Pump disabled for this cycle",
        recommendation= f"Check {sensor_name} wiring and RS485/I2C connection",
    )


def alert_sensor_lock(sensor_name: str, lock_minutes: int):
    send_telegram_alert(
        title         = "Sensor Lock — Pump Disabled",
        message       = f"Too many consecutive bad readings from {sensor_name}",
        severity      = "CRITICAL",
        component     = sensor_name,
        action_taken  = f"Pump locked for {lock_minutes} minutes",
        recommendation= f"Inspect {sensor_name} immediately",
    )


def alert_actuator_failure(actuator_name: str, command: str, attempts: int):
    send_telegram_alert(
        title         = "Actuator Command Failed",
        message       = f"Could not send '{command}' command after {attempts} attempts",
        severity      = "CRITICAL",
        component     = actuator_name,
        action_taken  = "Retried and aborted",
        recommendation= f"Check ESP32 connection and {actuator_name} hardware",
    )


def alert_pump_rate_limit(pump_name: str, count: int, max_count: int):
    send_telegram_alert(
        title         = "Pump Rate Limit Reached",
        message       = f"Activated {count}x in the last hour — limit is {max_count}x",
        severity      = "WARNING",
        component     = pump_name,
        action_taken  = "Activation skipped",
        recommendation= "Inspect irrigation system — may indicate a leak or sensor fault",
    )


def alert_dangerous_ec(ec_value: float):
    send_telegram_alert(
        title         = "DANGEROUS EC Level",
        message       = "EC is critically high — root burn risk!",
        severity      = "DANGER",
        component     = "EC Sensor / Fertilizer",
        current_value = f"{ec_value:.0f} µS/cm",
        allowed_range = "750 – 1999 µS/cm",
        action_taken  = "Fertilizer pump OFF, water dilution pulse activated",
        recommendation= "Check nutrient solution immediately and perform manual dilution",
    )


def alert_ec_above_target(ec_value: float):
    send_telegram_alert(
        title         = "EC Above Target",
        message       = "EC is above 950 µS/cm — above the target range for lettuce",
        severity      = "WARNING",
        component     = "EC Sensor / Fertilizer",
        current_value = f"{ec_value:.0f} µS/cm",
        allowed_range = "target: 850 µS/cm  |  OK range: 750–950 µS/cm",
        action_taken  = "Fertilizer pump OFF",
        recommendation= "Monitor EC — reduce feeding or increase watering if EC keeps rising",
    )


def alert_ec_high(ec_value: float):
    send_telegram_alert(
        title         = "EC Very High",
        message       = "EC is critically above the safe threshold (>= 1600 µS/cm)",
        severity      = "WARNING",
        component     = "EC Sensor / Fertilizer",
        current_value = f"{ec_value:.0f} µS/cm",
        allowed_range = "< 1600 µS/cm",
        action_taken  = "Fertilizer pump OFF",
        recommendation= "Monitor EC — may need manual dilution if it keeps rising",
    )


def alert_ec_low(ec_value: float):
    send_telegram_alert(
        title         = "EC Low",
        message       = "EC is below 600 µS/cm — nutrient level is too low for lettuce",
        severity      = "WARNING",
        component     = "EC Sensor / Fertilizer",
        current_value = f"{ec_value:.0f} µS/cm",
        allowed_range = "target: 850 µS/cm  |  minimum: 600 µS/cm",
        action_taken  = "Fertilizer pump pulsed (2 seconds)",
        recommendation= "Check fertilizer supply and dosing pump flow rate",
    )


def alert_ph_warning(ph_value: float, direction: str):
    tip = "Add pH Up solution to raise pH" if direction == "low" else "Add pH Down solution to lower pH"
    send_telegram_alert(
        title         = "pH Out of Safe Range",
        message       = f"pH is too {'low' if direction == 'low' else 'high'} — outside the allowed range for lettuce",
        severity      = "WARNING",
        component     = "pH Sensor",
        current_value = f"{ph_value:.2f}",
        allowed_range = "5.2 – 7.5",
        action_taken  = "Warning only — fertilizer pump not blocked",
        recommendation= tip,
    )


def alert_ph_critical(ph_value: float):
    send_telegram_alert(
        title         = "CRITICAL: pH Dangerously Low",
        message       = (
            f"Soil pH is critically low ({ph_value:.2f}) — below 4.8. "
            "At this level nutrient uptake is severely blocked and roots may sustain damage."
        ),
        severity      = "CRITICAL",
        component     = "pH Sensor",
        current_value = f"{ph_value:.2f}",
        allowed_range = "5.2 – 7.5  (critical threshold: 4.8)",
        action_taken  = "Warning only — add pH Up immediately",
        recommendation= "Add pH Up solution immediately and recheck within 30 minutes",
    )


def alert_moisture_critical(moisture: float):
    send_telegram_alert(
        title         = "Soil Moisture Critically Low",
        message       = "Soil is very dry — immediate irrigation triggered",
        severity      = "CRITICAL",
        component     = "Soil Moisture Sensor",
        current_value = f"{moisture:.1f}%",
        allowed_range = ">= 30%",
        action_taken  = "2-second water pump pulse fired",
        recommendation= "Check water supply and irrigation system",
    )


def alert_moisture_high(moisture: float):
    send_telegram_alert(
        title         = "Soil Moisture Too High",
        message       = "Soil moisture is above the allowed maximum",
        severity      = "WARNING",
        component     = "Soil Moisture Sensor",
        current_value = f"{moisture:.1f}%",
        allowed_range = "< 70%",
        action_taken  = "Water pump disabled",
        recommendation= "Check irrigation system and soil moisture sensor",
    )


def alert_temperature_error(error: str):
    send_telegram_alert(
        title         = "Temperature Sensor Error",
        message       = f"Failed to read DHT22: {error}",
        severity      = "WARNING",
        component     = "DHT22 Temperature/Humidity",
        action_taken  = "Control loop cycle skipped",
        recommendation= "Check DHT22 wiring and GPIO pin",
    )


def alert_camera_failure(camera_id, error: str):
    send_telegram_alert(
        title         = "Camera Capture Failed",
        message       = f"Could not capture frame: {error}",
        severity      = "WARNING",
        component     = f"Camera {camera_id}",
        action_taken  = "Camera skipped in this session",
        recommendation= "Check camera USB/CSI connection",
    )


def alert_s3_failure(s3_key: str, error: str):
    send_telegram_alert(
        title         = "S3 Upload Failed",
        message       = f"Could not upload image to AWS S3: {error}",
        severity      = "WARNING",
        component     = "AWS S3",
        current_value = s3_key,
        action_taken  = "Image not stored in cloud",
        recommendation= "Check AWS credentials and internet connection",
    )


def alert_db_failure(operation: str, error: str):
    send_telegram_alert(
        title         = "Database Write Failed",
        message       = f"MongoDB '{operation}' failed: {error}",
        severity      = "WARNING",
        component     = "MongoDB",
        action_taken  = "Data may be lost for this cycle",
        recommendation= "Check MongoDB connection and disk space",
    )


def alert_system_crash(component: str, error: str):
    send_telegram_alert(
        title         = "System Loop Crashed",
        message       = f"Critical error in {component}: {error}",
        severity      = "CRITICAL",
        component     = component,
        action_taken  = "Loop will retry",
        recommendation= "Check backend logs immediately",
    )


def alert_temperature_high(temp: float):
    send_telegram_alert(
        title         = "Temperature Too High",
        message       = (
            "Air temperature is above the allowed threshold. "
            "High temperature increases plant stress and may slow lettuce growth, "
            "cause tip burn, and reduce yield."
        ),
        severity      = "WARNING",
        component     = "Temperature Sensor",
        current_value = f"{temp:.1f}°C",
        allowed_range = "up to 27°C",
        action_taken  = "Warning only — backend continues running",
        recommendation= "Check fan, cooling system, and airflow in the grow chamber",
    )


def alert_health_api_failure(error: str):
    send_telegram_alert(
        title         = "Plant Health API Failed",
        message       = f"Health API did not return a valid response: {error}",
        severity      = "WARNING",
        component     = "Plant Health API",
        action_taken  = "Backend continued running — health result not saved",
        recommendation= "Check API key, internet connection, API quota, and response format",
    )


def alert_no_sensor_data(minutes: int):
    send_telegram_alert(
        title         = "No Sensor Data Received",
        message       = f"No new sensor readings for {minutes} minutes — system may be stuck",
        severity      = "CRITICAL",
        component     = "Sensor System",
        action_taken  = "None — automatic intervention not possible",
        recommendation= "Restart the backend and check all sensor connections",
    )
