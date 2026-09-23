import math

from aegissat.config import env_float
from aegissat.orbit import load_tle_by_norad


SPEED_OF_LIGHT_M_S = 299_792_458.0


def create_doppler_tracker(norad_id):
    from skyfield.api import EarthSatellite, load, wgs84

    name, line1, line2 = load_tle_by_norad(norad_id)

    timescale = load.timescale()
    satellite = EarthSatellite(
        line1,
        line2,
        name,
        timescale,
    )

    station = wgs84.latlon(
        env_float("GROUND_STATION_LAT", 0.0),
        env_float("GROUND_STATION_LON", 0.0),
        elevation_m=env_float(
            "GROUND_STATION_ALT_M",
            0,
        ),
    )

    return {
        "norad_id": int(norad_id),
        "name": name,
        "timescale": timescale,
        "satellite": satellite,
        "station": station,
    }


def calculate_doppler(tracker, nominal_frequency_hz):
    instant = tracker["timescale"].now()

    relative = (
        tracker["satellite"]
        - tracker["station"]
    ).at(instant)

    position_km = relative.position.km
    velocity_km_s = relative.velocity.km_per_s

    distance_km = math.sqrt(
        sum(component * component for component in position_km)
    )

    radial_velocity_km_s = sum(
        position * velocity
        for position, velocity in zip(
            position_km,
            velocity_km_s,
        )
    ) / distance_km

    radial_velocity_m_s = float(
        radial_velocity_km_s * 1000.0
    )

    doppler_shift_hz = float(
        -float(nominal_frequency_hz)
        * radial_velocity_m_s
        / SPEED_OF_LIGHT_M_S
    )

    corrected_frequency_hz = float(
        float(nominal_frequency_hz)
        + doppler_shift_hz
    )

    altitude, azimuth, distance = relative.altaz()

    return {
        "timestamp_utc": (
            instant.utc_datetime().isoformat()
        ),
        "nominal_frequency_hz": float(
            nominal_frequency_hz
        ),
        "corrected_frequency_hz": (
            corrected_frequency_hz
        ),
        "doppler_shift_hz": doppler_shift_hz,
        "radial_velocity_m_s": (
            radial_velocity_m_s
        ),
        "elevation_deg": float(
            altitude.degrees
        ),
        "azimuth_deg": float(
            azimuth.degrees
        ),
        "distance_km": float(
            distance.km
        ),
    }
