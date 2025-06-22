from fastapi import FastAPI, HTTPException, Query, Body, Request
from geoip2.database import Reader
from geoip2.errors import AddressNotFoundError
import os
from typing import List, Dict, Any, Optional
import socket
import datetime
from fastapi.responses import JSONResponse, Response
import csv
import io
from fastapi.staticfiles import StaticFiles
import ipaddress
import subprocess
import sys

app = FastAPI()

# Initialize database readers (optional)
reader = None
asn_reader = None
country_reader = None

def download_databases():
    """Download MaxMind databases if credentials are provided"""
    account_id = os.getenv('MAXMIND_ACCOUNT_ID')
    license_key = os.getenv('MAXMIND_LICENSE_KEY')
    
    if not account_id or not license_key:
        print("MaxMind credentials not found in environment variables.")
        print("Set MAXMIND_ACCOUNT_ID and MAXMIND_LICENSE_KEY to enable automatic database download.")
        return False
    
    try:
        # Create DB directory if it doesn't exist
        os.makedirs('DB', exist_ok=True)
        
        # Create GeoIP.conf file
        config_content = f"""AccountID {account_id}
LicenseKey {license_key}
EditionIDs GeoLite2-ASN GeoLite2-City GeoLite2-Country
"""
        
        with open('GeoIP.conf', 'w') as f:
            f.write(config_content)
        
        # Install geoipupdate if not available
        try:
            subprocess.run(['geoipupdate', '--version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Installing geoipupdate...")
            subprocess.run(['apt-get', 'update'], check=True)
            subprocess.run(['apt-get', 'install', '-y', 'wget', 'gnupg'], check=True)
            subprocess.run([
                'wget', '-O', '-', 
                'https://github.com/maxmind/geoipupdate/releases/download/v6.1.0/geoipupdate_6.1.0_linux_amd64.deb'
            ], check=True, stdout=subprocess.PIPE)
            subprocess.run(['dpkg', '-i', 'geoipupdate_6.1.0_linux_amd64.deb'], check=True)
        
        # Download databases
        print("Downloading MaxMind databases...")
        subprocess.run(['geoipupdate', '-f', 'GeoIP.conf'], check=True)
        
        # Move databases to DB directory
        if os.path.exists('/usr/share/GeoIP/GeoLite2-City.mmdb'):
            subprocess.run(['mv', '/usr/share/GeoIP/GeoLite2-City.mmdb', 'DB/'], check=True)
        if os.path.exists('/usr/share/GeoIP/GeoLite2-ASN.mmdb'):
            subprocess.run(['mv', '/usr/share/GeoIP/GeoLite2-ASN.mmdb', 'DB/'], check=True)
        if os.path.exists('/usr/share/GeoIP/GeoLite2-Country.mmdb'):
            subprocess.run(['mv', '/usr/share/GeoIP/GeoLite2-Country.mmdb', 'DB/'], check=True)
        
        # Clean up
        if os.path.exists('GeoIP.conf'):
            os.remove('GeoIP.conf')
        
        print("Database download completed successfully!")
        return True
        
    except Exception as e:
        print(f"Error downloading databases: {e}")
        return False

# Try to download databases on startup
download_success = download_databases()

# Try to load databases if they exist
try:
    db_path = os.path.join("DB", "GeoLite2-City.mmdb")
    if os.path.exists(db_path):
        reader = Reader(db_path)
        print("City database loaded successfully")
    else:
        print("City database not found")
except Exception as e:
    print(f"Warning: Could not load City database: {e}")

try:
    asn_db_path = os.path.join("DB", "GeoLite2-ASN.mmdb")
    if os.path.exists(asn_db_path):
        asn_reader = Reader(asn_db_path)
        print("ASN database loaded successfully")
    else:
        print("ASN database not found")
except Exception as e:
    print(f"Warning: Could not load ASN database: {e}")

try:
    country_db_path = os.path.join("DB", "GeoLite2-Country.mmdb")
    if os.path.exists(country_db_path):
        country_reader = Reader(country_db_path)
        print("Country database loaded successfully")
    else:
        print("Country database not found")
except Exception as e:
    print(f"Warning: Could not load Country database: {e}")

LOG_FILE = "requests.log"

def log_request(endpoint: str, ip: str, result: str, user_agent: str = "-"):
    timestamp = datetime.datetime.utcnow().isoformat()
    with open(LOG_FILE, "a") as f:
        f.write(f"{timestamp}\t{endpoint}\t{ip}\t{result}\t{user_agent}\n")

def validate_ip(ip: str):
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

@app.get("/geolocate")
def geolocate(request: Request, ip: Optional[str] = Query(None, description="IP address to geolocate"), format: str = Query("json", description="Response format: json or csv")):
    user_agent = request.headers.get("user-agent", "-")
    if not ip:
        ip = request.client.host
    if not validate_ip(ip):
        log_request("/geolocate", ip, "invalid_ip", user_agent)
        raise HTTPException(status_code=400, detail="Invalid IP address format.")
    
    if reader is None:
        log_request("/geolocate", ip, "database_not_available", user_agent)
        raise HTTPException(status_code=503, detail="Geolocation database not available. Please check configuration.")
    
    try:
        response = reader.city(ip)
        result = {
            "ip": ip,
            "city": response.city.name,
            "country": response.country.name,
            "continent": response.continent.name,
            "latitude": response.location.latitude,
            "longitude": response.location.longitude,
            "timezone": response.location.time_zone,
            "postal_code": response.postal.code,
            "subdivision": response.subdivisions.most_specific.name,
            "accuracy_radius_km": response.location.accuracy_radius
        }
        log_request("/geolocate", ip, "success", user_agent)
        if format == "csv":
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=result.keys())
            writer.writeheader()
            writer.writerow(result)
            return Response(content=output.getvalue(), media_type="text/csv")
        return JSONResponse(content=result)
    except AddressNotFoundError:
        log_request("/geolocate", ip, "not_found", user_agent)
        raise HTTPException(status_code=404, detail="IP address not found in database.")
    except Exception as e:
        log_request("/geolocate", ip, f"error: {str(e)}", user_agent)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/geolocate/batch")
def batch_geolocate(request: Request, ips: List[str] = Body(..., example=["8.8.8.8", "1.1.1.1", "2001:4860:4860::8888"], description="List of IP addresses to geolocate"), format: str = Query("json", description="Response format: json or csv")) -> Response:
    user_agent = request.headers.get("user-agent", "-")
    
    if reader is None:
        log_request("/geolocate/batch", "batch", "database_not_available", user_agent)
        raise HTTPException(status_code=503, detail="Geolocation database not available. Please check configuration.")
    
    results = []
    for ip in ips:
        if not validate_ip(ip):
            results.append({"ip": ip, "error": "Invalid IP address format."})
            log_request("/geolocate/batch", ip, "invalid_ip", user_agent)
            continue
        try:
            response = reader.city(ip)
            results.append({
                "ip": ip,
                "city": response.city.name,
                "country": response.country.name,
                "continent": response.continent.name,
                "latitude": response.location.latitude,
                "longitude": response.location.longitude,
                "timezone": response.location.time_zone,
                "postal_code": response.postal.code,
                "subdivision": response.subdivisions.most_specific.name,
                "accuracy_radius_km": response.location.accuracy_radius
            })
            log_request("/geolocate/batch", ip, "success", user_agent)
        except AddressNotFoundError:
            results.append({"ip": ip, "error": "IP address not found in database."})
            log_request("/geolocate/batch", ip, "not_found", user_agent)
        except Exception as e:
            results.append({"ip": ip, "error": str(e)})
            log_request("/geolocate/batch", ip, f"error: {str(e)}", user_agent)
    if format == "csv":
        output = io.StringIO()
        if results:
            writer = csv.DictWriter(output, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        return Response(content=output.getvalue(), media_type="text/csv")
    return JSONResponse(content=results)

@app.get("/asn")
def asn_lookup(request: Request, ip: Optional[str] = Query(None, description="IP address to lookup ASN info")):
    user_agent = request.headers.get("user-agent", "-")
    if not ip:
        ip = request.client.host
    if not validate_ip(ip):
        log_request("/asn", ip, "invalid_ip", user_agent)
        raise HTTPException(status_code=400, detail="Invalid IP address format.")
    
    if asn_reader is None:
        log_request("/asn", ip, "database_not_available", user_agent)
        raise HTTPException(status_code=503, detail="ASN database not available. Please check configuration.")
    
    try:
        response = asn_reader.asn(ip)
        result = {
            "ip": ip,
            "autonomous_system_number": response.autonomous_system_number,
            "autonomous_system_organization": response.autonomous_system_organization
        }
        log_request("/asn", ip, "success", user_agent)
        return result
    except AddressNotFoundError:
        log_request("/asn", ip, "not_found", user_agent)
        raise HTTPException(status_code=404, detail="IP address not found in ASN database.")
    except Exception as e:
        log_request("/asn", ip, f"error: {str(e)}", user_agent)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/country")
def country_lookup(request: Request, ip: Optional[str] = Query(None, description="IP address to lookup country info")):
    user_agent = request.headers.get("user-agent", "-")
    if not ip:
        ip = request.client.host
    if not validate_ip(ip):
        log_request("/country", ip, "invalid_ip", user_agent)
        raise HTTPException(status_code=400, detail="Invalid IP address format.")
    
    if country_reader is None:
        log_request("/country", ip, "database_not_available", user_agent)
        raise HTTPException(status_code=503, detail="Country database not available. Please check configuration.")
    
    try:
        response = country_reader.country(ip)
        result = {
            "ip": ip,
            "country": response.country.name,
            "iso_code": response.country.iso_code,
            "continent": response.continent.name
        }
        log_request("/country", ip, "success", user_agent)
        return result
    except AddressNotFoundError:
        log_request("/country", ip, "not_found", user_agent)
        raise HTTPException(status_code=404, detail="IP address not found in Country database.")
    except Exception as e:
        log_request("/country", ip, f"error: {str(e)}", user_agent)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/reverse_dns")
def reverse_dns(request: Request, ip: Optional[str] = Query(None, description="IP address to lookup reverse DNS (PTR record)")):
    user_agent = request.headers.get("user-agent", "-")
    if not ip:
        ip = request.client.host
    if not validate_ip(ip):
        log_request("/reverse_dns", ip, "invalid_ip", user_agent)
        raise HTTPException(status_code=400, detail="Invalid IP address format.")
    try:
        ptr_record = socket.gethostbyaddr(ip)[0]
        log_request("/reverse_dns", ip, "success", user_agent)
        return {"ip": ip, "ptr_record": ptr_record}
    except socket.herror:
        log_request("/reverse_dns", ip, "not_found", user_agent)
        raise HTTPException(status_code=404, detail="PTR record not found for this IP.")
    except Exception as e:
        log_request("/reverse_dns", ip, f"error: {str(e)}", user_agent)
        raise HTTPException(status_code=500, detail=str(e))

app.mount("/", StaticFiles(directory="static", html=True), name="static") 