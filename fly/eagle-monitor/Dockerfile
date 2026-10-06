FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app.py .
COPY security_monitor.py .
COPY monitor_data_staleness.py .
COPY store.py .
COPY dashboard.py .
COPY site_traffic.py .

# Set environment variables
ENV PYTHONUNBUFFERED=1
# Use the pinned tzdata package, not the base image's timezone files, so billing days
# follow current BC clock rules (permanent UTC-7 from 2026; IANA 2026d = tzdata 2026.4)
ENV PYTHONTZPATH=""
ENV PORT=5000

# Expose port
EXPOSE 5000

# Run the application
CMD ["python", "app.py"]