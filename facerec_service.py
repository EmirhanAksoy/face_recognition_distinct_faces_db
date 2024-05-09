from os import listdir
from os.path import isfile, join, splitext
import face_recognition
from flask import Flask , request ,jsonify
from flask_cors import CORS
from PIL import Image    
import logging
import pyodbc
import uuid 
import numpy
import os
import time

# Create flask app
app = Flask(__name__)
CORS(app)


db_server = 'tcp:sqlserver'
db_name = 'WhoIs'
db_username = 'sa'
db_password = 'Admin123*_!'
dbConnection = {}
max_retries = 5
retry_interval_seconds = 5
retry_count = 0
image_encodings = []

os.makedirs(os.path.join(os.getcwd(), 'faces'), exist_ok=True)

FACES_FOLDER_PATH = os.path.join(os.getcwd(), 'faces')

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

logging.info("App started")

all_drivers = pyodbc.drivers()

# Filter drivers for SQL Server
sql_server_drivers = [driver for driver in all_drivers if 'SQL Server' in driver]

logging.info(pyodbc.drivers())

# Print the list of SQL Server drivers
for driver in sql_server_drivers:
    logging.info(driver)


logging.info("Waiting for database connection ...")

while retry_count < max_retries:
    try:
        dbConnection = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=' + db_server +
                      ';DATABASE=' + db_name +
                      ';UID=' + db_username +
                      ';PWD=' + db_password)
        print("Connected to database")
        break  
    except pyodbc.Error as ex:
        print("Failed to connect to the database:", ex)
        print("Retrying in {} seconds...".format(retry_interval_seconds))
        retry_count += 1
        time.sleep(retry_interval_seconds)

if retry_count == max_retries:
    print("Failed to establish a connection after {} retries. Exiting...".format(max_retries))
    exit()

cursor = dbConnection.cursor()


def load_image_encodings(cursor, image_encodings):
    cursor.execute("SELECT FaceId, FacePath FROM Faces")
    existing_faces = cursor.fetchall()

    if len(existing_faces) :
      for face_id, face_path in existing_faces:
         singleFaceImageFromDb = face_recognition.load_image_file(face_path)
         singleFaceImageEncodings = face_recognition.face_encodings(singleFaceImageFromDb)
         if len(singleFaceImageEncodings) :
            singleImageEndcodingFromDb = singleFaceImageEncodings[0]
            image_encoding = [numpy.array(singleImageEndcodingFromDb)]
            image_encodings.append({
            "face_id" : face_id,
            "face_path" : face_path,
            "image_encoding" : image_encoding
            })

def detect_faces_in_image_new(file_stream):
    
    img = face_recognition.load_image_file(file_stream)

    # Get face locations and encodings for any faces in the uploaded image
    face_locations = face_recognition.face_locations(img)
    # Initialize variables
    faceCountOnUploadedImage = len(face_locations)
    faces = []
   
    if faceCountOnUploadedImage:
        for i in range(len(face_locations)):
            currentFaceLocation = face_locations[i]
            single_face_encoding_from_uploaded_image = face_recognition.face_encodings(img, [currentFaceLocation])
            single_face_encoding_array =  numpy.array(single_face_encoding_from_uploaded_image)
            if len(image_encodings) :
                matchFound = False
                for image_encoding_item in image_encodings:
                    distanceBetweenDbAndUploadImage = face_recognition.face_distance(image_encoding_item["image_encoding"],single_face_encoding_array)[0]
                        # If the distance is below a threshold, consider it a match
                    if distanceBetweenDbAndUploadImage < 0.6:
                        matchFound = True
                        faces.append({"id": image_encoding_item["face_id"], "dist": distanceBetweenDbAndUploadImage})
                        break
                # If nonMatchingFaceLocations list count greater than 0 insert missing faces into db and return list
                if not matchFound:
                    insert_newly_found_images(img, faces, currentFaceLocation,single_face_encoding_array)
            else :
               insert_newly_found_images(img, faces, currentFaceLocation,single_face_encoding_array)             
               
    return {"count": faceCountOnUploadedImage, "faces": faces}

def insert_newly_found_images(img, faces, currentFaceLocation,single_face_encoding):
    unique_face_id = str(uuid.uuid4())
    top, right, bottom, left = currentFaceLocation
    faceImage = img[top:bottom, left:right]
    final = Image.fromarray(faceImage)
    final.seek(0)
    face_path = os.path.join(FACES_FOLDER_PATH,unique_face_id)+'.png'
    final.save(face_path)
    cursor.execute("INSERT INTO Faces (FaceId, FacePath) VALUES (?, ?)",
                                unique_face_id, face_path)
    dbConnection.commit()
    faces.append({"id": unique_face_id, "dist": 0.0})
    image_encodings.append({
         "face_id" : unique_face_id,
         "face_path" : face_path,
         "image_encoding" : single_face_encoding
    })

load_image_encodings(cursor, image_encodings)  

# <Controllers>

@app.route('/detect_faces', methods=['POST'])
def detect_faces():
    # Check if a valid image file was uploaded
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Empty filename"}), 400

    # Detect faces in the uploaded image
    faces_info = detect_faces_in_image_new(file)

    # Return the detected faces information
    return jsonify(faces_info)

@app.route('/get_cached_encodings', methods=['GET'])
def get_cached_encodings():
    return jsonify(image_encodings)

if __name__ == "__main__":
    print("Starting WebServer...")
    app.run(host='0.0.0.0', port=8080, debug=False)
