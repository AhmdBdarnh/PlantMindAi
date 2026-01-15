from Actuators.actuators import GH_Actuators
import numpy as np
import time

act = GH_Actuators(0x30)
act.setup_heater_esp32(2, 0, 100, 0)
while True:
    # if act.set_heater_duty_cycle(np.random.randint(0, 4096)) == False:
    #     print("Failed to set heater duty cycle")
    # else:        
    #     act.toggle_esp32_onboard_led()
    #     print("Heater duty cycle set successfully")

    for i in range(0, 4096, 100):
        act.set_heater_duty_cycle(i)
        time.sleep(0.1)

    for i in range(4096, 0, -100):
        act.set_heater_duty_cycle(i)
        time.sleep(0.1)
