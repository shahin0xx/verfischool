# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app
# Install dependencies
COPY  ./requirements.txt /app/requirements.txt

RUN apt-get update && apt-get install -y cmake build-essential libopenblas-dev liblapack-dev libx11-dev libgtk-3-dev
RUN pip install --no-cache-dir -r requirements.txt


COPY . .
RUN python3 manage.py migrate






# Copy project
COPY . /app/

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["python3", "manage.py", "runserver", "0.0.0.0:8000"]