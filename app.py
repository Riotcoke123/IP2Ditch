
import os
import json
import requests
import logging
import datetime
import re
import time # Added
import threading # Added
from flask import Flask, jsonify, request, render_template
from urllib.parse import urlparse, unquote # Added for better filename parsing

# --- Configuration ---
COMMUNITIES_API_URLS = [
    "https://communities.win/api/v2/post/newv2.json?community=ip2always",
    "https://communities.win/api/v2/post/hotv2.json?community=ip2always"
]

# WARNING: Hardcoding credentials is insecure. Use environment variables or config files.
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
    'x-api-key': '',
    'x-api-platform': 'Scored-Desktop',
    'x-api-secret': '',
    'x-xsrf-token': '' # This might expire/change
}

FILEDITCH_UPLOAD_URL = "https://up1.fileditch.com/upload.php"
DATA_FILE_PATH = os.path.join('data.json') # Use your actual path
REQUEST_TIMEOUT = 30
UPLOAD_TIMEOUT = 300
PROCESSING_INTERVAL_SECONDS = 300 # 5 minutes

# --- Logging Setup ---
log_format = '%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s' # Added threadName
logging.basicConfig(level=logging.INFO, format=log_format, datefmt='%Y-%m-%dT%H:%M:%S%z')
logging.Formatter.converter = lambda *args: datetime.datetime.now(datetime.timezone.utc).timetuple()

# --- Flask App ---
app = Flask(__name__)

# --- Thread Safety ---
data_lock = threading.Lock() # Added lock for file access

# --- Helper Functions ---

def load_data(filepath):
    """Loads data from the JSON file. Assumes lock is held."""
    try:
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
        logging.info(f"Data file {filepath} not found (caught during open). Starting fresh.")
        return []
    except Exception as e:
        logging.error(f"Error loading data from {filepath}: {e}")
        return [] # Return empty list on generic error

def save_data(filepath, data):
    """Saves data to the JSON file. Assumes lock is held."""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
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
            'User-Agent': COMMUNITIES_HEADERS.get('user-agent'),
            'Accept': 'video/mp4,video/webm,video/ogg,video/*;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': mp4_url # Sometimes needed
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
                    # Regex to find filename*=UTF-8'' or filename= format
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
                    filename = "upload.mp4"
                    logging.debug(f"Using fallback filename: '{filename}'")

                # Ensure it has a reasonable extension (simple check)
                if '.' not in filename[-5:]:
                    filename += ".mp4"
                    logging.debug(f"Appended .mp4 extension, final filename: '{filename}'")

            except Exception as e_fname:
                logging.warning(f"Could not reliably determine filename for {mp4_url}: {e_fname}. Using fallback 'upload.mp4'.")
                filename = "upload.mp4"
            # --- End Filename Determination ---

            # FileDitch expects 'files[]' as the key for multipart upload
            files = {'files[]': (filename, r.raw, 'video/mp4')}
            logging.info(f"Uploading '{filename}' (from {mp4_url}) to FileDitch...")

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
                logging.error(f"FileDitch upload failed. Success flag: {upload_data.get('success')}. Error: {error_message}. Full response: {upload_data}")
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
            # Still release the lock implicitly via 'with' statement exit
            return False, 0, 0, 0 # Indicate failure

        current_total_items = len(existing_data)

        # Use a set for efficient duplicate checking (title, author tuple)
        existing_post_ids = set()
        for item in existing_data:
             if isinstance(item, dict):
                 # Normalize and strip whitespace for comparison
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
            data = fetch_communities_data(url)
            if data:
                posts_list = None
                # --- Flexible Post List Extraction ---
                if isinstance(data, list):
                    posts_list = data
                    logging.info(f"Received list ({len(posts_list)} items) directly from {url}")
                elif isinstance(data, dict):
                    logging.debug(f"Received dictionary from {url}. Looking for posts list...")
                    # Common keys where post lists might be nested
                    possible_keys = ['posts', 'data', 'items', 'results', 'threads', 'newPosts', 'hotPosts']
                    found_key = None
                    for key in possible_keys:
                        potential_list = data.get(key)
                        if isinstance(potential_list, list):
                            posts_list = potential_list
                            found_key = key
                            logging.info(f"Found list ({len(posts_list)} items) under key '{found_key}' in dict response from {url}")
                            break
                    # Handle case where the root dict *is* the post (less common)
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
                            # Basic validation: Ensure essential keys exist before adding
                            if all(k in post for k in ['title', 'author', 'link']):
                                all_posts_from_apis.append(post)
                                valid_posts_count += 1
                            else:
                                logging.warning(f"Skipping post from {url} missing required keys (title, author, link): {post}")
                        else:
                            logging.warning(f"Skipping non-dictionary item found in list from {url}: {post}")
                    logging.info(f"Added {valid_posts_count} valid-structured posts from {url} (or nested key) to process queue.")
            else:
                logging.warning(f"No valid data received or fetched from {url}")

        logging.info(f"Total valid posts fetched across all APIs: {len(all_posts_from_apis)}. Processing...")

        items_to_add = [] # Collect new items before modifying existing_data

        for post in all_posts_from_apis:
            processed_api_posts_count += 1

            # Safely get values, defaulting to empty strings
            author = post.get('author', '').strip()
            title = post.get('title', '').strip()
            link = post.get('link', '') # Don't strip link initially

            if not author:
                logging.warning(f"Skipping post due to missing or empty author. Data: {post}")
                continue
            if not title:
                logging.warning(f"Skipping post due to missing or empty title. Data: {post}")
                continue
            if not link or not isinstance(link, str):
                logging.debug(f"Skipping post with missing or non-string link: Title='{title}', Author='{author}'")
                continue

            # Check if it's an MP4 link (case-insensitive)
            if link.lower().endswith('.mp4'):
                post_id_tuple = (title, author) # Use stripped title/author for checking

                if post_id_tuple in existing_post_ids:
                    logging.debug(f"Skipping already processed/existing MP4 post: Title='{title}', Author='{author}'")
                    continue

                # --- Upload ---
                fileditch_link = upload_to_fileditch(link)
                # ---------------

                if fileditch_link:
                    new_entry = {
                        "title": title, # Store original (but stripped) title
                        "author": author, # Store original (but stripped) author
                        "fileditch_link": fileditch_link,
                        "original_link": link, # Store original link
                    }
                    items_to_add.append(new_entry)
                    existing_post_ids.add(post_id_tuple) # Add to set to prevent duplicates within this run
                    new_items_added += 1
                    logging.info(f"Prepared new entry for '{title}' by {author}.")
                else:
                    logging.warning(f"Failed to upload MP4 for post: Title='{title}', Author='{author}' (Link: {link})")
            else:
                logging.debug(f"Skipping non-MP4 link: Title='{title}', Author='{author}', Link: {link[:100]}...") # Log only start of long links

        logging.info(f"Checked {processed_api_posts_count} posts fetched from APIs in this cycle.")

        if new_items_added > 0:
            existing_data.extend(items_to_add) # Add all new items at once
            logging.info(f"Attempting to save {len(existing_data)} total items ({new_items_added} new) to {DATA_FILE_PATH}")
            save_data(DATA_FILE_PATH, existing_data)
            current_total_items = len(existing_data) # Update total count after saving
            success = True # Assume save worked if no exception
        else:
            logging.info("No new MP4 posts found or processed successfully. Data file not modified.")
            success = True # Still considered a successful cycle, just no changes

    # Lock is released here
    return success, new_items_added, current_total_items, processed_api_posts_count

# --- Background Processing Thread ---

def background_processor():
    """Target function for the background thread."""
    logging.info("Background processing thread started.")
    # Optional: Wait a bit before the first run to ensure Flask is up
    # time.sleep(10)

    while True:
        try:
            logging.info("Background thread waking up for processing cycle.")
            with app.app_context(): # Ensure thread has access to Flask app context if needed (e.g., for logging)
                 success, added, total, checked = _run_processing_cycle()
            if success:
                 logging.info(f"Background processing cycle complete. Added: {added}, Total: {total}, Checked: {checked}")
            else:
                 logging.warning("Background processing cycle finished with errors (check logs above).")

        except Exception as e:
            logging.exception("!!! Unhandled exception in background_processor loop: {} !!!".format(e))
            # Avoid crashing the thread, log the error and continue

        logging.info(f"Background thread sleeping for {PROCESSING_INTERVAL_SECONDS} seconds.")
        time.sleep(PROCESSING_INTERVAL_SECONDS)

# --- Flask Routes ---
@app.route('/', methods=['GET'])
def index():
    """Renders the HTML table page with data from the JSON file."""
    logging.info("Request received for index page ('/')")
    backup_data = []  # <<< Initialize backup_data BEFORE the try block

    try:
        with data_lock: # Acquire lock just for reading
            # Attempt to load the data. load_data itself returns [] on error.
            loaded_data = load_data(DATA_FILE_PATH)

        # Ensure loaded_data is actually a list (robustness check)
        # If load_data worked correctly, loaded_data will be a list (possibly empty)
        # If load_data failed internally, it already returned [], so loaded_data is []
        if isinstance(loaded_data, list):
             backup_data = loaded_data # Assign the loaded list
        else:
             # This case indicates a deeper issue if load_data didn't return a list
             logging.error("Loaded data in index route was not a list! Forcing empty list.")
             # backup_data remains [] because of the initialization above

    except Exception as e:
        # Catch any unexpected error during lock acquisition or the load_data call itself
        logging.exception(f"Unexpected error acquiring lock or loading data in index route: {e}")
        # backup_data will remain [] because of the initialization above

    # Now backup_data is guaranteed to be a list (possibly empty)
    item_count = len(backup_data)

    # Render the external template, passing reversed items and the count
    return render_template('index.html', items=reversed(backup_data), item_count=item_count)

@app.route('/process', methods=['POST']) # Keep this as POST
def process_posts_request():
    """
    Manual trigger endpoint. Runs the processing cycle and returns status.
    """
    logging.info("Manual processing request received via /process endpoint...")
    try:
        with app.app_context(): # Ensure context is available
             success, new_items, total_items, posts_checked = _run_processing_cycle()

        if success:
            return jsonify({
                "message": "Processing complete.",
                "new_items_added": new_items,
                "total_items_in_file": total_items,
                "posts_checked_this_cycle": posts_checked
            }), 200
        else:
             # Potential issue during loading or saving, _run_processing_cycle logs specifics
             return jsonify({
                "message": "Processing completed with errors. Check server logs.",
                "new_items_added": new_items,
                "total_items_in_file": total_items, # Report count before potential save failure
                "posts_checked_this_cycle": posts_checked
             }), 500 # Internal Server Error status

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
        # Return an empty list or an error message in JSON format
        return jsonify({"error": "Failed to load data correctly", "data": []}), 500

    # Return the loaded data directly as JSON
    return jsonify(current_data)

# --- Main Execution ---
if __name__ == '__main__':
    # --- Ensure backup directory exists ---
    backup_dir = os.path.dirname(DATA_FILE_PATH)
    try:
        os.makedirs(backup_dir, exist_ok=True)
        logging.info(f"Ensured backup directory exists: {backup_dir}")
    except Exception as e:
        logging.error(f"Fatal: Could not create directory {backup_dir}: {e}. Exiting.")
        exit(1)

    # --- Ensure templates directory exists (but don't create index.html) ---
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_dir = os.path.join(script_dir, 'templates')
    if not os.path.exists(template_dir):
        try:
            os.makedirs(template_dir)
            logging.info(f"Created missing 'templates' directory at {template_dir}. Ensure index.html is present.")
        except Exception as e:
            logging.warning(f"Could not create 'templates' directory: {e}. Ensure it exists manually.")

    # --- Ensure static directory exists ---
    static_dir = os.path.join(script_dir, 'static')
    if not os.path.exists(static_dir):
        try:
            os.makedirs(static_dir)
            logging.info(f"Created missing 'static' directory at {static_dir}. Place style.css and 6.webp here.")
        except Exception as e:
            logging.warning(f"Could not create 'static' directory: {e}. Ensure it exists manually.")

    # --- Start Background Thread ---
    processor_thread = threading.Thread(target=background_processor, name="BackgroundProcessor", daemon=True)
    processor_thread.start()
    logging.info("Background processing thread initiated.")

    # --- Run Flask App ---
    logging.info("Starting Flask development server...")
    app.run(debug=False, host='127.0.0.1', port=5000, use_reloader=False)
