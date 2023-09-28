import requests
import json
from bs4 import BeautifulSoup
import os

# Function to fetch user profile data and save it to a file
def fetch_user_data_and_save(onion_link, index, output_dir):
    url = f'http://{onion_link}/profile.php?id={index}'

    # Configure the proxy to route requests through Tor
    proxies = {
        'http': 'socks5h://127.0.0.1:9050',
        'https': 'socks5h://127.0.0.1:9050'
    }

    response = requests.get(url, proxies=proxies)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        data_dict = {
            "Email": "",
            "RegistrationDate": ""
        }

        # Find email and registration date based on HTML structure
        for td in soup.find_all('td', class_='left'):
            lines = td.get_text().strip().split('\n')
            for line in lines:
                if "Email:" in line:
                    data_dict["Email"] = line.split("Email:")[1].strip()
                elif "This user was registred on" in line:
                    data_dict["RegistrationDate"] = line.split("on")[1].strip()

        # Create a JSON string
        json_data = json.dumps(data_dict, indent=4)

        # Save JSON data to a file
        output_file = os.path.join(output_dir, f'recon{index}.json')
        with open(output_file, 'w') as json_file:
            json_file.write(json_data)

        print(f"JSON response saved to '{output_file}'")

        return output_file
    else:
        print(f"Request for ID {index} failed with status code:", response.status_code)
        return None

# Onion link and output directory
onion_link = "gunsganos2raowan5y2nkblujnmza32v2cwkdgy6okciskzabchx4iqd.onion"
os.system("echo 'gunsganos2raowan5y2nkblujnmza32v2cwkdgy6okciskzabchx4iqd.onion ; Guns & Ganja - Buy Illegal Weapons [ Verified Vendors ]' | lolcat")
output_dir = 'json_response'
os.makedirs(output_dir, exist_ok=True)

# List to store response files
response_files = []

# Loop through IDs from 1 to 20 and fetch user data
for index in range(1, 21):
    response_file = fetch_user_data_and_save(onion_link, index, output_dir)
    if response_file:
        response_files.append(response_file)

# Display the JSON content in the terminal using cat and jq
if response_files:
    cat_command = f"cat {' '.join(response_files)} | jq"
    os.system(cat_command)