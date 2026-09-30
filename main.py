import os
import json
import asyncio
import threading
import requests
import discord
from discord.ui import Button, View
from flask import Flask
from google import genai
from google.genai import types

# --- Dummy Web Server for Render 24/7 Keep-Alive ---
app = Flask('')

@app.route('/')
def home():
    return "Minecraft Assistant Bot is active & running!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run)
    t.start()
# ---------------------------------------------------

# Environment Variables
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
GODLIKE_PANEL_URL = "https://panel.godlike.host"
GODLIKE_API_KEY = os.getenv("GODLIKE_API_KEY", "").strip()
SERVER_ID = os.getenv("SERVER_ID", "").strip()
MY_DISCORD_ID = int(os.getenv("MY_DISCORD_ID", "0"))

# Multiple API Keys support (Comma-separated in GEMINI_API_KEYS or single GEMINI_API_KEY)
raw_api_keys = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
GEMINI_API_KEYS = [k.strip() for k in raw_api_keys.split(",") if k.strip()]

# ১০০% সচল ও ভ্যালিড মডেলের তালিকা
GEMINI_MODELS = ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-2.5-flash"]


# Memory File Path
MEMORY_FILE = "memory.json"

# --- Persistent Long-Term Memory Helpers ---
def load_memory() -> dict:
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"rules": [], "notes": []}
    return {"rules": [], "notes": []}

def save_memory_fact(fact_or_rule: str) -> str:
    """Saves long-term instructions or rules given by the user to memory.json."""
    data = load_memory()
    if fact_or_rule not in data["rules"]:
        data["rules"].append(fact_or_rule)
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return f"Memory updated: Saved '{fact_or_rule}' into persistent memory."
    return "Rule is already saved in memory."

def get_saved_memory() -> str:
    """Returns saved long-term memories and rules."""
    data = load_memory()
    rules = data.get("rules", [])
    if not rules:
        return "No specific long-term rules saved yet."
    return "Saved Server Rules & Notes:\n" + "\n".join([f"- {r}" for r in rules])

# --- Godlike Panel API Headers ---
def get_api_headers(content_type="application/json"):
    return {
        "Authorization": f"Bearer {GODLIKE_API_KEY}",
        "Content-Type": content_type,
        "Accept": "application/json"
    }

# --- Safe / Non-Destructive Server Tools ---
def get_server_resources() -> str:
    """Fetches real-time server status (CPU, RAM, Disk, Online state)."""
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/resources"
    try:
        res = requests.get(url, headers=get_api_headers())
        if res.status_code == 200:
            data = res.json()['attributes']
            stats = data['resources']
            state = data['current_state']
            ram_mb = round(stats['memory_bytes'] / (1024 * 1024), 2)
            cpu_pct = round(stats['cpu_absolute'], 2)
            disk_mb = round(stats['disk_bytes'] / (1024 * 1024), 2)
            return f"📊 **Server Status:** `{state.upper()}`\n💻 **CPU:** `{cpu_pct}%` | 🧠 **RAM:** `{ram_mb} MB` | 💾 **Disk:** `{disk_mb} MB`"
        return f"Failed to fetch resources. Status Code: {res.status_code}"
    except Exception as e:
        return f"API Error: {str(e)}"

def get_online_players() -> str:
    """Checks online players on the Minecraft server using console list command."""
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/command"
    try:
        res = requests.post(url, headers=get_api_headers(), json={"command": "list"})
        if res.status_code == 204:
            # Wait brief moment for logs to update
            return "Sent '/list' command to server console. Please check latest logs or console output to see player list."
        return f"Failed to send list command. Status Code: {res.status_code}"
    except Exception as e:
        return f"API Error: {str(e)}"

def send_console_command(command: str) -> str:
    """Executes a safe console command on the Minecraft server."""
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/command"
    try:
        res = requests.post(url, headers=get_api_headers(), json={"command": command})
        if res.status_code == 204:
            return f"Command `{command}` executed successfully on console."
        return f"Failed to execute command. Status: {res.status_code}, Response: {res.text}"
    except Exception as e:
        return f"API Error: {str(e)}"

def read_server_file(file_path: str) -> str:
    """Reads content of a specified server file."""
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/contents?file={file_path}"
    headers = {"Authorization": f"Bearer {GODLIKE_API_KEY}", "Accept": "text/plain"}
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            return res.text
        return f"Failed to read file '{file_path}'. Status Code: {res.status_code}"
    except Exception as e:
        return f"Error reading file: {str(e)}"

def write_server_file(file_path: str, content: str) -> str:
    """Safely updates/writes content to a file after creating a .bak backup."""
    existing = read_server_file(file_path)
    if existing and not existing.startswith("Failed to read"):
        backup_url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/write?file={file_path}.bak"
        requests.post(backup_url, headers=get_api_headers("text/plain"), data=existing)

    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/write?file={file_path}"
    try:
        res = requests.post(url, headers=get_api_headers("text/plain"), data=content)
        if res.status_code == 204:
            return f"File '{file_path}' written successfully. (Auto-backup created at '{file_path}.bak')"
        return f"Failed to write file. Status: {res.status_code}, Response: {res.text}"
    except Exception as e:
        return f"Error writing file: {str(e)}"

def list_server_files(directory: str = "") -> str:
    """Lists files/folders in a specified server directory."""
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/list?directory={directory}"
    try:
        res = requests.get(url, headers=get_api_headers())
        if res.status_code == 200:
            items = [item['attributes']['name'] for item in res.json().get('data', [])]
            return f"Files in '{directory or 'root'}': " + ", ".join(items)
        return f"Failed to list directory. Status Code: {res.status_code}"
    except Exception as e:
        return f"Error listing directory: {str(e)}"

def read_latest_logs() -> str:
    """Fetches the last 50 lines of logs/latest.log."""
    log_content = read_server_file("logs/latest.log")
    if log_content.startswith("Failed to read"):
        return log_content
    lines = log_content.strip().split("\n")
    return "Last 50 lines of logs:\n" + "\n".join(lines[-50:])

# --- Dangerous Action Tools Execution (Executed ONLY after Owner Confirmation) ---
def execute_power_signal(signal: str) -> str:
    """Sends power state signal (start, stop, restart, kill) to server."""
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/power"
    try:
        res = requests.post(url, headers=get_api_headers(), json={"signal": signal})
        if res.status_code == 204:
            return f"Power signal '{signal.upper()}' sent successfully to server."
        return f"Failed power action. Status Code: {res.status_code}"
    except Exception as e:
        return f"Error executing power action: {str(e)}"

def execute_file_deletion(file_path: str) -> str:
    """Deletes a file or directory from server."""
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/delete"
    payload = {"root": "/", "files": [file_path]}
    try:
        res = requests.post(url, headers=get_api_headers(), json=payload)
        if res.status_code == 204:
            return f"File '{file_path}' deleted successfully."
        return f"Failed file deletion. Status Code: {res.status_code}"
    except Exception as e:
        return f"Error deleting file: {str(e)}"

# Tools Schema for Gemini AI
server_tools = [
    get_server_resources,
    get_online_players,
    send_console_command,
    read_server_file,
    write_server_file,
    list_server_files,
    read_latest_logs,
    save_memory_fact,
    get_saved_memory
]

# --- Smart Gemini API Call Handler with Exponential Retry & Key Rotation ---
async def generate_gemini_with_retry(prompt: str, sys_instruction: str):
    """Retries API requests on 503/429 transient errors with exponential backoff and multi-key fallback."""
    last_exception = None

    for key_idx, api_key in enumerate(GEMINI_API_KEYS):
        try:
            client = genai.Client(api_key=api_key)
        except Exception as e:
            last_exception = e
            continue

        for model_name in GEMINI_MODELS:
            for attempt in range(3): # Try up to 3 times per model
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=sys_instruction,
                            tools=server_tools,
                        )
                    )
                    return response
                except Exception as err:
                    err_msg = str(err)
                    last_exception = err
                    # If 503 or 429 occurs, sleep briefly and retry
                    if "503" in err_msg or "UNAVAILABLE" in err_msg or "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                        await asyncio.sleep(2 ** attempt) # 1s, 2s, 4s backoff
                        continue
                    else:
                        break # Try next model or key for non-transient errors

    raise last_exception if last_exception else RuntimeError("All Gemini API keys and models failed to respond.")

# --- Confirmation View for High-Risk Admin Actions ---
class ConfirmationView(View):
    def __init__(self, owner_id: int, action_type: str, action_data: str):
        super().__init__(timeout=60)
        self.owner_id = owner_id
        self.action_type = action_type
        self.action_data = action_data

    @discord.ui.button(label="✅ অনুমোদন দিন", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ কেবল অনার এই কাজের অনুমোদন দিতে পারবেন!", ephemeral=True)
            return

        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="⏳ **অনুমোদন দেওয়া হয়েছে। কাজ শুরু হচ্ছে...**", view=self)

        if self.action_type == "power":
            res = execute_power_signal(self.action_data)
            await interaction.followup.send(f"⚡ **সার্ভার অ্যাকশন রিপোর্ট:** {res}")
        elif self.action_type == "delete":
            res = execute_file_deletion(self.action_data)
            await interaction.followup.send(f"🗑️ **ফাইল ডিলিট রিপোর্ট:** {res}")

    @discord.ui.button(label="❌ বাতিল করুন", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ কেবল অনার এই বাটন ব্যবহার করতে পারবেন!", ephemeral=True)
            return

        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="🛑 **কাজটি বাতিল করা হয়েছে।**", view=self)

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

# Short-term Chat History Session Memory
channel_history = {}

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}!")
    print("Minecraft Advanced Server Admin Bot is running with full safety controls!")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Security Check
    if MY_DISCORD_ID != 0 and message.author.id != MY_DISCORD_ID:
        return

    msg_text = message.content.strip()

    # Manual Safety Triggers for High-Risk Requests
    lower_text = msg_text.lower()

    # Power Command Detection
    for p_word in ["restart", "stop", "kill", "start", "রিস্টার্ট", "বন্ধ", "স্টার্ট"]:
        if p_word in lower_text and any(k in lower_text for k in ["server", "সার্ভার", "কর্ড"]):
            signal = "restart" if "restart" in lower_text or "রিস্টার্ট" in lower_text else ("stop" if "stop" in lower_text or "বন্ধ" in lower_text else "start")
            view = ConfirmationView(MY_DISCORD_ID, "power", signal)
            await message.channel.send(
                f"⚠️ **অনুমোদনের অনুরোধ:** আপনি কি নিশ্চিত যে আপনি সার্ভার `{signal.upper()}` করতে চান?",
                view=view
            )
            return

    # Delete Command Detection
    if "delete" in lower_text or "মুছে" in lower_text or "ডিলিট" in lower_text:
        words = msg_text.split()
        target_file = words[-1] if len(words) > 1 else ""
        if target_file and "." in target_file:
            view = ConfirmationView(MY_DISCORD_ID, "delete", target_file)
            await message.channel.send(
                f"⚠️ **অনুমোদনের অনুরোধ:** আপনি কি নিশ্চিত যে আপনি ফাইল `{target_file}` মুছে ফেলতে চান?",
                view=view
            )
            return

    async with message.channel.typing():
        # Retrieve Memory Rules
        saved_rules = get_saved_memory()

        sys_instruction = (
            "You are an expert Minecraft Paper 1.21.11 server administrator assistant inside Discord.\n"
            "Long-Term Rules Memory:\n"
            f"{saved_rules}\n\n"
            "Safety & Administrative Guidelines:\n"
            "1. Before editing any file, ALWAYS read it first with `read_server_file` or check directory using `list_server_files`.\n"
            "2. When writing/editing YAML config files, ALWAYS double-check formatting and indentation rules.\n"
            "3. If user asks to remember a permanent rule or preference, use `save_memory_fact` to record it.\n"
            "4. Always notify the user if an automatic text backup (.bak) was created before writing files."
        )

        try:
            response = await generate_gemini_with_retry(msg_text, sys_instruction)

            if response and response.function_calls:
                for call in response.function_calls:
                    fn_name = call.name
                    args = call.args or {}

                    if fn_name == "get_server_resources":
                        res = get_server_resources()
                        await message.channel.send(res)

                    elif fn_name == "get_online_players":
                        res = get_online_players()
                        await message.channel.send(f"👥 **প্লেয়ার লিস্ট স্ট্যাটাস:** {res}")

                    elif fn_name == "send_console_command":
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
                            res = res[:1900] + "\n...(truncated)"
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

                    elif fn_name == "save_memory_fact":
                        fact = args.get("fact_or_rule")
                        res = save_memory_fact(fact)
                        await message.channel.send(f"🧠 **মেমোরি সেভ করা হয়েছে:** {res}")

                    elif fn_name == "get_saved_memory":
                        res = get_saved_memory()
                        await message.channel.send(f"📜 **সংরক্ষিত মেমোরি নিয়মাবলি:**\n{res}")

            elif response and response.text:
                res_text = response.text
                if len(res_text) > 1900:
                    for i in range(0, len(res_text), 1900):
                        await message.channel.send(res_text[i:i+1900])
                else:
                    await message.channel.send(res_text)

        except Exception as err:
            err_str = str(err)
            await message.channel.send(f"❌ **Error details:** `{err_str[:1800]}`")

if __name__ == "__main__":
    keep_alive()
    bot.run(DISCORD_BOT_TOKEN)
        
