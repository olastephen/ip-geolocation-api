# Use official Python image
FROM python:3.11-slim

# Install system dependencies for geoipupdate
RUN apt-get update && \
    apt-get install -y wget gnupg curl && \
    wget -O /tmp/geoipupdate.deb https://github.com/maxmind/geoipupdate/releases/download/v6.1.0/geoipupdate_6.1.0_linux_amd64.deb && \
    dpkg -i /tmp/geoipupdate.deb && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/geoipupdate.deb

# Set work directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create DB directory
RUN mkdir -p DB

# Create startup script
RUN echo '#!/bin/bash\n\
echo "Starting IP Geolocation API..."\n\
\n\
# Check if MaxMind credentials are provided\n\
if [ -n "$MAXMIND_ACCOUNT_ID" ] && [ -n "$MAXMIND_LICENSE_KEY" ]; then\n\
    echo "MaxMind credentials found. Downloading databases..."\n\
    \n\
    # Create GeoIP.conf\n\
    cat > GeoIP.conf << EOF\n\
AccountID $MAXMIND_ACCOUNT_ID\n\
LicenseKey $MAXMIND_LICENSE_KEY\n\
EditionIDs GeoLite2-ASN GeoLite2-City GeoLite2-Country\n\
EOF\n\
    \n\
    # Download databases\n\
    geoipupdate -f GeoIP.conf\n\
    \n\
    # Move databases to DB directory\n\
    if [ -f "/usr/share/GeoIP/GeoLite2-City.mmdb" ]; then\n\
        mv /usr/share/GeoIP/GeoLite2-City.mmdb DB/\n\
        echo "City database downloaded"\n\
    fi\n\
    if [ -f "/usr/share/GeoIP/GeoLite2-ASN.mmdb" ]; then\n\
        mv /usr/share/GeoIP/GeoLite2-ASN.mmdb DB/\n\
        echo "ASN database downloaded"\n\
    fi\n\
    if [ -f "/usr/share/GeoIP/GeoLite2-Country.mmdb" ]; then\n\
        mv /usr/share/GeoIP/GeoLite2-Country.mmdb DB/\n\
        echo "Country database downloaded"\n\
    fi\n\
    \n\
    # Clean up\n\
    rm -f GeoIP.conf\n\
    echo "Database download completed!"\n\
else\n\
    echo "MaxMind credentials not provided. Running without geolocation databases."\n\
    echo "Set MAXMIND_ACCOUNT_ID and MAXMIND_LICENSE_KEY environment variables to enable geolocation."\n\
fi\n\
\n\
# Start the FastAPI app\n\
exec uvicorn main:app --host 0.0.0.0 --port 8000\n\
' > /app/start.sh && chmod +x /app/start.sh

# Expose port
EXPOSE 8000

# Use the startup script
CMD ["/app/start.sh"] 
