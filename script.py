import requests
from bs4 import BeautifulSoup
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import re
import sys

def send_email(dates, success):
    print("Preparing to send email notification...")
    # Email configuration
    sender_email = os.getenv('SENDER_EMAIL')
    sender_password = os.getenv('EMAIL_PASSWORD')
    receiver_email = os.getenv('RECEIVER_EMAIL')

    # Validate required environment variables
    if not all([sender_email, sender_password, receiver_email]):
        print("Warning: Missing email configuration. Email will not be sent.")
        return

    # Create message
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email

    print("Creating email content...")
    if success:
        message["Subject"] = "Nowe bilety!"
        body = f"Tickets are now available for dates: {', '.join(dates)} !"
    else:
        message["Subject"] = "Error Checking Tickets"
        body = f"An error occurred while checking tickets for dates: {', '.join(dates)}"
    
    message.attach(MIMEText(body, "plain"))
    
    print("Email content created. Setting up email server...")
    # Send email
    try:
        SMTP_SERVER = os.getenv('SMTP_SERVER')
        SMTP_PORT = int(os.getenv('SMTP_PORT', 465))
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            print("Logging in to email server...")
            server.login(sender_email, sender_password)
            print("Sending email...")
            server.send_message(message)
        print("Email notification sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")


def get_html():
    try:
        # Download the webpage
        print("Downloading the webpage...")
        url = os.getenv('MAQ_URL')
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes

        print("Webpage downloaded successfully.")
        # Parse the HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        return soup

    except requests.RequestException as e:
        print(f"Error downloading the page: {e}")
        raise  # Re-raise the exception
    except Exception as e:
        print(f"Error processing the page: {e}")
        raise  # Re-raise the exception

def parse_places(html: str) -> dict:
    """
    Zwraca słownik:
    {
        '29/05/2026': 1,
        '30/05/2026': 1,
        ...
    }
    """
    print("Parsing the HTML to extract ticket availability...")
    soup = BeautifulSoup(html, "html.parser")

    result = {}

    rows = soup.find_all("div", class_="termin")

    for row in rows:
        date_div = row.find("div", class_="data")
        free_div = row.find("div", class_="wolne")

        if not date_div or not free_div:
            continue

        # Data
        date = date_div.text.strip().replace(" ", "")

        # Liczba miejsc (wyciągamy cyfrę regexem)
        match = re.search(r"(\d+)", free_div.text)
        if match:
            places = int(match.group(1))
            result[date] = places
    print(f"Parsed ticket availability.")
    return result

def save_places(places: dict):
    print("Saving current ticket availability to places.json...")
    with open("places.json", "w") as f:
        json.dump(places, f)

def load_places() -> dict:
    print("Loading previous ticket availability from places.json...")
    if not os.path.exists("places.json"):
        return {}
    
    with open("places.json", "r") as f:
        return json.load(f)

def compare_places(old_places: dict, new_places: dict) -> list:
    """
    Porównuje dwa słowniki miejsc i zwraca listę dat, dla których liczba miejsc wzrosła.
    """
    print("Comparing current ticket availability with previous data...")
    changed_dates = []
    for date, new_count in new_places.items():
        old_count = old_places.get(date, 0)
        if new_count > old_count:
            print(f"Found change for date {date}: old count = {old_count}, new count = {new_count}")
            changed_dates.append(date)
    return changed_dates

if __name__ == "__main__":
    try:
        html = get_html()
        new_places = parse_places(str(html))
        old_places = load_places()
        changed_dates = compare_places(old_places, new_places)
        if changed_dates:
            print(f"Changes found for dates: {', '.join(changed_dates)}")
            send_email(changed_dates, True)
        else:
            print("No changes found in ticket availability.")
        save_places(new_places)
    except Exception as e:
        print(f"An error occurred: {e}")
        send_email([], False)
        sys.exit(1)