import requests
from datetime import datetime
from typing import List, Dict, Any

CALENDARIFIC_API_KEY = "z9YHmzVKF2yXCRQTTuxryxNmLcd4HDUN"

def get_country_code(country_name: str) -> str:
    """
    Simple mapping for common countries. Falls back to first 2 letters if not found.
    """
    mapping = {
        "india": "IN",
        "united states": "US",
        "usa": "US",
        "united kingdom": "GB",
        "uk": "GB",
        "united arab emirates": "AE",
        "uae": "AE",
        "canada": "CA",
        "australia": "AU",
        "germany": "DE",
        "france": "FR"
    }
    
    clean_name = country_name.lower().strip()
    if clean_name in mapping:
        return mapping[clean_name]
    
    # If it's already a 2-letter code
    if len(clean_name) == 2:
        return clean_name.upper()
        
    return "IN" # Default fallback for this project

def fetch_holidays_from_api(country_name: str, year: int = None) -> List[Dict[str, Any]]:
    """
    Fetch holidays from Calendarific API.
    """
    if not year:
        year = datetime.utcnow().year
    
    country_code = get_country_code(country_name)
    url = f"https://calendarific.com/api/v2/holidays?&api_key={CALENDARIFIC_API_KEY}&country={country_code}&year={year}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        holidays = []
        if data.get("response") and data["response"].get("holidays"):
            for h in data["response"]["holidays"]:
                # The API returns date in various formats, we want the ISO string
                h_date = h["date"]["iso"]
                if "T" in h_date:
                    h_date = h_date.split("T")[0]

                # Map API holiday type to our enum values
                api_type = h["type"][0].lower() if h["type"] else "public"
                
                # Mapping logic
                if "public" in api_type:
                    h_type = "public"
                elif "optional" in api_type or "observance" in api_type:
                    h_type = "optional"
                elif "restricted" in api_type:
                    h_type = "restricted"
                else:
                    h_type = "public"

                holidays.append({
                    "holiday_name": h["name"],
                    "holiday_date": h_date,
                    "holiday_type": h_type
                })
        return holidays
    except Exception as e:
        print(f"Error fetching holidays: {str(e)}")
        return []
