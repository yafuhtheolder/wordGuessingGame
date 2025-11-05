from typing import Optional, Dict, Set
from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
import uuid
import random
import requests

app = FastAPI()

games: Dict[str, Dict] = {}


class StartRequest(BaseModel):
    turns: Optional[int] = 12
    session_id: Optional[str] = None


class GuessRequest(BaseModel):
    session_id: str
    guess_char: str


def fetch_random_word() -> str:
    try:
        r = requests.get("https://random-word-api.herokuapp.com/word", timeout=3)
        r.raise_for_status()
        word = r.json()[0]
        return str(word).lower()
    except Exception:
        WORDS = [
            "python",
            "fastapi",
            "hangman",
            "testing",
            "server",
            "frontend",
            "backend",
            "session",
            "response",
            "deployment",
        ]
        return random.choice(WORDS)


def mask_word(word: str, guesses: Set[str]) -> str:
    return " ".join([c if c in guesses else "_" for c in word])


@app.get("/")
async def root():
    return RedirectResponse("/game")


@app.get("/game")
async def game_page():
    return FileResponse("static/index.html")


@app.post("/start")
async def start_game(req: StartRequest):
    session_id = req.session_id or str(uuid.uuid4())
    word = fetch_random_word()
    turns = req.turns if req.turns and req.turns > 0 else 6

    games[session_id] = {"word": word, "guesses": set(), "turns": turns, "done": False}

    return {
        "session_id": session_id,
        "message": {"text": "Game started.", "level": "success"},
        "masked": mask_word(word, set()),
        "turns": turns,
        "guessed": [],
    }


@app.post("/guess")
async def make_guess(req: GuessRequest):
    s = games.get(req.session_id)
    if not s:
        return {
            "message": {
                "text": "Session not found. Start a new game.",
                "level": "error",
            }
        }

    if s["done"]:
        return {
            "message": {
                "text": "Game already finished. Start a new game.",
                "level": "info",
            }
        }

    char = req.guess_char.lower().strip()
    if len(char) != 1 or not char.isalpha():
        return {
            "message": {"text": "Enter a single letter (a-z).", "level": "error"},
            "masked": mask_word(s["word"], s["guesses"]),
            "turns": s["turns"],
            "guessed": sorted(list(s["guesses"])),
        }

    if char in s["guesses"]:
        return {
            "message": {"text": f"'{char}' already guessed.", "level": "info"},
            "masked": mask_word(s["word"], s["guesses"]),
            "turns": s["turns"],
            "guessed": sorted(list(s["guesses"])),
        }

    s["guesses"].add(char)

    if char not in s["word"]:
        s["turns"] -= 1
        if s["turns"] <= 0:
            s["done"] = True
            masked = mask_word(s["word"], s["guesses"])
            # remove completed/failed session (optional)
            del games[req.session_id]
            return {
                "message": {
                    "text": f"You lose. The word was '{s['word']}'.",
                    "level": "error",
                },
                "done": True,
                "masked": masked,
                "turns": 0,
                "guessed": sorted(list(s["guesses"])),
            }

        return {
            "message": {"text": "Wrong guess.", "level": "info"},
            "done": False,
            "masked": mask_word(s["word"], s["guesses"]),
            "turns": s["turns"],
            "guessed": sorted(list(s["guesses"])),
        }

    # correct guess
    masked = mask_word(s["word"], s["guesses"])
    if "_" not in masked:
        s["done"] = True
        del games[req.session_id]
        return {
            "message": {"text": "Congratulations! You win!", "level": "success"},
            "done": True,
            "masked": masked,
            "turns": s["turns"],
            "guessed": sorted(list(s["guesses"])),
        }

    return {
        "message": {"text": "Good guess!", "level": "success"},
        "done": False,
        "masked": masked,
        "turns": s["turns"],
        "guessed": sorted(list(s["guesses"])),
    }


@app.post("/reset")
async def reset(req: dict):
    sid = req.get("session_id")
    if sid and sid in games:
        del games[sid]
    return {"message": {"text": "Game reset.", "level": "warning"}}
