# 🌱 Smart Greenhouse Automation System

An advanced IoT-based greenhouse automation system with real-time monitoring, autonomous climate control, and web-based dashboard.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [System Architecture](#system-architecture)
- [Hardware Requirements](#hardware-requirements)
- [Software Requirements](#software-requirements)
- [Installation](#installation)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Configuration](#configuration)
- [Contributing](#contributing)
- [License](#license)

## 🎯 Overview

This project implements a complete greenhouse automation solution combining:
- **IoT Hardware**: Raspberry Pi 5, ESP32, and multiple environmental sensors
- **Backend**: Python Flask server with PID control algorithms
- **Frontend**: React-based web dashboard with real-time updates
- **Cloud Integration**: MQTT (HiveMQ), MongoDB Atlas, AWS S3

## ✨ Features

### Environmental Monitoring
- 🌡️ Air temperature and humidity (DHT22)
- 💡 Light intensity monitoring (TEMT6000)
- 🌿 Soil parameters: pH, EC, moisture, temperature, NPK (RS485 sensor)
- 💧 Water flow rate and total consumption tracking
- ⚡ Power consumption monitoring (PZEM-004T)

### Intelligent Control
- 🔥 **Heater Control**: PID-based temperature regulation
- 💡 **LED Grow Lights**: PID-controlled brightness (2x strips)
- 🌀 **Cooling Fan**: Variable speed control
- 💦 **Water Pump**: Automated irrigation with hysteresis control

### Operation Modes
- **Manual Mode**: Direct control via web dashboard
- **Autonomous Mode**: PID controllers maintain optimal conditions

### Web Dashboard
- 📊 Real-time sensor data display (auto-refresh every 3s)
- 🎛️ Power control sliders (0-100% for all actuators)
- 🔄 Mode switching (Manual/Autonomous)
- 📱 Responsive design for mobile access

### Cloud Features
- 📤 MQTT telemetry to HiveMQ Cloud
- 💾 Historical data storage in MongoDB Atlas
- 📸 Plant image storage in AWS S3
- 🔐 Secure encrypted connections (TLS)

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Raspberry Pi 5 (Backend)                   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐  │
│  │  Flask Server (Port 5000)                       │  │
│  │  • REST API                                     │  │
│  │  • PID Control Loops                            │  │
│  │  • MQTT Publisher/Subscriber                    │  │
│  └─────────────────────────────────────────────────┘  │
│           │              │              │              │
└───────────┼──────────────┼──────────────┼──────────────┘
            │              │              │
    ┌───────▼──────┐   ┌──▼───────┐  ┌──▼──────────┐
    │   Sensors    │   │  ESP32   │  │ Cloud       │
    │   (GPIO/I2C/ │   │(I2C 0x30)│  │ Services    │
    │    UART)     │   │          │  │ • HiveMQ    │
    └──────────────┘   └──┬───────┘  │ • MongoDB   │
                          │          │ • AWS S3    │
                    ┌─────▼─────┐    └─────────────┘
                    │ Actuators │
                    │ (PWM)     │
                    └───────────┘

    ┌─────────────────────────────────────────────────┐
    │     React Frontend (Port 3000)                  │
    │     • Dashboard                                 │
    │     • Real-time monitoring                      │
    │     • Manual controls                           │
    └─────────────────────────────────────────────────┘
```

## 🔧 Hardware Requirements

### Main Controller
- **Raspberry Pi 5** (8GB RAM recommended)
- microSD card (32GB minimum)
- Power supply (5V, 5A USB-C)

### Microcontroller
- **ESP32** Development Board
- Connected via I2C (address: 0x30)

### Sensors
- **DHT22**: Air temperature & humidity (GPIO 26)
- **TEMT6000**: Light intensity (ADS1115 channel 1)
- **VEML7700**: Alternative light sensor (I2C)
- **NPKPHCTH-S**: 7-in-1 soil sensor (RS485, /dev/ttyAMA0)
- **YF-S201**: Water flow sensor (GPIO 12)
- **PZEM-004T**: AC power meter (UART, /dev/ttyAMA1)
- **ADS1115**: 16-bit ADC (I2C)

### Actuators
- 2× UV LED grow light strips (PWM controlled)
- 50W heater with integrated fan
- Cooling fan (12V DC)
- Water pump (240L/h)
- 2× MOSFET modules (IRF540, 4 channels each)

### Additional Hardware
- Camera modules (2× Raspberry Pi Camera)
- RS485 to UART converter (MAX13487)
- Breadboard and jumper wires
- 12V/5V power supplies

## 💻 Software Requirements

### Backend (Raspberry Pi)
- Python 3.11+
- Flask web framework
- Libraries:
  - `adafruit-circuitpython-dht`
  - `adafruit-circuitpython-ads1x15`
  - `paho-mqtt`
  - `pymongo`
  - `boto3`
  - `simple-pid`
  - `flask-cors`
  - `pyserial`

### Frontend
- Node.js 16+ and npm
- React 18.2.0
- Modern web browser

### Cloud Services
- HiveMQ Cloud MQTT broker
- MongoDB Atlas cluster
- AWS account with S3 bucket

## 📥 Installation

### 1. Clone Repository
```bash
git clone https://github.com/yourusername/greenhouse-automation.git
cd greenhouse-automation
```

### 2. Backend Setup (Raspberry Pi)
```bash
# Navigate to backend directory
cd AboriaGreenHouse

# Create virtual environment
python3 -m venv envGreenHouse
source envGreenHouse/bin/activate

# Install dependencies
pip install -r docs/requirements.txt

# Configure credentials (edit with your details)
# - MQTT: mqtt_handler.py line 27
# - MongoDB: mongo_db_handler.py line 31
# - AWS: Run 'aws configure'
```

### 3. Frontend Setup
```bash
# Navigate to frontend directory
cd GreenHouseFrontend

# Install dependencies
npm install

# Start development server
npm start
```

### 4. Hardware Setup
- Connect sensors according to pin assignments (see docs/hardware.txt)
- Upload ESP32 firmware for PWM control
- Enable I2C and Camera interfaces on Raspberry Pi:
  ```bash
  sudo raspi-config
  # Interface Options → I2C → Enable
  # Interface Options → Camera → Enable
  ```

### 5. Start Backend
```bash
cd AboriaGreenHouse
source envGreenHouse/bin/activate
python3 app.py
```

## 🚀 Usage

### Access Dashboard
Open browser and navigate to:
```
http://localhost:3000
```

### Dashboard Features

#### Status Bar
- **Last Update**: Shows timestamp of last data refresh
- **Auto-Refresh**: Toggle automatic updates (every 3 seconds)
- **Refresh Now**: Manual refresh button

#### Operation Modes
- **Manual Mode**: Control actuators directly via dashboard
- **Autonomous Mode**: PID controllers maintain setpoints

#### Sensor Monitoring
Real-time display of:
- Air temperature/humidity
- Light intensity
- Soil conditions (pH, EC, moisture, temperature)
- Water usage
- Power consumption

#### Actuator Control
- **Power Sliders**: Adjust power from 0-100%
  - Heater: Temperature control
  - Lights: Brightness adjustment
  - Fan: Speed control
  - Pump: Flow rate control
- **Quick Controls**: ON/OFF buttons (50%/0%)

### API Endpoints

#### Sensors
- `GET /api/sensors` - Get all sensor readings

#### Actuators
- `GET /api/actuators` - Get actuator states
- `POST /api/actuators/heater` - Control heater
  ```json
  { "state": "on" }  // or "off"
  { "duty_cycle": 2048 }  // 0-4095
  ```
- `POST /api/actuators/light` - Control lights
- `POST /api/actuators/fan` - Control fan
- `POST /api/actuators/water_pump` - Control pump

#### Operation Mode
- `GET /api/operation_mode` - Get current mode
- `POST /api/operation_mode` - Set mode
  ```json
  { "mode": "manual" }  // or "autonomous"
  ```

#### Camera
- `GET /video_c1` - Camera 1 stream
- `GET /video_c2` - Camera 2 stream

## ⚙️ Configuration

### PID Controller Tuning
Edit `app.py` to adjust PID parameters:

```python
# Temperature Control (lines 265-267)
KP_TEMP = 1034.05
KI_TEMP = 1.52
KD_TEMP = 0.0

# Light Control (lines ~400-402)
KP_LIGHT = 20
KI_LIGHT = 7.5
KD_LIGHT = 0.1
```

### Setpoints
Default setpoints in `setpoints.py`:
- Temperature: 25°C
- Light Intensity: 1000 Lux
- Soil Moisture: 50%

### Auto-Refresh Interval
Edit `GreenHouseFrontend/src/App.js` line 162:
```javascript
}, 3000); // Change to desired milliseconds
```

## 🔐 Security Notes

- **Never commit credentials** to git
- Use environment variables for sensitive data
- Enable HTTPS for production deployments
- Implement authentication for remote access
- Keep firmware and software updated

## 📊 Data Storage

### Local Storage
- Water consumption: `consumption/water_amount.txt`
- Logs: Console output

### MongoDB Collections
- `sensors_data`: Time-series sensor readings
- `actuators_data`: Actuator state history
- `resources`: Energy and water consumption
- `plant_images`: Image metadata

### MQTT Topics
- Publish: `env_monitoring_system/sensors/*`
- Subscribe: `env_monitoring_system/actuators/*/dc`
- Setpoints: `loops/setpoints/*`

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📄 License

This project is licensed under the MIT License - see LICENSE file for details.

## 👨‍💻 Author

**Mohamad Aboria**
- GitHub: [@mohamadaboria](https://github.com/mohamadaboria)

## 🙏 Acknowledgments

- Adafruit for sensor libraries
- HiveMQ for MQTT broker
- MongoDB for database services
- AWS for cloud storage

## 📞 Support

For issues and questions:
- Open an issue on GitHub
- Check documentation in `/docs` folder

---

**Built with ❤️ for sustainable agriculture**
