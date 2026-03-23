# Smart Greenhouse Frontend

React-based control panel for the Smart Greenhouse system.

## Prerequisites

You need to install Node.js and npm first:

```bash
# Install Node.js and npm on Raspberry Pi
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

## Installation

1. Navigate to the frontend directory:
```bash
cd /home/mohamadaboria/Desktop/GreenHouse/NewProject/GreenHouseFrontend
```

2. Install dependencies:
```bash
npm install
```

## Running the Application

### 1. Start the Flask Backend (Terminal 1)

```bash
cd /home/mohamadaboria/Desktop/GreenHouse/NewProject/AboriaGreenHouse
python3 app.py
```

The backend will run on `http://localhost:5000`

### 2. Start the React Frontend (Terminal 2)

```bash
cd /home/mohamadaboria/Desktop/GreenHouse/NewProject/GreenHouseFrontend
npm start
```

The frontend will run on `http://localhost:3000`

## Features

### Sensor Readings
Click "Read Sensors" button to fetch current readings:
- Air Temperature & Humidity
- Light Intensity
- Soil pH, EC, Humidity, Temperature
- Water Flow & Amount
- Electrical measurements (Voltage, Current, Power, Energy)

### Actuator Controls
Control greenhouse equipment with ON/OFF buttons:
- 🔥 Heater
- 💡 Light Strips
- 🌀 Fan
- 💦 Water Pump

## API Endpoints

The frontend connects to these Flask backend endpoints:

- `GET /api/sensors` - Get all sensor readings
- `GET /api/actuators` - Get actuator states
- `POST /api/actuators/heater` - Control heater
- `POST /api/actuators/light` - Control lights
- `POST /api/actuators/fan` - Control fan
- `POST /api/actuators/water_pump` - Control water pump

## Troubleshooting

### CORS Errors
Make sure `flask-cors` is installed in the backend:
```bash
pip3 install flask-cors
```

### Connection Refused
- Check that Flask backend is running on port 5000
- Check that both apps are running on the same network
- Try accessing `http://localhost:5000/api/sensors` in your browser

### Port Already in Use
If port 3000 is busy:
```bash
PORT=3001 npm start
```
