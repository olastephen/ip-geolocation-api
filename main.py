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

app = FastAPI()

db_path = os.path.join("DB", "GeoLite2-City.mmdb")
reader = Reader(db_path)

asn_db_path = os.path.join("DB", "GeoLite2-ASN.mmdb")
asn_reader = Reader(asn_db_path)

country_db_path = os.path.join("DB", "GeoLite2-Country.mmdb")
country_reader = Reader(country_db_path)

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