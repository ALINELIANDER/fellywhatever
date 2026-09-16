from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import textbook, learning_material, lesson_dictionary

app = FastAPI(title="Bhasha Setu - Textbook Library Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(textbook.router)
app.include_router(learning_material.router)
app.include_router(lesson_dictionary.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "textbook-library-backend"}