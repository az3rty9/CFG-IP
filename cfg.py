import sys , os  , re
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
import datetime  
import socket
import zipfile
import shutil
import http.client
import socket
import ssl
import time

import argparse
import geoip2.database

class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m" 

totale = 0
success = 0
fail = 0
zip_url = "zip.baipiao.eu.org"
request_url = "speed.cloudflare.com"
request_url_path = "/cdn-cgi/trace"
timeout = 4 
no_test = False 
headers = {"user-agent": "Mozilla/5.0"}
enable_tls = True
verbose = False
max_workers = 10
country_names = []
country_continent_names = []

database_file = Path(__file__).with_name('GeoLite2-Country.mmdb')
asn_database_file = Path(__file__).with_name('GeoLite2-ASN.mmdb')

script_dir = Path(__file__).parent
result_dir_day = datetime.datetime.now().strftime('%Y-%m-%d')
timestamp = f"{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
result_folder = f"{script_dir}\\Result\\{result_dir_day}\\{timestamp}"


def save_to_file(data , country_name):
    os.makedirs(result_folder, exist_ok=True)
    result_file = os.path.join(result_folder, f"{country_name}_{timestamp}.txt")
    with open(result_file, "a") as f :
        f.writelines(f"{data}\n")
        f.close()


def banner():
    banner = """
  ██████╗███████╗ ██████╗ -      -██╗██████╗ 
 ██╔════╝██╔════╝██╔════╝ -      -██║██╔══██╗
 ██║     █████╗  ██║  ███╗-█████╗-██║██████╔╝
 ██║     ██╔══╝  ██║   ██║-╚════╝-██║██╔═══╝ 
 ╚██████╗██║     ╚██████╔╝-      -██║██║     
  ╚═════╝╚═╝      ╚═════╝ -      -╚═╝╚═╝     
"""

    for l in banner.split('\n') :
        split = l.split('-')
        if len(split) > 1:
            print(Colors.RED + split[0], Colors.WHITE + split[1], Colors.YELLOW + split[2] + Colors.RESET)

    max_banner_lenght =  max(len(banner) for banner in banner.split('\n'))
    print(Colors.WHITE + "".ljust(max_banner_lenght, '─'))
    space = "   "#.ljust(int(max_banner_lenght / 4 ), ' ') 
    print (space + "•Author  : " , "! AZERTY9 !" )
    print (space + "•Github  : " , "https://github.com/az3rty9" )
    print (space + "Telegram : " , "https://t.me/N3wB0rn9" ) 
    print (space + "•Version : " , "1.0" )
    
    print("".ljust(max_banner_lenght, '─'))


def remove_duplicates(input_file):
    with open(input_file, 'r') as file:
        lines = file.read().split('\n') #.readlines()
        unique_urls = list(set(lines))#list(dict.fromkeys(lines))
    return unique_urls       


def print_ascii_table(data):

    max_country_len = max(len(country) for country in data.keys())
    max_count_len = max(len(str(count)) for count in data.values())

    if max_count_len < 5 :
        max_count_len = max_count_len + (5 - max_count_len  )
    if max_country_len < 7 :
        max_country_len = max_country_len + (7 - max_country_len)

    print(f"+{'-' * (max_country_len + 2)}+{'-' * (max_count_len + 2)}+")
    print(f"| {'Country':<{max_country_len}} | {'Count':<{max_count_len }} |")
    print(f"+{'-' * (max_country_len + 2)}+{'-' * (max_count_len + 2)}+")


    for country, count in data.items():
        print(f"| {country:<{max_country_len}} | { count:>{ max_count_len}} |")


    print(f"+{'-' * (max_country_len + 2)}+{'-' * (max_count_len + 2)}+")


def create_ssl_connection(ip_addr, port, timeout):
    sock = socket.create_connection((ip_addr, port), timeout=timeout)
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    ssl_sock = context.wrap_socket(sock, server_hostname=request_url)
    return ssl_sock


def test_ipaddress (ip_addr, port):
    try:  
        conn = None
        if int(port) in [443,2053,2083,2087,2096,8443] :
            conn = create_ssl_connection(ip_addr, port, timeout)
        else:
           conn = socket.create_connection((ip_addr, port), timeout=timeout)  
           
        #,context=ssl._create_unverified_context()
        client = http.client.HTTPSConnection(request_url) if not enable_tls else http.client.HTTPSConnection(request_url)
        client.sock = conn
                        
        start_time = time.time()
        client.request("GET", request_url_path,headers=headers)
        response = client.getresponse()
        tcp_duration = time.time() - start_time
        body = response.read().decode("utf-8")
        #print(body)
        #matches = dict(re.findall(r"(\w+)=(.+)", body))
        #if matches.get('ip') == ip_addr:
        if f"ip={ip_addr}" in body : 
            latency = f"{tcp_duration * 1000:.0f} ms"
            return latency#, matches
        conn.close()
        return None       
    except Exception as e:
        #print(f'{Colors.RED}[ERROR]{Colors.WHITE}', e)
        return None
    


def geoip_asn_info(ip_address):
    reader = geoip2.database.Reader(asn_database_file)
    try:
        response = reader.asn(ip_address)
        asn_number = response.autonomous_system_number
        asn_name = response.autonomous_system_organization
        return asn_number, asn_name
    except geoip2.errors.AddressNotFoundError:
        print("IP address not found in the database")
    finally:
        reader.close()


def geoip_country(ip_address, port):
    global totale
    global success
    global fail
    totale +=1
    reader = geoip2.database.Reader(database_file)
    try:
        if is_ip_address(ip_address):
            to_print = None
            if not no_test :
                print('test')
                latency = test_ipaddress (ip_address, port)
                if latency:
                    to_print = f"latency: {latency}"
                else:
                    fail+=1
                    return

            response = reader.country(ip_address)
            country_name = response.country.name
            country_names.append(country_name)
            
            country_continent = response.continent.name   
            country_continent_names.append(country_continent)
            asn_number, asn_name = geoip_asn_info(ip_address)

            to_print = ' , '.join(map(str, [
                            f"IPaddress: {ip_address}:{port}",
                            f"Country: {country_name}/{country_continent}",
                            f"ASN Number: {asn_number}",
                            f"ASN Name: {asn_name}",
                            to_print                       
                            ]))
            
                
            if verbose : print (f"[{Colors.GREEN}{success}{Colors.WHITE}]", to_print)
            success+=1
            save_to_file(to_print, country_name)

               
                    
               # {Colors.RESET}
        else :
            fail+=1
        
    except geoip2.errors.AddressNotFoundError:
        print(f"{Colors.RED}[ERROR]{Colors.WHITE} No information found for the IP address {ip_address}.")
        fail+=1
    except Exception as e  : 
        print("{Colors.RED}[ERROR]{Colors.WHITE}", e)
        fail+=1
    finally:
        reader.close()


def is_ip_address(string):
    try:
        socket.inet_pton(socket.AF_INET, string)
        return True
    except socket.error:
        pass

    try:
        socket.inet_pton(socket.AF_INET6, string)
        return True
    except socket.error:
        pass

    return False


def download_file(zip_url, file_path, file_name):

    old_dir = os.path.join(script_dir, "trash")
    os.makedirs(old_dir, exist_ok=True)
  
    if os.path.exists(file_path):
        old_file_path = os.path.join(old_dir, f"{timestamp}_{file_name}")
        shutil.move(file_path, old_file_path)
        print(f"Moved old file to {old_file_path}")
    
    conn = http.client.HTTPSConnection(zip_url)
    conn.request("GET", "/")
    response = conn.getresponse()
    if response.status == 200:
        with open(file_path, 'wb') as file:
            file.write(response.read())
        print(f"File downloaded successfully to {file_path}")
        return True
    else:
        print(f"Failed to download file: {response.status} {response.reason}")
    

pattern = r'(\d+)-\d+-(\d+)'
def extract_port(file_name):
    match = re.search(pattern, file_name)
    if match:
        asn = match.group(1)
        return match.group(2)
    return None


def fromFile(file_path, port):
    #try:
    print("\n[+]Processing: ", file_path)
    with open(file_path) as f:
        ips = f.read().split('\n')       
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            list(pool.map(partial(geoip_country, port=port), ips))
    #except KeyboardInterrupt:
    #    print("\nKeyboardInterrupt: Ctrl+C was pressed. Cleaning up...")
        

def allFile():
    files = os.listdir(script_dir)
    text_files = [file for file in files if file.endswith('.txt')]
    for file_name in text_files:
        port = extract_port(file_name)
        if port:
            file_path = os.path.join(script_dir, file_name)         
            fromFile(file_path, port)   
        else:
            print("No match found for filename:", file_name)
        

def from_zip_file(file_path):
    with zipfile.ZipFile(file_path, "r") as zip_file:
        for file_name in zip_file.namelist():
            if file_name.endswith(".txt"):
                print(file_name)
                with zip_file.open(file_name, "r") as file:
                    content = file.read().decode("utf-8").split('\n')  # Assuming UTF-8 encoding
                    port = extract_port(file_name)
                    if port:
                        with ThreadPoolExecutor(max_workers=20) as pool:
                            list(pool.map(partial(geoip_country, port=port),content)) 
                    else:
                        print("No match found for filename:", file_name)
        

def main():
    global verbose, max_workers, timeout, enable_tls, no_test
    global country_names, country_continent_names
    parser = argparse.ArgumentParser(description="Read text files from a zip archive.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-zip', action='store_true', help="Path to the zip file")
    group.add_argument('-f', action='store_true', help="Path to the text file")
    group.add_argument('-ip', action='store', help="Test target")   
    parser.add_argument('-dw', action='store_true', help="Download zip file")
    parser.add_argument('-fn', action='store', help="File name")
    parser.add_argument('-notls', action='store_false', help="Disable Tls")
    parser.add_argument('-notest', action='store_true', help="Sort ip by country only")
    parser.add_argument('-t',type=int, action='store',default=4, help="Timeout")
    parser.add_argument('-th',type=int, action='store',default=10, help="Max workers")
    parser.add_argument('-v', action='store_true', help="Verbose")

    args = parser.parse_args()
    print(args)
    verbose = args.v
    max_workers = args.th
    timeout = args.t
    enable_tls = args.notls
    no_test = args.notest

    if args.zip:
        file_path = Path(__file__).with_name('txt.zip')
        if args.dw :#or not os.path.exists(file_path)
            if download_file(zip_url, file_path, 'txt.zip'):
                from_zip_file(file_path)
        elif args.fn:
            from_zip_file(args.fn)
        else:
            from_zip_file(file_path)
    
    elif args.f:
        if args.fn:
            port = extract_port(args.fn)
            if port:
                file_path = Path(__file__).with_name(args.fn) 
                fromFile(file_path, port)
        else : 
            allFile()
    elif args.ip:
        print("\n[+]Processing: ",args.ip)
        splited = args.ip.split(':')
        ipaddress = splited[0]
        port = splited[1]
        geoip_country(ipaddress, port)
    
    country_names = ['NV' if country is None else country for country in country_names]
    country_continent_names = ['NV' if continent is None else continent for continent in country_continent_names]
    
    if country_names :
        print(country_names, len(country_names))
        country_counts = {}
        for country in country_names:
            if country in country_counts:
                country_counts[country] += 1
            else:
                country_counts[country] = 1

        continent_counts = {}
        for continent in country_continent_names:
            if continent in continent_counts:
                continent_counts[continent] += 1
            else:
                continent_counts[continent] = 1
        
        print_ascii_table(country_counts)
        print_ascii_table(continent_counts)

    print(f"\nTotale Scanned: {totale} | Success : {success} | Fail : {fail} ")


if __name__ == "__main__":
    banner()
    main()


