"""Airport repository providing global airport metadata with ICAO and IATA indexes."""

from __future__ import annotations

import math
from typing import Optional, Tuple
from app.repositories.base import AirportRepositoryBase

# Pre-indexed database of key commercial, international, and regional airports globally
# Fields: (icao, iata, name, municipality, country_name, country_iso, lat, lon, elevation_ft, tz)
_GLOBAL_AIRPORTS = [
    # India
    ("VIDP", "DEL", "Indira Gandhi International Airport", "New Delhi", "India", "IN", 28.5665, 77.1031, 777, "Asia/Kolkata"),
    ("VABB", "BOM", "Chhatrapati Shivaji Maharaj International Airport", "Mumbai", "India", "IN", 19.0896, 72.8656, 39, "Asia/Kolkata"),
    ("VOBL", "BLR", "Kempegowda International Airport", "Bengaluru", "India", "IN", 13.1986, 77.7066, 3000, "Asia/Kolkata"),
    ("VOMM", "MAA", "Chennai International Airport", "Chennai", "India", "IN", 12.9941, 80.1709, 52, "Asia/Kolkata"),
    ("VOHS", "HYD", "Rajiv Gandhi International Airport", "Hyderabad", "India", "IN", 17.2403, 78.4294, 2024, "Asia/Kolkata"),
    ("VECC", "CCU", "Netaji Subhash Chandra Bose International Airport", "Kolkata", "India", "IN", 22.6547, 88.4467, 16, "Asia/Kolkata"),
    ("VAAH", "AMD", "Sardar Vallabhbhai Patel International Airport", "Ahmedabad", "India", "IN", 23.0772, 72.6347, 189, "Asia/Kolkata"),
    ("VOCI", "COK", "Cochin International Airport", "Kochi", "India", "IN", 10.1520, 76.4019, 30, "Asia/Kolkata"),
    ("VOGO", "GOI", "Dabolim Airport", "Goa", "India", "IN", 15.3808, 73.8314, 184, "Asia/Kolkata"),
    ("VOGA", "GOX", "Manohar International Airport", "Mopa", "India", "IN", 15.7443, 73.8606, 552, "Asia/Kolkata"),
    ("VAPO", "PNQ", "Pune Airport", "Pune", "India", "IN", 18.5821, 73.9197, 1942, "Asia/Kolkata"),
    ("VIJP", "JAI", "Jaipur International Airport", "Jaipur", "India", "IN", 26.8242, 75.8122, 1263, "Asia/Kolkata"),
    ("VILK", "LKO", "Chaudhary Charan Singh International Airport", "Lucknow", "India", "IN", 26.7606, 80.8893, 405, "Asia/Kolkata"),
    ("VEPT", "PAT", "Jay Prakash Narayan Airport", "Patna", "India", "IN", 25.5913, 85.0880, 170, "Asia/Kolkata"),
    ("VEBS", "BBI", "Biju Patnaik International Airport", "Bhubaneswar", "India", "IN", 20.2444, 85.8178, 140, "Asia/Kolkata"),
    ("VEGT", "GAU", "Lokpriya Gopinath Bordoloi International Airport", "Guwahati", "India", "IN", 26.1061, 91.5859, 162, "Asia/Kolkata"),
    ("VICG", "IXC", "Shaheed Bhagat Singh International Airport", "Chandigarh", "India", "IN", 30.6735, 76.7885, 1012, "Asia/Kolkata"),
    ("VISR", "SXR", "Sheikh ul-Alam International Airport", "Srinagar", "India", "IN", 33.9871, 74.7741, 5456, "Asia/Kolkata"),
    ("VIAR", "ATQ", "Sri Guru Ram Dass Jee International Airport", "Amritsar", "India", "IN", 31.7096, 74.7973, 756, "Asia/Kolkata"),
    ("VOTR", "TRV", "Thiruvananthapuram International Airport", "Thiruvananthapuram", "India", "IN", 8.4821, 76.9200, 15, "Asia/Kolkata"),

    # Middle East
    ("OMDB", "DXB", "Dubai International Airport", "Dubai", "United Arab Emirates", "AE", 25.2532, 55.3657, 62, "Asia/Dubai"),
    ("OMDW", "DWC", "Al Maktoum International Airport", "Dubai", "United Arab Emirates", "AE", 24.8960, 55.1732, 171, "Asia/Dubai"),
    ("OMAA", "AUH", "Zayed International Airport", "Abu Dhabi", "United Arab Emirates", "AE", 24.4330, 54.6511, 88, "Asia/Dubai"),
    ("OTHH", "DOH", "Hamad International Airport", "Doha", "Qatar", "QA", 25.2731, 51.6081, 13, "Asia/Qatar"),
    ("OEDF", "DMM", "King Fahd International Airport", "Dammam", "Saudi Arabia", "SA", 26.4712, 49.7979, 72, "Asia/Riyadh"),
    ("OERK", "RUH", "King Khalid International Airport", "Riyadh", "Saudi Arabia", "SA", 24.9576, 46.6988, 2049, "Asia/Riyadh"),
    ("OEJN", "JED", "King Abdulaziz International Airport", "Jeddah", "Saudi Arabia", "SA", 21.6796, 39.1565, 48, "Asia/Riyadh"),
    ("OBBI", "BAH", "Bahrain International Airport", "Manama", "Bahrain", "BH", 26.2708, 50.6336, 6, "Asia/Bahrain"),
    ("OKBK", "KWI", "Kuwait International Airport", "Kuwait City", "Kuwait", "KW", 29.2266, 47.9689, 206, "Asia/Kuwait"),
    ("OOMS", "MCT", "Muscat International Airport", "Muscat", "Oman", "OM", 23.5933, 58.2844, 48, "Asia/Muscat"),
    ("LLBG", "TLV", "Ben Gurion Airport", "Tel Aviv", "Israel", "IL", 32.0094, 34.8864, 135, "Asia/Jerusalem"),

    # Europe
    ("EGLL", "LHR", "Heathrow Airport", "London", "United Kingdom", "GB", 51.4700, -0.4543, 83, "Europe/London"),
    ("EGKK", "LGW", "Gatwick Airport", "London", "United Kingdom", "GB", 51.1481, -0.1903, 202, "Europe/London"),
    ("EGSS", "STN", "London Stansted Airport", "London", "United Kingdom", "GB", 51.8860, 0.2389, 348, "Europe/London"),
    ("EGCC", "MAN", "Manchester Airport", "Manchester", "United Kingdom", "GB", 53.3537, -2.2750, 257, "Europe/London"),
    ("EIDW", "DUB", "Dublin Airport", "Dublin", "Ireland", "IE", 53.4264, -6.2499, 242, "Europe/Dublin"),
    ("LFPG", "CDG", "Charles de Gaulle International Airport", "Paris", "France", "FR", 49.0097, 2.5479, 392, "Europe/Paris"),
    ("LFPO", "ORY", "Paris Orly Airport", "Paris", "France", "FR", 48.7262, 2.3652, 291, "Europe/Paris"),
    ("EDDF", "FRA", "Frankfurt am Main Airport", "Frankfurt", "Germany", "DE", 50.0379, 8.5622, 364, "Europe/Berlin"),
    ("EDDM", "MUC", "Munich Airport", "Munich", "Germany", "DE", 48.3537, 11.7861, 1487, "Europe/Berlin"),
    ("EDDB", "BER", "Berlin Brandenburg Airport", "Berlin", "Germany", "DE", 52.3667, 13.5033, 157, "Europe/Berlin"),
    ("EHAM", "AMS", "Amsterdam Airport Schiphol", "Amsterdam", "Netherlands", "NL", 52.3105, 4.7683, -11, "Europe/Amsterdam"),
    ("EBBR", "BRU", "Brussels Airport", "Brussels", "Belgium", "BE", 50.9014, 4.4844, 184, "Europe/Brussels"),
    ("LSZH", "ZRH", "Zurich Airport", "Zurich", "Switzerland", "CH", 47.4582, 8.5555, 1416, "Europe/Zurich"),
    ("LSGG", "GVA", "Geneva Airport", "Geneva", "Switzerland", "CH", 46.2381, 6.1089, 1411, "Europe/Zurich"),
    ("LOWW", "VIE", "Vienna International Airport", "Vienna", "Austria", "AT", 48.1103, 16.5697, 600, "Europe/Vienna"),
    ("LEMD", "MAD", "Adolfo Suárez Madrid–Barajas Airport", "Madrid", "Spain", "ES", 40.4839, -3.5680, 2000, "Europe/Madrid"),
    ("LEBL", "BCN", "Josep Tarradellas Barcelona-El Prat Airport", "Barcelona", "Spain", "ES", 41.2974, 2.0833, 14, "Europe/Madrid"),
    ("LPPT", "LIS", "Humberto Delgado Airport", "Lisbon", "Portugal", "PT", 38.7742, -9.1342, 374, "Europe/Lisbon"),
    ("LIRF", "FCO", "Leonardo da Vinci–Fiumicino Airport", "Rome", "Italy", "IT", 41.8003, 12.2389, 14, "Europe/Rome"),
    ("LIMC", "MXP", "Milan Malpensa Airport", "Milan", "Italy", "IT", 45.6301, 8.7255, 768, "Europe/Rome"),
    ("LTFM", "IST", "Istanbul Airport", "Istanbul", "Turkey", "TR", 41.2753, 28.7519, 325, "Europe/Istanbul"),
    ("LTFJ", "SAW", "Sabiha Gökçen International Airport", "Istanbul", "Turkey", "TR", 40.8986, 29.3092, 312, "Europe/Istanbul"),
    ("EKCH", "CPH", "Copenhagen Airport", "Copenhagen", "Denmark", "DK", 55.6180, 12.6508, 17, "Europe/Copenhagen"),
    ("ESSA", "ARN", "Stockholm Arlanda Airport", "Stockholm", "Sweden", "SE", 59.6498, 17.9238, 137, "Europe/Stockholm"),
    ("ENGM", "OSL", "Oslo Airport, Gardermoen", "Oslo", "Norway", "NO", 60.1976, 11.1004, 681, "Europe/Oslo"),
    ("EFHK", "HEL", "Helsinki-Vantaa Airport", "Helsinki", "Finland", "FI", 60.3172, 24.9633, 179, "Europe/Helsinki"),
    ("EPWA", "WAW", "Warsaw Chopin Airport", "Warsaw", "Poland", "PL", 52.1672, 20.9679, 362, "Europe/Warsaw"),
    ("LGAV", "ATH", "Athens International Airport", "Athens", "Greece", "GR", 37.9364, 23.9445, 308, "Europe/Athens"),

    # North America
    ("KJFK", "JFK", "John F. Kennedy International Airport", "New York", "United States", "US", 40.6413, -73.7781, 13, "America/New_York"),
    ("KEWR", "EWR", "Newark Liberty International Airport", "Newark", "United States", "US", 40.6895, -74.1745, 18, "America/New_York"),
    ("KLGA", "LGA", "LaGuardia Airport", "New York", "United States", "US", 40.7769, -73.8740, 21, "America/New_York"),
    ("KLAX", "LAX", "Los Angeles International Airport", "Los Angeles", "United States", "US", 33.9416, -118.4085, 128, "America/Los_Angeles"),
    ("KSFO", "SFO", "San Francisco International Airport", "San Francisco", "United States", "US", 37.6213, -122.3790, 13, "America/Los_Angeles"),
    ("KORD", "ORD", "O'Hare International Airport", "Chicago", "United States", "US", 41.9742, -87.9073, 672, "America/Chicago"),
    ("KATL", "ATL", "Hartsfield–Jackson Atlanta International Airport", "Atlanta", "United States", "US", 33.6407, -84.4277, 1026, "America/New_York"),
    ("KDFW", "DFW", "Dallas/Fort Worth International Airport", "Dallas", "United States", "US", 32.8998, -97.0403, 607, "America/Chicago"),
    ("KDEN", "DEN", "Denver International Airport", "Denver", "United States", "US", 39.8561, -104.6737, 5434, "America/Denver"),
    ("KMIA", "MIA", "Miami International Airport", "Miami", "United States", "US", 25.7959, -80.2870, 8, "America/New_York"),
    ("KSEA", "SEA", "Seattle-Tacoma International Airport", "Seattle", "United States", "US", 47.4502, -122.3088, 433, "America/Los_Angeles"),
    ("KBOS", "BOS", "Logan International Airport", "Boston", "United States", "US", 42.3656, -71.0096, 20, "America/New_York"),
    ("KIAD", "IAD", "Washington Dulles International Airport", "Washington", "United States", "US", 38.9531, -77.4565, 313, "America/New_York"),
    ("CYYZ", "YYZ", "Toronto Pearson International Airport", "Toronto", "Canada", "CA", 43.6777, -79.6248, 569, "America/Toronto"),
    ("CYVR", "YVR", "Vancouver International Airport", "Vancouver", "Canada", "CA", 49.1947, -123.1792, 14, "America/Vancouver"),
    ("CYUL", "YUL", "Montréal–Trudeau International Airport", "Montreal", "Canada", "CA", 45.4657, -73.7455, 118, "America/Toronto"),
    ("MMMX", "MEX", "Mexico City International Airport", "Mexico City", "Mexico", "MX", 19.4361, -99.0719, 7316, "America/Mexico_City"),
    ("MMUN", "CUN", "Cancún International Airport", "Cancún", "Mexico", "MX", 21.0365, -86.8771, 20, "America/Cancun"),

    # Asia & Oceania
    ("WSSS", "SIN", "Singapore Changi Airport", "Singapore", "Singapore", "SG", 1.3644, 103.9915, 22, "Asia/Singapore"),
    ("VHHH", "HKG", "Hong Kong International Airport", "Hong Kong", "Hong Kong", "HK", 22.3080, 113.9185, 28, "Asia/Hong_Kong"),
    ("VTBS", "BKK", "Suvarnabhumi Airport", "Bangkok", "Thailand", "TH", 13.6900, 100.7501, 5, "Asia/Bangkok"),
    ("WMKK", "KUL", "Kuala Lumpur International Airport", "Kuala Lumpur", "Malaysia", "MY", 2.7456, 101.7072, 69, "Asia/Kuala_Lumpur"),
    ("WIII", "CGK", "Soekarno–Hatta International Airport", "Jakarta", "Indonesia", "ID", -6.1275, 106.6537, 34, "Asia/Jakarta"),
    ("RPLL", "MNL", "Ninoy Aquino International Airport", "Manila", "Philippines", "PH", 14.5086, 121.0194, 75, "Asia/Manila"),
    ("RJTT", "HND", "Tokyo Haneda Airport", "Tokyo", "Japan", "JP", 35.5494, 139.7798, 35, "Asia/Tokyo"),
    ("RJAA", "NRT", "Narita International Airport", "Tokyo", "Japan", "JP", 35.7720, 140.3929, 141, "Asia/Tokyo"),
    ("RJBB", "KIX", "Kansai International Airport", "Osaka", "Japan", "JP", 34.4320, 135.2304, 50, "Asia/Tokyo"),
    ("RKSI", "ICN", "Incheon International Airport", "Seoul", "South Korea", "KR", 37.4602, 126.4407, 23, "Asia/Seoul"),
    ("RCTP", "TPE", "Taiwan Taoyuan International Airport", "Taipei", "Taiwan", "TW", 25.0797, 121.2342, 106, "Asia/Taipei"),
    ("ZBAA", "PEK", "Beijing Capital International Airport", "Beijing", "China", "CN", 40.0799, 116.6031, 116, "Asia/Shanghai"),
    ("ZBAD", "PKX", "Beijing Daxing International Airport", "Beijing", "China", "CN", 39.5098, 116.4105, 98, "Asia/Shanghai"),
    ("ZSPD", "PVG", "Shanghai Pudong International Airport", "Shanghai", "China", "CN", 31.1443, 121.8083, 13, "Asia/Shanghai"),
    ("ZGGG", "CAN", "Guangzhou Baiyun International Airport", "Guangzhou", "China", "CN", 23.3924, 113.2988, 50, "Asia/Shanghai"),
    ("YSSY", "SYD", "Sydney Kingsford Smith Airport", "Sydney", "Australia", "AU", -33.9399, 151.1753, 21, "Australia/Sydney"),
    ("YMML", "MEL", "Melbourne Airport", "Melbourne", "Australia", "AU", -37.6690, 144.8410, 434, "Australia/Melbourne"),
    ("YBBN", "BNE", "Brisbane Airport", "Brisbane", "Australia", "AU", -27.3842, 153.1175, 13, "Australia/Brisbane"),
    ("NZAA", "AKL", "Auckland Airport", "Auckland", "New Zealand", "NZ", -37.0082, 174.7850, 23, "Pacific/Auckland"),

    # South America & Africa
    ("SBGR", "GRU", "São Paulo/Guarulhos International Airport", "São Paulo", "Brazil", "BR", -23.4356, -46.4731, 2461, "America/Sao_Paulo"),
    ("SAEZ", "EZE", "Ministro Pistarini International Airport", "Buenos Aires", "Argentina", "AR", -34.8222, -58.5358, 67, "America/Argentina/Buenos_Aires"),
    ("SCEL", "SCL", "Arturo Merino Benítez International Airport", "Santiago", "Chile", "CL", -33.3930, -70.7858, 1555, "America/Santiago"),
    ("SKBO", "BOG", "El Dorado International Airport", "Bogota", "Colombia", "CO", 4.7016, -74.1469, 8361, "America/Bogota"),
    ("SPJC", "LIM", "Jorge Chávez International Airport", "Lima", "Peru", "PE", -12.0219, -77.1143, 113, "America/Lima"),
    ("FAOR", "JNB", "O. R. Tambo International Airport", "Johannesburg", "South Africa", "ZA", -26.1367, 28.2411, 5558, "Africa/Johannesburg"),
    ("FACT", "CPT", "Cape Town International Airport", "Cape Town", "South Africa", "ZA", -33.9715, 18.6021, 151, "Africa/Johannesburg"),
    ("HECA", "CAI", "Cairo International Airport", "Cairo", "Egypt", "EG", 30.1219, 31.4056, 382, "Africa/Cairo"),
    ("HKJK", "NBO", "Jomo Kenyatta International Airport", "Nairobi", "Kenya", "KE", -1.3192, 36.9278, 5327, "Africa/Nairobi"),
    ("DNMM", "LOS", "Murtala Muhammed International Airport", "Lagos", "Nigeria", "NG", 6.5774, 3.3212, 135, "Africa/Lagos"),
    ("GMMN", "CMN", "Mohammed V International Airport", "Casablanca", "Morocco", "MA", 33.3675, -7.5899, 656, "Africa/Casablanca"),
    ("HAAB", "ADD", "Addis Ababa Bole International Airport", "Addis Ababa", "Ethiopia", "ET", 8.9779, 38.7993, 7625, "Africa/Addis_Ababa"),
]


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return r * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


class AirportRepository(AirportRepositoryBase):
    """In-memory indexed global airport repository with O(1) code lookups."""

    def __init__(self) -> None:
        self._by_icao: dict[str, dict] = {}
        self._by_iata: dict[str, dict] = {}
        self._all_airports: list[dict] = []

        for row in _GLOBAL_AIRPORTS:
            icao, iata, name, municipality, country, iso, lat, lon, elev, tz = row
            data = {
                "icao_code": icao,
                "iata_code": iata,
                "name": name,
                "municipality": municipality,
                "country_name": country,
                "country_iso": iso,
                "latitude": lat,
                "longitude": lon,
                "elevation_ft": elev,
                "timezone": tz,
            }
            self._by_icao[icao.upper()] = data
            if iata:
                self._by_iata[iata.upper()] = data
            self._all_airports.append(data)

    def get_by_code(self, code: str) -> Optional[dict]:
        """Lookup airport by 3-letter IATA or 4-letter ICAO code."""
        clean = code.strip().upper()
        if len(clean) == 4 and clean in self._by_icao:
            return self._by_icao[clean]
        if len(clean) == 3 and clean in self._by_iata:
            return self._by_iata[clean]
        # Fallback check both
        return self._by_icao.get(clean) or self._by_iata.get(clean)

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Fuzzy-search airports by code, name, city, or country."""
        q = query.strip().lower()
        if not q:
            return []

        results = []
        for apt in self._all_airports:
            if (
                q in apt["icao_code"].lower()
                or (apt["iata_code"] and q in apt["iata_code"].lower())
                or q in apt["name"].lower()
                or q in apt["municipality"].lower()
                or q in apt["country_name"].lower()
            ):
                results.append(apt)
                if len(results) >= limit:
                    break
        return results

    def find_nearest(self, lat: float, lon: float, max_radius_km: float = 500.0) -> Optional[tuple[dict, float]]:
        """Find the closest airport to given coordinates within max_radius_km."""
        best_apt = None
        min_dist = float("inf")

        for apt in self._all_airports:
            dist = _haversine(lat, lon, apt["latitude"], apt["longitude"])
            if dist < min_dist and dist <= max_radius_km:
                min_dist = dist
                best_apt = apt

        if best_apt is not None:
            return best_apt, round(min_dist, 2)
        return None
