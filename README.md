# Pi GPX Camera
*Pi GPX Camera* is a simple Python application designed to stream hardware encoded h.264 from a Raspberry Pi equiped with a HQ camera module, directly to a browser and allow recording of full res mjpeg stream. 


# Viewing
When server.py is running the feed can be vied from any broswer via the following urls. **_rpi_address_** is the ip address or hostname of your Raspberry Pi, and **_serverPort_** is the port you set in the configuration section.  
1. The primary viewing screen 
    ```
    http://<rpi_address>:<serverPort>/
    ```
2. The focus peaking screen 
    ```
    http://<rpi_address>:<serverPort>/focus/
    ```
3. The center reticle screen 
    ```
    http://<rpi_address>:<serverPort>/center/
    ```

# Installation
1. [Ensure the camera module is properly connected to the Raspberry Pi](https://projects.raspberrypi.org/en/projects/getting-started-with-picamera/2) with Bullseye or later based OS.


2. If Needed Disable legacy camera with `sudo raspi-config`

3. Bullseye and above come with Picamera2, if not installed then follow [Picamera2](https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf) documentation

    ``` sh
    sudo apt-get install python3-picamera2
    ```

5. Install the [Pi GPX Camera package](https://github.com/Revive-Our-Gulf/pi-gpx-camera) and create a venv with system-site-packages enabled
    ```
    mkdir repos
    cd repos
    git clone https://github.com/Revive-Our-Gulf/pi-gpx-camera.git
    cd ppi-gpx-camera
    python -m venv --system-site-packages 'venv'
    source ./venv/bin/activate
    pip install --upgrade pip
    pip install -e .
    ```


# Optional configuration
open server.py and edit the following section of code as needed. 
- The webserver will run on the port you set **_serverPort_** to.  
- Refer to the Picamera2 documentation for details on how to configure it. A lage number of options exist 


# Mavlink
Setup a MAV endpoint in Blueos as follows 
![BlueOS MAVLink Endpoint](readmeAssets/blueos-mavlink-endpoint.png)


# other
Disable legacy camera with `sudo raspi-config`



