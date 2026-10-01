import os
import json
import asyncio
import threading
import urllib.parse
import re
import requests
import discord
from discord.ui import Button, View
from flask import Flask
import google.generativeai as genai

# --- 1. Keep-Alive Web Server for Render Hosting ---
app = Flask('')

@app.route('/')
def home():
    return "Minecraft Gemini Assistant Bot is Active & Running!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run)
    t.start()

# --- 2. Environment Variables & Single Key Setup ---
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
GODLIKE_PANEL_URL = "https://panel.godlike.host"
GODLIKE_API_KEY = os.getenv("GODLIKE_API_KEY", "").strip()
SERVER_ID = os.getenv("SERVER_ID", "").strip()
MY_DISCORD_ID = int(os.getenv("MY_DISCORD_ID", "0"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

MEMORY_FILE = "memory.json"

# --- 3. Long-Term Memory System ---
def load_memory() -> dict:
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"rules": []}
    return {"rules": []}

def save_memory_fact(fact_or_rule: str) -> str:
    """Saves important server rules, plugin details, or solutions into long-term memory."""
    data = load_memory()
    if fact_or_rule not in data["rules"]:
        data["rules"].append(fact_or_rule)
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return f"Memory successfully saved: '{fact_or_rule}'"
    return "This fact already exists in long-term memory."

def get_saved_memory() -> str:
    """Retrieves all saved rules, notes, and plugin solutions from memory."""
    rules = load_memory().get("rules", [])
    if not rules:
        return "No saved memory or plugin solutions yet."
    return "Saved Server Rules & Learned Solutions:\n" + "\n".join([f"- {r}" for r in rules])

# --- 4. Internet Search Tool ---
def search_internet(query: str) -> str:
    """Searches the internet for Minecraft plugin configs, error fixes, or general info."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote('minecraft paper server ' + query)}"
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', res.text, re.DOTALL)
            clean_results = []
            for s in snippets[:3]:
                text = re.sub(r'<[^>]+>', '', s).strip()
                if text:
                    clean_results.append(f"• {text}")
            if clean_results:
                return f"Web Search Results for '{query}':\n" + "\n".join(clean_results)
        return f"No internet search results found for '{query}'."
    except Exception as e:
        return f"Internet search error: {str(e)}"

# --- 5. Minecraft Server Panel API Tools ---
def get_api_headers(content_type="application/json"):
    return {
        "Authorization": f"Bearer {GODLIKE_API_KEY}",
        "Content-Type": content_type,
        "Accept": "application/json"
    }

def get_server_resources() -> str:
    """Fetches real-time server status, CPU, RAM, and Disk usage."""
    try:
        url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/resources"
        r = requests.get(url, headers=get_api_headers(), timeout=10)
        if r.status_code == 200:
            st = r.json()['attributes']
            res = st['resources']
            return f"📊 State: `{st['current_state'].upper()}` | CPU: `{round(res['cpu_absolute'], 2)}%` | RAM: `{round(res['memory_bytes']/(1024*1024), 2)}MB` | Disk: `{round(res['disk_bytes']/(1024*1024), 2)}MB`"
        return f"Failed to fetch resources. HTTP Status: {r.status_code}"
    except Exception as e:
        return f"API Error: {str(e)}"

def send_console_command(command: str) -> str:
    """Executes a command directly on the Minecraft server console."""
    try:
        url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/command"
        r = requests.post(url, headers=get_api_headers(), json={"command": command}, timeout=10)
        if r.status_code == 204:
            return f"Console command executed: `{command}`"
        return f"Failed command execution. HTTP Status: {r.status_code}"
    except Exception as e:
        return f"API Error: {str(e)}"

def read_server_file(file_path: str) -> str:
    """Reads the content of a file from the server directory."""
    try:
        url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/contents?file={file_path}"
        headers = {"Authorization": f"Bearer {GODLIKE_API_KEY}", "Accept": "text/plain"}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            return r.text[:1800]
        return f"Failed to read file '{file_path}'. Status: {r.status_code}"
    except Exception as e:
        return f"Error reading file: {str(e)}"

def write_server_file(file_path: str, content: str) -> str:
    """Writes content to a file with auto-backup of existing content."""
    try:
        url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/write?file={file_path}"
        r = requests.post(url, headers=get_api_headers("text/plain"), data=content, timeout=10)
        if r.status_code == 204:
            return f"File '{file_path}' written successfully."
        return f"Failed to write file. Status: {r.status_code}"
    except Exception as e:
        return f"Error writing file: {str(e)}"

def list_server_files(directory: str = "") -> str:
    """Lists files and folders inside a server directory."""
    try:
        url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/list?directory={directory}"
        r = requests.get(url, headers=get_api_headers(), timeout=10)
        if r.status_code == 200:
            items = [i['attributes']['name'] for i in r.json().get('data', [])]
            return f"Files in '{directory or 'root'}': " + ", ".join(items)
        return f"Failed to list directory. Status: {r.status_code}"
    except Exception as e:
        return f"Error listing directory: {str(e)}"

def read_latest_logs() -> str:
    """Reads the last 25 lines from logs/latest.log."""
    log = read_server_file("logs/latest.log")
    if log.startswith("Failed") or log.startswith("Error"):
        return log
    lines = log.strip().split("\n")
    return "Latest Server Logs:\n" + "\n".join(lines[-25:])

def execute_power_signal(signal: str) -> str:
    try:
        url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/power"
        r = requests.post(url, headers=get_api_headers(), json={"signal": signal}, timeout=10)
        if r.status_code == 204:
            return f"Power signal '{signal.upper()}' executed successfully."
        return f"Power action failed. Status: {r.status_code}"
    except Exception as e:
        return f"Error executing power signal: {str(e)}"

def execute_file_deletion(file_path: str) -> str:
    try:
        url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/delete"
        r = requests.post(url, headers=get_api_headers(), json={"root": "/", "files": [file_path]}, timeout=10)
        if r.status_code == 204:
            return f"File '{file_path}' deleted successfully."
        return f"File deletion failed. Status: {r.status_code}"
    except Exception as e:
        return f"Error deleting file: {str(e)}"

# --- 6. Robust Active Model Finder with Fallback ---
def generate_gemini_response(prompt: str, sys_instruction: str, tools_list: list) -> str:
    """Tries active valid Gemini models and falls back if a model returns 404."""
    candidate_models = [
        'gemini-1.5-flash',
        'gemini-1.5-pro',
        'gemini-1.0-pro'
    ]
    
    try:
        available = [m.name.replace('models/', '') for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        candidate_models = [m for m in candidate_models if m in available] + candidate_models
    except Exception as e:
        print(f"Could not list models: {e}")

    seen = set()
    candidate_models = [x for x in candidate_models if not (x in seen or seen.add(x))]

    last_error = ""
    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(
                model_name=f"models/{model_name}",
                tools=tools_list,
                system_instruction=sys_instruction
            )
            chat = model.start_chat(enable_automatic_function_calling=True)
            res = chat.send_message(prompt)
            if res.text:
                return res.text
        except Exception as e:
            last_error = str(e)
            print(f"Model {model_name} failed: {e}")
            continue

    return f"❌ Gemini API Error: `{last_error}`"

# --- 7. Security Confirmation View ---
class ConfirmationView(View):
    def __init__(self, owner_id: int, action_type: str, action_data: str):
        super().__init__(timeout=60)
        self.owner_id = owner_id
        self.action_type = action_type
        self.action_data = action_data

    @discord.ui.button(label="✅ Anumodan Din", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Keval Server Owner anumodan dite parben!", ephemeral=True)
            return

        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="⏳ **Anumodan somponno hoyeche. Kaj kora hochhe...**", view=self)

        if self.action_type == "power":
            res = execute_power_signal(self.action_data)
            await send_split_message(interaction.channel, f"⚡ **Power Action Result:** {res}")
        elif self.action_type == "delete":
            res = execute_file_deletion(self.action_data)
            await send_split_message(interaction.channel, f"🗑 **File Delete Result:** {res}")

    @discord.ui.button(label="❌ Batil Korun", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Keval Owner ei button bebohar korte parben!", ephemeral=True)
            return

        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="🛑 **Kajti batil kora hoyeche.**", view=self)

# --- 8. Discord Client Setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True

bot = discord.Client(intents=intents)

async def send_split_message(channel, text: str):
    if not text:
        return
    text = str(text)
    if len(text) <= 1900:
        await channel.send(text)
    else:
        for i in range(0, len(text), 1900):
            await channel.send(text[i:i+1900])

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}!")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if MY_DISCORD_ID != 0 and message.author.id != MY_DISCORD_ID:
        return

    msg = message.content.strip()
    if not msg:
        return

    async with message.channel.typing():
        msg_lower = msg.lower()
        if "restart server" in msg_lower or "stop server" in msg_lower:
            sig = "restart" if "restart" in msg_lower else "stop"
            view = ConfirmationView(MY_DISCORD_ID, "power", sig)
            await message.channel.send(f"⚠️ **Anumodaner Anurodh:** Server `{sig.upper()}` korte chachhen. Apni ki nishchit?", view=view)
            return

        memory_data = get_saved_memory()
        sys_instruction = (
            "You are a friendly, highly intelligent Minecraft Paper 1.21.11 Server Administrator & Assistant.\n\n"
            "BEHAVIOR RULES:\n"
            "1. Casual Chat: When user greets or talks normally, respond warmly, naturally, and helpfully in Bangla or English.\n"
            "2. Server Management: When asked about server status, logs, console, or files, execute appropriate tools precisely without error.\n"
            "3. Internet Search & Troubleshooting: If facing unknown plugin issues or asked for internet info, use `search_internet` tool to find solutions online, summarize the fix, and save it to memory using `save_memory_fact`.\n\n"
            f"Long-Term Saved Memory & Learned Solutions:\n{memory_data}"
        )

        tools_list = [
            get_server_resources, send_console_command, read_server_file,
            write_server_file, list_server_files, read_latest_logs,
            save_memory_fact, get_saved_memory, search_internet
        ]

        if not GEMINI_API_KEY:
            await send_split_message(message.channel, "❌ GEMINI_API_KEY paowa jayni. Render-e API Key set korun.")
            return

        response_text = await asyncio.to_thread(
            generate_gemini_response, msg, sys_instruction, tools_list
        )

        await send_split_message(message.channel, response_text)

if __name__ == "__main__":
    keep_alive()
    bot.run(DISCORD_BOT_TOKEN)
        
