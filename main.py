import os
import threading
import requests
import discord
import asyncio
from flask import Flask
from google import genai
from google.genai import types

# --- Dummy Web Server for Render 24/7 Keep-Alive ---
app = Flask('')

@app.route('/')
def home():
    return "Minecraft Assistant Bot is running active!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run)
    t.start()
# ---------------------------------------------------

# Environment Variables Configuration
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
GODLIKE_PANEL_URL = "https://panel.godlike.host"
GODLIKE_API_KEY = os.getenv("GODLIKE_API_KEY", "")
SERVER_ID = os.getenv("SERVER_ID", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MY_DISCORD_ID = int(os.getenv("MY_DISCORD_ID", "0"))

# Initialize Gemini Client
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# Helper headers for Godlike Pterodactyl API
def get_api_headers(content_type="application/json"):
    return {
        "Authorization": f"Bearer {GODLIKE_API_KEY}",
        "Content-Type": content_type,
        "Accept": "application/json"
    }

# --- TOOL 1: Console Command Execution ---
def send_console_command(command: str) -> str:
    """Executes a command on the Minecraft server console."""
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/command"
    payload = {"command": command}
    
    try:
        response = requests.post(url, headers=get_api_headers(), json=payload)
        if response.status_code == 204:
            return f"Command '{command}' executed successfully on console."
        return f"Failed to execute command. Status: {response.status_code}, Error: {response.text}"
    except Exception as e:
        return f"API Connection Error: {str(e)}"

# --- TOOL 2: Read Server File ---
def read_server_file(file_path: str) -> str:
    """Reads the text content of any server file (e.g., config.yml, server.properties)."""
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/contents?file={file_path}"
    headers = {"Authorization": f"Bearer {GODLIKE_API_KEY}", "Accept": "text/plain"}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.text
        return f"Failed to read file '{file_path}'. Status: {response.status_code}"
    except Exception as e:
        return f"Error reading file: {str(e)}"

# --- TOOL 3: Safe Write File (Auto-Backup Included) ---
def write_server_file(file_path: str, content: str) -> str:
    """Safely writes content to a file after creating an automatic backup (.bak)."""
    # Step 1: Create a backup of the original file if it exists
    existing_content = read_server_file(file_path)
    if existing_content and not existing_content.startswith("Failed to read"):
        backup_path = f"{file_path}.bak"
        backup_url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/write?file={backup_path}"
        requests.post(backup_url, headers=get_api_headers("text/plain"), data=existing_content)

    # Step 2: Write new content to the target file
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/write?file={file_path}"
    try:
        response = requests.post(url, headers=get_api_headers("text/plain"), data=content)
        if response.status_code == 204:
            return f"File '{file_path}' written successfully. (Auto-backup created at '{file_path}.bak')"
        return f"Failed to write file. Status: {response.status_code}, Error: {response.text}"
    except Exception as e:
        return f"Error writing file: {str(e)}"

# --- TOOL 4: List Directory Files ---
def list_server_files(directory: str = "") -> str:
    """Lists files and folders inside a directory (e.g. 'plugins' or root '')."""
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/list?directory={directory}"
    try:
        response = requests.get(url, headers=get_api_headers())
        if response.status_code == 200:
            data = response.json()
            items = [item['attributes']['name'] for item in data.get('data', [])]
            return f"Files/Folders in '{directory or 'root'}': " + ", ".join(items)
        return f"Failed to list directory. Status: {response.status_code}"
    except Exception as e:
        return f"Error listing directory: {str(e)}"

# --- TOOL 5: Read Latest Server Logs ---
def read_latest_logs() -> str:
    """Reads the last 50 lines of the server's latest.log file to debug errors or crashes."""
    log_content = read_server_file("logs/latest.log")
    if log_content.startswith("Failed to read"):
        return log_content
    lines = log_content.strip().split("\n")
    last_50_lines = "\n".join(lines[-50:])
    return f"Last 50 lines of logs/latest.log:\n{last_50_lines}"

# --- TOOL 6: Get Server CPU & RAM Usage ---
def get_server_resources() -> str:
    """Fetches real-time server stats (CPU, RAM, Disk, Power State)."""
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/resources"
    try:
        response = requests.get(url, headers=get_api_headers())
        if response.status_code == 200:
            stats = response.json()['attributes']['resources']
            state = response.json()['attributes']['current_state']
            ram_mb = round(stats['memory_bytes'] / (1024 * 1024), 2)
            cpu_pct = round(stats['cpu_absolute'], 2)
            disk_mb = round(stats['disk_bytes'] / (1024 * 1024), 2)
            return f"📊 **Server Status:** {state.upper()}\n💻 **CPU:** {cpu_pct}%\n🧠 **RAM Usage:** {ram_mb} MB\n💾 **Disk Usage:** {disk_mb} MB"
        return f"Failed to fetch resources. Status: {response.status_code}"
    except Exception as e:
        return f"Error fetching stats: {str(e)}"

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}!")
    print("Advanced Minecraft Admin Bot is online and fully active!")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Security: Restrict bot control strictly to your Discord ID
    if MY_DISCORD_ID != 0 and message.author.id != MY_DISCORD_ID:
        return

    async with message.channel.typing():
        # System Instruction for Expert Management & Safety
        sys_instruction = (
            "You are an expert Minecraft Paper 1.21.11 server administrator assistant inside Discord.\n"
            "Safety & Accuracy Rules:\n"
            "1. Before editing any file, ALWAYS read it first with `read_server_file` or check directory files using `list_server_files`.\n"
            "2. When writing/editing YAML config files, ALWAYS double-check spacing, quotes, and YAML indentation rules carefully.\n"
            "3. If unfamiliar with a plugin or its settings, use `google_search` to find official plugin documentation/wiki first.\n"
            "4. If the user reports server errors or crashes, check `read_latest_logs` or `get_server_resources` to diagnose.\n"
            "5. Always notify the user if an automatic file backup (.bak) was created before making changes."
        )

        all_tools = [
            send_console_command,
            read_server_file,
            write_server_file,
            list_server_files,
            read_latest_logs,
            get_server_resources,
            {"google_search": {}}
        ]

        # Auto-retry loop for 503 High Demand Error handling
        max_retries = 3
        response = None

        for attempt in range(max_retries):
            try:
                response = gemini_client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=message.content,
                    config=types.GenerateContentConfig(
                        system_instruction=sys_instruction,
                        tools=all_tools,
                    )
                )
                break
            except Exception as err:
                if ("503" in str(err) or "UNAVAILABLE" in str(err)) and attempt < max_retries - 1:
                    await asyncio.sleep(3)
                    continue
                else:
                    await message.channel.send(f"❌ **Error processing request:** `{str(err)}`")
                    return

        try:
            if response and response.function_calls:
                for call in response.function_calls:
                    fn_name = call.name
                    args = call.args

                    if fn_name == "send_console_command":
                        cmd = args.get("command")
                        res = send_console_command(cmd)
                        await message.channel.send(f"⚙️ **Console Executed:** `{cmd}`\n📄 **Result:** {res}")

                    elif fn_name == "write_server_file":
                        path = args.get("file_path")
                        content = args.get("content")
                        res = write_server_file(path, content)
                        await message.channel.send(f"📝 **File Saved:** `{path}`\n📄 **Result:** {res}")

                    elif fn_name == "read_server_file":
                        path = args.get("file_path")
                        res = read_server_file(path)
                        if len(res) > 1900:
                            res = res[:1900] + "\n...(truncated due to length)"
                        await message.channel.send(f"📖 **File Content (`{path}`):**\n```yaml\n{res}\n```")

                    elif fn_name == "list_server_files":
                        directory = args.get("directory", "")
                        res = list_server_files(directory)
                        await message.channel.send(f"📁 **Directory List:**\n{res}")

                    elif fn_name == "read_latest_logs":
                        res = read_latest_logs()
                        if len(res) > 1900:
                            res = res[-1900:]
                        await message.channel.send(f"📋 **Server Logs:**\n```log\n{res}\n```")

                    elif fn_name == "get_server_resources":
                        res = get_server_resources()
                        await message.channel.send(f"{res}")

            elif response and response.text:
                await message.channel.send(response.text)

        except Exception as e:
            await message.channel.send(f"❌ **Error executing response:** `{str(e)}`")

if __name__ == "__main__":
    keep_alive()
    bot.run(DISCORD_BOT_TOKEN)
    
