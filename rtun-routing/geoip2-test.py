
import geoip2.webservice

# This creates a Client object that can be reused across requests.
# Replace "42" with your account ID and "license_key" with your license
# key. Set the "host" keyword argument to "geolite.info" to use the
# GeoLite2 web service instead of the GeoIP2 web service.

with geoip2.webservice.Client(host="geolite.info") as client:
    response = client.city('203.0.113.0')
    response.country.iso_code
