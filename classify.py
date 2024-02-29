import subprocess
import requests
import time
import datetime
import RPi.GPIO as GPIO
from model_inference import load_model, predict_image
from mfrc522 import SimpleMFRC522

rfid_reader = SimpleMFRC522()



model = load_model('/home/daniel/myproject/model/material_classification_model.pth')
GPIO.cleanup()
GPIO.setmode(GPIO.BCM)
TRIG = 23
ECHO = 24
GPIO.setup(TRIG, GPIO.OUT)
GPIO.setup(ECHO, GPIO.IN)

def get_distance():
    GPIO.output(TRIG, False)
    time.sleep(0.5)

    GPIO.output(TRIG, True)
    time.sleep(0.00001)
    GPIO.output(TRIG, False)

    while GPIO.input(ECHO) == 0:
        pulse_start = time.time()

    while GPIO.input(ECHO) == 1:
        pulse_end = time.time()

    pulse_duration = pulse_end - pulse_start
    distance = pulse_duration * 17150
    distance = round(distance, 2)
    
    return distance

def capture_image(file_name):
    file_path = f"/home/daniel/myproject/captured_images/{file_name}"
    command = ["libcamera-still", "-o", file_path]
    subprocess.run(command, check=True)
    
def send_disposal_event(rfid_id, material, disposal_time):
    url = 'http://172.20.10.4:8000/api/disposal/'
    data = {
        'rfid_id': rfid_id,
        'material': material,
        'disposal_time': disposal_time  
    }
    response = requests.post(url, json=data)
    return response.ok

def send_distance_update(distance):
    url = 'http://172.20.10.4:8000/api/bin_status/'
    data = {
        'distance': distance,
        'update_time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")  
    }
    response = requests.post(url, json=data)
    print("Distance update sent" if response.ok else "Failed to send distance update")


try:
    print('Starting measurement')
    last_sent_time = time.time()
    while True:
        distance = get_distance()
        print(f'Distance: {distance} cm')
        send_measured_distance(distance)
        
        if distance < 20:
            print("Please scan your RFID tag")
            user_id, _ = rfid_reader.read()
            print(f"RFID ID: {user_id}")
            
            print("Object detected close enough. Capturing image...")
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            image_name = f'object_{timestamp}.jpg'
            capture_image(image_name)
            
            print("Classifying object...")
            image_path = f"/home/daniel/myproject/captured_images/{image_name}"
            predicted_class = predict_image(image_path, model)
            print(f"Predicted class: {predicted_class}")
            
            disposal_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            print("Sending disposal event to server...")
            if send_disposal_event(user_id, predicted_class, disposal_time):
                print("Disposal event logged successfully.")
            else:
                print("Failed to log disposal event.")

        if time.time() - last_sent_time >= 300: 
            send_distance_update(distance)
            last_sent_time = time.time()
                
        time.sleep(1)

except KeyboardInterrupt:
    print("Program exited")
    GPIO.cleanup()
finally:
    GPIO.cleanup()
