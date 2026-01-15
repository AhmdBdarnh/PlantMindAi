import cv2

cap = cv2.VideoCapture(0)  # USB camera

if not cap.isOpened():
    print("❌ Could not open /dev/video0")
    exit()

ret, frame = cap.read()
if not ret:
    print("❌ Failed to read frame.")
else:
    print("✅ Frame captured from USB camera.")
    cv2.imwrite("usb_test.jpg", frame)
    print("🖼️ Saved image as usb_test.jpg")

cap.release()
