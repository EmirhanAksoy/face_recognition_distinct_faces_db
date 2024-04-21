from os import listdir, remove
from os.path import isfile, join, splitext
import face_recognition
from flask import Flask , request ,jsonify
from flask_cors import CORS
from werkzeug.exceptions import BadRequest
import io
from PIL import Image    
import logging
import pyodbc
import uuid 
import numpy
import os


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
    logging.error(driver)

# Your database connection parameters
db_server = 'tcp:sqlserver'
db_name = 'WhoIs'
db_username = 'sa'
db_password = 'Admin123*_!'

# Establish a connection to the database
dbConnection = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=' + db_server +
                      ';DATABASE=' + db_name +
                      ';UID=' + db_username +
                      ';PWD=' + db_password)

# Create a cursor object to execute SQL queries
cursor = dbConnection.cursor()

# Global storage for images
faces_dict = {}
persistent_faces = "/root/faces"

# Create flask app
app = Flask(__name__)
CORS(app)

# <Picture functions> #

# Define the detect_faces_in_image method
def detect_faces_in_image_new(file_stream):
    
    img = face_recognition.load_image_file(file_stream)

    # Get face locations and encodings for any faces in the uploaded image
    face_locations = face_recognition.face_locations(img)
    # Initialize variables
    faceCountOnUploadedImage = len(face_locations)
    faces = []

    cursor.execute("SELECT UniqueId, FacePath FROM Faces")
    existing_faces = cursor.fetchall()
    if faceCountOnUploadedImage:
        for i in range(len(face_locations)):
            currentFaceLocation = face_locations[i]
            singleFaceEncodingFromUploadImage = face_recognition.face_encodings(img, [currentFaceLocation])
            if len(existing_faces) :
                # Find if any match exists in db records
                matchFound = False
                for unique_id, image_path in existing_faces:
                    singleFaceImageFromDb = face_recognition.load_image_file(image_path)
                    singleImageEndcodingFromDb = face_recognition.face_encodings(singleFaceImageFromDb)[0]
                    distanceBetweenDbAndUploadImage = face_recognition.face_distance([numpy.array(singleImageEndcodingFromDb)], numpy.array(singleFaceEncodingFromUploadImage))[0]
                    logmessage = "Distance calculated as > "+str(distanceBetweenDbAndUploadImage)
                    logging.info(logmessage)
                    # If the distance is below a threshold, consider it a match
                    if distanceBetweenDbAndUploadImage < 0.6:
                        matchFound = True
                        faces.append({"id": unique_id, "dist": distanceBetweenDbAndUploadImage})
                        break
                # If nonMatchingFaceLocations list count greater than 0 insert missing faces into db and return list
                if not matchFound:
                    unique_idx = str(uuid.uuid4())
                    insert_newly_found_images(img, faces, currentFaceLocation, unique_idx)
            else :
               unique_idx = str(uuid.uuid4())
               insert_newly_found_images(img, faces, currentFaceLocation, unique_idx)             
               
    return {"count": faceCountOnUploadedImage, "faces": faces}

def insert_newly_found_images(img, faces, currentFaceLocation, unique_idx):
    top, right, bottom, left = currentFaceLocation
    faceImage = img[top:bottom, left:right]
    final = Image.fromarray(faceImage)
    final.seek(0)
    facePath = os.path.join(FACES_FOLDER_PATH,unique_idx)+'.png'
    final.save(facePath)
    cursor.execute("INSERT INTO Faces (UniqueId, FacePath) VALUES (?, ?)",
                                unique_idx, facePath)
    dbConnection.commit()
    faces.append({"id": unique_idx, "dist": 0.0})


def is_picture(filename):
    image_extensions = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in image_extensions


def get_all_picture_files(path):
    files_in_dir = [join(path, f) for f in listdir(path) if isfile(join(path, f))]
    return [f for f in files_in_dir if is_picture(f)]


def remove_file_ext(filename):
    return splitext(filename.rsplit('/', 1)[-1])[0]

def calc_face_encoding(image):
    # Currently only use first face found on picture
    loaded_image = face_recognition.load_image_file(image)
    faces = face_recognition.face_encodings(loaded_image)

    # If more than one face on the given image was found -> error
    if len(faces) > 1:
        raise Exception(
            "Found more than one face in the given training image.")

    # If none face on the given image was found -> error
    if not faces:
        raise Exception("Could not find any face in the given training image.")

    return faces[0]


def get_faces_dict(path):
    image_files = get_all_picture_files(path)
    return dict([(remove_file_ext(image), calc_face_encoding(image))
        for image in image_files])


def detect_faces_in_image(file_stream):
    # Load the uploaded image file
    img = face_recognition.load_image_file(file_stream)

    # Get face encodings for any faces in the uploaded image
    uploaded_faces = face_recognition.face_encodings(img)

    # Defaults for the result object
    faces_found = len(uploaded_faces)
    faces = []

    if faces_found:
        face_encodings = list(faces_dict.values())
        for uploaded_face in uploaded_faces:
            match_results = face_recognition.compare_faces(
                face_encodings, uploaded_face)
            for idx, match in enumerate(match_results):
                if match:
                    match = list(faces_dict.keys())[idx]
                    match_encoding = face_encodings[idx]
                    dist = face_recognition.face_distance([match_encoding],
                            uploaded_face)[0]
                    faces.append({
                        "id": match,
                        "dist": dist
                    })

    return {
        "count": faces_found,
        "faces": faces
    }

# <Picture functions> #

# <Controller>


# Define the endpoint to detect faces in an image
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


@app.route('/', methods=['POST'])
def web_recognize():
    file = extract_image(request)

    if file and is_picture(file.filename):
        # The image file seems valid! Detect faces and return the result.
        return jsonify(detect_faces_in_image(file))
    else:
        raise BadRequest("Given file is invalid!")


@app.route('/faces', methods=['GET', 'POST', 'DELETE'])
def web_faces():
    # GET
    if request.method == 'GET':
        return jsonify(list(faces_dict.keys()))

    # POST/DELETE
    file = extract_image(request)
    if 'id' not in request.args:
        raise BadRequest("Identifier for the face was not given!")

    if request.method == 'POST':
        app.logger.info('%s loaded', file.filename)
        # HINT jpg included just for the image check -> this is faster then passing boolean var through few methods
        # TODO add method for extension persistence - do not forget abut the deletion
        file.save("{0}/{1}.jpg".format(persistent_faces, request.args.get('id')))
        try:
            new_encoding = calc_face_encoding(file)
            faces_dict.update({request.args.get('id'): new_encoding})
        except Exception as exception:
            raise BadRequest(exception)

    elif request.method == 'DELETE':
        faces_dict.pop(request.args.get('id'))
        remove("{0}/{1}.jpg".format(persistent_faces, request.args.get('id')))

    return jsonify(list(faces_dict.keys()))


def extract_image(request):
    # Check if a valid image file was uploaded
    if 'file' not in request.files:
        raise BadRequest("Missing file parameter!")

    file = request.files['file']
    if file.filename == '':
        raise BadRequest("Given file is invalid")

    return file
# </Controller>


if __name__ == "__main__":
    print("Starting by generating encodings for found images...")
    # Calculate known faces
    faces_dict = get_faces_dict(persistent_faces)
    print(faces_dict)

    # Start app
    print("Starting WebServer...")
    app.run(host='0.0.0.0', port=8080, debug=False)
