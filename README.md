# IP Geolocation API

This project provides a powerful IP Geolocation API using FastAPI and the MaxMind GeoLite2 databases. The API returns geolocation, ASN, country, and reverse DNS information for IPv4 and IPv6 addresses. It includes a modern web dashboard with map visualization and supports CSV/JSON export, batch lookups, and more.

## Features
- **Local, privacy-friendly geolocation lookup**
- **Batch geolocation** (lookup multiple IPs at once)
- **ASN and Country lookup** (using GeoLite2-ASN and GeoLite2-Country)
- **Reverse DNS lookup**
- **Request logging** (IP, timestamp, endpoint, result, user-agent)
- **User-Agent and client IP detection** (auto-geolocate client if no IP provided)
- **Detailed location data** (postal code, subdivision, accuracy radius)
- **CSV/JSON export** for results
- **Dockerized for easy deployment**
- **Web dashboard** with map (Leaflet.js) for city lookups
- **IPv6 support**
- **Input validation** for IP addresses

## Prerequisites
- Python 3.7+
- [GeoLite2-City.mmdb](https://dev.maxmind.com/geoip/geolite2-free-geolocation-data), [GeoLite2-ASN.mmdb](https://dev.maxmind.com/geoip/geolite2-free-geolocation-data), and [GeoLite2-Country.mmdb](https://dev.maxmind.com/geoip/geolite2-free-geolocation-data) from MaxMind (requires free account)

## Setup
1. **Clone this repository or download the code.**
2. **Download the GeoLite2 database files:**
   - Sign up at [MaxMind](https://www.maxmind.com/en/geolite2/signup)
   - Download the City, ASN, and Country databases
   - Extract and place `GeoLite2-City.mmdb`, `GeoLite2-ASN.mmdb`, and `GeoLite2-Country.mmdb` in the `DB` directory
3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Running the API
Start the FastAPI server with Uvicorn:
```bash
uvicorn main:app --reload
```
The API will be available at [http://127.0.0.1:8000](http://127.0.0.1:8000)

## Docker Deployment
Build and run with Docker:
```bash
docker build -t ip-geolocation-api .
docker run -p 8000:8000 ip-geolocation-api
```

## Web Dashboard
Open [http://localhost:8000/](http://localhost:8000/) in your browser for a modern dashboard:
- Enter one or more IPs (IPv4 or IPv6)
- Select lookup type (City, ASN, Country, Reverse DNS)
- See results in a table
- For City lookups, see results on a map (Leaflet.js)

## API Usage
### Geolocate an IP Address
```
GET /geolocate?ip=8.8.8.8
```
Or omit `ip` to geolocate the client:
```
GET /geolocate
```

### Batch Geolocation
```
POST /geolocate/batch
Body: ["8.8.8.8", "1.1.1.1", "2001:4860:4860::8888"]
```

### ASN Lookup
```
GET /asn?ip=8.8.8.8
```

### Country Lookup
```
GET /country?ip=8.8.8.8
```

### Reverse DNS Lookup
```
GET /reverse_dns?ip=8.8.8.8
```

### CSV/JSON Export
Add `format=csv` to any geolocation endpoint:
```
GET /geolocate?ip=8.8.8.8&format=csv
POST /geolocate/batch?format=csv
```

## Input Validation
- Both IPv4 and IPv6 addresses are supported.
- Invalid IPs return a 400 error with a clear message.

## Request Logging
- All requests are logged to `requests.log` with timestamp, endpoint, IP, result, and user-agent.

## API Documentation
Interactive docs are available at:
- [Swagger UI](http://127.0.0.1:8000/docs)
- [ReDoc](http://127.0.0.1:8000/redoc)

## License
This project is for educational and personal use. The GeoLite2 database is licensed by MaxMind. #   i p - g e o l o c a t i o n - a p i  
 