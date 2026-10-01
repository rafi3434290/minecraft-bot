import os, json, asyncio, threading, requests, discord
from discord.ui import Button, View
from flask import Flask
from groq import Groq
import google.generativeai as genai

# Keep-Alive Web Server
app = Flask('')
@app.route('/')
def home(): return "Minecraft Gemini Assistant Active!"
def run(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def keep_alive(): threading.Thread(target=run).start()

# Environment Variables
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
GODLIKE_PANEL_URL = "https://panel.godlike.host"
GODLIKE_API_KEY = os.getenv("GODLIKE_API_KEY", "").strip()
SERVER_ID = os.getenv("SERVER_ID", "").strip()
MY_DISCORD_ID = int(os.getenv("MY_DISCORD_ID", "0"))
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

MEMORY_FILE = "memory.json"

def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except Exception: return {"rules": []}
    return {"rules": []}

def save_memory_fact(fact_or_rule: str) -> str:
    data = load_memory()
    if fact_or_rule not in data["rules"]:
        data["rules"].append(fact_or_rule)
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return f"Saved to memory: '{fact_or_rule}'"
    return "Rule already exists."

def get_saved_memory() -> str:
    rules = load_memory().get("rules", [])
    return "Saved Rules:\n" + "\n".join([f"- {r}" for r in rules]) if rules else "No rules saved."

def get_headers(ct="application/json"):
    return {"Authorization": f"Bearer {GODLIKE_API_KEY}", "Content-Type": ct, "Accept": "application/json"}

def get_server_resources() -> str:
    try:
        r = requests.get(f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/resources", headers=get_headers(), timeout=10)
        if r.status_code == 200:
            st = r.json()['attributes']
            res = st['resources']
            return f"📊 Status: `{st['current_state'].upper()}` | CPU: `{round(res['cpu_absolute'], 2)}%` | RAM: `{round(res['memory_bytes']/(1024*1024),2)}MB`"
        return f"Error HTTP {r.status_code}"
    except Exception as e: return f"API Error: {str(e)}"

def send_console_command(command: str) -> str:
    try:
        r = requests.post(f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/command", headers=get_headers(), json={"command": command}, timeout=10)
        return f"Executed command: `{command}`" if r.status_code == 204 else f"Failed: {r.status_code}"
    except Exception as e: return f"Error: {str(e)}"

def read_server_file(file_path: str) -> str:
    try:
        r = requests.get(f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/contents?file={file_path}", headers={"Authorization": f"Bearer {GODLIKE_API_KEY}"}, timeout=10)
        return r.text if r.status_code == 200 else f"Failed to read file: {r.status_code}"
    except Exception as e: return f"Error: {str(e)}"

def write_server_file(file_path: str, content: str) -> str:
    try:
        r = requests.post(f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/write?file={file_path}", headers=get_headers("text/plain"), data=content, timeout=10)
        return f"File `{file_path}` updated successfully." if r.status_code == 204 else f"Failed: {r.status_code}"
    except Exception as e: return f"Error: {str(e)}"

def list_server_files(directory: str = "") -> str:
    try:
        r = requests.get(f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/list?directory={directory}", headers=get_headers(), timeout=10)
        if r.status_code == 200:
            items = [i['attributes']['name'] for i in r.json().get('data', [])]
            return f"Files in '{directory or 'root'}': " + ", ".join(items)
        return f"Failed: {r.status_code}"
    except Exception as e: return f"Error: {str(e)}"

def read_latest_logs() -> str:
    log = read_server_file("logs/latest.log")
    if "Failed" in log or "Error" in log: return log
    return "Latest Logs:\n" + "\n".join(log.strip().split("\n")[-25:])

def execute_power_signal(signal: str) -> str:
    try:
        r = requests.post(f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/power", headers=get_headers(), json={"signal": signal}, timeout=10)
        return f"Power signal `{signal}` sent." if r.status_code == 204 else f"Failed: {r.status_code}"
    except Exception as e: return f"Error: {str(e)}"

def execute_file_deletion(file_path: str) -> str:
    try:
        r = requests.post(f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/delete", headers=get_headers(), json={"root": "/", "files": [file_path]}, timeout=10)
        return f"Deleted `{file_path}`." if r.status_code == 204 else f"Failed: {r.status_code}"
    except Exception as e: return f"Error: {str(e)}"

# Dynamic Gemini Caller
def call_gemini_smart(sys_prompt: str, user_prompt: str):
    if not GEMINI_API_KEY: return None
    try:
        active_model = None
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                if 'flash' in m.name or 'pro' in m.name:
                    active_model = m.name
                    break
        if not active_model: active_model = 'models/gemini-1.5-flash'
        
        model = genai.GenerativeModel(
            model_name=active_model,
            system_instruction=sys_prompt
        )
        res = model.generate_content(user_prompt)
        return res.text
    except Exception as e:
        return None

# Dynamic Groq Backup Caller
def call_groq_backup(sys_prompt: str, user_prompt: str):
    if not GROQ_API_KEY: return None
    try:
        client = Groq(api_key=GROQ_API_KEY)
        models = [m.id for m in client.models.list().data if "whisper" not in m.id]
        for m_id in models:
            try:
                res = client.chat.completions.create(
                    model=m_id,
                    messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_prompt}],
                    max_tokens=500
                )
                return res.choices[0].message.content
            except Exception: continue
    except Exception: pass
    return None

class ConfirmationView(View):
    def __init__(self, owner_id: int, action_type: str, action_data: str):
        super().__init__(timeout=60)
        self.owner_id, self.action_type, self.action_data = owner_id, action_type, action_data

    @discord.ui.button(label="✅ অনুমোদন দিন", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ কেবল অনার অনুমোদন করতে পারবেন!", ephemeral=True)
            return
        await interaction.response.edit_message(content="⏳ **কাজ সম্পন্ন হচ্ছে...**", view=None)
        res = execute_power_signal(self.action_data) if self.action_type == "power" else execute_file_deletion(self.action_data)
        await interaction.channel.send(f"📄 **ফলাফল:** {res}")

    @discord.ui.button(label="❌ বাতিল", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id == self.owner_id:
            await interaction.response.edit_message(content="🛑 **বাতিল করা হয়েছে।**", view=None)

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
    print(f"Logged in as {bot.user.name}! Powered by Gemini & Groq.")

@bot.event
async def on_message(message):
    if message.author == bot.user or (MY_DISCORD_ID != 0 and message.author.id != MY_DISCORD_ID):
        return

    msg = message.content.strip()
    if not msg: return

    async with message.channel.typing():
        sys_p = f"You are Minecraft Paper 1.21.11 Server Manager.\nSaved Rules:\n{get_saved_memory()}"
        
        # Check command keywords manually for fast tool execution
        msg_l = msg.lower()
        if "status" in msg_l or "resource" in msg_l:
            await send_split(message.channel, get_server_resources())
            return
        elif "log" in msg_l:
            await send_split(message.channel, read_latest_logs())
            return
        elif "restart" in msg_l or "stop" in msg_l:
            sig = "restart" if "restart" in msg_l else "stop"
            view = ConfirmationView(MY_DISCORD_ID, "power", sig)
            await message.channel.send(f"⚠️ **অনুমোদনের অনুরোধ:** সার্ভার `{sig.upper()}` করতে চাচ্ছেন?", view=view)
            return

        # AI Response Generation
        reply = call_gemini_smart(sys_p, msg)
        if not reply:
            reply = call_groq_backup(sys_p, msg)

        if reply:
            await send_split(message.channel, reply)
        else:
            await send_split(message.channel, "❌ AI পরিষেবা সাড়া দিচ্ছে না। অনুগ্রহ করে API Key বা কানেকশন চেক করুন।")

if __name__ == "__main__":
    keep_alive()
    bot.run(DISCORD_BOT_TOKEN)
                           
