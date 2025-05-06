import os
import json
import requests
import logging
import datetime
import re
import time
import threading
import mimetypes
import concurrent.futures # Added for concurrent fetching
from flask import Flask, jsonify, request, render_template
from urllib.parse import urlparse, unquote
from dotenv import load_dotenv
from waitress import serve

load_dotenv() 



DEFAULT_CW_API_URLS = [
    "https://communities.win/api/v2/post/newv2.json?community=ip2always",
    "https://communities.win/api/v2/post/hotv2.json?community=ip2always",
    "https://communities.win/api/v2/post/newv2.json?community=spictank",
    "https://communities.win/api/v2/post/hotv2.json?community=spictank",
    "https://communities.win/api/v2/post/newv2.json?community=freddiebeans2",
    "https://communities.win/api/v2/post/hot2.json?community=freddiebeans2"

]
CW_API_URLS_STR = os.environ.get('CW_API_URLS')
if CW_API_URLS_STR:
    COMMUNITIES_API_URLS = [url.strip() for url in CW_API_URLS_STR.split(',') if url.strip()]
    if not COMMUNITIES_API_URLS: # Handle case where env var is set but empty after split/strip
        logging.warning("CW_API_URLS environment variable is empty or invalid after parsing. Using default URLs.")
        COMMUNITIES_API_URLS = DEFAULT_CW_API_URLS
    else:
          logging.info(f"Using API URLs from environment variable CW_API_URLS: {COMMUNITIES_API_URLS}")
else:
    logging.info("Using default API URLs.")
    COMMUNITIES_API_URLS = DEFAULT_CW_API_URLS

DEFAULT_FILEDITCH_URL = "https://up1.fileditch.com/upload.php"
FILEDITCH_UPLOAD_URL = os.environ.get('APP_FILEDITCH_URL', DEFAULT_FILEDITCH_URL)

DEFAULT_DATA_PATH = os.path.join('data.json')
DATA_FILE_PATH = os.environ.get('APP_DATA_FILE_PATH', DEFAULT_DATA_PATH)
# Resolve to absolute path for consistency
DATA_FILE_PATH = os.path.abspath(DATA_FILE_PATH)
logging.info(f"Using data file path: {DATA_FILE_PATH}")


# Communities.Win Headers - Load sensitive parts from environment
# Define non-sensitive headers first
COMMUNITIES_HEADERS = {
    'accept': 'application/json, text/plain, */*',
    'accept-encoding': 'gzip, deflate, br, zstd',
    'accept-language': 'en-US,en;q=0.9',
    'priority': 'u=1, i',
    'referer': 'https://communities.win/c/IP2Always/new', # Consider making this dynamic based on URLs?
    'sec-ch-ua': '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
    'x-api-platform': 'Scored-Desktop',
    # Sensitive headers below will be added from environment variables
}

# Get sensitive headers from environment - exit if missing mandatory ones
CW_API_KEY = os.environ.get('CW_API_KEY')
CW_API_SECRET = os.environ.get('CW_API_SECRET')
CW_XSRF_TOKEN = os.environ.get('CW_XSRF_TOKEN')

missing_vars = []
if not CW_API_KEY: missing_vars.append('CW_API_KEY')
if not CW_API_SECRET: missing_vars.append('CW_API_SECRET')
if not CW_XSRF_TOKEN: missing_vars.append('CW_XSRF_TOKEN')

if missing_vars:
    logging.critical(f"Missing required environment variables: {', '.join(missing_vars)}. Please set them and restart. Exiting.")
    exit(1) # Exit if critical configuration is missing
else:
    logging.info("Successfully loaded API Key, Secret, and XSRF Token from environment.")
    COMMUNITIES_HEADERS['x-api-key'] = CW_API_KEY
    COMMUNITIES_HEADERS['x-api-secret'] = CW_API_SECRET
    COMMUNITIES_HEADERS['x-xsrf-token'] = CW_XSRF_TOKEN

SUPPORTED_VIDEO_EXTENSIONS = {'.mp4'}
SUPPORTED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.gif', '.png', '.webp'}
SUPPORTED_EXTENSIONS = SUPPORTED_VIDEO_EXTENSIONS.union(SUPPORTED_IMAGE_EXTENSIONS)

REQUEST_TIMEOUT = 30
UPLOAD_TIMEOUT = 300
PROCESSING_INTERVAL_SECONDS = 120 

log_format = '%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s' # Added threadName
logging.basicConfig(level=logging.INFO, format=log_format, datefmt='%Y-%m-%dT%H:%M:%S%z')
logging.Formatter.converter = lambda *args: datetime.datetime.now(datetime.timezone.utc).timetuple()

script_dir = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(script_dir, 'templates'), static_folder=os.path.join(script_dir, 'static'))


data_lock = threading.Lock()

def load_data(filepath):
    """Loads data from the JSON file. Assumes lock is held."""
    try:
        # Ensure the *directory* exists before trying to read/write
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        if not os.path.exists(filepath):
            logging.info(f"Data file {filepath} not found. Starting fresh.")
            return []
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                logging.info(f"Data file {filepath} is empty. Starting fresh.")
                return []
            try:
                data = json.loads(content)
            except json.JSONDecodeError as json_err:
                logging.error(f"Error decoding JSON from {filepath}: {json_err}. File content: '{content[:100]}...' Starting with empty data.")
                return [] # Return empty list on error
            if not isinstance(data, list):
                logging.error(f"Data in {filepath} is not a list (found {type(data)}). Starting with empty data.")
                return [] # Return empty list if format is wrong
            logging.info(f"Successfully loaded {len(data)} items from {filepath}")
            return data
    except FileNotFoundError:
        # This specific catch might be less likely now with os.makedirs, but keep for robustness
        logging.info(f"Data file {filepath} not found (caught during open). Starting fresh.")
        return []
    except Exception as e:
        logging.error(f"Error loading data from {filepath}: {e}")
        return [] # Return empty list on generic error

def save_data(filepath, data):
    """Saves data to the JSON file. Assumes lock is held."""
    try:
        # Ensure the *directory* exists before trying to write
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        temp_filepath = filepath + ".tmp"
        with open(temp_filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        os.replace(temp_filepath, filepath) # Atomic replace on most OS
        logging.info(f"Data successfully saved to {filepath} ({len(data)} items)")
    except Exception as e:
        logging.error(f"Error saving data to {filepath}: {e}")
        if 'temp_filepath' in locals() and os.path.exists(temp_filepath):
            try:
                os.remove(temp_filepath)
                logging.info(f"Removed temporary file {temp_filepath} after save error.")
            except Exception as remove_err:
                logging.error(f"Could not remove temporary file {temp_filepath} after save error: {remove_err}")


def fetch_communities_data(api_url):
    """Fetches data from a communities.win API endpoint."""
    # This function remains unchanged, designed to fetch one URL
    logging.info(f"Attempting to fetch data from: {api_url}")
    try:
        # Uses the global COMMUNITIES_HEADERS which now includes env vars
        response = requests.get(api_url, headers=COMMUNITIES_HEADERS, timeout=REQUEST_TIMEOUT)
        logging.debug(f"Response status code for {api_url}: {response.status_code}")
        response.raise_for_status()
        try:
            data = response.json()
            logging.debug(f"Successfully decoded JSON from {api_url}")
            return data # Return the parsed data or None on error below
        except json.JSONDecodeError as json_err:
            logging.error(f"Error decoding JSON response from {api_url}. Error: {json_err}. Response text: {response.text[:200]}...")
            return None
    except requests.exceptions.Timeout:
        logging.error(f"Timeout occurred while fetching data from {api_url} after {REQUEST_TIMEOUT} seconds.")
        return None
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error occurred for {api_url}: {http_err}")
        if http_err.response is not None:
             # Check for 401/403 which might indicate bad credentials
             if http_err.response.status_code in [401, 403]:
                  logging.error("Received 401/403 Unauthorized/Forbidden error. Check your CW_API_KEY, CW_API_SECRET, CW_XSRF_TOKEN environment variables.")
             logging.error(f"Status Code: {http_err.response.status_code}, Response: {http_err.response.text[:200]}...")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Generic network error fetching data from {api_url}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logging.error(f"Status Code: {e.response.status_code}, Response: {e.response.text[:200]}...")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred during fetch for {api_url}: {e}")
        return None

def upload_to_fileditch(file_url):
    """Downloads a file (video/image) from a URL and uploads it to FileDitch."""
    try:
        logging.info(f"Attempting to download: {file_url}")
        download_headers = {
            'User-Agent': COMMUNITIES_HEADERS.get('user-agent'), # Get from global headers
            'Accept': 'image/jpeg, image/png, image/gif, image/webp, video/mp4, */*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': file_url
        }
        with requests.get(file_url, stream=True, timeout=REQUEST_TIMEOUT, headers=download_headers) as r:
            r.raise_for_status()
            logging.info(f"Download started for {file_url} (Status: {r.status_code})")

            filename = None
            original_extension = os.path.splitext(urlparse(file_url).path)[1].lower()

            try:
                content_disposition = r.headers.get('content-disposition')
                if content_disposition:
                    fname_match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', content_disposition, re.IGNORECASE)
                    if fname_match:
                        filename = unquote(fname_match.group(1))
                        filename = re.sub(r'[\\/*?:"<>|]', '_', filename) # Basic sanitization
                        logging.debug(f"Filename from Content-Disposition: '{filename}'")

                if not filename:
                    parsed_url = urlparse(file_url)
                    path_part = unquote(parsed_url.path.split('/')[-1])
                    if path_part and '.' in path_part:
                        filename = re.sub(r'[\\/*?:"<>|]', '_', path_part) # Basic sanitization
                        logging.debug(f"Filename from URL path: '{filename}'")

                if not filename:
                    fallback_ext = original_extension if original_extension in SUPPORTED_EXTENSIONS else ".dat"
                    filename = f"upload{fallback_ext}"
                    logging.debug(f"Using fallback filename: '{filename}'")

                # Ensure filename has an extension (add original if missing and supported)
                if '.' not in filename[-6:]: # Check last few chars for extension
                    current_ext = os.path.splitext(filename)[1]
                    if not current_ext:
                          add_ext = original_extension if original_extension in SUPPORTED_EXTENSIONS else ".dat"
                          filename += add_ext
                          logging.debug(f"Appended extension '{add_ext}', final filename: '{filename}'")

            except Exception as e_fname:
                logging.warning(f"Could not reliably determine filename for {file_url}: {e_fname}. Using fallback 'upload.dat'.")
                filename = "upload.dat"

            mime_type, _ = mimetypes.guess_type(filename)
            if not mime_type:
                # Fallback MIME type guessing based on known extensions
                if original_extension == '.mp4': mime_type = 'video/mp4'
                elif original_extension in ['.jpg', '.jpeg']: mime_type = 'image/jpeg'
                elif original_extension == '.png': mime_type = 'image/png'
                elif original_extension == '.gif': mime_type = 'image/gif'
                elif original_extension == '.webp': mime_type = 'image/webp'
                else: mime_type = 'application/octet-stream'
                logging.warning(f"Could not guess MIME type for '{filename}'. Using fallback: {mime_type}")
            logging.debug(f"Using MIME type: {mime_type} for upload.")

            files = {'files[]': (filename, r.raw, mime_type)}
            # Uses the global FILEDITCH_UPLOAD_URL
            logging.info(f"Uploading '{filename}' (from {file_url}, type: {mime_type}) to {FILEDITCH_UPLOAD_URL}...")

            upload_response = requests.post(FILEDITCH_UPLOAD_URL, files=files, timeout=UPLOAD_TIMEOUT)
            upload_response.raise_for_status()

            try:
                upload_data = upload_response.json()
            except json.JSONDecodeError:
                logging.error(f"Error decoding FileDitch JSON response. Status: {upload_response.status_code}. Response text: {upload_response.text[:200]}...")
                return None

            logging.debug(f"FileDitch response: {json.dumps(upload_data, indent=2)}")

            if upload_data.get("success") is True and isinstance(upload_data.get("files"), list) and len(upload_data["files"]) > 0:
                first_file = upload_data["files"][0]
                if isinstance(first_file, dict) and first_file.get("url"):
                    fileditch_link = first_file["url"]
                    logging.info(f"Successfully uploaded to FileDitch: {fileditch_link}")
                    return fileditch_link
                else:
                    logging.error(f"FileDitch response structure mismatch or missing 'url'. File data: {first_file}")
                    return None
            else:
                error_message = upload_data.get("error", "No specific error message provided.")
                logging.error(f"FileDitch upload failed. Success flag: {upload_data.get('success')}. Error: {error_message}. Full response: {upload_data}")
                return None

    except requests.exceptions.Timeout:
        stage = "download" if 'r' not in locals() else "upload"
        timeout_val = REQUEST_TIMEOUT if stage == "download" else UPLOAD_TIMEOUT
        logging.error(f"Timeout ({timeout_val}s) occurred during {stage} for URL: {file_url}")
        return None
    except requests.exceptions.HTTPError as http_err:
        stage = "download" if 'r' not in locals() else "upload"
        logging.error(f"HTTP error occurred during {stage} for {file_url}: {http_err}")
        if hasattr(http_err, 'response') and http_err.response is not None:
            logging.error(f"Status Code: {http_err.response.status_code}, Response: {http_err.response.text[:200]}...")
        return None
    except requests.exceptions.RequestException as e:
        stage = "download" if 'r' not in locals() else "upload"
        logging.error(f"Network error during {stage} for {file_url}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logging.error(f"Status Code: {e.response.status_code}, Response: {e.response.text[:200]}...")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred during upload processing for {file_url}: {e}", exc_info=True)
        return None

# Core Processing Logic (_run_processing_cycle)
def _run_processing_cycle():
    """
    Internal function to fetch, process, and save data. Handles locking.
    Fetches API data concurrently.
    Returns a tuple: (success_flag, new_items_added, total_items_in_file, posts_checked_this_cycle)
    """
    logging.info("Starting processing cycle...")
    new_items_added = 0
    processed_api_posts_count = 0
    current_total_items = 0
    success = False

    # Uses global DATA_FILE_PATH loaded from env
    with data_lock:
        existing_data = load_data(DATA_FILE_PATH)
        if not isinstance(existing_data, list):
            logging.error("Loaded data is not a list. Aborting processing cycle.")
            return False, 0, 0, 0

        current_total_items = len(existing_data)
        # Use (title, author) tuple for duplicate checking
        existing_post_ids = set()
        for item in existing_data:
             if isinstance(item, dict):
                 title = item.get('title', '').strip()
                 author = item.get('author', '').strip()
                 if title and author:
                     existing_post_ids.add((title, author))
                 else:
                     logging.warning(f"Found item in existing data with missing title or author: {item}")
             else:
                 logging.warning(f"Found non-dictionary item in existing data: {item}")
        logging.info(f"Initialized duplicate check set with {len(existing_post_ids)} existing post IDs.")

        all_posts_from_apis = []
        # Fetch data from all APIs concurrently using ThreadPoolExecutor
        logging.info(f"Starting concurrent fetch for {len(COMMUNITIES_API_URLS)} URLs...")
        results = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # map applies fetch_communities_data to each URL in the list concurrently
            # it returns an iterator yielding results in the order the URLs were submitted
            results = executor.map(fetch_communities_data, COMMUNITIES_API_URLS)

        logging.info("Concurrent fetching complete. Processing results...")
        # Process results from the concurrent fetches
        for data in results: # data here is the return value of fetch_communities_data (dict, list or None)
            if data: # Check if fetch was successful and returned data
                posts_list = None
                original_url = "Unknown" # Placeholder, map doesn't easily provide the originating URL alongside the result

                # Determine the structure of the returned data (list or dict containing list)
                if isinstance(data, list):
                    posts_list = data
                elif isinstance(data, dict):
                    possible_keys = ['posts', 'data', 'items', 'results', 'threads', 'newPosts', 'hotPosts']
                    found_key = None
                    for key in possible_keys:
                        potential_list = data.get(key)
                        if isinstance(potential_list, list):
                            posts_list = potential_list
                            found_key = key
                            break
                    if posts_list is None and all(k in data for k in ['title', 'author', 'link']):
                         posts_list = [data] # Treat root dict as single post

                    if posts_list is None:
                         logging.warning(f"Could not find a list of posts under expected keys or as root dict in response. Keys found: {list(data.keys())}") # Removed URL as it's harder to track here
                else:
                    logging.warning(f"Received unexpected data type from fetch: {type(data)}") # Removed URL

                # Process the found list of posts
                if posts_list is not None:
                    valid_posts_count = 0
                    for post in posts_list:
                        if isinstance(post, dict):
                            if all(k in post for k in ['title', 'author', 'link']):
                                all_posts_from_apis.append(post)
                                valid_posts_count += 1
                            else:
                                logging.warning(f"Skipping post missing required keys (title, author, link): {post}") # Removed URL
                        else:
                            logging.warning(f"Skipping non-dictionary item found in list: {post}") # Removed URL
                    # logging.info(f"Added {valid_posts_count} valid posts from one API result to process queue.") # Reduce verbosity
            else:
                 # Fetch returned None (likely due to error logged in fetch_communities_data)
                 logging.warning("A fetch operation returned None (check logs above for details).")


        logging.info(f"Total valid posts fetched across all APIs: {len(all_posts_from_apis)}. Processing...")

        items_to_add = []
        for post in all_posts_from_apis:
            processed_api_posts_count += 1

            author = post.get('author', '').strip()
            title = post.get('title', '').strip()
            link = post.get('link', '')

            if not author or not title or not link or not isinstance(link, str):
                logging.debug(f"Skipping post with missing info: Title='{title}', Author='{author}', Link Type='{type(link)}'")
                continue

            # Extract extension safely
            try:
                _, extension = os.path.splitext(urlparse(link).path) # Parse path before splitext
                extension = extension.lower()
            except Exception as ext_err:
                 logging.warning(f"Could not extract extension from link '{link}': {ext_err}. Skipping.")
                 continue

            # Uses global SUPPORTED_EXTENSIONS
            if extension in SUPPORTED_EXTENSIONS:
                post_id_tuple = (title, author)

                if post_id_tuple in existing_post_ids:
                    logging.debug(f"Skipping already processed/existing post: Title='{title}', Author='{author}'")
                    continue

                logging.info(f"Found new post with supported file: Title='{title}', Author='{author}', Link='{link}'")
                fileditch_link = upload_to_fileditch(link) # upload uses global upload URL

                if fileditch_link:
                    new_entry = {
                        "title": title,
                        "author": author,
                        "fileditch_link": fileditch_link,
                        "original_link": link,
                        "type": "video" if extension in SUPPORTED_VIDEO_EXTENSIONS else "image"
                    }
                    items_to_add.append(new_entry)
                    existing_post_ids.add(post_id_tuple) # Add to set immediately
                    new_items_added += 1
                    logging.info(f"Prepared new entry for '{title}' by {author} (Type: {new_entry['type']}).")
                else:
                    logging.warning(f"Failed to upload file for post: Title='{title}', Author='{author}' (Link: {link})")
            else:
                logging.debug(f"Skipping post with unsupported extension ('{extension}'): Title='{title}', Author='{author}', Link: {link[:100]}...")

        logging.info(f"Checked {processed_api_posts_count} posts fetched from APIs in this cycle.")

        if new_items_added > 0:
            existing_data.extend(items_to_add)
            logging.info(f"Attempting to save {len(existing_data)} total items ({new_items_added} new) to {DATA_FILE_PATH}")
            save_data(DATA_FILE_PATH, existing_data) # save uses global data path
            current_total_items = len(existing_data)
            success = True
        else:
            logging.info("No new supported media posts found or processed successfully. Data file not modified.")
            success = True # Still successful cycle, just no new items

    return success, new_items_added, current_total_items, processed_api_posts_count

# Background Processing Thread (background_processor)
# No changes needed, it calls _run_processing_cycle which uses global vars
def background_processor():
    """Target function for the background thread."""
    logging.info("Background processing thread started.")
    while True:
        try:
            logging.info("Background thread waking up for processing cycle.")
            # Need app context if background thread interacts with Flask extensions,
            # but here it only calls _run_processing_cycle which doesn't directly.
            # However, keeping it is harmless and good practice if dependencies change.
            with app.app_context():
                 success, added, total, checked = _run_processing_cycle()
            if success:
                 logging.info(f"Background processing cycle complete. Added: {added}, Total: {total}, Checked: {checked}")
            else:
                 logging.warning("Background processing cycle finished with errors (check logs above).")
        except Exception as e:
            # Log the full traceback for unexpected errors in the loop
            logging.exception(f"!!! Unhandled exception in background_processor loop: {e} !!!")

        logging.info(f"Background thread sleeping for {PROCESSING_INTERVAL_SECONDS} seconds.")
        time.sleep(PROCESSING_INTERVAL_SECONDS)


# Flask Routes (index, process_posts_request, get_data)
# These use DATA_FILE_PATH and call _run_processing_cycle, which use global vars
@app.route('/', methods=['GET'])
def index():
    """Renders the HTML table page with data from the JSON file."""
    logging.info("Request received for index page ('/')")
    backup_data = []
    try:
        with data_lock:
             # Uses global DATA_FILE_PATH
             loaded_data = load_data(DATA_FILE_PATH)
        if isinstance(loaded_data, list):
            backup_data = loaded_data
        else:
            logging.error("Loaded data in index route was not a list! Forcing empty list.")
            backup_data = [] # Ensure backup_data is always a list for render_template
    except Exception as e:
        logging.exception(f"Unexpected error acquiring lock or loading data in index route: {e}")
        backup_data = [] # Ensure backup_data is always a list for render_template

    item_count = len(backup_data)
    # Pass data in reverse chronological order (newest first)
    return render_template('index.html', items=reversed(backup_data), item_count=item_count)

@app.route('/process', methods=['POST'])
def process_posts_request():
    """Manual trigger endpoint. Runs the processing cycle and returns status."""
    logging.info("Manual processing request received via /process endpoint...")
    try:
        # Need app context if _run_processing_cycle interacts with Flask extensions
        with app.app_context():
            success, new_items, total_items, posts_checked = _run_processing_cycle()
        if success:
            return jsonify({
                "message": "Processing complete.",
                "new_items_added": new_items,
                "total_items_in_file": total_items,
                "posts_checked_this_cycle": posts_checked
            }), 200
        else:
            # Even if the cycle had internal errors (e.g., failed fetch),
            # the request itself might succeed, but report the outcome.
            # Return 500 only if the request handler itself fails catastrophically.
             return jsonify({
                 "message": "Processing cycle finished, potentially with errors (check server logs).",
                 "new_items_added": new_items,
                 "total_items_in_file": total_items,
                 "posts_checked_this_cycle": posts_checked
             }), 200 # Or maybe 500 if 'success=False' implies a server-side failure state
    except Exception as e:
        logging.exception(f"Error during manual /process request: {e}")
        return jsonify({"message": "An unexpected error occurred during processing."}), 500

@app.route('/data', methods=['GET'])
def get_data():
    """Returns the current data as raw JSON."""
    logging.info("Request received for /data endpoint")
    with data_lock:
        # Uses global DATA_FILE_PATH
        current_data = load_data(DATA_FILE_PATH)
    if not isinstance(current_data, list):
        logging.error("Data loaded for /data endpoint was not a list.")
        return jsonify({"error": "Failed to load data correctly", "data": []}), 500
    return jsonify(current_data)

# Main Execution
if __name__ == '__main__':
    # Ensure backup directory exists (uses DATA_FILE_PATH from env)
    backup_dir = os.path.dirname(DATA_FILE_PATH)
    try:
        os.makedirs(backup_dir, exist_ok=True)
        logging.info(f"Ensured backup directory exists: {backup_dir}")
    except Exception as e:
        logging.error(f"Could not create backup directory {backup_dir}: {e}. File operations might fail.")

    template_dir = app.template_folder 
    static_dir = app.static_folder   

    if not os.path.exists(template_dir):
        try:
            os.makedirs(template_dir)
            logging.info(f"Created missing 'templates' directory at {template_dir}. Ensure index.html is present.")
        except Exception as e:
            logging.warning(f"Could not create 'templates' directory: {e}. Ensure it exists manually.")
    elif not os.path.isfile(os.path.join(template_dir, 'index.html')):
         logging.warning(f"Templates directory '{template_dir}' exists, but 'index.html' is missing.")

    if not os.path.exists(static_dir):
        try:
            os.makedirs(static_dir)
            logging.info(f"Created missing 'static' directory at {static_dir}. Place static assets here.")
        except Exception as e:
            logging.warning(f"Could not create 'static' directory: {e}. Ensure it exists manually.")

    processor_thread = threading.Thread(target=background_processor, name="BackgroundProcessor", daemon=True)
    processor_thread.start()
    logging.info("Background processing thread initiated.")

    listen_host = os.environ.get('APP_HOST', '0.0.0.0')
    listen_port = int(os.environ.get('APP_PORT', 5000))
    waitress_threads = int(os.environ.get('WAITRESS_THREADS', 8)) # Default to 8 threads

    logging.info(f"Starting Waitress server on http://{listen_host}:{listen_port} with {waitress_threads} threads...")
    serve(app, host=listen_host, port=listen_port, threads=waitress_threads)
