from flask import Flask, render_template, request, jsonify, url_for
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import os
from flask import redirect
from termcolor import colored
import requests
from requests.adapters import HTTPAdapter
import subprocess
import json
import urllib.parse
from time import sleep
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from stem import CircStatus
from stem.control import Controller

load_dotenv()

os.system("echo 'hidden service ->' $(sudo cat /var/lib/tor/capNcook/hostname)")

app = Flask(__name__, static_url_path='/static', template_folder='templates')

SCREENSHOT_DIR = 'screenshots'
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# --- Secure requests session (fixes Requests CVEs) ---
def make_tor_session():
    session = requests.Session()
    session.proxies = {
        'http': 'socks5h://127.0.0.1:9050',
        'https': 'socks5h://127.0.0.1:9050'
    }
    session.verify = True
    return session


def get_last_entry_exit_relay():
    entry_node = {}
    exit_node = {}

    with Controller.from_port(port=9051) as controller:
        try:
            controller.authenticate()
            controller.signal("NEWNYM")

            last_circuit = None

            for circ in controller.get_circuits():
                if circ.status != CircStatus.BUILT:
                    continue

                last_circuit = circ

            if last_circuit:
                entry_fp, entry_nickname = last_circuit.path[0]
                entry_desc = controller.get_network_status(entry_fp, None)
                entry_address = entry_desc.address if entry_desc else 'unknown'

                entry_node = {
                    "fingerprint": entry_fp,
                    "nickname": entry_nickname,
                    "address": entry_address
                }

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

                if entry_fp == exit_fp:
                    print("Entry and exit nodes are the same. Rebuilding circuits...")
                    controller.signal("NEWNYM")
                    print("All circuits have been flushed and rebuilt!")

        except Exception as e:
            print(f"An error occurred: {e}")

    return entry_node, exit_node

@app.route("/")
def index():
    entry_node, exit_node = get_last_entry_exit_relay()
    return render_template("index.html", entry_node=entry_node, exit_node=exit_node)

@app.route('/onion_check', methods=['GET', 'POST'])
def onion_check():

    if request.method == 'POST':
        with open('domains.txt', 'r') as file:
            domains = file.readlines()

        results = []

        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = []

            for url in domains:
                url = url.strip('\n')
                future = executor.submit(check_domain, url)
                futures.append(future)

            for future in as_completed(futures):
                result = future.result()
                results.append(result)

        return render_template("onion_check.html", results=results)
    
    else:
        return render_template("onion_check_form.html")

def check_domain(url):
    session = make_tor_session()
    result = {}
    status = 'N/A'
    status_code = 'N/A'

    try:
        data = session.get(url, timeout=30)
        soup = BeautifulSoup(data.text, 'html.parser')
        page_title = soup.title.string if soup.title else 'N/A'
        meta_description = soup.find("meta", attrs={"name": "description"})
        page_description = meta_description.get("content") if meta_description else 'N/A'

        result['url'] = url
        result['status'] = 'Active'
        result['status_code'] = data.status_code
        result['page_title'] = page_title
        result['page_description'] = page_description

        print(colored(f"[{data.status_code}]: {url}: {page_title} -> Active", "cyan"))

    except Exception:
        result['url'] = url
        result['status'] = 'Inactive'
        result['status_code'] = 'N/A'
        result['page_title'] = 'N/A'
        result['page_description'] = 'N/A'

        print(colored(f"[N/A]: {url} -> Inactive", "cyan"))

    return result

@app.route('/recon', methods=['GET', 'POST'])
def recon():

    if request.method == 'POST':
        def run_whois(onion_link, index):
            command = f"sleep 0.5s; whois -h torwhois.com {onion_link} | tee recon_output/recon{index}.txt"
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

        return render_template("recon.html", recon_outputs=recon_outputs)

    else:
        return render_template("recon_form.html")

@app.route('/headers', methods=['GET', 'POST'])
def headers():

    if request.method == 'POST':
        print(colored("\n[+] Capturing Screenshots via gowitness...", "green"))

        with open('domains.txt', 'r') as file:
            onion_urls = file.read().splitlines()
        
        gowitness_cmd = (
            f"gowitness scan file -f domains.txt "
            f"--chrome-proxy socks5://127.0.0.1:9050 "
            f"--screenshot-path static/{SCREENSHOT_DIR} "
            f"--screenshot-format png "
            f"--chrome-window-x 1920 "
            f"--chrome-window-y 1080 "
            f"--timeout 60 "
            f"--threads 5 "
            f"--write-none"
        )
        os.system(gowitness_cmd)
        print(colored("[+] Screenshots done!", "green"))

        domains = []

        def fetch_header(onion_url):
            session = make_tor_session()
            try:
                onion_url = onion_url.strip()

                screenshot_path = None
                
                ss_dir = os.path.join("static", SCREENSHOT_DIR)

                if os.path.exists(ss_dir):
                    slug = onion_url.strip().replace('://', '---').replace('/', '-')

                    for f in os.listdir(ss_dir):
                        if slug in f and f.endswith('.png'):
                            screenshot_path = f"{SCREENSHOT_DIR}/{f}"
                            print("[DEBUG]", onion_url, "→", screenshot_path)
                            break

                response = session.get(onion_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
                if response.status_code == 200:
                    domains.append({
                        'title': onion_url,
                        'headers': response.headers,
                        'screenshot': screenshot_path,
                    })
            except Exception as e:
                print(f"An error occurred for {onion_url}: {str(e)}")

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(fetch_header, url) for url in onion_urls]
            for future in as_completed(futures):
                pass

        return render_template("headers.html", domains=domains)

    else:
        return render_template("headers_form.html")

@app.route('/enumeration', methods=['GET', 'POST'])
def enumeration():

    if  request.method == 'POST':
        if not os.path.exists('ferox_log'):
            os.makedirs('ferox_log')

        with open('domains.txt', 'r') as file:
            onion_links = file.read().splitlines()

        enumeration_outputs = []

        def run_feroxbuster_for_link(onion_link, index):
            feroxbuster_output = run_feroxbuster(onion_link, index)
            enumeration_outputs.append({
                'onion_link': onion_link,
                'feroxbuster_output': feroxbuster_output
            })

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []

            for index, onion_link in enumerate(onion_links, start=1):
                future = executor.submit(run_feroxbuster_for_link, onion_link, index)
                futures.append(future)

            for future in as_completed(futures):
                pass

        return render_template("enumeration.html", enumeration_outputs=enumeration_outputs)
    
    else:
        return render_template("enumeration_form.html")

def run_feroxbuster(onion_link, index):

    feroxbuster_command = f"feroxbuster -u {onion_link} -w wordlist.txt --proxy socks5h://127.0.0.1:9050 --threads 30 -C 404 --time-limit 40s --auto-bail -q"
    
    try:
        feroxbuster_output = subprocess.check_output(feroxbuster_command, shell=True, stderr=subprocess.STDOUT, text=True)
    except subprocess.CalledProcessError as e:
        feroxbuster_output = e.output
    
    filtered_output_lines = [line for line in feroxbuster_output.split('\n') if "404" not in line]
    filtered_output = '\n'.join(filtered_output_lines)

    with open(f'ferox_log/fuzz{index}.log', 'w') as log_file:
        log_file.write(filtered_output)

    return filtered_output

@app.route("/search", methods=["GET", "POST"])
def search():
    entry_node, exit_node = get_last_entry_exit_relay()
    keywords = request.form.get("keywords")
    selected_engine = request.form.get("search_engine")
    
    if keywords is None:
        message = "capNcook|"
        return render_template("index.html", entry_node=entry_node, exit_node=exit_node, message=message)

    encoded_keywords = urllib.parse.quote(keywords.encode("utf-8"))
    
    search_engines = {
        "ahmia": "https://ahmia.fi/search/?q={}&f4d0c1=25fa80",
        "excavator": "http://2fd6cemt4gmccflhm6imvdfvli3nf7zn6rfrwpsy7uhxrgbypvwf5fad.onion/search/{}",
        "torch": "http://torchdeedp3i2jigzjdmfpn5ttjhthh5wbmda2rr3jvqjg5p77c54dqd.onion/search?query={}",
        "deepsearch": "http://search7tdrcvri22rieiwgi5g46qnwsesvnubqav2xakhezv4hjzkkad.onion/result.php?search={}",
        "underdir": "http://underdiriled6lvdfgiw4e5urfofuslnz7ewictzf76h4qb73fxbsxad.onion/?search={}",
        "onionland": "https://onionland.io/search?q={}",
        "grams": "http://grams64rarzrk7rzdaz2fpb7lehcyi7zrrf5kd6w2uoamp7jw2aq6vyd.onion/search?key={}"
    }
    
    print(colored(f"\nSelected search engine: {selected_engine}", "cyan"))

    excavator_engine = "http://2fd6cemt4gmccflhm6imvdfvli3nf7zn6rfrwpsy7uhxrgbypvwf5fad.onion"
    disgust_1 = "http://ccjbylumupbwqj6ucfjpo72o4dw5rs4blby24l3qtf33we3kx5zpk7yd.onion"
    disgust_2 = "http://4qmgm3znqd2m6foedblw4llbz3vg6eosnwjzx23wlmahuf6e2dsiqmad.onion"
    
    if selected_engine not in search_engines:
        selected_engine = "ahmia"
        return "Invalid search engine selected, setting default to ahmia."
    
    search_url = search_engines[selected_engine].format(encoded_keywords)
    print(search_url)
    
    print(colored("[+] Searching for top domains... \n", "yellow"))

    if selected_engine == "ahmia":
        search = f"curl -s '{search_url}' | grep -oE 'http[s]?://[^/]+\\.onion' 2>/dev/null | head -n 20 | uniq > domains.txt 2>/dev/null"
    elif selected_engine == "excavator":
        search = f'curl -x socks5h://localhost:9050 -s "{search_url}" | grep -A 400 "<h6>SEARCH RESULTS</h6>" | grep -v "{excavator_engine}" | grep -v "{disgust_1}" | grep -v "{disgust_2}" | grep -oE "http[s]?://[^/]+\\.onion" | head -n 15 > domains.txt 2>/dev/null'
    elif selected_engine == "torch":
        search = f'curl -x socks5h://localhost:9050 -s "{search_url}" | grep -A 800 "Your search" | grep -oE "http[s]?://[^/]+\\.onion" 2>/dev/null | uniq -u | head -n 15 > domains.txt 2>/dev/null'
    elif selected_engine == "deepsearch":
        search = f'curl -x socks5h://localhost:9050 -s "{search_url}" | grep -oE "http[s]?://[^/]+\\.onion" 2>/dev/null | head -n 40 | uniq > domains.txt 2>/dev/null'
    elif selected_engine == "underdir":
        search = f'curl -x socks5h://localhost:9050 -s "{search_url}" | grep -oE "http[s]?://[^/]+\\.onion" 2>/dev/null | head -n 20 > domains.txt 2>/dev/null'
    elif selected_engine == "onionland":
        search = f'curl -s "{search_url}" | grep -oE "http[s]?://[^/]+\\.onion" 2>/dev/null | head -n 40 | uniq > domains.txt 2>/dev/null'
    elif selected_engine == "grams":
        search = f'curl -x socks5h://localhost:9050 -s "{search_url}" | grep -A 800 "<ul>" | grep -oE "http[s]?://[^/]+\\.onion" 2>/dev/null | head -n 15 > domains.txt 2>/dev/null'
    else:
        search = "echo 'y0u n00b'"

    os.system(search)

    print(colored("[-] Done!", "blue"))

    with open('domains.txt', 'r') as file:
        links = file.readlines()        

    domain_links = [{'title': link.strip(), 'link': 'http://' + link.strip()} for link in links]

    message = f"Domains Listed for {keywords}|"
    
    return render_template("index.html", entry_node=entry_node, exit_node=exit_node, message=message, domain_links=domain_links)

@app.route('/refresh/<functionality>', methods=['GET'])
def refresh(functionality):
    route_map = {
        'onion_check': 'onion_check',
        'recon': 'recon',
        'headers': 'headers',
        'enumeration': 'enumeration'
    }
    return redirect(url_for(route_map.get(functionality, 'index')))

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=False)