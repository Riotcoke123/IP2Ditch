<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
  </head>
<body>

  <img src="https://github.com/user-attachments/assets/203d973f-364c-436c-99d0-7f3666bfe484" 
         alt="YouTube Anti-Viewbot Detector" width="250" height="250">
    <h1>IP2Ditch - IP2Always Media Backup & Archiver</h1> <p>
        <strong>IP2Ditch</strong> is a Python application designed to monitor the <code>communities.win/c/IP2Always</code> community (fetching both 'new' and 'hot' posts), identify direct links to supported video (<code>.mp4</code>) and image (<code>.jpg</code>, <code>.jpeg</code>, <code>.gif</code>, <code>.png</code>, <code>.webp</code>) files within posts, download these files, and subsequently upload them to <a href="https://fileditch.com/" target="_blank" rel="noopener noreferrer">FileDitch</a> for archival purposes. </p>
    <p>
        It maintains a local JSON database (<code>data.json</code>) to track processed files (based on post title and author) and prevent duplicates. The application uses environment variables for secure configuration of API keys and paths. It runs a background thread for continuous, automated processing and provides a simple Flask web interface to view the list of archived media files with their original and FileDitch links. </p>
    <h2>Key Features</h2>
    <ul>
        <li>Fetches posts from <a href="https://communities.win/c/IP2Always/new" target="_blank" rel="noopener noreferrer"><code>communities.win/c/IP2Always</code></a> (New & Hot endpoints by default, configurable via environment variable).</li>
        <li>Identifies posts containing direct links to supported media files (<code>.mp4</code>, <code>.jpg</code>, <code>.jpeg</code>, <code>.gif</code>, <code>.png</code>, <code>.webp</code>).</li> <li>Downloads the media file.</li> <li>Uploads the downloaded file to <a href="https://fileditch.com/" target="_blank" rel="noopener noreferrer">FileDitch</a>.</li> <li>Stores metadata (Title, Author, Original Link, FileDitch Link, Type) in <code>data.json</code>.</li> <li>Secure configuration using environment variables (or <code>.env</code> file) for API keys and secrets.</li> <li>Prevents duplicate processing of the same post (based on title/author).</li>
        <li>Provides a web UI (Flask) served locally (default: <code>http://127.0.0.1:5000/</code>) to display archived media items.</li> <li>Runs processing automatically in a background thread at configurable intervals.</li>
        <li>Includes a manual trigger endpoint (<code>/process</code>) via POST request.</li>
        <li>Includes a raw data endpoint (<code>/data</code>) to get the JSON content.</li>
        <li>Robust error handling for network requests, timeouts, JSON parsing, and file operations.</li>
        <li>Thread-safe operations for reading/writing the data file.</li>
    </ul>
    <h2>Prerequisites</h2>
    <ul>
        <li>Python 3.x</li>
        <li><code>pip</code> (Python package installer)</li>
    </ul>
    <h2>Installation & Setup</h2>
    <ol>
        <li>
            <strong>Clone the repository (if you haven't already):</strong>
            <pre><code>git clone https://github.com/Riotcoke123/IP2Ditch.git</code></pre>
        </li>
        <li>
            <strong>Navigate into the directory:</strong>
            <pre><code>cd IP2Ditch</code></pre>
        </li>
        <li>
            <strong>(Recommended) Create and activate a virtual environment:</strong>
            <pre><code>python -m venv venv
# On Windows
.\venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate</code></pre>
        </li>
        <li>
            <strong>Install required Python libraries:</strong>
            <pre><code>pip install Flask requests python-dotenv</code></pre> <p><em>(Note: The script also uses standard libraries like <code>os</code>, <code>json</code>, <code>logging</code>, <code>datetime</code>, <code>re</code>, <code>time</code>, <code>threading</code>, <code>mimetypes</code>, and <code>urllib.parse</code>, which are built into Python.)</em></p> </li>
        <li>
             <strong>Configure Environment Variables (IMPORTANT):</strong> <p>This application requires API credentials and configuration settings to be set via environment variables. The recommended way is to create a <code>.env</code> file in the root directory of the project (<code>IP2Ditch/</code>). Alternatively, set them directly in your system's environment.</p>
             <p>Create a file named <code>.env</code> with the following content, replacing placeholder values with your actual credentials:</p>
             <pre><code># Required Communities.Win Credentials
CW_API_KEY=your_communities_win_api_key
CW_API_SECRET=your_communities_win_api_secret
CW_XSRF_TOKEN=your_communities_win_xsrf_token

# Required Path to Data File (use forward slashes even on Windows)
# Example: Store 'data.json' in a 'backup' subdirectory relative to the script
APP_DATA_FILE_PATH=./backup/data.json
# Example: Store 'data.json' at an absolute path (Windows)
# APP_DATA_FILE_PATH=C:/Users/YourUser/Documents/IP2DitchBackup/data.json
# Example: Store 'data.json' at an absolute path (Linux/macOS)
# APP_DATA_FILE_PATH=/home/youruser/ip2ditch_backup/data.json

# Optional: Comma-separated list of API URLs to fetch (defaults shown)
# CW_API_URLS=https://communities.win/api/v2/post/newv2.json?community=ip2always,https://communities.win/api/v2/post/hotv2.json?community=ip2always

# Optional: FileDitch Upload URL (defaults shown)
# APP_FILEDITCH_URL=https://up1.fileditch.com/upload.php
</code></pre>
             <p><strong>Notes:</strong></p>
             <ul>
               <li>Make sure the <strong>directory</strong> specified in <code>APP_DATA_FILE_PATH</code> (e.g., <code>./backup/</code> or <code>C:/Users/YourUser/Documents/IP2DitchBackup/</code>) exists, or the script has permission to create it.</li>
               <li>Add <code>.env</code> to your <code>.gitignore</code> file to prevent accidentally committing secrets.</li>
               <li>The script will exit on startup if the required variables (<code>CW_API_KEY</code>, <code>CW_API_SECRET</code>, <code>CW_XSRF_TOKEN</code>) are not found in the environment or the <code>.env</code> file.</li>
             </ul>
         </li>
         <li>
            <strong>Create necessary directories:</strong>
            <p>Ensure you have <code>templates</code> and <code>static</code> directories in the same location as your script (<code>app.py</code>):</p>
            <pre><code>mkdir templates
mkdir static</code></pre>
            <p>Also ensure the directory for your <code>data.json</code> file exists (as configured in <code>APP_DATA_FILE_PATH</code> in your <code>.env</code> file, e.g., <code>mkdir backup</code> if using the default relative path).</p>
        </li>
        <li>
            <strong>Place Web Files:</strong>
             <ul>
                <li>Place your <code>index.html</code> file inside the <code>templates</code> directory.</li>
                <li>Place any static assets like <code>style.css</code> or images inside the <code>static</code> directory.</li>
             </ul>
        </li>
    </ol>
    <h2>Configuration via Environment Variables</h2> <p>The application's behavior is controlled via environment variables (preferably set in a <code>.env</code> file):</p>
    <ul>
        <li><code>CW_API_KEY</code> (Required): Your API key for communities.win.</li>
        <li><code>CW_API_SECRET</code> (Required): Your API secret for communities.win.</li>
        <li><code>CW_XSRF_TOKEN</code> (Required): Your XSRF token for communities.win requests (may need updating periodically).</li>
        <li><code>APP_DATA_FILE_PATH</code> (Required): The full or relative path where the <code>data.json</code> file will be stored. Ensure the parent directory exists or is creatable. (Default if not set: <code>./backup/data.json</code>)</li>
        <li><code>CW_API_URLS</code> (Optional): A comma-separated string of communities.win API endpoints to fetch posts from. (Default: Fetches new and hot posts from <code>IP2Always</code> community).</li>
        <li><code>APP_FILEDITCH_URL</code> (Optional): The target URL for FileDitch uploads. (Default: <code>https://up1.fileditch.com/upload.php</code>)</li>
        <li><code>REQUEST_TIMEOUT</code> (Hardcoded): Timeout in seconds for network requests (fetching API data, downloading files). Default: 30.</li>
        <li><code>UPLOAD_TIMEOUT</code> (Hardcoded): Timeout in seconds specifically for uploading files to FileDitch. Default: 300.</li>
        <li><code>PROCESSING_INTERVAL_SECONDS</code> (Hardcoded): How often (in seconds) the background thread runs the processing cycle. Default: 300 (5 minutes).</li>
    </ul>
    <p><em>Note: Timeouts and processing interval are currently hardcoded in <code>app.py</code> but could be converted to environment variables if further customization is needed.</em></p>
    <h2>Usage</h2>
    <ol>
        <li>
            <strong>Run the application:</strong>
            <pre><code>python app.py</code></pre>
            <em>(Ensure your virtual environment is active if you created one)</em>
        </li>
        <li>
            <strong>Access the Web Interface:</strong>
            <p>Open your web browser and navigate to:</p>
            <pre><code>http://127.0.0.1:5000/</code></pre>
            <p>This will display the table of archived media files.</p> </li>
         <li>
            <strong>Background Processing:</strong>
            <p>The script automatically starts a background thread that fetches, downloads, and uploads new supported media files every <code>PROCESSING_INTERVAL_SECONDS</code> (default: 5 minutes).</p> </li>
        <li>
            <strong>Manual Trigger:</strong>
            <p>To force an immediate processing cycle, send a POST request to the <code>/process</code> endpoint. You can use tools like <code>curl</code>:</p>
            <pre><code>curl -X POST http://127.0.0.1:5000/process</code></pre>
            <p>The response will indicate the outcome of the processing cycle.</p>
        </li>
        <li>
            <strong>Access Raw Data:</strong>
            <p>To get the raw JSON data stored in <code>data.json</code>, navigate to:</p>
            <pre><code>http://127.0.0.1:5000/data</code></pre>
        </li>
        <li>
            <strong>Stopping the Application:</strong> Press <code>Ctrl + C</code> in the terminal where the script is running.
        </li>
    </ol>
    <h2>File Structure</h2>
    <pre><code>IP2Ditch/
├── app.py             # Main Python script
├── .env               # Environment variables (API keys, paths - DO NOT COMMIT) <-- Added
├── data.json          # Stores archived media data (created automatically in path defined by APP_DATA_FILE_PATH) <-- Updated description
├── templates/
│   └── index.html     # HTML template for the web UI
├── static/
│   ├── style.css      # Optional: CSS styling for index.html
│   └── ...            # Other static assets (images, etc.)
├── venv/              # Virtual environment directory (if used)
└── README.md          # This file (in HTML format)
</code></pre>
    <h2>Limitations & Potential Issues</h2>
    <ul>
        <li><strong>API Key/Token Expiry:</strong> The API credentials loaded from environment variables may expire or be invalidated, causing API requests to fail (check for 401/403 errors in logs). The XSRF token is particularly likely to change.</li> <li><strong>Rate Limiting:</strong> Frequent requests might hit rate limits imposed by <code>communities.win</code> or <code>FileDitch</code>.</li>
        <li><strong>API Changes:</strong> Changes to the <code>communities.win</code> API structure or the <code>FileDitch</code> upload process/response format could break the script.</li>
        <li><strong>Resource Consumption:</strong> Downloading and uploading numerous large media files can consume significant bandwidth, disk space (temporarily during download), and CPU time.</li> <li><strong>Error Handling:</strong> While efforts have been made to handle common errors, edge cases might still exist. Check logs for details on failures.</li>
        <li><strong>Content Policies:</strong> Users are responsible for ensuring their use of this script complies with the terms of service of both <code>communities.win</code> and <code>FileDitch</code>.</li>
    </ul>
    <h2>License</h2>
    <p>
    GNU GENERAL PUBLIC LICENSE
    </p>

</body>
</html>
