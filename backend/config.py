"""Single source of configuration. All env vars are read here; nowhere else."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Dataset
    hugging_face_dataset: str = "rag-datasets/rag-mini-bioasq"

    # Embedding
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # Elasticsearch
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index: str = "medical-rag-chunks"

    # LLM
    ollama_url: str = "http://localhost:11434"
    llm_model: str = "llama3.2:3b"

    # Evaluation
    ragas_judge_model: str = "qwen2.5:3b"
    eval_question_answer_split: str = "question-answer-passages"
    eval_test_split: str = "test"
    eval_random_seed: int = 42
    supabase_db_url: str = "postgresql://postgres:postgres@localhost:5432/medical_rag"
    # Not currently used -- kept available in case a Gemini judge is reintroduced later.
    gemini_api_key: str | None = None
    open_router_api_key: str | None = None
    open_router_url: str = "https://openrouter.ai/api/v1"
    open_router_generation_model: str = "nvidia/nemotron-3-ultra-550b-a55b:free"
    open_router_judge_model: str = "typesafe/jev-1.13"
    open_router_decisions_url: str = "https://openrouter.ai/api/alpha/decisions"

    # CORS
    frontend_origin: str = "http://localhost:3000"


settings = Settings()
