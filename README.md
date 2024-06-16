# PROJECT IN PROGRESS 
# PROJECT UNDER TESTING
# License

This project consists of two main components:

1. **Firmware for ESP32 (MIT License)**: This component is licensed under the MIT License. See the `LICENSE` file for the full text.
2. **Python Program using BirdNET Analyzer (CC BY-NC-SA 4.0)**: The Python program integrates BirdNET Analyzer, which is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.

### Attribution

This project integrates BirdNET Analyzer, which requires proper attribution as specified in the license terms. You can view the full license here: https://creativecommons.org/licenses/by-nc-sa/4.0/.

# Bioaccoustic_esp32
This project aims to capture bird and other sounds using an ESP32 microcontroller and an INMP441 audio mems Mic. The recording can be controlled remotely over a local Wi-Fi network, allowing for real-time monitoring and adjustment of the audio capture process. (Currently under testing.)
# PIN INMP441
#### SD -----> 33
#### WS -----> 25
#### SCK ----> 32
#### L/R ----> GND
#### GND ----> GND
#### 3.3v ---> 3.3v

# PIN SDCARD (USE SDCARD MODULE WITH BUFFER)

#### MISO -----> 19
#### MOSI -----> 23
#### SCK ----> 18
#### CS ----> 5
#### GND ----> GND
#### VDD ---> 3.3v

# Recomended to remove AMS117 regulator from sdcard module
# Requirement
1. Visual Studio Code 
2. Platformio
3. Python
   Python Requirement
   1. Tkinter
   2. tqdm (non-GUI)
   3. zeroconf

# Python app in SRC (app.py)
