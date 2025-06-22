# Use official Python image
FROM python:3.11-slim

# Install geoipupdate for downloading MaxMind databases
RUN apt-get update && apt-get install -y wget gnupg && \
    wget -O - https://github.com/maxmind/geoipupdate/releases/download/v6.1.0/geoipupdate_6.1.0_linux_amd64.deb | dpkg -i - && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Create DB directory and download MaxMind databases
RUN mkdir -p DB
# Create GeoIP.conf from environment variables during build
ARG MAXMIND_ACCOUNT_ID
ARG MAXMIND_LICENSE_KEY
RUN echo "AccountID ${MAXMIND_ACCOUNT_ID}" > GeoIP.conf && \
    echo "LicenseKey ${MAXMIND_LICENSE_KEY}" >> GeoIP.conf && \
    echo "EditionIDs GeoLite2-ASN GeoLite2-City GeoLite2-Country" >> GeoIP.conf && \
    geoipupdate -f GeoIP.conf && \
    mv /usr/share/GeoIP/GeoLite2-City.mmdb DB/ && \
    mv /usr/share/GeoIP/GeoLite2-ASN.mmdb DB/ && \
    mv /usr/share/GeoIP/GeoLite2-Country.mmdb DB/ && \
    rm GeoIP.conf

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run the FastAPI app with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 