import os
import json
import asyncio
import threading
import requests
import discord
from discord.ui import Button, View
from flask import Flask
from groq import Groq
import google.generativeai as genai

# --- Keep-Alive Web Server for Render/Replit ---
app = Flask('')

@app.route('/')
def home():
    return "Ultra-Fast & Secure Minecraft Dual-AI Bot is active!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run, daemon=True)
    t.start()

# Environment Variables
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
GODLIKE_PANEL_URL = os.getenv("GODLIKE_PANEL_URL", "https://panel.godlike.host").strip()
GODLIKE_API_KEY = os.getenv("GODLIKE_API_KEY", "").strip()
SERVER_ID = os.getenv("SERVER_ID", "").strip()
MY_DISCORD_ID = int(os.getenv("MY_DISCORD_ID", "0"))
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# Configure Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

MEMORY_FILE = "memory.json"

# --- SECURITY HELPER FUNCTIONS ---
def is_safe_path(file_path: str) -> bool:
    """Prevents Path Traversal attacks (e.g. ../../etc/passwd)"""
    if not file_path:
        return False
    normalized = os.path.normpath(file_path)
    if normalized.startswith("..") or "/.." in normalized or "\\.." in normalized:
        return False
    return True

def is_sensitive_command(command: str) -> bool:
    """Checks if a Minecraft console command is dangerous or privileged."""
    cmd_lower = command.strip().lower()
    dangerous_keywords = ["op ", "deop ", "stop", "restart", "kill", "ban", "pardon", "reload", "whitelist off"]
    return any(cmd_lower.startswith(kw) or f" {kw}" in cmd_lower for kw in dangerous_keywords)

# --- MEMORY SYSTEM ---
def load_memory() -> dict:
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"rules": [], "notes": []}
    return {"rules": [], "notes": []}

def save_memory_fact(fact_or_rule: str) -> str:
    data = load_memory()
    if fact_or_rule not in data["rules"]:
        data["rules"].append(fact_or_rule)
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return f"Memory updated: Saved '{fact_or_rule}'"
    return "Rule is already saved."

def get_saved_memory() -> str:
    data = load_memory()
    rules = data.get("rules", [])
    if not rules:
        return "No specific long-term rules saved yet."
    return "Saved Server Rules & Notes:\n" + "\n".join([f"- {r}" for r in rules])

# --- GODLIKE PANEL API FUNCTIONS ---
def get_api_headers(content_type="application/json"):
    return {
        "Authorization": f"Bearer {GODLIKE_API_KEY}",
        "Content-Type": content_type,
        "Accept": "application/json"
    }

def get_server_resources() -> str:
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/resources"
    try:
        res = requests.get(url, headers=get_api_headers(), timeout=10)
        if res.status_code == 200:
            data = res.json()['attributes']
            stats = data['resources']
            state = data['current_state']
            ram_mb = round(stats['memory_bytes'] / (1024 * 1024), 2)
            cpu_pct = round(stats['cpu_absolute'], 2)
            disk_mb = round(stats['disk_bytes'] / (1024 * 1024), 2)
            return f"📊 **Server Status:** `{state.upper()}`\n💻 **CPU:** `{cpu_pct}%` | 🧠 **RAM:** `{ram_mb} MB` | 💾 **Disk:** `{disk_mb} MB`"
        return f"Failed to fetch resources. Status: {res.status_code}"
    except Exception as e:
        return f"API Error: {str(e)}"

def get_online_players() -> str:
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/command"
    try:
        res = requests.post(url, headers=get_api_headers(), json={"command": "list"}, timeout=10)
        if res.status_code == 204:
            return "Sent '/list' command to server console. Check latest logs for output."
        return f"Failed to send command. Status: {res.status_code}"
    except Exception as e:
        return f"API Error: {str(e)}"

def send_console_command(command: str) -> str:
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/command"
    try:
        res = requests.post(url, headers=get_api_headers(), json={"command": command}, timeout=10)
        if res.status_code == 204:
            return f"Command `{command}` executed successfully on console."
        return f"Failed to execute. Status: {res.status_code}"
    except Exception as e:
        return f"API Error: {str(e)}"

def read_server_file(file_path: str) -> str:
    if not is_safe_path(file_path):
        return "❌ Security Error: Invalid or unsafe file path."
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/contents?file={file_path}"
    headers = {"Authorization": f"Bearer {GODLIKE_API_KEY}", "Accept": "text/plain"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            return res.text
        return f"Failed to read file '{file_path}'. Status: {res.status_code}"
    except Exception as e:
        return f"Error reading file: {str(e)}"

def write_server_file(file_path: str, content: str) -> str:
    if not is_safe_path(file_path):
        return "❌ Security Error: Invalid or unsafe file path."
    if not content or len(content.strip()) == 0:
        return "Error: Cannot write empty content."

    # Auto Backup
    existing = read_server_file(file_path)
    if existing and not existing.startswith("Failed to read") and not existing.startswith("❌ Security Error"):
        backup_url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/write?file={file_path}.bak"
        requests.post(backup_url, headers=get_api_headers("text/plain"), data=existing, timeout=10)

    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/write?file={file_path}"
    try:
        res = requests.post(url, headers=get_api_headers("text/plain"), data=content, timeout=10)
        if res.status_code == 204:
            return f"File '{file_path}' written successfully (Auto-backup created: `{file_path}.bak`)."
        return f"Failed to write file. Status: {res.status_code}"
    except Exception as e:
        return f"Error writing file: {str(e)}"

def list_server_files(directory: str = "") -> str:
    if directory and not is_safe_path(directory):
        return "❌ Security Error: Invalid or unsafe directory path."
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/list?directory={directory}"
    try:
        res = requests.get(url, headers=get_api_headers(), timeout=10)
        if res.status_code == 200:
            items = [item['attributes']['name'] for item in res.json().get('data', [])]
            return f"Files in '{directory or 'root'}': " + ", ".join(items)
        return f"Failed to list files. Status: {res.status_code}"
    except Exception as e:
        return f"Error listing directory: {str(e)}"

def read_latest_logs() -> str:
    log_content = read_server_file("logs/latest.log")
    if log_content.startswith("Failed to read") or log_content.startswith("❌"):
        return log_content
    lines = log_content.strip().split("\n")
    return "Last 30 lines of logs:\n" + "\n".join(lines[-30:])

def execute_power_signal(signal: str) -> str:
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/power"
    try:
        res = requests.post(url, headers=get_api_headers(), json={"signal": signal}, timeout=10)
        if res.status_code == 204:
            return f"Power signal '{signal.upper()}' sent successfully."
        return f"Failed power signal. Status: {res.status_code}"
    except Exception as e:
        return f"Error executing power action: {str(e)}"

def execute_file_deletion(file_path: str) -> str:
    if not is_safe_path(file_path):
        return "❌ Security Error: Invalid or unsafe file path."
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/delete"
    payload = {"root": "/", "files": [file_path]}
    try:
        res = requests.post(url, headers=get_api_headers(), json=payload, timeout=10)
        if res.status_code == 204:
            return f"File '{file_path}' deleted successfully."
        return f"Failed deletion. Status: {res.status_code}"
    except Exception as e:
        return f"Error deleting file: {str(e)}"

# --- GROQ TOOLS SCHEMA ---
groq_tools = [
    {"type": "function", "function": {"name": "get_server_resources", "description": "Fetches real-time server status (CPU, RAM, Disk, State)."}},
    {"type": "function", "function": {"name": "get_online_players", "description": "Checks online players using console list command."}},
    {"type": "function", "function": {"name": "send_console_command", "description": "Executes a console command on the Minecraft server.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "read_server_file", "description": "Reads content of a specified server file safely.", "parameters": {"type": "object", "properties": {"file_path": {"type": "string"}}, "required": ["file_path"]}}},
    {"type": "function", "function": {"name": "write_server_file", "description": "Safely updates/writes content to a file with auto-backup.", "parameters": {"type": "object", "properties": {"file_path": {"type": "string"}, "content": {"type": "string"}}, "required": ["file_path", "content"]}}},
    {"type": "function", "function": {"name": "list_server_files", "description": "Lists files/folders in a specified server directory.", "parameters": {"type": "object", "properties": {"directory": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "read_latest_logs", "description": "Fetches the last 30 lines of logs/latest.log."}},
    {"type": "function", "function": {"name": "save_memory_fact", "description": "Saves long-term rules/facts given by the owner.", "parameters": {"type": "object", "properties": {"fact_or_rule": {"type": "string"}}, "required": ["fact_or_rule"]}}},
    {"type": "function", "function": {"name": "get_saved_memory", "description": "Returns saved long-term memories and rules."}},
    {"type": "function", "function": {"name": "execute_power_signal", "description": "Sends power signal (start, stop, restart, kill).", "parameters": {"type": "object", "properties": {"signal": {"type": "string"}}, "required": ["signal"]}}},
    {"type": "function", "function": {"name": "execute_file_deletion", "description": "Deletes a file or directory from server.", "parameters": {"type": "object", "properties": {"file_path": {"type": "string"}}, "required": ["file_path"]}}}
]

# --- DISCORD CONFIRMATION VIEW ---
class ConfirmationView(View):
    def __init__(self, owner_id: int, action_type: str, action_data: str):
        super().__init__(timeout=60)
        self.owner_id = owner_id
        self.action_type = action_type
        self.action_data = action_data

    @discord.ui.button(label="✅ অনুমোদন দিন (Approve)", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ কেবল অনার এই কাজের অনুমোদন দিতে পারবেন!", ephemeral=True)
            return

        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="⏳ **অনুমোদন দেওয়া হয়েছে। কাজ সম্পন্ন হচ্ছে...**", view=self)

        if self.action_type == "power":
            res = execute_power_signal(self.action_data)
            await send_split_message(interaction.channel, f"⚡ **সার্ভার অ্যাকশন রিপোর্ট:** {res}")
        elif self.action_type == "delete":
            res = execute_file_deletion(self.action_data)
            await send_split_message(interaction.channel, f"🗑 **ফাইল ডিলিট রিপোর্ট:** {res}")
        elif self.action_type == "command":
            res = send_console_command(self.action_data)
            await send_split_message(interaction.channel, f"⚙️ **Sensitive Console Command Executed:** `{self.action_data}`\n📄 **Result:** {res}")

    @discord.ui.button(label="❌ বাতিল করুন (Cancel)", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ কেবল অনার এই বাটন ব্যবহার করতে পারবেন!", ephemeral=True)
            return

        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="🛑 **কাজটি বাতিল করা হয়েছে।**", view=self)

# --- DISCORD BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

async def send_split_message(channel, text: str):
    """Safely splits and sends long text to Discord avoiding 2000 character limits."""
    if not text:
        return
    text = str(text)
    if len(text) <= 1900:
        await channel.send(text)
    else:
        for i in range(0, len(text), 1900):
            chunk = text[i:i+1900]
            await channel.send(chunk)

# --- AI FALLBACK ENGINE (GROQ -> GEMINI) ---
async def query_ai_with_fallback(sys_instruction: str, user_prompt: str):
    """Tries Groq (70B Smart Models) first. On rate-limit or error, falls back to Gemini 2.0/1.5 Flash."""
    
    # Preferred Groq Models (Smartest 70B Class)
    groq_preferred_models = ["llama-3.3-70b-versatile", "deepseek-r1-distill-llama-70b", "llama3-70b-8192"]
    
    messages = [
        {"role": "system", "content": sys_instruction},
        {"role": "user", "content": user_prompt}
    ]

    # 1. Attempt Groq
    if GROQ_API_KEY:
        try:
            client = Groq(api_key=GROQ_API_KEY)
            for model_id in groq_preferred_models:
                try:
                    def call_groq():
                        return client.chat.completions.create(
                            model=model_id,
                            messages=messages,
                            tools=groq_tools,
                            tool_choice="auto",
                            max_tokens=800
                        )
                    res = await asyncio.to_thread(call_groq)
                    return ("groq", res.choices[0].message)
                except Exception:
                    continue
        except Exception as e:
            print(f"Groq API Error, switching to Gemini: {e}")

    # 2. Fallback to Gemini API if Groq fails or rate-limits
    if GEMINI_API_KEY:
        try:
            def call_gemini():
                # Gemini 2.0 / 1.5 Flash
                gemini_model = genai.GenerativeModel(
                    model_name='gemini-2.0-flash',
                    system_instruction=sys_instruction
                )
                response = gemini_model.generate_content(user_prompt)
                return response.text

            text_res = await asyncio.to_thread(call_gemini)
            return ("gemini_text", text_res)
        except Exception as gem_err:
            print(f"Gemini API Error: {gem_err}")

    raise Exception("Both Groq and Gemini APIs failed or are unconfigured.")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}!")
    print("Dual AI (Groq + Gemini Backup) Minecraft Manager is ready.")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if MY_DISCORD_ID != 0 and message.author.id != MY_DISCORD_ID:
        return

    msg_text = message.content.strip()
    if not msg_text:
        return

    async with message.channel.typing():
        # Chat history context
        recent_history = []
        async for msg in message.channel.history(limit=3):
            recent_history.append(f"{msg.author.name}: {msg.content[:200]}")
        recent_history.reverse()
        chat_context = "\n".join(recent_history)

        saved_rules = get_saved_memory()

        sys_instruction = (
            "You are an expert Minecraft Paper 1.21 Server Administrator.\n"
            f"Long-Term Saved Memory:\n{saved_rules}\n\n"
            "Rules:\n"
            "1. Answer concisely and precisely in Benglish/Bangla.\n"
            "2. Always use tools to check or modify server configuration/status.\n"
            "3. Do not modify or delete files without reason."
        )

        user_prompt = f"Context:\n{chat_context}\n\nUser Request: {msg_text}"

        try:
            source, ai_response = await query_ai_with_fallback(sys_instruction, user_prompt)

            if source == "groq":
                msg_obj = ai_response
                if msg_obj.tool_calls:
                    for tool_call in msg_obj.tool_calls:
                        fn_name = tool_call.function.name
                        args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}

                        if fn_name == "execute_power_signal":
                            signal = args.get("signal", "restart")
                            view = ConfirmationView(MY_DISCORD_ID, "power", signal)
                            await message.channel.send(
                                f"⚠️ **অনুমোদনের অনুরোধ:** AI সার্ভারটি `{signal.upper()}` করতে চাচ্ছে। আপনি কি অনুমোদন দিচ্ছেন?",
                                view=view
                            )

                        elif fn_name == "execute_file_deletion":
                            path = args.get("file_path", "")
                            view = ConfirmationView(MY_DISCORD_ID, "delete", path)
                            await message.channel.send(
                                f"⚠️ **অনুমোদনের অনুরোধ:** AI `{path}` ফাইলটি মুছে ফেলতে চাচ্ছে। আপনি কি অনুমোদন দিচ্ছেন?",
                                view=view
                            )

                        elif fn_name == "send_console_command":
                            cmd = args.get("command", "")
                            if is_sensitive_command(cmd):
                                view = ConfirmationView(MY_DISCORD_ID, "command", cmd)
                                await message.channel.send(
                                    f"⚠️ **সংবেদনশীল কম্যান্ড সেন্ড করার চেষ্টা:** AI কনসোলে `{cmd}` চালাতে চাচ্ছে। অনুমোদন দিচ্ছেন?",
                                    view=view
                                )
                            else:
                                res = send_console_command(cmd)
                                await send_split_message(message.channel, f"⚙️ **Console Executed:** `{cmd}`\n📄 **Result:** {res}")

                        elif fn_name == "get_server_resources":
                            res = get_server_resources()
                            await send_split_message(message.channel, res)

                        elif fn_name == "get_online_players":
                            res = get_online_players()
                            await send_split_message(message.channel, f"👥 **প্লেয়ার লিস্ট স্ট্যাটাস:** {res}")

                        elif fn_name == "write_server_file":
                            path = args.get("file_path")
                            content = args.get("content")
                            res = write_server_file(path, content)
                            await send_split_message(message.channel, f"📝 **File Saved:** `{path}`\n📄 **Result:** {res}")

                        elif fn_name == "read_server_file":
                            path = args.get("file_path")
                            res = read_server_file(path)
                            await send_split_message(message.channel, f"📖 **File Content (`{path}`):**\n```yaml\n{res[:1800]}\n```")

                        elif fn_name == "list_server_files":
                            directory = args.get("directory", "")
                            res = list_server_files(directory)
                            await send_split_message(message.channel, f"📁 **Directory List:**\n{res}")

                        elif fn_name == "read_latest_logs":
                            res = read_latest_logs()
                            await send_split_message(message.channel, f"📋 **Server Logs:**\n```log\n{res[:1800]}\n```")

                        elif fn_name == "save_memory_fact":
                            fact = args.get("fact_or_rule")
                            res = save_memory_fact(fact)
                            await send_split_message(message.channel, f"🧠 **মেমোরি সেভ করা হয়েছে:** {res}")

                        elif fn_name == "get_saved_memory":
                            res = get_saved_memory()
                            await send_split_message(message.channel, f"📜 **সংরক্ষিত মেমোরি নিয়মাবলি:**\n{res}")

                elif msg_obj.content:
                    await send_split_message(message.channel, msg_obj.content)

            elif source == "gemini_text":
                await send_split_message(message.channel, f"🟢 **[Gemini Backup Mode]:**\n{ai_response}")

        except Exception as err:
            err_str = f"❌ **Error details:** `{str(err)[:1800]}`"
            await send_split_message(message.channel, err_str)

if __name__ == "__main__":
    keep_alive()
    if DISCORD_BOT_TOKEN:
        bot.run(DISCORD_BOT_TOKEN)
    else:
        print("Error: DISCORD_BOT_TOKEN is not set.")
