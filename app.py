from flask import Flask, render_template, request, jsonify, url_for
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import os
from flask import redirect
from termcolor import colored
import requests
import subprocess
import json
import urllib.parse
from time import sleep
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from stem import CircStatus
from stem.control import Controller

load_dotenv()

# Really ignore this, I regret not deleting this - Hoodie
# os.system('curl --socks5 localhost:9050 --socks5-hostname localhost:9050 -s https://check.torproject.org/ | cat | grep -m 1 Congratulations | xargs')
# print("\n")
os.system("echo 'hidden service ->' $(echo 'h00di3' | sudo -S cat /var/lib/tor/capNcook/hostname)")

app = Flask(__name__, static_url_path='/static', template_folder='templates')

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

                if entry_fp == exit_fp:
                    # Entry and exit nodes are the same, flush circuits and rebuild
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
        # The "Run" button has been clicked; execute the backend code
        proxies = {
            'http': 'socks5h://127.0.0.1:9050',
            'https': 'socks5h://127.0.0.1:9050'
        }

        with open('domains.txt', 'r') as file:
            domains = file.readlines()

        results = []

        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = []

            for url in domains:
                url = url.strip('\n')
                future = executor.submit(check_domain, url, proxies)
                futures.append(future)

            for future in as_completed(futures):
                result = future.result()
                results.append(result)

        return render_template("onion_check.html", results=results)
    
    else:
        # Display the form with the "Run" button
        return render_template("onion_check_form.html")

def check_domain(url, proxies):
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
        meta_description = soup.find("meta", attrs={"name": "description"})
        page_description = meta_description.get("content") if meta_description else 'N/A'

        result['url'] = url
        result['status'] = 'Active'
        result['status_code'] = data.status_code
        result['page_title'] = page_title
        result['page_description'] = page_description

    elif data == 'error':
        status = "Inactive"
        status_code = 'NA'
        page_title = 'NA'
        page_description = 'NA'
        result['url'] = url
        result['status'] = 'Inactive'
        result['status_code'] = 'NA'
        result['page_title'] = 'NA'
        result['page_description'] = 'NA'

    print("\n")
    print(colored(f"{[status_code]}: {url}: {page_title} -> {status}", "cyan"))

    return result

@app.route('/recon', methods=['GET', 'POST'])
def recon():

    if request.method == 'POST':
        # The "Run" button has been clicked; execute the backend code
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
        # Display the form with the "Run" button
        return render_template("recon_form.html")

@app.route('/headers', methods=['GET', 'POST'])
def headers():

    if  request.method == 'POST':
        # The "Run" button has been clicked; execute the backend code

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
                    domains.append(headers)
            except Exception as e:
                print(f"An error occurred for {onion_url}: {str(e)}")

        domains = []
        screenshot_dir = 'aqua_out/screenshots'

        with open('domains.txt', 'r') as file:
            onion_urls = file.read().splitlines()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []

            for onion_url in onion_urls:
                future = executor.submit(fetch_header, onion_url)
                futures.append(future)

            for future in as_completed(futures):
                # The result is not needed, as data is appended to the 'domains' list within the function.
                pass

        return render_template("headers.html", domains=domains)

    else:
        return render_template("headers_form.html")

@app.route('/enumeration', methods=['GET', 'POST'])
def enumeration():

    if  request.method == 'POST':
        # The "Run" button has been clicked; execute the backend code

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

        # Create a ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []

            for index, onion_link in enumerate(onion_links, start=1):
                # Submit tasks to the executor
                future = executor.submit(run_feroxbuster_for_link, onion_link, index)
                futures.append(future)

            # Wait for all tasks to complete
            for future in as_completed(futures):
                # The result is not needed, as data is appended to the 'enumeration_outputs' list within the function.
                pass

        return render_template("enumeration.html", enumeration_outputs=enumeration_outputs)
    
    else:
        # Display the form with the "Run" button
        return render_template("enumeration_form.html")

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

@app.route("/search", methods=["GET", "POST"])
def search():
    entry_node, exit_node = get_last_entry_exit_relay()
    keywords = request.form.get("keywords")
    selected_engine = request.form.get("search_engine")
    
    if keywords is None:
        message = "capNcook|"
        return render_template("index.html", entry_node=entry_node, exit_node=exit_node, message=message)
    
    # return {
        #     'pub_ip': pub_ip,
        #     'anon_ip': anon_ip,
        #     'message': 'No search input provided in the request.',
        #     'domain_links': []
        # }

    encoded_keywords = urllib.parse.quote(keywords.encode("utf-8"))
    
    search_engines = {
        "ahmia": "https://ahmia.fi/search/?q={}",
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

    encoded_keywords = urllib.parse.quote(keywords.encode("utf-8"))

    if selected_engine == "ahmia":
        search = f"curl -s '{search_url}' | grep -oE 'http[s]?://[^/]+\.onion' 2>/dev/null | head -n 15 > domains.txt 2>/dev/null"
    elif selected_engine == "excavator":
        excavator_search = f'curl -x socks5h://localhost:9050 -s "{search_url}" | grep -A 400 "<h6>SEARCH RESULTS</h6>" | grep -v "{excavator_engine}" | grep -v "{disgust_1}" | grep -v "{disgust_2}" | grep -oE "http[s]?://[^/]+\.onion" | head -n 15 > domains.txt 2>/dev/null'
        search = excavator_search
    elif selected_engine == "torch":
        search = f'curl -x socks5h://localhost:9050 -s "{search_url}" | grep -A 800 "Your search" | grep -v "http://tordexu73joywapk2txdr54jed4imqledpcvcuf75qsas2gwdgksvnyd.onion" | grep -oE "http[s]?://[^/]+\.onion" 2>/dev/null | uniq -u | head -n 15 > domains.txt 2>/dev/null'
    elif selected_engine == "deepsearch":
        # search = f'curl -x socks5h://localhost:9050 -s "{search_url}" | grep -A 800 "Last seen" | grep -oE "http[s]?://[^/]+\.onion" 2>/dev/null | uniq -u | awk \"{{print $1}}\" | sed -e "s/\'.*//g" | head -n 15 > domains.txt 2>/dev/null'
        search = f'curl -x socks5h://localhost:9050 -s "{search_url}" | grep -oE "http[s]?://[^/]+\.onion" 2>/dev/null | head -n 40 | uniq > domains.txt 2>/dev/null'
    elif selected_engine == "underdir":
        search = f'curl -x socks5h://localhost:9050 -s "{search_url}" | grep -oE "http[s]?://[^/]+\.onion" 2>/dev/null | head -n 20 > domains.txt 2>/dev/null'
    elif selected_engine == "onionland":
        search = f'curl -s "{search_url}" | grep -oE "http[s]?://[^/]+\.onion" 2>/dev/null | head -n 40 | uniq > domains.txt 2>/dev/null'
    elif selected_engine == "grams":
        search = f'curl -x socks5h://localhost:9050 -s "{search_url}" | grep -A 800 "<ul>" | grep -oE "http[s]?://[^/]+\.onion" 2>/dev/null | head -n 15 > domains.txt 2>/dev/null'
    else:
        search = "echo 'y0u n00b'"

    os.system(search)

    print(colored("[-] Done!", "blue"))

    with open('domains.txt', 'r') as file:
        links = file.readlines()        

    domain_links = [{'title': link.strip(), 'link': 'http://' + link.strip()} for link in links]

    message = f"Domains Listed for {keywords}|"
    
    return render_template("index.html", entry_node=entry_node, exit_node=exit_node, message=message, domain_links=domain_links)

@app.route('/run', methods=['POST'])
def run():
    referrer = request.referrer  # Get the referrer URL to determine the calling route

    if "/onion_check" in referrer:
        # Execute the onion_check backend code
        results = onion_check_backend()
        return render_template("onion_check.html", results=results)
    elif "/recon" in referrer:
        # Execute the recon backend code
        results = recon_backend()
        return render_template("recon.html", recon_outputs=recon_outputs)
    elif "/headers" in referrer:
        # Execute the headers backend code
        results = headers_backend()
        return render_template("headers.html", domains=domains)
    elif "/enumeration" in referrer:
        # Execute the enumeration backend code
        results = enumeration_backend()
        return render_template("enumeration.html", enumeration_outputs=enumeration_outputs)

    # Handle the case where the referrer doesn't match any known route
    return redirect(request.referrer)

@app.route('/refresh/<functionality>', methods=['GET'])
def refresh(functionality):

    if functionality == 'onion_check':
        return redirect(url_for('onion_check'))
    elif functionality == 'recon':
        return redirect(url_for('recon'))
    elif functionality == 'headers':
        return redirect(url_for('headers'))
    elif functionality == 'enumeration':
        return redirect(url_for('enumeration'))
    else:
        # Handle the case where 'functionality' doesn't match any known value
        return redirect(url_for('index'))

if __name__ == "__main__":

    app.run(host='0.0.0.0')