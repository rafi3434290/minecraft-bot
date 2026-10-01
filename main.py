import os, json, asyncio, threading, requests, discord
from flask import Flask
from dotenv import load_dotenv
from groq import Groq
import google.generativeai as genai

load_dotenv()

# Web Server for Render Keep-Alive
app = Flask('')
@app.route('/')
def home(): return "Minecraft Bot Active"

def keep_alive():
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.getenv("PORT", 8080))), daemon=True).start()

# Config & Environment Variables
TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
URL = os.getenv("GODLIKE_PANEL_URL", "https://panel.godlike.host").strip()
KEY = os.getenv("GODLIKE_API_KEY", "").strip()
SID = os.getenv("SERVER_ID", "").strip()
OWNER_ID = int(os.getenv("MY_DISCORD_ID", "0"))
GROQ_KEY = os.getenv("GROQ_API_KEY", "").strip()
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# Utility Functions
def safe_path(p): return p and not (".." in p or "\\.." in p)

def panel_req(method, ep, data=None, text_mode=False):
    headers = {"Authorization": f"Bearer {KEY}", "Accept": "text/plain" if text_mode else "application/json"}
    if not text_mode and data: headers["Content-Type"] = "application/json"
    try:
        r = requests.request(method, f"{URL}/api/client/servers/{SID}{ep}", headers=headers, json=data if not text_mode else None, data=data if text_mode else None, timeout=10)
        return r.text if text_mode else (r.json() if r.status_code in [200, 204] else f"Status: {r.status_code}")
    except Exception as e: return f"Error: {e}"

def load_mem():
    try: return json.load(open("memory.json"))
    except: return {"rules": []}

def save_mem(fact):
    m = load_mem()
    if fact not in m["rules"]: m["rules"].append(fact); json.dump(m, open("memory.json","w"), indent=2)
    return "Rule saved in memory."

# Groq AI Tools Definition
tools = [
    {"type": "function", "function": {"name": "get_res", "description": "Get CPU/RAM stats"}},
    {"type": "function", "function": {"name": "send_cmd", "description": "Send console command", "parameters": {"type":"object","properties":{"cmd":{"type":"string"}},"required":["cmd"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read server file", "parameters": {"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Write server file", "parameters": {"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}}},
    {"type": "function", "function": {"name": "power_sys", "description": "Power action (start, stop, restart)", "parameters": {"type":"object","properties":{"signal":{"type":"string"}},"required":["signal"]}}},
    {"type": "function", "function": {"name": "save_fact", "description": "Save long term memory", "parameters": {"type":"object","properties":{"fact":{"type":"string"}},"required":["fact"]}}}
]

# Discord Client
bot = discord.Client(intents=discord.Intents.default())
bot.intents.message_content = True

async def send_msg(ch, text):
    text = str(text)
    for i in range(0, len(text), 1900): await ch.send(text[i:i+1900])

async def query_ai(sys_inst, prompt):
    errs = []
    if GROQ_KEY:
        try:
            c = Groq(api_key=GROQ_KEY)
            res = await asyncio.to_thread(c.chat.completions.create, model="llama-3.3-70b-versatile", messages=[{"role":"system","content":sys_inst},{"role":"user","content":prompt}], tools=tools, max_tokens=1000)
            return ("groq", res.choices[0].message)
        except Exception as e: errs.append(f"Groq: {e}")
    if GEMINI_KEY:
        try:
            genai.configure(api_key=GEMINI_KEY)
            m = genai.GenerativeModel('gemini-1.5-flash', system_instruction=sys_inst)
            res = await asyncio.to_thread(m.generate_content, prompt)
            return ("gemini", res.text)
        except Exception as e: errs.append(f"Gemini: {e}")
    raise Exception("\n".join(errs))

@bot.event
async def on_message(msg):
    if msg.author == bot.user or (OWNER_ID and msg.author.id != OWNER_ID) or not msg.content.strip(): return
    async with msg.channel.typing():
        sys_i = f"You are Minecraft Admin. Saved Memory: {load_mem().get('rules',[])}"
        try:
            src, ai_res = await query_ai(sys_i, msg.content)
            if src == "groq":
                if ai_res.tool_calls:
                    for t in ai_res.tool_calls:
                        fn, args = t.function.name, json.loads(t.function.arguments or "{}")
                        if fn == "get_res":
                            r = panel_req("GET", "/resources")
                            await send_msg(msg.channel, f"Stats: {r}")
                        elif fn == "send_cmd":
                            cmd = args.get("cmd","")
                            r = panel_req("POST", "/command", {"command": cmd})
                            await send_msg(msg.channel, f"Cmd `{cmd}` sent: {r}")
                        elif fn == "read_file" and safe_path(args.get("path","")):
                            r = panel_req("GET", f"/files/contents?file={args.get('path')}", text_mode=True)
                            await send_msg(msg.channel, f"File Content:\n```yaml\n{str(r)[:1800]}\n```")
                        elif fn == "write_file" and safe_path(args.get("path","")):
                            r = panel_req("POST", f"/files/write?file={args.get('path')}", args.get("content",""), text_mode=True)
                            await send_msg(msg.channel, f"Write Status: {r}")
                        elif fn == "power_sys":
                            r = panel_req("POST", "/power", {"signal": args.get("signal","")})
                            await send_msg(msg.channel, f"Power Signal: {r}")
                        elif fn == "save_fact":
                            r = save_mem(args.get("fact",""))
                            await send_msg(msg.channel, r)
                elif ai_res.content: await send_msg(msg.channel, ai_res.content)
            else: await send_msg(msg.channel, f"🟢 [Gemini]: {ai_res}")
        except Exception as e: await send_msg(msg.channel, f"❌ Error Details:\n```{e}```")

if __name__ == "__main__":
    keep_alive()
    if TOKEN: bot.run(TOKEN)
                            
