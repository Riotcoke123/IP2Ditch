import os
import json
import requests
import logging
import datetime
import re
import time
import threading
from flask import Flask, jsonify, request, render_template
from urllib.parse import urlparse, unquote
from dotenv import load_dotenv # <-- Import load_dotenv

# --- Load Environment Variables ---
load_dotenv() # <-- Load variables from .env file into environment

# --- Configuration ---
COMMUNITIES_API_URLS = [
    "https://communities.win/api/v2/post/newv2.json?community=ip2always",
    "https://communities.win/api/v2/post/hotv2.json?community=ip2always"
]

# --- Retrieve Credentials Safely ---
# Use os.getenv to read environment variables. Provide None as default.
api_key = os.getenv('COMMUNITIES_API_KEY')
api_secret = os.getenv('COMMUNITIES_API_SECRET')
xsrf_token = os.getenv('COMMUNITIES_XSRF_TOKEN')

# --- Check if required variables are set ---
if not api_key:
    logging.warning("COMMUNITIES_API_KEY environment variable not set. API calls may fail.")
    # Depending on requirements, you might want to exit here:
    # raise ValueError("Missing required environment variable: COMMUNITIES_API_KEY")
if not api_secret:
    logging.warning("COMMUNITIES_API_SECRET environment variable not set. API calls may fail.")
    # raise ValueError("Missing required environment variable: COMMUNITIES_API_SECRET")
if not xsrf_token:
    logging.warning("COMMUNITIES_XSRF_TOKEN environment variable not set. API calls may fail.")
    # raise ValueError("Missing required environment variable: COMMUNITIES_XSRF_TOKEN")


# --- Headers using Environment Variables ---
COMMUNITIES_HEADERS = {
    'accept': 'application/json, text/plain, */*',
    'accept-encoding': 'gzip, deflate, br, zstd',
    'accept-language': 'en-US,en;q=0.9',
    'priority': 'u=1, i',
    'referer': 'https://communities.win/c/IP2Always/new',
    'sec-ch-ua': '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"', # Adjust version if needed
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36', # Adjust version if needed
    'x-api-key': api_key,         # <-- Use variable
    'x-api-platform': 'Scored-Desktop',
    'x-api-secret': api_secret,   # <-- Use variable
    'x-xsrf-token': xsrf_token    # <-- Use variable (might still expire/change)
}

# --- Other Configurations ---
FILEDITCH_UPLOAD_URL = os.getenv('FILEDITCH_UPLOAD_URL', "https://up1.fileditch.com/upload.php") # Example of using default
DATA_FILE_PATH = os.getenv('DATA_FILE_PATH', 'data.json') # Example using default
REQUEST_TIMEOUT = 30
UPLOAD_TIMEOUT = 300
PROCESSING_INTERVAL_SECONDS = 300 # 5 minutes

# --- Logging Setup ---
log_format = '%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format, datefmt='%Y-%m-%dT%H:%M:%S%z')
logging.Formatter.converter = lambda *args: datetime.datetime.now(datetime.timezone.utc).timetuple()

# --- Flask App ---
app = Flask(__name__)

# --- Thread Safety ---
data_lock = threading.Lock()

# --- Helper Functions ---
# (load_data, save_data, fetch_communities_data, upload_to_fileditch functions remain the same)
# ... (rest of your helper functions) ...
def load_data(filepath):
    """Loads data from the JSON file. Assumes lock is held."""
    # Make sure the directory exists *before* trying to open the file
    dirname = os.path.dirname(filepath)
    if dirname: # Ensure dirname is not empty (e.g., if filepath is just "data.json")
        os.makedirs(dirname, exist_ok=True)

    if not os.path.exists(filepath):
        logging.info(f"Data file {filepath} not found. Starting fresh.")
        return []
    try:
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
        logging.info(f"Data file {filepath} not found (caught during open). Starting fresh.")
        return []
    except Exception as e:
        logging.error(f"Error loading data from {filepath}: {e}")
        return [] # Return empty list on generic error

def save_data(filepath, data):
    """Saves data to the JSON file. Assumes lock is held."""
    try:
        # Ensure directory exists before writing temp file
        dirname = os.path.dirname(filepath)
        if dirname: # Ensure dirname is not empty
             os.makedirs(dirname, exist_ok=True)

        temp_filepath = filepath + ".tmp"
        with open(temp_filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        os.replace(temp_filepath, filepath) # Atomic replace on most OS
        logging.info(f"Data successfully saved to {filepath} ({len(data)} items)")
    except Exception as e:
        logging.error(f"Error saving data to {filepath}: {e}")
        # Attempt to remove temporary file if it exists after an error
        if 'temp_filepath' in locals() and os.path.exists(temp_filepath):
            try:
                os.remove(temp_filepath)
                logging.info(f"Removed temporary file {temp_filepath} after save error.")
            except Exception as remove_err:
                logging.error(f"Could not remove temporary file {temp_filepath} after save error: {remove_err}")

def fetch_communities_data(api_url):
    """Fetches data from a communities.win API endpoint."""
    # Check if required headers are present before making the request
    if not COMMUNITIES_HEADERS.get('x-api-key') or \
       not COMMUNITIES_HEADERS.get('x-api-secret') or \
       not COMMUNITIES_HEADERS.get('x-xsrf-token'):
        logging.error(f"Missing required API credentials in headers for {api_url}. Aborting fetch.")
        return None

    logging.info(f"Attempting to fetch data from: {api_url}")
    try:
        response = requests.get(api_url, headers=COMMUNITIES_HEADERS, timeout=REQUEST_TIMEOUT)
        logging.debug(f"Response status code for {api_url}: {response.status_code}")
        response.raise_for_status()
        try:
            data = response.json()
            logging.debug(f"Successfully decoded JSON from {api_url}")
            return data
        except json.JSONDecodeError as json_err:
            logging.error(f"Error decoding JSON response from {api_url}. Error: {json_err}. Response text: {response.text[:200]}...")
            return None
    except requests.exceptions.Timeout:
        logging.error(f"Timeout occurred while fetching data from {api_url} after {REQUEST_TIMEOUT} seconds.")
        return None
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error occurred for {api_url}: {http_err}")
        if http_err.response is not None:
            logging.error(f"Status Code: {http_err.response.status_code}, Response: {http_err.response.text[:200]}...")
            if http_err.response.status_code in [401, 403]:
                 logging.error("Authorization error. Check your API Key/Secret/Token.")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Generic network error fetching data from {api_url}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logging.error(f"Status Code: {e.response.status_code}, Response: {e.response.text[:200]}...")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred during fetch for {api_url}: {e}")
        return None

def upload_to_fileditch(mp4_url):
    """Downloads an MP4 from a URL and uploads it to FileDitch."""
    try:
        logging.info(f"Attempting to download: {mp4_url}")
        # Use a common user-agent for downloading
        download_headers = {
            'User-Agent': COMMUNITIES_HEADERS.get('user-agent'), # Re-use user agent from main headers
            'Accept': 'video/mp4,video/webm,video/ogg,video/*;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            # Sometimes helpful to mimic browser behavior
            'Referer': COMMUNITIES_HEADERS.get('referer', mp4_url)
        }
        # Use stream=True for potentially large files
        with requests.get(mp4_url, stream=True, timeout=REQUEST_TIMEOUT, headers=download_headers) as r:
            r.raise_for_status()
            logging.info(f"Download started for {mp4_url} (Status: {r.status_code})")

            # --- Filename Determination Logic ---
            filename = None
            try:
                # 1. Try Content-Disposition header
                content_disposition = r.headers.get('content-disposition')
                if content_disposition:
                    fname_match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', content_disposition, re.IGNORECASE)
                    if fname_match:
                        filename = unquote(fname_match.group(1)) # Decode URL encoding
                        filename = re.sub(r'[\\/*?:"<>|]', '_', filename) # Sanitize
                        logging.debug(f"Filename from Content-Disposition: '{filename}'")

                # 2. If no header, try parsing the URL path
                if not filename:
                    parsed_url = urlparse(mp4_url)
                    path_part = unquote(parsed_url.path.split('/')[-1]) # Get last part and decode
                    if path_part and '.' in path_part: # Basic check if it looks like a filename
                        filename = re.sub(r'[\\/*?:"<>|]', '_', path_part) # Sanitize
                        logging.debug(f"Filename from URL path: '{filename}'")

                # 3. Fallback filename
                if not filename:
                    # Generate a slightly more unique fallback using timestamp
                    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
                    filename = f"upload_{ts}.mp4"
                    logging.debug(f"Using timestamped fallback filename: '{filename}'")

                # Ensure it has a reasonable extension (simple check)
                # Make sure it ends with .mp4, even if derived filename didn't
                if not filename.lower().endswith(('.mp4', '.webm', '.mov', '.avi')): # Allow common video types
                     base, _ = os.path.splitext(filename)
                     filename = base + ".mp4"
                     logging.debug(f"Ensured .mp4 extension, final filename: '{filename}'")

            except Exception as e_fname:
                logging.warning(f"Could not reliably determine filename for {mp4_url}: {e_fname}. Using fallback 'upload.mp4'.")
                filename = "upload.mp4" # Simple fallback if complex logic fails
            # --- End Filename Determination ---

            # FileDitch expects 'files[]' as the key for multipart upload
            # Pass r.raw (the raw byte stream) directly to avoid loading large files into memory
            files = {'files[]': (filename, r.raw, 'video/mp4')} # Assume mp4 for simplicity, could check Content-Type header from download
            logging.info(f"Uploading '{filename}' (from {mp4_url}) to FileDitch...")

            # Increase upload timeout as needed
            upload_response = requests.post(FILEDITCH_UPLOAD_URL, files=files, timeout=UPLOAD_TIMEOUT)
            upload_response.raise_for_status()

            try:
                upload_data = upload_response.json()
            except json.JSONDecodeError:
                logging.error(f"Error decoding FileDitch JSON response. Status: {upload_response.status_code}. Response text: {upload_response.text[:200]}...")
                return None

            logging.debug(f"FileDitch response: {json.dumps(upload_data, indent=2)}")

            # Check FileDitch response structure carefully
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
                status_code = upload_data.get("status_code", "N/A") # Example if API provides status
                logging.error(f"FileDitch upload failed. Success: {upload_data.get('success')}, Status Code: {status_code}, Error: {error_message}. Full response: {upload_data}")
                return None

    except requests.exceptions.Timeout:
        stage = "download" if 'r' not in locals() else "upload"
        timeout_val = REQUEST_TIMEOUT if stage == "download" else UPLOAD_TIMEOUT
        logging.error(f"Timeout ({timeout_val}s) occurred during {stage} for URL: {mp4_url}")
        return None
    except requests.exceptions.HTTPError as http_err:
        stage = "download" if 'r' not in locals() else "upload"
        logging.error(f"HTTP error occurred during {stage} for {mp4_url}: {http_err}")
        if hasattr(http_err, 'response') and http_err.response is not None:
            logging.error(f"Status Code: {http_err.response.status_code}, Response: {http_err.response.text[:200]}...")
        return None
    except requests.exceptions.RequestException as e:
        stage = "download" if 'r' not in locals() else "upload"
        logging.error(f"Network error during {stage} for {mp4_url}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logging.error(f"Status Code: {e.response.status_code}, Response: {e.response.text[:200]}...")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred during upload processing for {mp4_url}: {e}", exc_info=True) # Log traceback
        return None


# --- Core Processing Logic (Extracted) ---
# (_run_processing_cycle function remains the same, but will use the updated fetch/upload functions)
# ... (rest of your _run_processing_cycle function) ...
def _run_processing_cycle():
    """
    Internal function to fetch, process, and save data. Handles locking.
    Returns a tuple: (success_flag, new_items_added, total_items_in_file, posts_checked_this_cycle)
    """
    logging.info("Starting processing cycle...")
    new_items_added = 0
    processed_api_posts_count = 0
    current_total_items = 0
    success = False

    with data_lock: # Acquire lock for reading and potentially writing
        existing_data = load_data(DATA_FILE_PATH)
        if not isinstance(existing_data, list):
            logging.error("Loaded data is not a list. Aborting processing cycle.")
            return False, 0, 0, 0 # Indicate failure

        current_total_items = len(existing_data)

        # Use a set for efficient duplicate checking (title, author tuple)
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
        for url in COMMUNITIES_API_URLS:
            data = fetch_communities_data(url) # Uses updated function with header checks
            if data:
                posts_list = None
                # --- Flexible Post List Extraction ---
                if isinstance(data, list):
                    posts_list = data
                    logging.info(f"Received list ({len(posts_list)} items) directly from {url}")
                elif isinstance(data, dict):
                    logging.debug(f"Received dictionary from {url}. Looking for posts list...")
                    possible_keys = ['posts', 'data', 'items', 'results', 'threads', 'newPosts', 'hotPosts'] # Add more as needed
                    found_key = None
                    for key in possible_keys:
                        potential_list = data.get(key)
                        if isinstance(potential_list, list):
                            posts_list = potential_list
                            found_key = key
                            logging.info(f"Found list ({len(posts_list)} items) under key '{found_key}' in dict response from {url}")
                            break
                    if posts_list is None and all(k in data for k in ['title', 'author', 'link']):
                        logging.info(f"Treating root dictionary from {url} as a single post.")
                        posts_list = [data]

                    if posts_list is None:
                         logging.warning(f"Could not find a list of posts under expected keys ({', '.join(possible_keys)}) or as root dict in response from {url}. Keys found: {list(data.keys())}")
                else:
                    logging.warning(f"Received unexpected data type from {url}: {type(data)}")
                # --- End Extraction ---

                if posts_list is not None:
                    valid_posts_count = 0
                    for post in posts_list:
                        if isinstance(post, dict):
                            if all(k in post for k in ['title', 'author', 'link']):
                                all_posts_from_apis.append(post)
                                valid_posts_count += 1
                            else:
                                logging.warning(f"Skipping post from {url} missing required keys (title, author, link): {post}")
                        else:
                            logging.warning(f"Skipping non-dictionary item found in list from {url}: {post}")
                    logging.info(f"Added {valid_posts_count} valid-structured posts from {url} to process queue.")
            else:
                logging.warning(f"No valid data received or fetched from {url}")

        logging.info(f"Total valid posts fetched across all APIs: {len(all_posts_from_apis)}. Processing...")

        items_to_add = []

        for post in all_posts_from_apis:
            processed_api_posts_count += 1

            author = post.get('author', '').strip()
            title = post.get('title', '').strip()
            link = post.get('link', '')

            if not author:
                logging.warning(f"Skipping post due to missing or empty author. Data: {post}")
                continue
            if not title:
                logging.warning(f"Skipping post due to missing or empty title. Data: {post}")
                continue
            if not link or not isinstance(link, str):
                logging.debug(f"Skipping post with missing or non-string link: Title='{title}', Author='{author}'")
                continue

            # --- MP4 Processing ---
            is_mp4_link = False
            try:
                # Check extension (more robustly)
                parsed_link = urlparse(link)
                path_lower = parsed_link.path.lower()
                # Allow for query params after extension, e.g., video.mp4?token=...
                if path_lower.endswith('.mp4') or '.mp4?' in path_lower:
                    is_mp4_link = True
                # Add other video extensions if needed:
                # elif path_lower.endswith('.webm') or '.webm?' in path_lower:
                #     is_mp4_link = True # Treat other video types similarly if desired

            except Exception as parse_err:
                logging.warning(f"Error parsing link '{link}' for MP4 check: {parse_err}")


            if is_mp4_link:
                post_id_tuple = (title, author)

                if post_id_tuple in existing_post_ids:
                    logging.debug(f"Skipping already processed/existing MP4 post: Title='{title}', Author='{author}'")
                    continue

                # --- Upload ---
                fileditch_link = upload_to_fileditch(link) # Uses updated function
                # ---------------

                if fileditch_link:
                    new_entry = {
                        "title": title,
                        "author": author,
                        "fileditch_link": fileditch_link,
                        "original_link": link,
                    }
                    items_to_add.append(new_entry)
                    existing_post_ids.add(post_id_tuple)
                    new_items_added += 1
                    logging.info(f"Prepared new entry for '{title}' by {author}.")
                else:
                    logging.warning(f"Failed to upload MP4 for post: Title='{title}', Author='{author}' (Link: {link})")
            else:
                logging.debug(f"Skipping non-MP4 link: Title='{title}', Author='{author}', Link: {link[:100]}...")

        logging.info(f"Checked {processed_api_posts_count} posts fetched from APIs in this cycle.")

        if new_items_added > 0:
            existing_data.extend(items_to_add)
            logging.info(f"Attempting to save {len(existing_data)} total items ({new_items_added} new) to {DATA_FILE_PATH}")
            save_data(DATA_FILE_PATH, existing_data) # Uses updated function
            current_total_items = len(existing_data)
            success = True
        else:
            logging.info("No new MP4 posts found or processed successfully. Data file not modified.")
            success = True

    # Lock is released here
    return success, new_items_added, current_total_items, processed_api_posts_count

# --- Background Processing Thread ---
# (background_processor function remains the same)
# ... (rest of your background_processor function) ...
def background_processor():
    """Target function for the background thread."""
    logging.info("Background processing thread started.")
    # Optional: Wait a bit before the first run
    # time.sleep(10)

    while True:
        try:
            logging.info("Background thread waking up for processing cycle.")
            # Ensure Flask app context if operations within the cycle might need it
            # (e.g., url_for, session - not strictly needed for _run_processing_cycle here)
            with app.app_context():
                success, added, total, checked = _run_processing_cycle()
            if success:
                logging.info(f"Background processing cycle complete. Added: {added}, Total: {total}, Checked: {checked}")
            else:
                logging.warning("Background processing cycle finished with errors (check logs above).")

        except Exception as e:
            # Log the full exception traceback for debugging
            logging.exception("!!! Unhandled exception in background_processor loop: {} !!!".format(e))
            # Avoid crashing the thread, maybe wait longer before retrying after a major error
            time.sleep(60) # Wait a minute before next cycle after failure

        logging.info(f"Background thread sleeping for {PROCESSING_INTERVAL_SECONDS} seconds.")
        time.sleep(PROCESSING_INTERVAL_SECONDS)


# --- Flask Routes ---
# (Flask routes remain the same)
# ... (rest of your Flask routes) ...
@app.route('/', methods=['GET'])
def index():
    """Renders the HTML table page with data from the JSON file."""
    logging.info("Request received for index page ('/')")
    backup_data = []

    try:
        with data_lock: # Acquire lock just for reading
            loaded_data = load_data(DATA_FILE_PATH)

        # Ensure loaded_data is a list
        if isinstance(loaded_data, list):
             backup_data = loaded_data
        else:
             logging.error("Loaded data in index route was not a list! Forcing empty list.")
             # backup_data remains []

    except Exception as e:
        logging.exception(f"Unexpected error acquiring lock or loading data in index route: {e}")
        # backup_data will remain []

    item_count = len(backup_data)
    # Render template, passing reversed items for newest-first display
    return render_template('index.html', items=reversed(backup_data), item_count=item_count)


@app.route('/process', methods=['POST'])
def process_posts_request():
    """Manual trigger endpoint. Runs the processing cycle and returns status."""
    logging.info("Manual processing request received via /process endpoint...")
    try:
        # Run processing cycle within app context if needed by underlying functions
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
             # Cycle itself logged the specific errors
             return jsonify({
                "message": "Processing completed with errors. Check server logs.",
                "new_items_added": new_items,
                "total_items_in_file": total_items, # Report count as it was before potential save failure
                "posts_checked_this_cycle": posts_checked
             }), 500 # Internal Server Error

    except Exception as e:
        logging.exception("Error during manual /process request: {}".format(e))
        return jsonify({"message": "An unexpected error occurred during processing."}), 500


@app.route('/data', methods=['GET'])
def get_data():
    """Returns the current data as raw JSON."""
    logging.info("Request received for /data endpoint")
    with data_lock: # Ensure thread-safe reading
        current_data = load_data(DATA_FILE_PATH)

    if not isinstance(current_data, list):
        logging.error("Data loaded for /data endpoint was not a list.")
        return jsonify({"error": "Failed to load data correctly", "data": []}), 500

    return jsonify(current_data)

# --- Main Execution ---
if __name__ == '__main__':
    # --- Ensure essential directories exist ---
    # Directory for the data file
    backup_dir = os.path.dirname(DATA_FILE_PATH)
    if backup_dir: # Only create if DATA_FILE_PATH includes a directory part
        try:
            os.makedirs(backup_dir, exist_ok=True)
            logging.info(f"Ensured data directory exists: {backup_dir}")
        except Exception as e:
            logging.error(f"Fatal: Could not create directory {backup_dir}: {e}. Exiting.")
            exit(1) # Exit if we can't create the data directory

    # Templates directory (relative to script)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_dir = os.path.join(script_dir, 'templates')
    static_dir = os.path.join(script_dir, 'static')

    try:
        os.makedirs(template_dir, exist_ok=True)
        logging.info(f"Ensured 'templates' directory exists at {template_dir}.")
        # Check if index.html exists (optional but good practice)
        if not os.path.exists(os.path.join(template_dir, 'index.html')):
             logging.warning(f"Template file 'index.html' not found in {template_dir}. The '/' route will fail.")
    except Exception as e:
        logging.warning(f"Could not create/check 'templates' directory: {e}. Ensure it exists manually.")

    # Static directory (relative to script)
    try:
        os.makedirs(static_dir, exist_ok=True)
        logging.info(f"Ensured 'static' directory exists at {static_dir}.")
        # Check for required static files (optional)
        # if not os.path.exists(os.path.join(static_dir, 'style.css')):
        #     logging.warning(f"Static file 'style.css' not found in {static_dir}.")
        # if not os.path.exists(os.path.join(static_dir, '6.webp')):
        #     logging.warning(f"Static file '6.webp' not found in {static_dir}.")
    except Exception as e:
        logging.warning(f"Could not create/check 'static' directory: {e}. Ensure it exists manually.")


    # --- Check for required environment variables before starting threads/app ---
    # Moved checks near the top after load_dotenv()

    # --- Start Background Thread ---
    processor_thread = threading.Thread(target=background_processor, name="BackgroundProcessor", daemon=True)
    processor_thread.start()
    logging.info("Background processing thread initiated.")

    # --- Run Flask App ---
    logging.info("Starting Flask development server on http://127.0.0.1:5000")
    # use_reloader=False is important when using background threads managed manually
    # debug=False is recommended for anything beyond basic local testing
    app.run(debug=False, host='127.0.0.1', port=5000, use_reloader=False)
