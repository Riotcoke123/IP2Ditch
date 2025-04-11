<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IP2Ditch Readme</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
            line-height: 1.6;
            color: #24292e;
            max-width: 800px;
            margin: 20px auto;
            padding: 15px;
        }
        h1, h2, h3 {
            border-bottom: 1px solid #eaecef;
            padding-bottom: 0.3em;
            margin-top: 24px;
            margin-bottom: 16px;
            font-weight: 600;
        }
        h1 { font-size: 2em; }
        h2 { font-size: 1.5em; }
        h3 { font-size: 1.25em; }
        p { margin-bottom: 16px; }
        ul, ol { padding-left: 2em; margin-bottom: 16px; }
        li { margin-bottom: 8px; }
        code {
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace;
            background-color: rgba(27,31,35,0.05);
            padding: 0.2em 0.4em;
            margin: 0;
            font-size: 85%;
            border-radius: 3px;
        }
        pre {
            background-color: #f6f8fa;
            border-radius: 3px;
            font-size: 85%;
            line-height: 1.45;
            overflow: auto;
            padding: 16px;
            margin-bottom: 16px;
        }
        pre code {
            background-color: transparent;
            border: 0;
            padding: 0;
            margin: 0;
            font-size: 100%;
            line-height: inherit;
            word-break: normal;
        }
        strong { font-weight: 600; }
        a { color: #0366d6; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .warning {
             background-color: #fffbdd;
             border-left: 5px solid #ffea00;
             padding: 10px;
             margin-bottom: 15px;
        }
    </style>
</head>
<body>
    <h1>IP2Ditch - IP2Always Video Backup & Archiver</h1>
    <p>
        <strong>IP2Ditch</strong> is a Python application designed to monitor the <code>communities.win/c/IP2Always</code> community (fetching both 'new' and 'hot' posts), identify direct links to <code>.mp4</code> video files within posts, download these videos, and subsequently upload them to <a href="https://fileditch.com/" target="_blank" rel="noopener noreferrer">FileDitch</a> for archival purposes.
    </p>
    <p>
        It maintains a local JSON database (<code>data.json</code>) to track processed videos (based on post title and author) and prevent duplicates. The application runs a background thread for continuous, automated processing and provides a simple Flask web interface to view the list of archived videos with their original and FileDitch links.
    </p>
    <h2>Key Features</h2>
    <ul>
        <li>Fetches posts from <a href="https://communities.win/c/IP2Always/new" target="_blank" rel="noopener noreferrer"><code>communities.win/c/IP2Always</code></a> (New & Hot endpoints).</li>
        <li>Identifies posts containing direct <code>.mp4</code> links.</li>
        <li>Downloads the <code>.mp4</code> video file.</li>
        <li>Uploads the downloaded video to <a href="https://fileditch.com/" target="_blank" rel="noopener noreferrer">FileDitch</a>.</li>
        <li>Stores metadata (Title, Author, Original Link, FileDitch Link) in <code>data.json</code>.</li>
        <li>Prevents duplicate processing of the same post (based on title/author).</li>
        <li>Provides a web UI (Flask) served locally (default: <code>http://127.0.0.1:5000/</code>) to display archived items.</li>
        <li>Runs processing automatically in a background thread at configurable intervals.</li>
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
            <strong>Clone the repository:</strong>
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
            <pre><code>pip install Flask requests</code></pre>
            <p><em>(Note: The script also uses standard libraries like <code>os</code>, <code>json</code>, <code>logging</code>, <code>datetime</code>, <code>re</code>, <code>time</code>, <code>threading</code>, and <code>urllib.parse</code>, which are built into Python and do not require separate installation.)</em></p>
        </li>
        <li>
            <strong>Configure the script (<code>app.py</code> or your script name):</strong>
            <ul>
                <li>Review and potentially adjust constants at the top of the script, especially <code>DATA_FILE_PATH</code> if you want to store <code>data.json</code> elsewhere.</li>
                <li><strong>SECURITY WARNING:</strong> The script uses hardcoded API credentials (<code>x-api-key</code>, <code>x-api-secret</code>, <code>x-xsrf-token</code>) in <code>COMMUNITIES_HEADERS</code>. This is insecure. It's highly recommended to modify the script to load these from environment variables or a secure configuration file instead of committing them directly. These tokens might also expire or change, requiring updates.</li>
                <li>Update <code>user-agent</code> and <code>sec-ch-ua</code> headers if you encounter fetching issues due to browser version changes.</li>
            </ul>
        </li>
         <li>
            <strong>Create necessary directories:</strong>
            <p>Ensure you have <code>templates</code> and <code>static</code> directories in the same location as your script:</p>
            <pre><code>mkdir templates
mkdir static</code></pre>
        </li>
        <li>
            <strong>Place Web Files:</strong>
             <ul>
                 <li>Place your <code>index.html</code> file inside the <code>templates</code> directory.</li>
                 <li>Place any static assets like <code>style.css</code> or images (e.g., <code>6.webp</code> mentioned in script comments) inside the <code>static</code> directory.</li>
             </ul>
        </li>
    </ol>
    <h2>Configuration Details</h2>
    <p>Several constants at the beginning of <code>app.py</code> control its behavior:</p>
    <ul>
        <li><code>COMMUNITIES_API_URLS</code>: List of API endpoints to fetch posts from.</li>
        <li><code>COMMUNITIES_HEADERS</code>: Headers used for API requests. <strong>Contains sensitive keys/tokens that should ideally be externalized.</strong></li>
        <li><code>FILEDITCH_UPLOAD_URL</code>: The target URL for FileDitch uploads.</li>
        <li><code>DATA_FILE_PATH</code>: The full path where the <code>data.json</code> file is stored. Ensure the directory exists or the script can create it.</li>
        <li><code>REQUEST_TIMEOUT</code>: Timeout in seconds for network requests (fetching API data, downloading MP4s).</li>
        <li><code>UPLOAD_TIMEOUT</code>: Timeout in seconds specifically for uploading files to FileDitch.</li>
        <li><code>PROCESSING_INTERVAL_SECONDS</code>: How often (in seconds) the background thread runs the processing cycle.</li>
    </ul>
     <div class="warning">
        <strong>⚠️ Important Security Note:</strong> Do not commit sensitive API keys, secrets, or tokens directly into your Git repository. Use environment variables, a <code>.env</code> file (added to <code>.gitignore</code>), or a dedicated configuration management system.
    </div>
    <h2>Usage</h2>
    <ol>
        <li>
            <strong>Run the application:</strong>
            <pre><code>python app.py</code></pre>
            <em>(Replace <code>app.py</code> with your actual script filename if different)</em>
        </li>
        <li>
            <strong>Access the Web Interface:</strong>
            <p>Open your web browser and navigate to:</p>
            <pre><code>http://127.0.0.1:5000/</code></pre>
            <p>This will display the table of archived videos.</p>
        </li>
         <li>
            <strong>Background Processing:</strong>
            <p>The script automatically starts a background thread that fetches, downloads, and uploads new MP4s every <code>PROCESSING_INTERVAL_SECONDS</code> (default: 300 seconds / 5 minutes).</p>
         </li>
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
├── app.py               # Main Python script (or your filename)
├── data.json            # Stores archived video data (created automatically)
├── templates/
│   └── index.html       # HTML template for the web UI
├── static/
│   ├── style.css        # Optional: CSS styling for index.html
│   └── 6.webp           # Optional: Image mentioned in script comments
├── venv/                # Virtual environment directory (if used)
└── README.md            # This file
</code></pre>
    <h2>Limitations & Potential Issues</h2>
    <ul>
        <li><strong>API Key/Token Expiry:</strong> The hardcoded tokens in <code>COMMUNITIES_HEADERS</code> may expire or be invalidated, causing API requests to fail.</li>
        <li><strong>Rate Limiting:</strong> Frequent requests might hit rate limits imposed by <code>communities.win</code> or <code>FileDitch</code>.</li>
        <li><strong>API Changes:</strong> Changes to the <code>communities.win</code> API structure or the <code>FileDitch</code> upload process/response format could break the script.</li>
        <li><strong>Resource Consumption:</strong> Downloading and uploading numerous large video files can consume significant bandwidth, disk space (temporarily during download), and CPU time.</li>
        <li><strong>Error Handling:</strong> While efforts have been made to handle common errors, edge cases might still exist.</li>
        <li><strong>Content Policies:</strong> Users are responsible for ensuring their use of this script complies with the terms of service of both <code>communities.win</code> and <code>FileDitch</code>.</li>
    </ul>
    <h2>License</h2>
    <p>
        Please add a <code>LICENSE</code> file to your repository. If you haven't chosen one, the <a href="https://opensource.org/licenses/MIT" target="_blank" rel="noopener noreferrer">MIT License</a> is a common and permissive option.
    </p>

</body>
</html>
