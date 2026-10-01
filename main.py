import os, json, asyncio, threading, requests, discord
from discord.ui import Button, View
from flask import Flask
import google.generativeai as genai

# Keep-Alive Server for Render
app = Flask('')
@app.route('/')
def home(): return "Minecraft Gemini Assistant is Active!"
def run(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def keep_alive(): threading.Thread(target=run).start()

# Environment Variables
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
GODLIKE_PANEL_URL = "https://panel.godlike.host"
GODLIKE_API_KEY = os.getenv("GODLIKE_API_KEY", "").strip()
SERVER_ID = os.getenv("SERVER_ID", "").strip()
MY_DISCORD_ID = int(os.getenv("MY_DISCORD_ID", "0"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
MEMORY_FILE = "memory.json"

# Long-term Memory
def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except Exception: return {"rules": []}
    return {"rules": []}

def save_memory_fact(fact_or_rule: str) -> str:
    """Saves a server rule or instruction into long-term memory."""
    data = load_memory()
    if fact_or_rule not in data["rules"]:
        data["rules"].append(fact_or_rule)
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return f"Memory saved: '{fact_or_rule}'"
    return "Rule already exists in memory."

def get_saved_memory() -> str:
    """Retrieves all saved rules from long-term memory."""
    rules = load_memory().get("rules", [])
    return "Saved Server Rules:\n" + "\n".join([f"- {r}" for r in rules]) if rules else "No memory saved yet."

# Server Panel API Tools
def get_headers(ct="application/json"):
    return {"Authorization": f"Bearer {GODLIKE_API_KEY}", "Content-Type": ct, "Accept": "application/json"}

def get_server_resources() -> str:
    """Fetches real-time server status, CPU, RAM, and Disk usage."""
    try:
        r = requests.get(f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/resources", headers=get_headers(), timeout=10)
        if r.status_code == 200:
            st = r.json()['attributes']
            res = st['resources']
            return f"State: {st['current_state'].upper()} | CPU: {round(res['cpu_absolute'], 2)}% | RAM: {round(res['memory_bytes']/(1024*1024),2)}MB | Disk: {round(res['disk_bytes']/(1024*1024),2)}MB"
        return f"Error HTTP {r.status_code}"
    except Exception as e: return f"API Error: {str(e)}"

def send_console_command(command: str) -> str:
    """Executes a command on the Minecraft server console."""
    try:
        r = requests.post(f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/command", headers=get_headers(), json={"command": command}, timeout=10)
        return f"CommandExecuted: '{command}'" if r.status_code == 204 else f"Failed: {r.status_code}"
    except Exception as e: return f"Error: {str(e)}"

def read_server_file(file_path: str) -> str:
    """Reads text content of a server file."""
    try:
        r = requests.get(f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/contents?file={file_path}", headers={"Authorization": f"Bearer {GODLIKE_API_KEY}"}, timeout=10)
        return r.text[:1800] if r.status_code == 200 else f"Failed to read: {r.status_code}"
    except Exception as e: return f"Error: {str(e)}"

def write_server_file(file_path: str, content: str) -> str:
    """Writes or updates content of a server file."""
    try:
        r = requests.post(f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/write?file={file_path}", headers=get_headers("text/plain"), data=content, timeout=10)
        return f"File '{file_path}' updated successfully." if r.status_code == 204 else f"Failed: {r.status_code}"
    except Exception as e: return f"Error: {str(e)}"

def list_server_files(directory: str = "") -> str:
    """Lists files and folders in a specified directory."""
    try:
        r = requests.get(f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/list?directory={directory}", headers=get_headers(), timeout=10)
        if r.status_code == 200:
            items = [i['attributes']['name'] for i in r.json().get('data', [])]
            return f"Files in '{directory or 'root'}': " + ", ".join(items)
        return f"Failed: {r.status_code}"
    except Exception as e: return f"Error: {str(e)}"

def read_latest_logs() -> str:
    """Reads the last 25 lines of server log."""
    log = read_server_file("logs/latest.log")
    if "Failed" in log or "Error" in log: return log
    return "Latest Logs:\n" + "\n".join(log.strip().split("\n")[-25:])

def execute_power_signal(signal: str) -> str:
    try:
        r = requests.post(f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/power", headers=get_headers(), json={"signal": signal}, timeout=10)
        return f"Power signal '{signal.upper()}' sent." if r.status_code == 204 else f"Failed: {r.status_code}"
    except Exception as e: return f"Error: {str(e)}"

def execute_file_deletion(file_path: str) -> str:
    try:
        r = requests.post(f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/delete", headers=get_headers(), json={"root": "/", "files": [file_path]}, timeout=10)
        return f"Deleted '{file_path}'." if r.status_code == 204 else f"Failed: {r.status_code}"
    except Exception as e: return f"Error: {str(e)}"

# Gemini Model Setup with Native Tools
tools_list = [
    get_server_resources, send_console_command, read_server_file,
    write_server_file, list_server_files, read_latest_logs,
    save_memory_fact, get_saved_memory
]

gemini_model = genai.GenerativeModel(
    model_name='gemini-1.5-flash',
    tools=tools_list,
    system_instruction=(
        "You are an expert Minecraft Paper 1.21.11 Server Administrator bot on Discord.\n"
        "You have tools to check status, run console commands, read/write files, read logs, and save memory.\n"
        "Always use available tools to answer server queries accurately.\n"
        "Be smart, helpful, and concise."
    )
)

# Discord Confirmation View
class ConfirmationView(View):
    def __init__(self, owner_id: int, action_type: str, action_data: str):
        super().__init__(timeout=60)
        self.owner_id, self.action_type, self.action_data = owner_id, action_type, action_data

    @discord.ui.button(label="✅ Anumodan Din", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Keval Owner anumodan dite parben!", ephemeral=True)
            return
        await interaction.response.edit_message(content="⏳ **Kaj somponno hochhe...**", view=None)
        res = execute_power_signal(self.action_data) if self.action_type == "power" else execute_file_deletion(self.action_data)
        await interaction.channel.send(f"📄 **Report:** {res}")

    @discord.ui.button(label="❌ Batil", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id == self.owner_id:
            await interaction.response.edit_message(content="🛑 **Batil kora hoyeche.**", view=None)

# Discord Bot Setup
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True
bot = discord.Client(intents=intents)

async def send_split(channel, text: str):
    if not text: return
    text = str(text)
    for i in range(0, len(text), 1900):
        await channel.send(text[i:i+1900])

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}! Model: gemini-1.5-flash with Native Tools.")

@bot.event
async def on_message(message):
    if message.author == bot.user or (MY_DISCORD_ID != 0 and message.author.id != MY_DISCORD_ID):
        return

    msg = message.content.strip()
    if not msg: return

    async with message.channel.typing():
        msg_l = msg.lower()

        # Confirmation Safety Intercept for Power Signal / Delete
        if "restart" in msg_l or "stop" in msg_l:
            sig = "restart" if "restart" in msg_l else "stop"
            view = ConfirmationView(MY_DISCORD_ID, "power", sig)
            await message.channel.send(f"⚠️ **Anumodan Anurodh:** Server `{sig.upper()}` korte chachhen?", view=view)
            return
        elif "delete file" in msg_l or "remove file" in msg_l:
            file_p = msg.split()[-1] if len(msg.split()) > 1 else ""
            view = ConfirmationView(MY_DISCORD_ID, "delete", file_p)
            await message.channel.send(f"⚠️ **Anumodan Anurodh:** `{file_p}` delete korte chachhen?", view=view)
            return

        # Start Chat with Automatic Function Calling
        try:
            chat = gemini_model.start_chat(enable_automatic_function_calling=True)
            mem = get_saved_memory()
            full_prompt = f"[Long-Term Memory Context:\n{mem}]\nUser Message: {msg}"
            
            res = await asyncio.to_thread(chat.send_message, full_prompt)
            if res.text:
                await send_split(message.channel, res.text)
            else:
                await send_split(message.channel, "Kono response paowa jayni.")
        except Exception as e:
            await send_split(message.channel, f"❌ Gemini Error: `{str(e)}`")

if __name__ == "__main__":
    keep_alive()
    bot.run(DISCORD_BOT_TOKEN)
        
