from math import asin, cos, radians, sin, sqrt

# NGA populated-place coordinate, verified 17 October 2026. See docs/data-sources.md.
BANDARAGAMA_LATITUDE = 6.714444
BANDARAGAMA_LONGITUDE = 79.986667
MAX_DISTANCE_KM = 25


def distance_from_bandaragama(latitude, longitude):
    """Approximate great-circle distance, not a driving distance."""
    lat1, lon1, lat2, lon2 = map(radians, (
        BANDARAGAMA_LATITUDE, BANDARAGAMA_LONGITUDE, float(latitude), float(longitude),
    ))
    haversine = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * asin(sqrt(min(1, haversine)))
