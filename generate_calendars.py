import requests
from datetime import datetime, timedelta
from urllib.parse import urljoin

BASE_URL = "https://" + "://espn.com"

PATHS = {
    "nfl": "football/nfl/scoreboard",
    "nba": "basketball/nba/scoreboard",
    "mlb": "baseball/mlb/scoreboard",
    "nhl": "hockey/nhl/scoreboard",
    "ufc": "mma/ufc/scoreboard"
}

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
    current_time = datetime.now()
    current_year = current_time.year
    
    # FIX: Use a single-request year window to stop ESPN from rate-limiting/blocking your updates
    params = {
        "limit": 1000,
        "dates": f"{current_year}0101-{current_year}1231"
    }

    try:
        response = requests.get(url, params=params).json()
        events = response.get("events", [])
    except Exception:
        print(f"Skipping {league_name.upper()} - API connection throttled.")
        return

    for event in events:
        try:
            competitions_list = event.get("competitions", [])
            if not competitions_list:
                continue
            
            comp = competitions_list[0]
            date_raw = comp.get("date")
            if not date_raw:
                continue
                
            start_ical, dt_obj = format_ical_date(date_raw)
            
            # FIX: Skip old games! If the game happened before today, do not write it to the file.
            # This ensures Homepage's agenda view sees today's games at the very top.
            if dt_obj.date() < current_time.date():
                continue

            title = event.get("name") 
            uid = event.get("id")
            status = event.get("status", {}).get("type", {}).get("description", "")
            
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
    print(f"Successfully compiled {len(ical_events)} upcoming entries for {league_name.upper()}.")

if __name__ == "__main__":
    for league, api_url in LEAGUES.items():
        fetch_and_build(league, api_url)
