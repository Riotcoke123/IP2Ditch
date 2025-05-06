<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IP2Ditch - README</title>

</head><body>
    <img src="https://github.com/user-attachments/assets/bac0e1e1-5eba-4048-9142-22c394877122" alt="screenshot">
    <h1>IP2Ditch - IP2Always Media Backup & Archiver</h1>
    <p><strong>GitHub Repository:</strong> <a href="https://github.com/Riotcoke123/IP2Ditch">https://github.com/Riotcoke123/IP2Ditch</a></p>
    <h2>Overview</h2>
    <p>IP2Ditch is a Python-based web application designed to automatically fetch media (videos and images) from specified <a href="https://communities.win">communities.win</a> forums, upload them to <a href="https://fileditch.com/">Fileditch</a> for backup, and provide a simple web interface to browse the archived content. It runs a background process to periodically check for new media and can also be triggered manually.</p>
    <h2>Features</h2>
    <ul>
        <li><strong>Automated Media Fetching:</strong> Monitors multiple communities.win API endpoints (e.g., new/hot posts from specified communities).</li>
        <li><strong>Broad Media Support:</strong> Handles common video (<code>.mp4</code>) and image (<code>.jpg</code>, <code>.jpeg</code>, <code>.gif</code>, <code>.png</code>, <code>.webp</code>) formats.</li>
        <li><strong>Concurrent API Fetching:</strong> Uses threading to fetch data from multiple API URLs simultaneously for efficiency.</li>
        <li><strong>Fileditch Integration:</strong> Securely backs up media to Fileditch.</li>
        <li><strong>Local Metadata Storage:</strong> Saves information about archived posts (title, author, original link, Fileditch link, media type) in a local <code>data.json</code> file.</li>
        <li><strong>Web Interface:</strong> A Flask-powered web UI to view the collection of archived media, displaying the newest items first.</li>
        <li><strong>Background Processing:</strong> Continuously checks for new content at a configurable interval.</li>
        <li><strong>Manual Trigger:</strong> Option to trigger the processing cycle via a POST request to an API endpoint.</li>
        <li><strong>Highly Configurable:</strong> Uses environment variables for API URLs, Fileditch settings, API credentials, data storage paths, and operational parameters.</li>
        <li><strong>Robust Logging:</strong> Detailed logging of operations, errors, and system status, including thread names and UTC timestamps.</li>
        <li><strong>Duplicate Prevention:</strong> Avoids reprocessing and re-uploading media that has already been archived by checking post title and author.</li>
        <li><strong>Safe File Handling:</strong> Implements atomic writes for the data file to prevent corruption.</li>
    </ul>
    <h2>How It Works</h2>
    <ol>
        <li><strong>Initialization:</strong>
            <ul>
                <li>Loads configuration from environment variables (API keys, URLs, etc.).</li>
                <li>Starts a background thread for periodic processing.</li>
                <li>Launches a Flask web server (using Waitress) to serve the UI and API endpoints.</li>
            </ul>
        </li>
        <li><strong>Processing Cycle (Background or Manual):</strong>
            <ol>
                <li><strong>Fetch Data:</strong> Concurrently queries the configured <code>COMMUNITIES_API_URLS</code> for new posts.
                    <ul><li>Requires valid <code>CW_API_KEY</code>, <code>CW_API_SECRET</code>, and <code>CW_XSRF_TOKEN</code> for authentication.</li></ul>
                </li>
                <li><strong>Filter Posts:</strong>
                    <ul>
                        <li>Identifies posts containing direct links to media files with supported extensions (<code>.mp4</code>, <code>.jpg</code>, etc.).</li>
                        <li>Checks against a local list (<code>existing_post_ids</code> derived from <code>data.json</code>) to skip already processed posts (based on title and author).</li>
                    </ul>
                </li>
                <li><strong>Download & Upload:</strong>
                    <ul>
                        <li>For each new, supported media post:
                            <ul>
                                <li>Downloads the media file from its original URL.</li>
                                <li>Uploads the downloaded file to the configured <code>FILEDITCH_UPLOAD_URL</code>.</li>
                            </ul>
                        </li>
                    </ul>
                </li>
                <li><strong>Store Metadata:</strong>
                    <ul>
                        <li>If the upload to Fileditch is successful, a new entry is created containing:
                            <ul>
                                <li>Title of the post</li>
                                <li>Author of the post</li>
                                <li>Fileditch link (the new backup URL)</li>
                                <li>Original media link</li>
                                <li>Type of media ("video" or "image")</li>
                            </ul>
                        </li>
                        <li>This new entry is appended to the <code>data.json</code> file.</li>
                    </ul>
                </li>
            </ol>
        </li>
        <li><strong>Web Interface:</strong>
            <ul>
                <li>The Flask application serves an <code>index.html</code> page that reads <code>data.json</code> and displays the archived items in a table, with the most recent entries shown first.</li>
                <li>Provides direct links to the media on Fileditch.</li>
            </ul>
        </li>
    </ol>
    <h2>Setup and Running</h2>
    <ol>
        <li><strong>Clone the Repository:</strong>
            <pre><code>git clone https://github.com/Riotcoke123/IP2Ditch.git
cd IP2Ditch</code></pre>
        </li>
        <li><strong>Install Dependencies:</strong>
            <p>Ensure you have Python 3.x installed. Then, install the required packages. It's recommended to use a virtual environment.</p>
            <pre><code>python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install Flask requests python-dotenv waitress</code></pre>
            <p>Alternatively, if a <code>requirements.txt</code> file is provided:</p>
            <pre><code>pip install -r requirements.txt</code></pre>
        </li>
        <li><strong>Create <code>.env</code> File:</strong>
            <p>Create a file named <code>.env</code> in the root directory of the project and populate it with the necessary environment variables. <strong>Sensitive credentials should never be hardcoded.</strong></p>
            <pre><code class="language-ini"># Required Communities.win API Credentials
CW_API_KEY="YOUR_CW_API_KEY"
CW_API_SECRET="YOUR_CW_API_SECRET"
CW_XSRF_TOKEN="YOUR_CW_XSRF_TOKEN_FROM_HEADERS_OR_COOKIES"

# Optional: Override default API URLs (comma-separated)
# CW_API_URLS="https://communities.win/api/v2/post/newv2.json?community=somecommunity,https://communities.win/api/v2/post/hotv2.json?community=anothercommunity"

# Optional: Override default Fileditch upload URL
# APP_FILEDITCH_URL="https://up1.fileditch.com/upload.php"

# Optional: Override default data file path
# APP_DATA_FILE_PATH="data/my_archive.json"

# Optional: Server Configuration
# APP_HOST="0.0.0.0"
# APP_PORT="5000"
# WAITRESS_THREADS="8"

# Optional: Processing Configuration
# PROCESSING_INTERVAL_SECONDS="120" # How often to check for new posts (in seconds)
# REQUEST_TIMEOUT="30" # Timeout for network requests (seconds)
# UPLOAD_TIMEOUT="300" # Timeout for file uploads (seconds)
</code></pre>
            <div class="critical">
                <strong>Critical:</strong> <code>CW_API_KEY</code>, <code>CW_API_SECRET</code>, and <code>CW_XSRF_TOKEN</code> are mandatory for the application to fetch data from communities.win. The application will exit if these are not set.
            </div>
        </li>
        <li><strong>Ensure Templates and Static Directories:</strong>
            <p>The application expects an <code>index.html</code> file in a <code>templates</code> directory. The script attempts to create <code>templates</code> and <code>static</code> directories if they don't exist. Make sure your <code>templates/index.html</code> is correctly placed.
            Example <code>templates/index.html</code> (basic structure):
            <pre><code>&lt;!DOCTYPE html&gt;
&lt;html&gt;
&lt;head&gt;
    &lt;title&gt;Archived Media&lt;/title&gt;
    &lt;!-- Add styles here --&gt;
&lt;/head&gt;
&lt;body&gt;
    &lt;h1&gt;Archived Media ({{ item_count }} items)&lt;/h1&gt;
    &lt;form action="/process" method="POST"&gt;
        &lt;button type="submit"&gt;Run Processor Manually&lt;/button&gt;
    &lt;/form&gt;
    &lt;table border="1"&gt;
        &lt;thead&gt;
            &lt;tr&gt;
                &lt;th&gt;Title&lt;/th&gt;
                &lt;th&gt;Author&lt;/th&gt;
                &lt;th&gt;Type&lt;/th&gt;
                &lt;th&gt;Fileditch Link&lt;/th&gt;
                &lt;th&gt;Original Link&lt;/th&gt;
            &lt;/tr&gt;
        &lt;/thead&gt;
        &lt;tbody&gt;
            {% for item in items %}
            &lt;tr&gt;
                &lt;td&gt;{{ item.title }}&lt;/td&gt;
                &lt;td&gt;{{ item.author }}&lt;/td&gt;
                &lt;td&gt;{{ item.type }}&lt;/td&gt;
                &lt;td&gt;&lt;a href="{{ item.fileditch_link }}" target="_blank"&gt;View on Fileditch&lt;/a&gt;&lt;/td&gt;
                &lt;td&gt;&lt;a href="{{ item.original_link }}" target="_blank"&gt;Original&lt;/a&gt;&lt;/td&gt;
            &lt;/tr&gt;
            {% else %}
            &lt;tr&gt;&lt;td colspan="5"&gt;No items found.&lt;/td&gt;&lt;/tr&gt;
            {% endfor %}
        &lt;/tbody&gt;
    &lt;/table&gt;
&lt;/body&gt;
&lt;/html&gt;
            </code></pre>
            </p>
        </li>
        <li><strong>Run the Application:</strong>
            <p>Execute the main Python script (e.g., <code>main.py</code> or the name of your script file).</p>
            <pre><code>python your_script_name.py</code></pre>
            <p>The application will start, initiate the background processor, and the web server will be accessible at <code>http://&lt;APP_HOST&gt;:&lt;APP_PORT&gt;</code> (e.g., <code>http://0.0.0.0:5000</code> or <code>http://localhost:5000</code>).</p>
        </li>
    </ol>
    <h2>Configuration (Environment Variables)</h2>
    <p>The application is configured using environment variables. These can be set directly in your system or placed in a <code>.env</code> file in the project's root directory (which will be loaded automatically).</p>
    <table>
        <thead>
            <tr>
                <th>Variable Name</th>
                <th>Description</th>
                <th>Default Value</th>
                <th>Required</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><code class="env-var">CW_API_KEY</code></td>
                <td>communities.win API Key.</td>
                <td>None</td>
                <td><strong>Yes</strong></td>
            </tr>
            <tr>
                <td><code class="env-var">CW_API_SECRET</code></td>
                <td>communities.win API Secret.</td>
                <td>None</td>
                <td><strong>Yes</strong></td>
            </tr>
            <tr>
                <td><code class="env-var">CW_XSRF_TOKEN</code></td>
                <td>communities.win XSRF Token. This is usually obtained from browser cookies or request headers when interacting with the site.</td>
                <td>None</td>
                <td><strong>Yes</strong></td>
            </tr>
            <tr>
                <td><code class="env-var">CW_API_URLS</code></td>
                <td>Comma-separated list of communities.win API URLs to fetch posts from.</td>
                <td>
                    <code>https://communities.win/api/v2/post/newv2.json?community=ip2always</code>,<br>
                    <code>https://communities.win/api/v2/post/hotv2.json?community=ip2always</code>,<br>
                    <code>https://communities.win/api/v2/post/newv2.json?community=spictank</code>,<br>
                    <code>https://communities.win/api/v2/post/hotv2.json?community=spictank</code>,<br>
                    <code>https://communities.win/api/v2/post/newv2.json?community=freddiebeans2</code>,<br>
                    <code>https://communities.win/api/v2/post/hot2.json?community=freddiebeans2</code>
                </td>
                <td>No</td>
            </tr>
            <tr>
                <td><code class="env-var">APP_FILEDITCH_URL</code></td>
                <td>The upload URL for Fileditch.</td>
                <td><code>https://up1.fileditch.com/upload.php</code></td>
                <td>No</td>
            </tr>
            <tr>
                <td><code class="env-var">APP_DATA_FILE_PATH</code></td>
                <td>Path to the JSON file where archived media metadata is stored. The directory will be created if it doesn't exist.</td>
                <td><code>data.json</code> (relative to script location)</td>
                <td>No</td>
            </tr>
            <tr>
                <td><code class="env-var">APP_HOST</code></td>
                <td>Host address for the Flask application to listen on.</td>
                <td><code>0.0.0.0</code></td>
                <td>No</td>
            </tr>
            <tr>
                <td><code class="env-var">APP_PORT</code></td>
                <td>Port number for the Flask application.</td>
                <td><code>5000</code></td>
                <td>No</td>
            </tr>
            <tr>
                <td><code class="env-var">WAITRESS_THREADS</code></td>
                <td>Number of worker threads for the Waitress WSGI server.</td>
                <td><code>8</code></td>
                <td>No</td>
            </tr>
            <tr>
                <td><code class="env-var">PROCESSING_INTERVAL_SECONDS</code></td>
                <td>Interval in seconds for the background processing thread to fetch and process new posts.</td>
                <td><code>120</code> (2 minutes)</td>
                <td>No</td>
            </tr>
            <tr>
                <td><code class="env-var">REQUEST_TIMEOUT</code></td>
                <td>Timeout in seconds for general network requests (fetching API data, downloading files).</td>
                <td><code>30</code></td>
                <td>No</td>
            </tr>
            <tr>
                <td><code class="env-var">UPLOAD_TIMEOUT</code></td>
                <td>Timeout in seconds for uploading files to Fileditch.</td>
                <td><code>300</code> (5 minutes)</td>
                <td>No</td>
            </tr>
        </tbody>
    </table>
    <h2>API Endpoints</h2>
    <ul>
        <li><strong><code>GET /</code></strong>
            <ul>
                <li><strong>Description:</strong> Displays the main HTML page with a table of archived media.</li>
                <li><strong>Response:</strong> HTML page.</li>
            </ul>
        </li>
        <li><strong><code>POST /process</code></strong>
            <ul>
                <li><strong>Description:</strong> Manually triggers one full processing cycle (fetch, download, upload, save).</li>
                <li><strong>Response:</strong> JSON object indicating the outcome of the processing.
                    <pre><code>{
    "message": "Processing complete.",
    "new_items_added": 2,
    "total_items_in_file": 10,
    "posts_checked_this_cycle": 50
}</code></pre>
                </li>
            </ul>
        </li>
        <li><strong><code>GET /data</code></strong>
            <ul>
                <li><strong>Description:</strong> Returns the raw JSON data of all archived items.</li>
                <li><strong>Response:</strong> JSON array of archived media objects.
                    <pre><code>[
    {
        "title": "Cool Video Title",
        "author": "User123",
        "fileditch_link": "https://fileditch.com/...",
        "original_link": "https://example.com/video.mp4",
        "type": "video"
    },
    ...
]</code></pre>
                </li>
            </ul>
        </li>
    </ul>
    <h2>Dependencies</h2>
    <ul>
        <li>Python 3.x</li>
        <li>Flask</li>
        <li>Requests</li>
        <li>python-dotenv</li>
        <li>Waitress</li>
        <li><code>concurrent.futures</code> (Standard Python library)</li>
        <li><code>mimetypes</code> (Standard Python library)</li>
    </ul>
    <h2>Logging</h2>
    <p>The application employs Python's built-in <code>logging</code> module. Logs are output to standard output.</p>
    <ul>
        <li><strong>Format:</strong> <code>YYYY-MM-DDTHH:MM:SSZ - LEVELNAME - [ThreadName] - Message</code></li>
        <li><strong>Timestamp:</strong> UTC.</li>
        <li><strong>Level:</strong> Primarily INFO, with DEBUG for more verbose output, WARNING for recoverable issues, ERROR for significant problems, and CRITICAL for fatal errors (like missing essential configs).</li>
    </ul>
    <p>Check the console output where the script is running to monitor its activity and troubleshoot issues.</p>
    <h2>Error Handling and Resilience</h2>
    <ul>
        <li><strong>Network Issues:</strong> Timeouts and request exceptions are caught for API fetching, file downloading, and uploading. The application will log the error and typically skip the problematic item or API, continuing with others.</li>
        <li><strong>API Errors:</strong> HTTP errors (like 401/403 for bad credentials or 404 for not found) from communities.win or Fileditch are logged. Specific warnings are issued for credential-related errors.</li>
        <li><strong>Data File:</strong> Uses an atomic write process (save to a temporary file then replace) to minimize data corruption in <code>data.json</code> during saves. If the data file is missing, empty, or malformed, it starts with an empty list.</li>
        <li><strong>Background Thread:</strong> The main loop of the background processing thread is wrapped in a try-except block to catch unexpected errors and log them, preventing the thread from crashing silently.</li>
    </ul>
    <div class="note">
        <strong>Note on Communities.win Headers:</strong> The script uses a specific set of HTTP headers, including a User-Agent string, when making requests to the communities.win API. Sensitive parts of these headers (<code>x-api-key</code>, <code>x-api-secret</code>, <code>x-xsrf-token</code>) are loaded from environment variables. Ensure these are correctly set for the API requests to succeed.
    </div>

</body>
</html>
