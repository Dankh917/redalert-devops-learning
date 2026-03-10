#fectches the latest python 3.12 image from the docker hub
FROM python:3.12-slim 
#directory in the container where the app will be stored and run from
WORKDIR /app
#copies the requirements.txt file from the current directory to the /app directory in the container
COPY requirements.txt .
#installs the dependencies listed in the requirements.txt file using pip, with the --no-cache-dir option to reduce the size of the image by not caching the installed packages
RUN pip install --no-cache-dir -r requirements.txt
#copies all the files from the current directory (where the Dockerfile is located) to the /app directory in the container, which includes the application code and any other necessary files
COPY . .
#exposes port 8000 to allow external access to the application running inside the container. This means that when the container is run, it will listen for incoming connections on port 8000, which is the default port for FastAPI applications.
EXPOSE 8000
#specifies the command to run the application when the container starts. In this case, it uses uvicorn to run the FastAPI application defined in app.main:app, and it binds the server to all available network interfaces 
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

