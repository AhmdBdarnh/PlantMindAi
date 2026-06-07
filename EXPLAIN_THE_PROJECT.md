# PlantMind AI — הסבר מלא של הפרויקט

> כתוב בעברית. שמות טכניים נשארים באנגלית.

---

## 1. מה זה PlantMind AI?

מערכת חממה אוטומטית לגידול חסה. ה-Raspberry Pi 5 מנהל את כל החומרה, קורא חיישנים, שולח נתונים ל-cloud, ומחליט מתי להשקות ולדשן — הכל לבד.

**הבעיה שהיא פותרת:** גידול צמחים דורש ניטור רציף של טמפרטורה, לחות, אור, EC, pH ולחות קרקע. בלי מערכת אוטומטית, אדם צריך לבדוק ולהתאים הכל כל שעה.

**מה ייחודי בה — 3 שכבות AI:**
```
Layer 1 → שליטה מיידית (PID + hysteresis) — רץ כל שנייה
Layer 2 → יועץ AI (GPT) — ממליץ על setpoints כל יום ב-15:30
Layer 3 → מנהל תקציב — בודק את ההמלצות לפני שמאשרים
```

---

## 2. איך מריצים

```bash
# Backend
cd Backend
./venv/bin/python app.py

# Frontend
cd Frontend
npm start
```

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:5000`

---

## 3. ארכיטקטורה — כל החיבורים

```
React (port 3000)
      │ HTTP REST
      ▼
Flask (port 5000) ──► MongoDB Atlas   (כל הנתונים)
      │           ──► AWS S3          (תמונות)
      │           ──► OpenAI API      (AI המלצות)
      │           ──► HiveMQ MQTT     (telemetry)
      │           ──► Telegram API    (התראות)
      │           ──► Plant.id API    (בריאות צמח)
      │
    I2C (0x30)
      │
    ESP32 ──► PWM actuators
      │
  Sensors (GPIO/I2C/UART)
```

---

## 4. כל שירות חיצוני — מה שולחים ומה מקבלים

---

### 4.1 MongoDB Atlas

**מה זה:** בסיס נתונים בcloud. כל הנתונים נשמרים כאן.

**כתובת:** `MONGO_URI` ב-.env → `plantmindai.lma5ro9.mongodb.net`
**DB name:** `GreenHouse`

#### מה אנחנו שולחים (כותבים):

| Collection | מה כותבים | מתי |
|---|---|---|
| `sensors_data` | קריאת חיישן: `{sensor_id, sensor_value, timestamp}` | כל 10 שניות |
| `actuators_data` | מצב actuator: `{actuator_id, actuator_value, timestamp}` | upsert כל שינוי |
| `resources` | נפח מים/דשן/אנרגיה: `{resource_id, resource_value, unit}` | כל 10 שניות |
| `setpoints` | כל ה-setpoints בdoc אחד: `{temperature, humidity, light, ...}` | בכל שינוי |
| `system_state` | key-value: `{key: "total_water_liters", value: 47.3}` | כל כמה שניות |
| `pump_logs` | פעימה: `{pump_type, pulse_sec, duty_cycle, flow_rate, timestamp}` | אחרי כל פעימה |
| `plant_images` | metadata תמונה: `{image_path, timestamp}` | אחרי capture |
| `plant_health_results` | תוצאת Plant.id: `{is_healthy, health_probability, diseases}` | יומי 14:00 |
| `growth_measurements` | מדדי גדילה: `{area_cm2, height_cm, AGR, RGR, ...}` | יומי 14:15 |
| `ai_setpoint_recommendations` | המלצת Layer 2: `{changes, confidence, plant_status, status}` | יומי 15:30 |
| `layer3_decisions` | החלטת Layer 3: `{decision, gate_results, proposed_modifications}` | אחרי Layer 3 |
| `budget_config` | תצורת תקציב: `{daily_budget, water_budget, warning_threshold_pct}` | כשמשתמש מגדיר |
| `daily_costs` | בסיס יומי: `{baseline_water_liters, baseline_energy_wh, date}` | פעם ביום |

#### מה אנחנו מקבלים (קוראים):

| מה קוראים | מתי |
|---|---|
| `setpoints` — כל ה-setpoints הנוכחיים | בהפעלת הbackend |
| `system_state` — totals שנשמרו (מים, אנרגיה, דשן) | בהפעלת הbackend |
| `sensors_data` — ממוצעי 24 שעות | Layer 2 בונה context לGPT |
| `plant_health_results` — 7 אחרונות | Layer 2 בונה context |
| `growth_measurements` — 7 אחרונות | Layer 2 בונה context |
| `pump_logs` — היסטוריית משאבות | Layer 2 + ממשק Resources |
| `ai_setpoint_recommendations` — אחרונה | Layer 3, ממשק AI Advisor |
| `budget_config` | Layer 3 Gate 3 |
| `daily_costs` | Layer 3 Gate 3 |
| `layer3_decisions` — אחרונה | ממשק Budget Manager |

**אם MongoDB לא זמין:** הbackend ממשיך לפעול. חיישנים נקראים, actuators פועלים. רק שמירת היסטוריה נכשלת.

---

### 4.2 AWS S3 (Simple Storage Service)

**מה זה:** אחסון תמונות ב-cloud.

**bucket:** `plant-mindai` (מ-.env)
**region:** `eu-west-1`

#### מה שולחים לS3:

| תיקייה (prefix) | מה | מתי |
|---|---|---|
| `captures/` | תמונות JPEG מכל המצלמות | יומי 14:00 (health capture) |
| `growth_capture_input/` | תמונות JPEG לניתוח גדילה | יומי 14:10 |
| `growth_outputs/` | תמונות עם annotations מניתוח הגדילה | יומי 14:15 (plant-growth-calculator) |
| `health-checks/` | תמונות מ-manual health check | לפי דרישה |

**פורמט שליחה:**
```python
s3_handler.upload_bytes(img_bytes, object_key)
# img_bytes = JPEG bytes
# object_key = "captures/2026-06-02T14-00-00/camera_1.jpg"
```

#### מה מקבלים מS3:

**Presigned URL** — קישור זמני (שעה אחת) לצפייה בתמונה דרך הדפדפן:
```
https://plant-mindai.s3.eu-west-1.amazonaws.com/captures/...?X-Amz-Signature=...
```

**הורדה לניתוח גדילה:**
```python
s3_handler.download_last_x_images(prefix='growth_capture_input/', x=3)
# מוריד את 3 התמונות האחרונות לתיקייה מקומית זמנית
# plant-growth-calculator קורא אותן מהדיסק המקומי
```

**רשימת קבצים:**
```python
s3_handler.list_files(prefix)
# מחזיר: [{key, size, last_modified, url}, ...]
```

**הגבלות:**
- URL פג תוקף אחרי שעה — הممשק מחדש URL בכל בקשה
- תמונות נשמרות לצמיתות אלא אם מוחקים ידנית

---

### 4.3 OpenAI API (Layer 2)

**מה זה:** GPT מנתח את מצב הצמח וממליץ על setpoints.

**מודל:** מ-.env: `OPENAI_MODEL` — ברירת מחדל `gpt-4o`

#### מה שולחים לOpenAI:

**System message:**
```
"You are an expert hydroponic lettuce cultivation AI advisor.
You ONLY output valid JSON. No markdown fences, no extra text."
```

**User message — prompt מובנה עם 8 sections:**
```
SECTION 1: CURRENT SETPOINTS
  temperature=23.0°C, humidity=68%, light=60, soil_ec=750, ...

SECTION 2: LIVE SENSOR READINGS
  air_temp=25.8°C, humidity=79.4%, EC=100 µS/cm, pH=7.9, moisture=11.4%

SECTION 3: 24-HOUR SENSOR STATISTICS
  avg_temp=24.5, avg_humidity=74.2, avg_EC=685, ...

SECTION 4: PLANT HEALTH (last 7 checks)
  2026-06-01: is_healthy=True, probability=71.4%
  diseases: [...]

SECTION 5: GROWTH MEASUREMENTS (last 7)
  area=45cm², height=12cm, AGR=0.8, growth=2.3%

SECTION 6: ACTUATOR STATES
  light=ON (DC=2450), fan=ON (DC=4095), heater=OFF

SECTION 7: PUMP HISTORY & RESOURCE USAGE
  water pulses today: 3, avg pulse=1.2s
  total water: 47.3L, energy: 1200Wh

SECTION 8: DATA QUALITY NOTES
  collection_timestamp, missing data, data ages

+ OPTIMAL LETTUCE RANGES (hardcoded)
+ MAXIMUM ALLOWED CHANGES (safety limits)
+ REQUIRED JSON RESPONSE FORMAT
```

**פרמטרים לAPI:**
```python
model=OPENAI_MODEL,
temperature=0.2,          # שמרנות גבוהה
max_completion_tokens=2000 # (16000 למודלי thinking)
```

#### מה מקבלים מOpenAI:

**JSON מובנה:**
```json
{
  "plant_status": "slightly_stressed",
  "problem_detected": true,
  "severity": "low",
  "confidence": 0.72,
  "plant_stability_score": 0.68,
  "growth_assessment": "growing_well",
  "changes": [
    {
      "parameter": "soil_ec",
      "current_value": 750,
      "recommended_value": 850,
      "difference": 100,
      "reason": "EC trending below target...",
      "risk_level": "low"
    }
  ],
  "no_change_reason": {
    "temperature": "Already at optimal 23°C",
    "light": "Sensor may not reflect actual LED intensity"
  },
  "environment_issues": [
    {
      "description": "Air temperature slightly above optimal",
      "current_value": 25.8,
      "optimal_range": "18–24°C"
    }
  ],
  "warnings": ["EC sensor reading 100 µS/cm — may be sensor error"],
  "detailed_explanation": "...",
  "data_quality": "medium"
}
```

**אחרי קבלת התשובה:**
1. Layer 2 validates כל שינוי מול SAFETY_LIMITS
2. שומר ב-MongoDB עם status=`pending`
3. מפעיל Layer 3 אוטומטית
4. שולח Telegram

**עלות:** כל קריאה ≈ 2000–3000 tokens. מוגבל ל-3 קריאות ביום.

---

### 4.4 Plant.id API v3

**מה זה:** AI לבדיקת בריאות צמחים מתמונות.

**URL:** `https://plant.id/api/v3/health_assessment`
**API Key:** מ-.env: `PLANT_ID_API_KEY`

#### מה שולחים לPlant.id:

**HTTP POST:**
```json
{
  "images": [
    "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAA...",
    "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAA...",
    "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAA..."
  ]
}
```

**query params:**
```
?details=local_name,description,url,treatment,classification,common_names,cause
&language=en
```

**Headers:**
```
Api-Key: je18ysqgEm3v9hMtQXx4IPrIREAaFINKgqusoo5yqTTtOa1lhk
Content-Type: application/json
```

**מה שולחים:** 3 תמונות JPEG כ-base64 strings (אחת מכל מצלמה).

#### מה מקבלים מPlant.id:

**HTTP 201 → JSON:**
```json
{
  "result": {
    "is_healthy": {
      "binary": true,
      "probability": 0.714
    },
    "disease": {
      "suggestions": [
        {
          "name": "Botrytis cinerea",
          "probability": 0.12,
          "details": {
            "local_name": "Gray mold",
            "description": "Fungal disease...",
            "cause": "High humidity + poor air circulation",
            "treatment": {
              "biological": ["Trichoderma harzianum"],
              "chemical": ["Iprodione"],
              "prevention": ["Reduce humidity", "Improve ventilation"]
            },
            "url": "https://plant.id/..."
          }
        }
      ]
    }
  },
  "status": "COMPLETED"
}
```

**מה אנחנו מחזירים מה-parse:**
```python
{
  "success": True,
  "is_healthy": True,
  "health_probability": 71.4,    # אחוז בריאות
  "diseases": [
    {
      "name": "Botrytis cinerea",
      "probability": 12.0,       # % סיכוי
      "description": "...",
      "treatment": {...}
    }
  ]
}
```

**שמירה ב-MongoDB:** `plant_health_results`
**שימוש ב-Layer 2:** הציון והמחלות נכנסים ל-section 4 של הprompt

**שגיאות:**
- `401` → API key לא תקין
- `429` → אזלו credits
- `timeout` → 30 שניות timeout

---

### 4.5 HiveMQ MQTT

**מה זה:** broker ל-messaging. שידור נתוני חיישנים ל-cloud וקבלת פקודות.

**host:** `114fcbcf879e4e88a21d9f0bd7ab1ccc.s1.eu.hivemq.cloud`
**port:** `8883` (TLS מוצפן)
**user/pass:** SmartGreenHouse / SmartGreenHouse2025

#### מה אנחנו מפרסמים (Publish) — נשלח מהBackend לCloud:

| Topic | ערך | תדירות |
|---|---|---|
| `env_monitoring_system/sensors/air_temperature_C` | `25.8` | כל 10s |
| `env_monitoring_system/sensors/air_humidity` | `79.4` | כל 10s |
| `env_monitoring_system/sensors/light_intensity` | `62.1` | כל 10s |
| `env_monitoring_system/sensors/soil_ph` | `7.9` | כל 10s |
| `env_monitoring_system/sensors/soil_ec` | `100` | כל 10s |
| `env_monitoring_system/sensors/soil_temp` | `25.4` | כל 10s |
| `env_monitoring_system/sensors/soil_humidity` | `11.4` | כל 10s |
| `env_monitoring_system/sensors/water_flow` | `0.0` | כל 10s |
| `env_monitoring_system/sensors/fertilizer_flow` | `0.0` | כל 10s |
| `env_monitoring_system/sensors/voltage` | `228.4` | כל 10s |
| `env_monitoring_system/sensors/current` | `1.2` | כל 10s |
| `env_monitoring_system/resources/energy` | `1200.3` | כל 10s |
| `env_monitoring_system/resources/water_amount` | `47.3` | כל 10s |
| `env_monitoring_system/resources/fertilizer_amount` | `0.5` | כל 10s |
| `env_monitoring_system/actuators/heater/state` | `0` / `1` | בכל שינוי |
| `env_monitoring_system/actuators/light/state` | `0` / `1` | בכל שינוי |
| `env_monitoring_system/actuators/water_pump/state` | `0` / `1` | בכל שינוי |
| `env_monitoring_system/actuators/fan/state` | `0` / `1` | בכל שינוי |
| `env_monitoring_system/actuators/fertilizer_pump/state` | `0` / `1` | בכל שינוי |

#### מה אנחנו מקבלים (Subscribe) — פקודות מ-cloud לBackend:

| Topic | מה עושה | ערך |
|---|---|---|
| `env_monitoring_system/actuators/heater/dc` | מגדיר duty cycle לheater | `0`–`4095` |
| `env_monitoring_system/actuators/light/dc` | מגדיר duty cycle ל-LED | `0`–`4095` |
| `env_monitoring_system/actuators/water_pump/dc` | מגדיר duty cycle למשאבת מים | `0`–`4095` |
| `env_monitoring_system/actuators/fan/dc` | מגדיר duty cycle למאוורר | `0`–`4095` |
| `env_monitoring_system/actuators/fertilizer_pump/dc` | מגדיר duty cycle למשאבת דשן | `0`–`4095` |
| `loops/setpoints/temperature` | משנה setpoint טמפרטורה | `23.0` |
| `loops/setpoints/light_intensity` | משנה setpoint אור | `600` |
| `loops/setpoints/soil_moisture` | משנה setpoint לחות קרקע | `45.0` |
| `loops/setpoints/water_flow` | משנה setpoint זרימת מים | `2.0` |
| `loops/setpoints/fertilizer_flow` | משנה setpoint זרימת דשן | `0.5` |
| `loops/setpoints/operation_mode` | משנה מצב פעולה | `manual` / `autonomous` |

**שימוש:** MQTT מאפשר לשלוט במערכת גם ממכשירים אחרים (לא רק הfrontend) — למשל אפליקציית ניטור חיצונית.

---

### 4.6 Telegram Bot API

**מה זה:** שליחת הודעות לטלפון כשיש בעיה.

**URL:** `https://api.telegram.org/bot{TOKEN}/sendMessage`
**chat_id:** `902586320` (מ-.env: `TELEGRAM_CHAT_ID`)

#### מה שולחים לTelegram:

**HTTP POST:**
```json
{
  "chat_id": "902586320",
  "text": "⚠️ *WARNING* — Soil EC High\n\nComponent: EC/pH Sensor\nValue: 1650 µS/cm\nAllowed: 100–1600 µS/cm\nAction: Fertilizer pump OFF",
  "parse_mode": "Markdown"
}
```

#### מה מקבלים מTelegram:

```json
{
  "ok": true,
  "result": {
    "message_id": 4521,
    "chat": {"id": 902586320},
    "text": "...",
    "date": 1748865000
  }
}
```

או שגיאה:
```json
{"ok": false, "error_code": 429, "description": "Too Many Requests"}
```

#### אילו התראות נשלחות:

| פונקציה | מתי | חומרה | Cooldown |
|---|---|---|---|
| `alert_sensor_error` | חיישן החזיר None/NaN | WARNING | 10 דקות |
| `alert_sensor_lock` | 3 כשלות → נעילה | WARNING | 10 דקות |
| `alert_moisture_high` | לחות > 75% | WARNING | 10 דקות |
| `alert_moisture_critical` | לחות < T-H-10 | CRITICAL | 2 דקות |
| `alert_dangerous_ec` | EC >= 2000 | DANGER | 2 דקות |
| `alert_ec_high` | EC >= 1600 | WARNING | 10 דקות |
| `alert_ec_above_target` | EC > 1000 | WARNING | 10 דקות |
| `alert_ec_low` | EC < 550 | WARNING | 10 דקות |
| `alert_ph_critical` | pH < 4.8 | CRITICAL | 2 דקות |
| `alert_ph_warning` | pH < 5.2 או > 7.5 | WARNING | 10 דקות |
| `alert_actuator_failure` | pump ON נכשל 10 פעמים | CRITICAL | 2 דקות |

**Cooldown:** אותה התראה לא תישלח שוב עד שיחלוף הזמן. מונע spam.

**אם Telegram לא זמין:** הbackend לא נופל. ממשיך לפעול. רק מדפיס לterminal.

---

## 5. חומרה — חיישנים ו-Actuators

### חיישנים

| חיישן | חיבור | מה מחזיר | שימוש |
|---|---|---|---|
| **DHT22** | GPIO 26 | טמפ °C + לחות % | PID טמפ, Layer 2 |
| **ADS1115 ch0** | I2C | לחות קרקע analog → % | Layer 2 בלבד |
| **ADS1115 ch1** | I2C | עוצמת אור units | PID אור |
| **RS485 7-in-1** | UART /dev/ttyAMA0 | pH, EC, לחות%, טמפ קרקע, N, P, K | **שתי המשאבות** |
| **PZEM-004T** | UART /dev/ttyAMA1 | V, A, W, Wh, Hz | מעקב חשמל |
| **YF-S201 מים** | GPIO 12 | דופקים → L/min | נפח מים |
| **YF-S201 דשן** | GPIO 16 | דופקים → L/min | נפח דשן |

### Actuators (ESP32 I2C 0x30)

| Actuator | Pin | Channel | DC קבוע | מי שולט |
|---|---|---|---|---|
| LED strip 1 | 16 | 0 | PID (0–4095) | Light loop |
| LED strip 2 | 15 | 5 | PID (0–4095) | Light loop |
| Heater | 17 | 1 | PID (0–4095) | Temp loop |
| Heater fan | 18 | 2 | PID (0–4095) | Temp loop |
| Ventilator | 19 | 3 | 4095 (day) / 1024 (night) | Fan schedule |
| Water pump | 33 | 4 | **1800 תמיד** | Moisture loop |
| Fertilizer pump | 25 | 6 | **2662 תמיד** | EC loop |

---

## 6. Layer 1 — Control Loops

**קובץ:** `Backend/control_loops.py`

### 6.1 לולאת טמפרטורה
- **חיישן:** DHT22
- **PID:** KP=1034, KI=1.52, KD=0, deadband=1°C, sample=10s
- **output > 0** → Heater + Heater fan ON
- **output < 0** → Ventilator ON (רק אם fan schedule כבוי)
- **output = 0** → הכל כבוי

### 6.2 לולאת אור
- **חיישן:** ADS1115 ch1
- **PID:** KP=20, KI=7.5, KD=0.1, sample=0.1s
- **setpoint > 0** → PID שולח duty cycle לשני LED strips
- **setpoint = 0** → LEDs כבויים
- ⚠️ רץ כל 100ms → עומס I2C → חייב לעצור לפני פעולת משאבה

### 6.3 לוח זמנים מאוורר
- **06:00–20:00** → `fan_day_duty` (ברירת מחדל 4095 = 100%)
- **20:00–06:00** → `fan_night_duty` (ברירת מחדל 1024 = 25%)
- בדיקה כל 60 שניות
- ערכים נקראים מה-setpoints כל cycle

### 6.4 לולאת לחות קרקע (משאבת מים)
- **חיישן:** RS485
- **בדיקה:** כל 30 שניות
- **אחרי פעימה:** ממתין **3 שעות** (ABSORB_WAIT_SEC=10800)
- **DC קבוע:** 1800
- **hard cap:** 3 שניות מקסימום

**בנדים דינמיים:**
```
T = soil_moisture_setpoint (45%)
H = soil_hysteresis (12%)

moisture >= T           → כבוי
T-H   <= moisture < T  → כבוי (מקובל: 33–45%)
T-H-5 <= moisture < T-H → 1s פעימה (28–33%)
T-H-10<= moisture < T-H-5 → 1.5s פעימה (23–28%)
moisture < T-H-10       → 2s פעימה + CRITICAL טלגרם (<23%)
```

### 6.5 לולאת EC (משאבת דשן)
- **חיישנים:** RS485 — EC + pH
- **בדיקה:** כל שעה
- **אחרי פעימה:** ממתין **5 שעות** (SETTLE_WAIT_SEC=18000)
- **DC קבוע:** 2662
- **hard cap:** 2 שניות מקסימום

**שרשרת החלטות:**
```
EC >= 2000 → DANGER: כבוי + מים לדילול + Telegram DANGER
EC >= 1600 → כבוי + Telegram WARNING
EC > 1000  → כבוי + Telegram WARNING
EC >= ec_target → כבוי
EC >= ec_target-200 → כבוי (מקובל)
EC >= ec_target-400 → 1s פעימה
EC < ec_target-400  → 1.5s פעימה
EC < 550   → Telegram WARNING (נמוך באופן מוחלט)
```

---

## 7. Layer 2 — AI Setpoint Advisor

**קובץ:** `Backend/ai_setpoint_advisor.py`

**מתי:** כל יום 15:30, או ידנית `POST /api/ai-advisor/run`

**Pipeline:**
```
1. אוסף נתונים מ-sensor cache + MongoDB (8 sections)
2. בונה prompt טקסטואלי
3. שולח ל-OpenAI GPT
4. מקבל JSON עם המלצות
5. validates כל שינוי מול SAFETY_LIMITS
6. שומר ב-MongoDB (status: pending/needs_manual_review/invalid)
7. מפעיל Layer 3 אוטומטית
8. שולח Telegram
```

**Setpoints נעולים — GPT לא יכול לשנות:**
- Water Flow, Fertilizer Flow, Operation Mode

**גבולות בטיחות:**
| פרמטר | מקסימום | דחייה |
|---|---|---|
| Temperature | ±1°C | ±2°C |
| Soil pH | ±0.2 | ±0.3 |
| Soil EC | ±100 µS/cm | ±200 µS/cm |
| Soil Moisture | ±10% | ±15% |
| Light | ±100 | ±300 |

---

## 8. Layer 3 — Budget Manager

**קובץ:** `Backend/layer3_budget_manager.py`

**כלל:** Layer 3 לעולם לא מפעיל actuators. כל שינוי = אישור משתמש בלבד.

### שלושה שערים:

**שער 1 — Sensor Safety:**
- לחות קרקע < 20% → BLOCK
- EC > 2500 → BLOCK
- pH < 4.5 או > 8.0 → BLOCK
- טמפ > 35°C → BLOCK

**שער 2 — Plant Health:**
- stability_score >= 0.70 + גדילה תקינה → PASS
- stability_score 0.40–0.70 → MARGINAL
- stability_score < 0.40 או נתונים ישנים > 48h → FAIL

**שער 3 — Budget:**
- בודק: water_cost/water_budget, electricity/electricity_budget, total/daily_budget
- < threshold (80%) → OK
- >= threshold → WARNING
- > 100% → OVER_BUDGET

### החלטות:

| החלטה | מתי | Approve |
|---|---|---|
| APPROVE | הכל תקין + תקציב OK | ✅ |
| MODIFY | הכל תקין + תקציב חרג (מציע קיצוצים) | ✅ |
| BLOCK | שער 1 או 2 נכשל | ❌ |
| ALERT_ONLY | בריאות שולית + תקציב לא OK | ✅ |

---

## 9. מצבי הפעלה

### Manual Mode
- כל control loops עוצרים
- Frontend שולט ישירות על actuators
- Fan schedule עוצר

### Autonomous Mode
- כל loops פועלים
- משאבות חסומות עד קריאה תקפה ראשונה
- Mode משוחזר מMongoDB בהפעלה

---

## 10. כל ה-Threads

| Thread | פונקציה | אינטרוול |
|---|---|---|
| flask_thread | HTTP server | event-driven |
| serial_logger_thread | הדפסה לterminal | 1s |
| temperature_thread | PID טמפ | 10s |
| light_thread | PID אור | 0.1s |
| soil_thread | לחות קרקע | 30s |
| fertilizer_thread | EC + דשן | 3600s |
| app_thread | sensor polling + MQTT + DB | 10s/1s |
| fan_schedule_thread | לוח זמנים מאוורר | 60s |
| daily_capture_thread | health capture | יומי 14:00 |
| daily_growth_capture_thread | growth capture | יומי 14:10 |
| daily_growth_thread | growth analysis | יומי 14:15 |
| daily_ai_advisor_thread | AI advisor | יומי 15:30 |

---

## 11. בטיחות I2C

Light PID רץ כל 100ms ושולח I2C לESP32.
לפני כל פעימה:
```python
light_pause_event.clear()  # עוצר light loop
time.sleep(0.2)            # ממתין שיעצור
# fire pump
light_pause_event.set()    # מחדש light loop
```
ללא guard זה → I2C collision → pump OFF נכשל → משאבה ממשיכה לפעול!

---

## 12. לוח זמנים יומי

```
06:00 → מאוורר 100%
14:00 → צילום + Plant.id health check → plant_health_results
14:10 → צילום לגדילה → growth_capture_input/
14:15 → ניתוח גדילה → growth_measurements
15:30 → AI Advisor (GPT) → ai_setpoint_recommendations + Layer 3
20:00 → מאוורר 25%

כל 30s  → בדיקת לחות קרקע
כל שעה → בדיקת EC + דשן
כל 10s  → קריאת חיישנים + MongoDB + MQTT
```

---

## 13. REST API — כל ה-Endpoints

### Core
| Method | Route | מה עושה |
|---|---|---|
| GET | `/api/health` | סטטוס backend |
| GET | `/api/sensors` | כל נתוני חיישנים + משאבים + עלויות |
| GET | `/api/actuators` | duty cycles + fan schedule |
| GET/POST | `/api/setpoints` | קריאה/עדכון setpoints |
| GET/POST | `/api/operation_mode` | manual / autonomous |

### Actuators
| Method | Route | Body |
|---|---|---|
| POST | `/api/actuators/water_pump` | `{"state":"on"}` או `{"duty_cycle":1800}` |
| POST | `/api/actuators/fertilizer_pump` | אותו דבר |
| POST | `/api/actuators/light` | אותו דבר |
| POST | `/api/actuators/fan` | אותו דבר |
| POST | `/api/actuators/heater` | אותו דבר |

### Camera / Health
| Method | Route | מה עושה |
|---|---|---|
| GET | `/api/plant-health/latest` | תוצאת Plant.id אחרונה |
| GET | `/api/plant-health/history` | היסטוריה |
| POST | `/api/plant_health` | הפעלה ידנית |
| GET | `/api/pump-logs?limit=50` | לוג פעימות משאבה |
| GET | `/api/frame/<cam_id>` | JPEG מ-cam 1/2/4 |
| GET | `/video_c1` `/video_c2` `/video_c4` | MJPEG stream |

### Growth
| Method | Route | מה עושה |
|---|---|---|
| GET | `/api/growth/latest` | מדידת גדילה אחרונה |
| GET | `/api/growth/history` | היסטוריה |
| POST | `/api/growth/run-latest-s3` | הפעלה ידנית |

### Layer 2
| Method | Route | מה עושה |
|---|---|---|
| GET | `/api/ai-advisor/latest` | המלצה אחרונה |
| POST | `/api/ai-advisor/run` | הפעלה ידנית |
| POST | `/api/ai-advisor/<id>/approve` | אישור — מחיל setpoints |
| POST | `/api/ai-advisor/<id>/reject` | דחייה |

### Layer 3
| Method | Route | מה עושה |
|---|---|---|
| POST | `/api/layer3/run` | הפעלה |
| GET | `/api/layer3/latest` | החלטה אחרונה |
| POST | `/api/layer3/approve` | אישור |
| POST | `/api/layer3/reject` | דחייה |
| GET/POST | `/api/layer3/budget-config` | תצורת תקציב |
| POST | `/api/layer3/run-test` | הרצת בדיקה (ללא DB) |

### Plant Cycle
| Method | Route | מה עושה |
|---|---|---|
| POST | `/api/new-plant-cycle` | איפוס מונים — בטוח |
| POST | `/api/reset_resources` | מחיקת collections — לא הפיך |

---

## 14. Frontend — 9 דפים

| דף | URL hash | API עיקרי |
|---|---|---|
| Dashboard | `#dashboard` | `/api/sensors`, `/api/setpoints` |
| Plant Environment | `#environment` | `/api/sensors` |
| Actuator Control | `#actuators` | `/api/actuators`, `/api/operation_mode` |
| Resource Consumption | `#resources` | `/api/pump-logs`, `/api/sensors` |
| Plant Health | `#health` | `/api/plant-health/latest` |
| Plant Growth | `#growth` | `/api/growth/latest` |
| Live Cams | `#livecams` | `/video_c1`, `/api/capture_sessions` |
| AI Setpoint Advisor | `#ai-advisor` | `/api/ai-advisor/*` |
| Budget Manager | `#layer3` | `/api/layer3/*` |

**F5:** שומר מיקום דרך URL hash — `http://pi:3000/#layer3`

---

## 15. תרחיש יום מלא

```
08:00 — System רץ ב-autonomous mode
         soil_thread בודק כל 30s: moisture=28%, target=45%, H=12%
         28% < band_1s (28%) → 1s pulse
         → light_pause → pump ON 1s → pump OFF → light_resume
         → pump_log saved → ממתין 3 שעות

11:00 — fertilizer_thread בודק: EC=400, target=750
         400 >= ec_pulse_1s (350) → 1s pulse
         EC < 550 → Telegram "EC נמוך"
         → pump ON 1s → pump OFF → ממתין 5 שעות

14:00 — capture: 3 מצלמות → S3 captures/ + Plant.id
         מקבל: health=71%, diseases=[]
         שומר ב-plant_health_results

14:15 — growth analysis: S3 growth_capture_input/ → plant-growth-calculator
         מקבל: area=45cm², AGR=0.8, growth=2.3%
         שומר ב-growth_measurements

15:30 — AI Advisor: מאסף נתונים → OpenAI GPT
         שולח: כל sensor stats + health + growth + pump history
         מקבל JSON: "העלה soil_ec מ-750 ל-850"
         validates → שומר pending → Layer 3 אוטומטי

15:30 — Layer 3: Gate 1 PASS + Gate 2 PASS + Gate 3 OK → APPROVE
         שומר ב-layer3_decisions

16:00 — משתמש נכנס לAI Advisor:
         רואה: "soil_ec 750 → 850"
         לוחץ Approve → POST /api/ai-advisor/<id>/approve
         setpoints: soil_ec = 850
         fertilizer loop: ec_target=850, ec_close=650

20:00 — fan_schedule: מאוורר → 1024 (25%)
```

---

## 16. דברים שאסור לשנות

| מה | קובץ | למה |
|---|---|---|
| `CAM_CALIBRATION` | `plant-growth-calculator/functions.py` | מכויל לחומרה פיזית |
| `ESP32_I2C_ADDRESS = 0x30` | `config.py` | כתובת חומרה |
| PWM channels (0,1,2,3,4,5,6) | `app.py` | חייבים להתאים לESP32 firmware |
| `PUMP_DC = 1800` | `control_loops.py` | מכויל לזרימה נכונה |
| `FERT_DC = 2662` | `control_loops.py` | מכויל לזרימה נכונה |
| `MOISTURE_MIN_PLAUSIBLE = 5.0` | `control_loops.py` | הגנה מ-pump על נתון שגוי |
| I2C pause guard | `control_loops.py` | pump OFF חייב להצליח |
| Startup delays (1s, 5s) | `app.py` | ESP32 צריך זמן |

---

## 17. שאלות / נקודות לבדיקה

| נקודה | קובץ |
|---|---|
| `light setpoint = 60` — נמוך מאוד (רגיל 600–800). האם LED דולק? | setpoints ב-MongoDB |
| `soil moisture = 11%` — מתחת לsafety floor (20%). חיישן RS485 תקין? | פיזית |
| `soil EC = 100 µS/cm` — נמוך מאוד. sensor dead (< 50 = invalid)? | פיזית |
| `FAN_SCHEDULE_TEST_ENABLED` — שם מטעה. וודא שהוא True ב-production | `control_loops.py` |
| ABSORB=3h, SETTLE=5h — שונו בשיחה זו. מתאים לסוג הגידול? | `control_loops.py` |
