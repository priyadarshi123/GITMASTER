# 1. Base image
FROM python:3.11-slim

# 2. Set working directory
WORKDIR /app

# 3. Copy requirements first (for caching)
COPY requirements.txt .

# 4. Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy rest of the code
COPY . .

# 6. Expose Streamlit port
EXPOSE 8501

# 7. Run app
CMD ["streamlit", "run", "master.py", "--server.address=0.0.0.0" "--server.port=8501", "--server.headless=true"]



# To build and run the Docker container locally:
# docker build -t pd-economy-app .
#docker image ls
# docker run -p 8501:8501 pd-economy-app
#docker ps


# To push container  from local system to dockerhub

##docker login
# docker tag pd-economy-app <your_dockerhub_username>/pd-economy-app:latest
# docker push <your_dockerhub_username>/pd-economy-app:latest


#To install docker in aws (ununtu vs amazon linux 2):
# 1. sudo apt update           or         sudo dnf update
# 2. sudo apt install docker.io -y   or         sudo dnf install docker -y
# 3. sudo systemctl start docker ==> start docker service
# 4. sudo systemctl enable docker ==> enable docker to start on boot
# 5. sudo usermod -aG docker $USER ==> add current user to docker group (optional, for running docker without sudo)




#On Linux or EC2 server

#docker pull priyadarshi123/pd-economy-app:latest
#docker run -d --name pd-economy-app-container --restart always -p 8501:8501 priyadarshi123/pd-economy-app:latest

