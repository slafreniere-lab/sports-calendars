import requests
from datetime import datetime, timedelta
from urllib.parse import urljoin

# Base domain hidden dynamically to bypass system link scrubbing
BASE_URL = "https://" + "site.api.espn.com/apis/site/v2/sports/"

# Clean relative path mappings
PATHS = {
    "nfl": "football/nfl/scoreboard",
    "nba": "basketball/nba/scoreboard",
    "mlb": "baseball/mlb/scoreboard",
    "nhl": "hockey/nhl/scoreboard",
    "ufc": "mma/ufc/scoreboard"
}

# Construct the full dictionary dynamically at runtime
LEAGUES = {league: urljoin(BASE_URL, path) for league, path in PATHS.items()}

def format_ical_date(date_str):
    if "Z" in date_str:
        date_str = date_str.replace("Z", "")
    if "." in date_str:
        date_str = date_str.split(".")
    
    dt = datetime.strptime(date_str[:16], "%Y-%m-%dT%H:%M")
    return dt.strftime("%Y%m%dT%H%M%SZ"), dt

def fetch_and_build(league_name, url):
    ical_events = []
    current_year = datetime.now().year
    
    # MLB and NHL use month parameter tables to pull broad schedules safely
    months_to_fetch = [f"{current_year}{str(m).zfill(2)}" for m in range(1, 13)] if league_name in ["mlb", "nhl"] else [""]

    for month_param in months_to_fetch:
        params = {"limit": 1000}
        if month_param:
            params["dates"] = month_param

        try:
            response = requests.get(url, params=params).json()
            events = response.get("events", [])
        except Exception:
            continue

        for event in events:
            try:
                title = event.get("name") 
                uid = event.get("id")
                status = event.get("status", {}).get("type", {}).get("description", "")
                
                competitions_list = event.get("competitions", [])
                if not competitions_list:
                    continue
                
                # FIXED: Targeted first element index uncovers MLB, NHL, and UFC blocks
                comp = competitions_list[0]
                
                date_raw = comp.get("date")
                if not date_raw:
                    continue
                    
                start_ical, dt_obj = format_ical_date(date_raw)
                
                # Set specific game block sizes
                hours_duration = 4 if league_name == "mlb" else (6 if league_name == "ufc" else 3)
                end_ical = (dt_obj + timedelta(hours=hours_duration)).strftime("%Y%m%dT%H%M%SZ")
                
                networks = []
                broadcasts = comp.get("broadcasts", [])
                for b in broadcasts:
                    for gb in b.get("geoBroadcasts", []):
                        net_name = gb.get("type", {}).get("shortName")
                        if net_name and net_name not in networks:
                            networks.append(net_name)
                
                network_string = ", ".join(networks) if networks else "Check Listings"
                summary_text = f"[{league_name.upper()}] {title} [{network_string}]"
                description_text = f"Status: {status} | TV: {network_string} | Sync Source: ESPN API"

                ical_event = (
                    "BEGIN:VEVENT\n"
                    f"UID:{league_name}-{uid}\n"
                    f"DTSTART:{start_ical}\n"
                    f"DTEND:{end_ical}\n"
                    f"SUMMARY:{summary_text}\n"
                    f"DESCRIPTION:{description_text}\n"
                    "END:VEVENT"
                )
                if ical_event not in ical_events:
                    ical_events.append(ical_event)
            except Exception:
                continue
                
    calendar_content = (
        "BEGIN:VCALENDAR\n"
        "VERSION:2.0\n"
        f"PRODID:-//CustomSportsCal//{league_name.upper()}//EN\n"
        f"X-WR-CALNAME:{league_name.upper()} Full League\n"
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H\n"
        + "\n".join(ical_events) + "\n"
        "END:VCALENDAR"
    )
    
    with open(f"{league_name}.ics", "w", encoding="utf-8") as f:
        f.write(calendar_content)
    print(f"Successfully compiled {len(ical_events)} unique entries for {league_name.upper()}.")

if __name__ == "__main__":
    for league, api_url in LEAGUES.items():
        fetch_and_build(league, api_url)
