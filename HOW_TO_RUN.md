# 🌱 How to Run the Greenhouse System

## Prerequisites
- Python virtual environment is set up in `AboriaGreenHouse/venv`
- Node.js and npm are installed
- MongoDB Atlas connection configured

---

## 🚀 Quick Start (Run Everything)

### Step 1: Start the Backend (Flask/Python)
Open **Terminal 1** and run:

```bash
cd Backend
./venv/bin/python app.py
```


### Step 2: Start the Frontend (React)
Open **Terminal 2** and run:

```bash
cd Frontend
npm start
```



## 🌐 Access Your Application

After both terminals are running:

- **Frontend (React UI):** http://localhost:3000
- **Backend API:** http://localhost:5000
- **Network Access:** http://10.100.102.60:3000 (from other devices)

---

## 🛑 How to Stop

### Stop Backend:
- Go to Terminal 1
- Press `Ctrl + C`

### Stop Frontend:
- Go to Terminal 2
- Press `Ctrl + C`

---

## 🔧 Troubleshooting

### Backend Issues

**Problem:** Module not found errors
```bash
cd /home/mohamadaboria/Desktop/GreenHouse/NewProject/AboriaGreenHouse
./venv/bin/pip install -r requirements.txt
```

**Problem:** MongoDB connection error
- Check your internet connection
- Verify MongoDB Atlas credentials in `app.py` line 31-32

**Problem:** GPIO/sensor errors
- Make sure you're running on Raspberry Pi
- Check hardware connections

### Frontend Issues

**Problem:** `npm: command not found`
```bash
sudo apt update
sudo apt install nodejs npm
```

**Problem:** Dependencies not installed
```bash
cd /home/mohamadaboria/Desktop/GreenHouse/NewProject/GreenHouseFrontend
npm install
```

**Problem:** Port 3000 already in use
```bash
# Kill the process using port 3000
sudo lsof -ti:3000 | xargs kill -9
```

---

## 🔄 Run in Background (Optional)

### Backend in Background:
```bash
cd /home/mohamadaboria/Desktop/GreenHouse/NewProject/AboriaGreenHouse
nohup ./venv/bin/python app.py > backend.log 2>&1 &
```

Check logs:
```bash
tail -f backend.log
```

Stop background backend:
```bash
pkill -f "python app.py"
```

### Frontend in Background:
```bash
cd /home/mohamadaboria/Desktop/GreenHouse/NewProject/GreenHouseFrontend
nohup npm start > frontend.log 2>&1 &
```

Stop background frontend:
```bash
pkill -f "react-scripts start"
```

---

## 📋 Available API Endpoints

### Sensors
- `GET http://localhost:5000/api/sensors` - Get all sensor data

### Actuators
- `GET http://localhost:5000/api/actuators` - Get actuator status
- `POST http://localhost:5000/api/actuators/heater` - Control heater
- `POST http://localhost:5000/api/actuators/light` - Control lights
- `POST http://localhost:5000/api/actuators/fan` - Control fan
- `POST http://localhost:5000/api/actuators/water_pump` - Control water pump

### Operation Mode
- `GET http://localhost:5000/api/operation_mode` - Get current mode
- `POST http://localhost:5000/api/operation_mode` - Set operation mode

### Video Streams
- `GET http://localhost:5000/video_c1` - Camera 1 stream
- `GET http://localhost:5000/video_c2` - Camera 2 stream

---

## 📝 System Architecture

```
┌─────────────────────┐
│   React Frontend    │  Port 3000
│   (User Interface)  │
└──────────┬──────────┘
           │ HTTP Requests
           ▼
┌─────────────────────┐
│   Flask Backend     │  Port 5000
│   (Python API)      │
└──────────┬──────────┘
           │
    ┌──────┴──────┬──────────┬──────────┐
    ▼             ▼          ▼          ▼
┌────────┐  ┌─────────┐  ┌──────┐  ┌────────┐
│ Sensors│  │ MongoDB │  │ MQTT │  │ GPIO   │
│        │  │  Atlas  │  │      │  │ Hardware│
└────────┘  └─────────┘  └──────┘  └────────┘
```

---

## 🎯 Quick Command Reference

| Task | Command |
|------|---------|
| Start Backend | `cd AboriaGreenHouse && ./venv/bin/python app.py` |
| Start Frontend | `cd GreenHouseFrontend && npm start` |
| Stop (any) | `Ctrl + C` |
| View Backend Logs | Terminal output or `tail -f backend.log` |
| Install Backend Deps | `./venv/bin/pip install -r requirements.txt` |
| Install Frontend Deps | `npm install` |
| Check Processes | `ps aux | grep python` or `ps aux | grep node` |

---

## ✅ Checklist Before Running

- [ ] MongoDB Atlas connection string is correct in `app.py`
- [ ] MQTT broker credentials are valid
- [ ] Python virtual environment exists (`venv` folder)
- [ ] Node modules are installed (`node_modules` folder)
- [ ] Hardware sensors/actuators are connected (if using physical devices)
- [ ] You're on the same network if accessing from another device

---

## 📞 Need Help?

If something isn't working:
1. Check the terminal output for error messages
2. Verify all dependencies are installed
3. Make sure both backend and frontend are running
4. Check your internet connection for MongoDB/MQTT
5. Verify hardware connections on Raspberry Pi

---

**Created:** 2025-12-17
**Location:** `/home/mohamadaboria/Desktop/GreenHouse/NewProject/HOW_TO_RUN.md`
