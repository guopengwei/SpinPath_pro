# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY main.py .
COPY uploaded_slides ./uploaded_slides 
# The line above for 'uploaded_slides' is to ensure the directory exists at build time if needed.
# However, for runtime dynamic uploads, a volume mount is more appropriate.
# We'll create it here for completeness, but it will be typically overridden by a docker-compose volume.
RUN mkdir -p /app/uploaded_slides 

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define environment variable (optional, can be set in docker-compose too)
# ENV VAR_NAME value

# Run main.py when the container launches
# Use 0.0.0.0 to allow access from outside the container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
