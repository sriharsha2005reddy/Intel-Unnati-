import tkinter as tk
import threading
import time
import base64
import platform
from pathlib import Path

import pytesseract
import requests
import speech_recognition as sr
import pyttsx3
from PIL import Image, ImageTk, ImageGrab

# ─── CONFIG ───────────────────────────────────────────────────────────
pytesseract.pytesseract.tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
OLLAMA_URL = "http://localhost:11434/api/generate"
SYSTEM_PROMPT = "You are an AI classroom assistant. Explain everything clearly and simply."

if platform.system() == "Windows":
    import winsound
    def ding(): winsound.MessageBeep(winsound.MB_ICONASTERISK)
else:
    def ding(): print("[ding]")

# ─── UTILITIES ───────────────────────────────────────────────────────

def speak(text: str):
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()

def ocr_image(path: Path) -> str:
    try:
        img = Image.open(path).convert("L")
        return pytesseract.image_to_string(img).strip()
    except Exception as e:
        return f"[OCR Error] {e}"

def recognize_speech(max_seconds: int = 10) -> str:
    recognizer = sr.Recognizer()
    with sr.Microphone() as mic:
        recognizer.adjust_for_ambient_noise(mic)
        try:
            audio = recognizer.listen(mic, timeout=2, phrase_time_limit=max_seconds)
            return recognizer.recognize_google(audio)
        except sr.WaitTimeoutError:
            return "[Speech] No speech detected."
        except Exception as e:
            return f"[Speech Error] {e}"

# ─── LLaVA CALL ──────────────────────────────────────────────────────

def call_llava(prompt: str, img: Path | None = None) -> str:
    try:
        payload = {
            "model": "llava",
            "prompt": prompt,
            "system": SYSTEM_PROMPT,
            "stream": False,
        }
        if img and img.exists():
            with open(img, "rb") as f:
                payload["images"] = [base64.b64encode(f.read()).decode()]
        resp = requests.post(OLLAMA_URL, json=payload, timeout=180)
        resp.raise_for_status()
        return resp.json().get("response", "[LLM] Empty reply.").strip()
    except requests.exceptions.ConnectionError:
        return "[LLM Error] Cannot reach Ollama – did you run `ollama run llava`?"
    except Exception as e:
        return f"[LLM Error] {e}"

# ─── SNIP TOOL ───────────────────────────────────────────────────────

def drag_snip(root: tk.Tk) -> Path | None:
    class SnipWin(tk.Toplevel):
        def __init__(self):
            super().__init__(root)
            self.attributes("-alpha", 0.3)
            self.configure(bg="gray")
            self.attributes("-topmost", True)
            self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
            self.canvas = tk.Canvas(self, cursor="cross", bg="gray", highlightthickness=0)
            self.canvas.pack(fill=tk.BOTH, expand=True)
            self.start_x = self.start_y = 0
            self.rect = None
            self.path: Path | None = None
            self.canvas.bind("<ButtonPress-1>", self.on_start)
            self.canvas.bind("<B1-Motion>", self.on_drag)
            self.canvas.bind("<ButtonRelease-1>", self.on_release)

        def on_start(self, event):
            self.start_x, self.start_y = event.x, event.y
            self.rect = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="#FF3333", width=2)

        def on_drag(self, event):
            self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

        def on_release(self, event):
            x1, y1 = min(self.start_x, event.x), min(self.start_y, event.y)
            x2, y2 = max(self.start_x, event.x), max(self.start_y, event.y)
            self.destroy()
            if x2 - x1 < 5 or y2 - y1 < 5:
                return
            time.sleep(0.05)
            img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
            p = Path(f"snip_{int(time.time())}.png")
            img.save(p)
            self.path = p
            ding()
            prev = tk.Toplevel(root)
            prev.title("🖼️ Snip Preview")
            img_resized = img.resize((min(500, img.width), int(img.height * min(500 / img.width, 1))))
            tk_img = ImageTk.PhotoImage(img_resized)
            label = tk.Label(prev, image=tk_img, bg="white")
            label.image = tk_img
            label.pack()
            prev.after(1500, prev.destroy)

    snip = SnipWin()
    snip.wait_window()
    return snip.path

# ─── GUI CLASS ───────────────────────────────────────────────────────

class ClassroomGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("✨ AI Classroom Assistant")
        root.geometry("960x800")
        root.configure(bg="#f4f4f8")

        tk.Label(root, text="📥 Enter Question or Prompt", font=("Helvetica", 11, "bold"), bg="#f4f4f8").pack(anchor="w", padx=12)
        self.inbox = tk.Text(root, height=8, font=("Consolas", 11), bg="white", fg="#222")
        self.inbox.pack(fill=tk.X, padx=12, pady=(0, 12))

        tk.Label(root, text="📤 Assistant Response", font=("Helvetica", 11, "bold"), bg="#f4f4f8").pack(anchor="w", padx=12)
        self.outbox = tk.Text(root, height=14, font=("Consolas", 11), bg="#fefefe", fg="#333")
        self.outbox.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        bar = tk.Frame(root, bg="#f4f4f8")
        bar.pack(pady=12)
        btn_style = {"font": ("Segoe UI", 10), "bg": "#0052cc", "fg": "white", "activebackground": "#0041a8"}

        tk.Button(bar, text="📸 Snip Image", width=15, command=self.handle_snip, **btn_style).pack(side=tk.LEFT, padx=6)
        tk.Button(bar, text="🎙 Speak", width=15, command=self.handle_speak, **btn_style).pack(side=tk.LEFT, padx=6)
        tk.Button(bar, text="🧠 Ask AI", width=15, command=self.ask_ai, **btn_style).pack(side=tk.LEFT, padx=6)
        tk.Button(bar, text="🔊 Read Out", width=15, command=lambda: speak(self.outbox.get("1.0", tk.END)), **btn_style).pack(side=tk.LEFT, padx=6)
        tk.Button(bar, text="🗑 Clear", width=10, command=self.clear, bg="#999", fg="white", activebackground="#777").pack(side=tk.LEFT, padx=6)

    def handle_snip(self):
        img = drag_snip(self.root)
        if not img:
            return
        text = " ".join(ocr_image(img).split())
        keep = (sum(c.isalnum() for c in text) / max(len(text), 1) > 0.5) and len(text) > 15
        if keep:
            prompt = (
                "Below is OCR text from a slide, followed by the diagram.\n\n"
                "--- Extracted Text ---\n"
                f"{text}\n"
                "--- End Text ---\n\n"
                "1. Describe the diagram.\n2. Relate it to the text.\n3. Explain both in simple terms."
            )
        else:
            prompt = (
                "I snipped a technical diagram. Describe it in detail, identify the key parts, and explain the concept for a student."
            )
        self.inbox.delete("1.0", tk.END)
        self.inbox.insert(tk.END, prompt)
        self.query_llm(img=img)

    def handle_speak(self):
        self.outbox.delete("1.0", tk.END)
        self.outbox.insert("1.0", "🎤 Listening …")
        self.root.update_idletasks()
        threading.Thread(target=self._speech_thread, daemon=True).start()

    def _speech_thread(self):
        spoken = recognize_speech()
        self.inbox.delete("1.0", tk.END)
        self.inbox.insert(tk.END, spoken)
        self.query_llm()

    def ask_ai(self):
        self.query_llm()

    def query_llm(self, img: Path | None = None):
        prompt = self.inbox.get("1.0", tk.END).strip()
        if not prompt:
            return
        self.outbox.delete("1.0", tk.END)
        self.outbox.insert("1.0", "⏳ querying …")
        self.root.update_idletasks()
        threading.Thread(target=self._llm_thread, args=(prompt, img), daemon=True).start()

    def _llm_thread(self, prompt: str, img: Path | None):
        response = call_llava(prompt, img)
        self.outbox.delete("1.0", tk.END)
        self.outbox.insert(tk.END, response)

    def clear(self):
        self.inbox.delete("1.0", tk.END)
        self.outbox.delete("1.0", tk.END)

# ─── MAIN ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    ClassroomGUI(root)
    root.mainloop()
