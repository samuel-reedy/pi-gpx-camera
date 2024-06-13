#!/usr/bin/python3
import cv2

# Create a VideoCapture object and read from input file
cap = cv2.VideoCapture('/home/john/Downloads/transect-001 (3).avi')

# Check if camera opened successfully
if not cap.isOpened(): 
    print("Error opening video file")

# Create a window with normal size
cv2.namedWindow('Frame', cv2.WINDOW_NORMAL)
# Set the window size to 100 pixels width
ret, frame = cap.read()
if ret == True:
    width, height = frame.shape[1], frame.shape[0]
    cv2.resizeWindow('Frame', width*1000//width, height*1000//width)
# Read until video is completed
while(cap.isOpened()):
  
  # Capture frame-by-frame
  ret, frame = cap.read()
  if ret == True:

    # Display the resulting frame
    cv2.imshow('Frame', frame)

    # Press Q on keyboard to exit
    if cv2.waitKey(0) & 0xFF == ord('q'):
      break

  # Break the loop
  else: 
    break

# When everything done, release the video capture object
cap.release()

# Closes all the frames
cv2.destroyAllWindows()