# Face Recognition Service

This repository contains a face recognition service written in Python. This is a forked version of the original repository, which can be found [here](https://github.com/JanLoebel/face_recognition).

## Docker

To run the face recognition service using Docker, follow these steps:

1. Clone this repository to your local machine:

    ```bash
    git clone https://github.com/EmirhanAksoy/face_recognition_distinct_faces_db.git
    ```

2. Build the Docker image:

    ```bash
    docker build -t face_service .
    ```

    This command will build the Docker image with the tag `face_service`.

3. Run a Docker container from the `face_service` image:

    ```bash
    docker run --name face-service-container -p 8080:8080 face_service
    ```

4. The face recognition service will now be accessible at `http://localhost:8080`.

## Configuration

If you need to customize the service or any configurations, you can modify the relevant files within the repository.

## License

This project is licensed under the [MIT License](LICENSE).
