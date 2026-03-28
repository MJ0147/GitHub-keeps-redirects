from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.edo_model import EdoLanguageModel
from app.trainer import train_model

app = FastAPI(title="Language Academy Service")
model = EdoLanguageModel(Path(__file__).resolve().parent / "data" / "edo_vocab.json")

EDO_GRAMMAR_REFERENCE = {
    "polar_questions": {
        "pitch_rule": "Declarative statements can become polar questions when sentence pitch is raised.",
        "yi_particle": "The particle 'yi' can appear sentence-finally as a question marker.",
        "example": {
            "declarative": "Osaro gha rre.",
            "question": "Osaro gha rre yi?",
            "translation": "Will Osaro come?",
        },
    },
    "alternative_questions": {
        "marker": "ra",
        "description": "The conjunction/question marker 'ra' links alternatives and yields a question reading.",
        "example": {
            "edo": "Osaro bo owa ra Osaro rhie?",
            "translation": "Did Osaro build a house or marry a woman?",
        },
    },
    "focus_notes": {
        "summary": "In focus constructions, yi may add emphasis in addition to question force.",
        "note": "Sentence-final yi can be question marker, emphatic marker, or temporal adverb by context.",
    },
}


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1)


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1)
    direction: str = Field(default="en_to_edo")


class QuizAnswerRequest(BaseModel):
    answer: str = Field(min_length=1)
    expected: str = Field(min_length=1)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "language_academy"}


@app.post("/analyze")
def analyze(payload: AnalyzeRequest) -> dict[str, int | str]:
    words = payload.text.split()
    word_count = len(words)
    
    if word_count < 5:
        level = "novice"
    elif word_count < 20:
        level = "beginner"
    else:
        level = "intermediate"

    return {
        "model": "baseline-v1",
        "word_count": word_count,
        "classification": level,
    }


@app.post("/train")
def train() -> dict[str, int | str]:
    return train_model()


@app.get("/vocabulary")
def vocabulary(category: str | None = None, limit: int = 10) -> dict[str, object]:
    return {"items": model.vocabulary(category=category, limit=limit)}


@app.post("/translate")
def translate(payload: TranslateRequest) -> dict[str, str]:
    direction = payload.direction.lower()
    if direction not in {"en_to_edo", "edo_to_en"}:
        raise HTTPException(status_code=400, detail="Direction must be 'en_to_edo' or 'edo_to_en'")
    translated = model.translate(payload.text, direction)
    return {"direction": direction, "translated_text": translated}


@app.get("/quiz/question")
def quiz_question() -> dict[str, str | list[str]]:
    return model.quiz_question()


@app.post("/quiz/answer")
def quiz_answer(payload: QuizAnswerRequest) -> dict[str, object]:
    is_correct = payload.answer.strip().lower() == payload.expected.strip().lower()
    return {"correct": is_correct, "expected": payload.expected}


@app.get("/grammar/reference")
def grammar_reference() -> dict[str, object]:
    return EDO_GRAMMAR_REFERENCE
