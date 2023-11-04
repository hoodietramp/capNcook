import os

keyword="forums"

cmd1 = f"curl -s -x socks5h://localhost:9050 'http://2fd6cemt4gmccflhm6imvdfvli3nf7zn6rfrwpsy7uhxrgbypvwf5fad.onion/search/{keyword}' | grep -oE 'http[s]?://[^/]+\.onion' 2>/dev/null | head -n 15 > new.txt 2>/dev/null"

os.system(cmd1)