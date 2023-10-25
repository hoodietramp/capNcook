from flask import Flask, render_template, request, session, jsonify
from flask_caching import Cache
from flask import redirect
import os
from termcolor import colored
import requests
import subprocess
import json
import urllib.parse
from tqdm import tqdm
from time import sleep
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import threading
from stem import CircStatus
from stem.control import Controller

load_dotenv()

# Really ignore this, I regret not deleting this - Hoodie
os.system('curl --socks5 localhost:9050 --socks5-hostname localhost:9050 -s https://check.torproject.org/ | cat | grep -m 1 Congratulations | xargs')
print("\n")
os.system("echo 'Hidden Service Url -> hoodyfml6kphashjq4uxhu6fdro4rkmmtgwrvrqu7dlo32jitvqwabqd.onion'")

#command = "curl https://api.ipify.org"
#process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#output, _ = process.communicate()

#pub_ip = output.decode().strip()
#print(colored("\nPublic IP: " + pub_ip, "yellow"))

#command = "curl --socks5 '127.0.0.1:9050' https://api.ipify.org"
#process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#output, _ = process.communicate()

#anon_ip = output.decode().strip()
#print(colored("\nAnonymized IP: " + anon_ip, "red"))
#print("\n")

app = Flask(__name__, static_url_path='/static', template_folder='templates')
app.config['CACHE_TYPE'] = 'simple'
cache = Cache(app)
app.config['CACHE_DEFAULT_TIMEOUT'] = 3000

app.secret_key = os.getenv('secret_key')

def get_last_entry_exit_relay():
    entry_node = {}
    exit_node = {}

    with Controller.from_port(address="127.0.0.1", port=9051) as controller:
        try:
            controller.authenticate()
            controller.signal("NEWNYM")

            print("All circuits have been flushed.")
            
            last_circuit = None

            for circ in controller.get_circuits():
                if circ.status != CircStatus.BUILT:
                    continue

                last_circuit = circ

            if last_circuit:
                # Extract information about the entry node
                entry_fp, entry_nickname = last_circuit.path[0]
                entry_desc = controller.get_network_status(entry_fp, None)
                entry_address = entry_desc.address if entry_desc else 'unknown'

                entry_node = {
                    "fingerprint": entry_fp,
                    "nickname": entry_nickname,
                    "address": entry_address
                }

                # Extract information about the exit node
                exit_fp, exit_nickname = last_circuit.path[-1]
                exit_desc = controller.get_network_status(exit_fp, None)
                exit_address = exit_desc.address if exit_desc else 'unknown'

                exit_node = {
                    "fingerprint": exit_fp,
                    "nickname": exit_nickname,
                    "address": exit_address
                }

                print(f"Circuit Information:")
                print(f"Entry Node\n fingerprint: {entry_fp}\n nickname: {entry_nickname}\n address: {entry_address}")
                print(f"Exit Node\n fingerprint: {exit_fp}\n nickname: {exit_nickname}\n address: {exit_address}")
                print("=" * 50)

        except Exception as e:
            print(f"An error occurred: {e}")

    return entry_node, exit_node

@app.route("/")

def index():
    entry_node, exit_node = get_last_entry_exit_relay()
    return render_template("index.html", entry_node=entry_node, exit_node=exit_node)

@app.route('/onion_check')

def onion_check():
    if 'onionCheck_results' in session:
        results = session['onionCheck_results']
    else:
        results = run_backend_onionCheck() 
        session['onionCheck_results'] = results

    return render_template("onion_check.html", results=results)

def check_domain(url, proxies, results_lock, results):
    result = {}
    status = 'N/A'
    status_code = 'N/A'

    try:
        data = requests.get(url, proxies=proxies)
    except:
        data = 'error'

    if data != 'error':
        status = 'Active'
        status_code = data.status_code
        soup = BeautifulSoup(data.text, 'html.parser')
        page_title = str(soup.title)
        page_title = page_title.replace('<title>', '')
        page_title = page_title.replace('</title>', '')
        result['url'] = url
        result['status'] = 'Active'
        result['status_code'] = data.status_code
        result['page_title'] = page_title

    elif data == 'error':
        status = "Inactive"
        status_code = 'NA'
        page_title = 'NA'
        result['url'] = url
        result['status'] = 'Inactive'
        result['status_code'] = 'NA'
        result['page_title'] = 'NA'

    with results_lock:
        results.append(result)

    print("\n")
    print(colored(f"{url}: {status}: {status_code}: {page_title}", "cyan"))

def run_backend_onionCheck():
    proxies = {
        'http': 'socks5h://127.0.0.1:9050',
        'https': 'socks5h://127.0.0.1:9050'
    }

    with open('domains.txt', 'r') as file:
        domains = file.readlines()

    results = []
    results_lock = threading.Lock()

    threads = []

    for url in domains:
        url = url.strip('\n')
        thread = threading.Thread(target=check_domain, args=(url, proxies, results_lock, results))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    return results

@app.route('/recon')
def recon():
    if 'recon_results' in session:
        recon_outputs = session['recon_results']
    else:
        recon_outputs = run_backend_recon() 
        session['recon_results'] = recon_outputs

    return render_template("recon.html", recon_outputs=recon_outputs)

def run_backend_recon():
    def run_whois(onion_link, index):
        command = f"sleep 1s; whois -h torwhois.com {onion_link} | tee recon_output/recon{index}.txt"
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode == 0:
            output_lines = result.stdout.splitlines()
            output_lines = output_lines[:-3]
            output = '\n'.join(output_lines)

        else:
            output = f"Error: {result.stderr}"

        return output

    if not os.path.exists('recon_output'):
        os.makedirs('recon_output')
            
    with open('domains.txt', 'r') as file:
        onion_links = file.read().splitlines()

    recon_outputs = []

    for index, onion_link in enumerate(onion_links, start=1):
        whois_output = run_whois(onion_link, index)

        header_line = f"Output for {onion_link} (Domain {index}):\n"
        recon_outputs.append({
            'header': header_line,
            'output': whois_output.splitlines(),
        })

    return recon_outputs

@app.route('/headers')
def headers():

    cmd2 = "cat domains.txt 2>/dev/null | aquatone -out static/aqua_out -ports 80 -proxy socks5://127.0.0.1:9050 -http-timeout 30000 -screenshot-timeout 60000 2>/dev/null"

    print(colored("\n[+] Capturing Screenshots...", "green"))
    os.system(cmd2)
    
    def fetch_header(onion_url):
        
        proxies = {
        'http': 'socks5h://127.0.0.1:9050',
        'https': 'socks5h://127.0.0.1:9050'
        }
        
        try:
            onion_url = onion_url.strip()
            screenshot_filename = f"{onion_url.replace('://', '__').replace('.onion', '_onion')}__da39a3ee5e6b4b0d.png"
            screenshot_path = os.path.join(screenshot_dir, screenshot_filename)

            response = requests.get(onion_url, headers={'User-Agent': 'Mozilla/5.0'}, proxies=proxies)
            if response.status_code == 200:
                headers = {
                    'title': onion_url,
                    'headers': response.headers,
                    'screenshot': screenshot_path,
                }

                # Print headers in terminal
                # print(colored(f"\n{'-' * 40}\nHeaders for {onion_url}\n{'-' * 40}", "green"))
                # for header, value in response.headers.items():
                #     print(f"{header}: {value}")
                # print("-" * 40)

                domains.append(headers)
        except Exception as e:
            print(f"An error occurred for {onion_url}: {str(e)}")

    domains = []
    threads = []

    with open('domains.txt', 'r') as file:
        onion_urls = file.read().splitlines()

    screenshot_dir = 'aqua_out/screenshots'

    for onion_url in onion_urls:
        thread = threading.Thread(target=fetch_header, args=(onion_url,))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    return render_template("headers.html", domains=domains)

@app.route('/enumeration')
def enumeration():
    if 'enumeration_results' in session:
        enumeration_outputs = session['enumeration_results']
    else:
        enumeration_outputs = run_backend_enum()
        session['enumeration_results'] = enumeration_outputs

    return render_template("enumeration.html", enumeration_outputs=enumeration_outputs)

# if not os.path.exists('nikto_log'):
#     os.makedirs('nikto_log')

if not os.path.exists('ferox_log'):
        os.makedirs('ferox_log')

def run_feroxbuster(onion_link, index):

    feroxbuster_command = f"feroxbuster -u {onion_link} -w wordlist.txt --proxy socks5h://127.0.0.1:9050 --threads 30 -C 404 --time-limit 40s --auto-bail -q"
    
    try:
        feroxbuster_output = subprocess.check_output(feroxbuster_command, shell=True, stderr=subprocess.STDOUT, text=True)
    except subprocess.CalledProcessError as e:
        feroxbuster_output = e.output
    
    # Filter out lines containing "404"
    filtered_output_lines = [line for line in feroxbuster_output.split('\n') if "404" not in line]

    # Combine the filtered lines back into a single string
    filtered_output = '\n'.join(filtered_output_lines)

    with open(f'ferox_log/fuzz{index}.log', 'w') as log_file:
        log_file.write(filtered_output)

    return filtered_output

def run_backend_enum():
    with open('domains.txt', 'r') as file:
        onion_links = file.read().splitlines()

    enumeration_outputs = []

    def run_feroxbuster_for_link(onion_link, index):
        feroxbuster_output = run_feroxbuster(onion_link, index)
        enumeration_outputs.append({
            'onion_link': onion_link,
            'feroxbuster_output': feroxbuster_output
        })

    # Create a list to hold thread objects
    threads = []

    for index, onion_link in enumerate(onion_links, start=1):
        # Create a thread for each onion_link
        thread = threading.Thread(target=run_feroxbuster_for_link, args=(onion_link, index))
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    return enumeration_outputs

@app.route("/search", methods=["GET", "POST"])

def search():
    entry_node, exit_node = get_last_entry_exit_relay()
    keywords = request.form.get("keywords")
    
    if keywords is None:
        message = f"capNcook|"
        return render_template("index.html", entry_node=entry_node, exit_node=exit_node, message=message)
        # return {
        #     'pub_ip': pub_ip,
        #     'anon_ip': anon_ip,
        #     'message': 'No search input provided in the request.',
        #     'domain_links': []
        # }
    
    encoded_keywords = urllib.parse.quote(keywords.encode("utf-8"))
    
    print(colored("[+] Searching for top domains... \n", "yellow"))
    
    cmd1 = f"curl -s 'https://ahmia.fi/search/?q={encoded_keywords}' | grep -oE 'http[s]?://[^/]+\.onion' 2>/dev/null | head -n 15 > domains.txt 2>/dev/null"
    
    # cmd2 = "cat domains.txt 2>/dev/null | ./aquatone -out templates/aqua_out -proxy socks5://127.0.0.1:9050 -ports 80 -threads 50 -http-timeout 30000 -screenshot-timeout 10000 -resolution \"1920,1080\" 2>/dev/null"

    total_iterations = 1
    
    # Use tqdm to create a progress bar for cmd1
    custom_bar_format = "{desc} | {bar} | {percentage:3.0f}%"
    with tqdm(total=total_iterations, unit="onions", desc="Indexing: ", dynamic_ncols=True, bar_format=custom_bar_format, colour="green") as pbar:
        for i in range(total_iterations):
            os.system(cmd1)  # Execute cmd1
            pbar.update(1)   # Update the progress bar
            print('\r', end='')

    print(colored("\n[-] Done!", "blue"))

    with open('domains.txt', 'r') as file:
        links = file.readlines()        

    domain_links = [{'title': link.strip(), 'link': 'http://' + link.strip()} for link in links]

    message = f"Domains Listed for {keywords}|"

    return render_template("index.html", entry_node=entry_node, exit_node=exit_node, message=message, domain_links=domain_links)

@app.route('/refresh_cache', methods=['POST'])

def refresh_cache():
    if 'onionCheck_results' in session:
        del session['onionCheck_results']
    if 'recon_results' in session:
        del session['recon_results']
    if 'headers_results' in session:
        del session['headers_results']
    if 'enumeration_results' in session:
        del session['enumeration_results']

    return redirect(request.referrer)


if __name__ == "__main__":

    app.run(host='0.0.0.0')
