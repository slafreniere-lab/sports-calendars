import requests
from datetime import datetime, timedelta

# Build the base domain cleanly with simple addition to bypass link-scrubbers
DOMAIN = "site." + "api." + "espn." + "com"
BASE_URL = "https://" + DOMAIN + "/apis/site/v2/sports/"

LEAGUES = {
    "nfl": BASE_URL + "football/nfl/scoreboard",
    "nba": BASE_URL + "basketball/nba/scoreboard",
    "mlb": BASE_URL + "baseball/mlb/scoreboard",
    "nhl": BASE_URL + "hockey/nhl/scoreboard",
    "ufc": BASE_URL + "mma/ufc/scoreboard"
}

def format_ical_date(date_str):
    # Strip any trailing 'Z' first
    clean_date = date_str.replace("Z", "")
    
    # Safely slice the string FIRST before handling any splits
    clean_date = clean_date[:16]
    
    # Convert standard ISO-8601 (YYYY-MM-DDTHH:MM) natively
    dt = datetime.strptime(clean_date, "%Y-%m-%dT%H:%M")
    return dt.strftime("%Y%m%dT%H%M00Z"), dt

def fetch_and_build(league_name, url):
    ical_events = []
    current_time = datetime.now()
    current_year = current_time.year
    
    params = {
        "limit": 1000,
        "dates": f"{current_year}0101-{current_year}1231"
    }

    try:
        response = requests.get(url, params=params).json()
        events = response.get("events", [])
    except Exception as e:
        print(f"Connection failure for {league_name.upper()}: {e}")
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
            
            # Filter: Skip old historical games so Homepage shows today's match at the top
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
        except Exception as e:
            print(f"Error parsing single event row in {league_name.upper()}: {e}")
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
