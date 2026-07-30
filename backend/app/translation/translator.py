import json
import logging
import re
import traceback
from collections.abc import Sequence

from backend.app.translation.config import (
    SUPPORTED_LANGUAGES,
    TRANSLATION_BATCH_MAX_CHARS,
    TRANSLATION_BATCH_SIZE,
)
from backend.app.translation.ollama_client import get_ollama_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("translator")


def _build_localization_context(
    *,
    style_guide: str | None = None,
    glossary_terms: Sequence[dict[str, str]] | None = None,
) -> str:
    context_blocks: list[str] = []

    if style_guide:
        context_blocks.append(f"STYLE GUIDE:\n{style_guide.strip()}")

    normalized_glossary_terms = []
    for term in glossary_terms or []:
        source_term = str(term.get("source_term", "")).strip()
        target_term = str(term.get("target_term", "")).strip()
        if not source_term or not target_term:
            continue

        glossary_line = f"- {source_term} => {target_term}"
        notes = str(term.get("notes", "")).strip()
        if notes:
            glossary_line += f" ({notes})"
        normalized_glossary_terms.append(glossary_line)

    if normalized_glossary_terms:
        context_blocks.append(
            "MANDATORY GLOSSARY:\n"
            + "\n".join(normalized_glossary_terms)
        )

    if not context_blocks:
        return ""

    return "\n\n" + "\n\n".join(context_blocks)


def _normalize_translation_languages(
    source_language: str, target_language: str
) -> tuple[str, str, str, str]:
    if source_language not in SUPPORTED_LANGUAGES:
        logger.warning(
            "Source language %s not supported, defaulting to 'en'",
            source_language,
        )
        source_language = "en"

    if target_language not in SUPPORTED_LANGUAGES:
        logger.warning(
            "Target language %s not supported, defaulting to 'en'",
            target_language,
        )
        target_language = "en"

    return (
        source_language,
        target_language,
        SUPPORTED_LANGUAGES[source_language],
        SUPPORTED_LANGUAGES[target_language],
    )


def _build_translation_prompt(
    text: str,
    *,
    source_language_name: str,
    target_language_name: str,
    style_guide: str | None = None,
    glossary_terms: Sequence[dict[str, str]] | None = None,
) -> str:
    localization_context = _build_localization_context(style_guide=style_guide, glossary_terms=glossary_terms)
    return f"""You are a professional translator. \
Translate the following transcript from {source_language_name} to {target_language_name}.

IMPORTANT RULES:
1. Prioritize accuracy and natural readability in the target language over literal translation.
2. Preserve speaker identifications.
3. Keep timestamps exactly as they are.
4. Do not add or remove information.
5. Preserve specialized terminology and technical labels when appropriate.
6. Return only the translated transcript text.
7. Follow the provided style guide and glossary exactly when they are present.{localization_context}

TRANSCRIPT
{text}
"""


def translate_text(
    text: str,
    source_language: str,
    target_language: str,
    *,
    style_guide: str | None = None,
    glossary_terms: Sequence[dict[str, str]] | None = None,
) -> str:
    if source_language == target_language:
        logger.info(
            "Source and target languages match (%s), returning original text",
            source_language,
        )
        return text

    (
        source_language,
        target_language,
        source_language_name,
        target_language_name,
    ) = _normalize_translation_languages(source_language, target_language)

    try:
        client = get_ollama_client()
        return client.generate(
            _build_translation_prompt(
                text,
                source_language_name=source_language_name,
                target_language_name=target_language_name,
                style_guide=style_guide,
                glossary_terms=glossary_terms,
            ),
            temperature=0.1,
            max_tokens=2048,
        )
    except Exception as error:
        logger.error("Error translating text: %s", error)
        logger.error("Exception traceback: %s", traceback.format_exc())
        return text


def _chunk_text_batches(texts: Sequence[str]) -> list[list[str]]:
    batches: list[list[str]] = []
    current_batch: list[str] = []
    current_chars = 0

    for text in texts:
        text_length = len(text)
        if current_batch and (
            len(current_batch) >= TRANSLATION_BATCH_SIZE
            or current_chars + text_length > TRANSLATION_BATCH_MAX_CHARS
        ):
            batches.append(current_batch)
            current_batch = []
            current_chars = 0

        current_batch.append(text)
        current_chars += text_length

    if current_batch:
        batches.append(current_batch)

    return batches


def _extract_json_array(response: str) -> list[str]:
    response_text = response.strip()
    fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", response_text, re.DOTALL)
    if fenced_match:
        response_text = fenced_match.group(1).strip()

    start_index = response_text.find("[")
    end_index = response_text.rfind("]")
    if start_index == -1 or end_index == -1 or end_index < start_index:
        raise ValueError("LLM response did not contain a JSON array")

    candidate = response_text[start_index : end_index + 1]
    parsed = json.loads(candidate)
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ValueError("LLM response did not contain a string array")

    return parsed


def translate_texts(
    texts: Sequence[str],
    source_language: str,
    target_language: str,
    *,
    style_guide: str | None = None,
    glossary_terms: Sequence[dict[str, str]] | None = None,
) -> list[str]:
    if not texts:
        return []

    if source_language == target_language:
        return list(texts)

    (
        source_language,
        target_language,
        source_language_name,
        target_language_name,
    ) = _normalize_translation_languages(source_language, target_language)

    logger.info(
        "Batch translating %s texts from %s to %s",
        len(texts),
        source_language_name,
        target_language_name,
    )

    try:
        client = get_ollama_client()
    except Exception as error:
        logger.warning("Failed to initialize translation client: %s", error)
        return list(texts)

    translated_texts: list[str] = []
    batches = _chunk_text_batches(texts)

    for batch_index, batch in enumerate(batches, start=1):
        logger.info(
            "Translating batch %s/%s with %s text items (%s chars)",
            batch_index,
            len(batches),
            len(batch),
            sum(len(item) for item in batch),
        )

        localization_context = _build_localization_context(style_guide=style_guide, glossary_terms=glossary_terms)
        prompt = f"""You are a professional translator. \
Translate each string in the JSON array from {source_language_name} to {target_language_name}.

IMPORTANT RULES:
1. Return valid JSON only.
2. Return a JSON array of strings with the exact same number of items and the same order as the input.
3. Translate only the text content of each array entry.
4. Do not add commentary, markdown, code fences, or metadata.
5. Preserve speaker labels, timestamps, and special terminology when present in the text.
6. Follow the provided style guide and glossary exactly when they are present.{localization_context}

Input JSON:
{json.dumps(list(batch), ensure_ascii=False)}

Output JSON:"""

        try:
            batch_response = client.generate(
                prompt,
                temperature=0.1,
                max_tokens=2048,
            )
            translated_batch = _extract_json_array(batch_response)
            if len(translated_batch) != len(batch):
                raise ValueError(
                    "Translated batch length mismatch: "
                    f"expected {len(batch)}, got {len(translated_batch)}"
                )
            translated_texts.extend(translated_batch)
        except Exception as error:
            logger.warning(
                "Batch translation failed for batch %s/%s, falling back to per-item translation: %s",
                batch_index,
                len(batches),
                error,
            )
            translated_texts.extend(
                [
                    translate_text(
                        text,
                        source_language,
                        target_language,
                        style_guide=style_guide,
                        glossary_terms=glossary_terms,
                    )
                    if text
                    else text
                    for text in batch
                ]
            )

    return translated_texts


def translate_segments(
    segments,
    source_language: str,
    target_language: str,
    *,
    style_guide: str | None = None,
    glossary_terms: Sequence[dict[str, str]] | None = None,
):
    if not segments:
        return []

    logger.info(
        "Translating %s segments from %s to %s",
        len(segments),
        source_language,
        target_language,
    )

    source_texts = [segment.get("text", "") or "" for segment in segments]
    translated_texts = translate_texts(
        source_texts,
        source_language,
        target_language,
        style_guide=style_guide,
        glossary_terms=glossary_terms,
    )

    translated_segments = []
    for segment, translated_text in zip(segments, translated_texts, strict=True):
        translated_segment = segment.copy()
        if segment.get("text"):
            translated_segment["text"] = translated_text
        translated_segments.append(translated_segment)

    return translated_segments


def detect_language(text: str) -> str:
    try:
        client = get_ollama_client()
        sample_text = text[:500] if len(text) > 500 else text
        supported_langs = ", ".join(
            [f"{code} ({name})" for code, name in SUPPORTED_LANGUAGES.items()]
        )
        prompt = f"""Detect the language of the following text. Respond with ONLY the two-letter language code.

Supported languages: {supported_langs}

Text to analyze:
{sample_text}

Language code:"""

        response = client.generate(
            prompt,
            temperature=0,
            max_tokens=8,
        ).strip().lower()
        detected_lang = response[:2] if len(response) >= 2 else response

        if detected_lang in SUPPORTED_LANGUAGES:
            logger.info(
                "Detected language: %s (%s)",
                detected_lang,
                SUPPORTED_LANGUAGES[detected_lang],
            )
            return detected_lang

        logger.warning(
            "Detected language '%s' not supported, defaulting to 'en'",
            detected_lang,
        )
        return "en"
    except Exception as error:
        logger.error("Error detecting language: %s", error)
        logger.info("Defaulting to 'en' due to language detection error")
        return "en"
