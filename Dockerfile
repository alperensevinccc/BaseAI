# Use a Python 3.9 slim base image
FROM python:3.9-slim

# Set the working directory to /app
WORKDIR /app

# Copy the requirements.txt file and install the dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code to the /app directory
COPY app.py .

# Expose port 5000
EXPOSE 5000

# Define the command to run the Flask application
CMD ["python", "app.py"]