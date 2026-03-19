"""
CSV and JSON export processor for quiz questions.
Fixes:
- Empty fields validated before writing
- Proper fieldnames matching import format
- JSON export added
- Logging on parse failure
"""

import csv
import io
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Standard fieldnames used throughout the bot
CSV_FIELDNAMES = [
    "question",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "correct_answer",
    "explanation",
]


# ── Parser (CSV → questions list) ────────────────────────────────────────────

class CSVParser:
    @staticmethod
    def parse_csv_file(file_content: bytes) -> List[Dict]:
        questions: List[Dict] = []
        try:
            content = file_content.decode("utf-8-sig")   # handle BOM
            reader = csv.DictReader(io.StringIO(content))
            headers = reader.fieldnames or []

            for row_num, row in enumerate(reader, start=2):
                try:
                    question = CSVParser._parse_row(row, headers)
                    if question:
                        questions.append(question)
                except Exception as e:
                    logger.warning(f"Row {row_num} parse error: {e} — row={dict(row)}")

            if not questions:
                logger.warning("No valid questions extracted from CSV")
        except Exception as e:
            logger.error(f"CSV parse failed: {e}")
            raise Exception(f"Failed to parse CSV file: {e}")

        logger.info(f"Parsed {len(questions)} questions from CSV")
        return questions

    @staticmethod
    def _parse_row(row: Dict, headers: List[str]) -> Optional[Dict]:
        """Try both new-style (question/option_a…) and legacy (questions/option1…) headers."""
        # New-style headers
        if "question" in headers:
            q_text = (row.get("question") or "").strip()
            options = [
                (row.get("option_a") or "").strip(),
                (row.get("option_b") or "").strip(),
                (row.get("option_c") or "").strip(),
                (row.get("option_d") or "").strip(),
            ]
            correct_letter = (row.get("correct_answer") or "A").strip().upper()
            explanation = (row.get("explanation") or "").strip()
        # Legacy headers (original bot format)
        elif "questions" in headers:
            q_text = (row.get("questions") or "").strip()
            options = [
                (row.get("option1") or "").strip(),
                (row.get("option2") or "").strip(),
                (row.get("option3") or "").strip(),
                (row.get("option4") or "").strip(),
            ]
            try:
                answer_num = int(row.get("answer") or "1")
                correct_letter = chr(64 + answer_num)  # 1→A, 2→B …
            except (ValueError, TypeError):
                correct_letter = "A"
            explanation = (row.get("explanation") or "").strip()
        else:
            logger.warning(f"Unrecognised CSV headers: {headers}")
            return None

        # Drop empty options
        options = [o for o in options if o]
        if not q_text or len(options) < 2:
            return None

        letter_map = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}
        correct_index = letter_map.get(correct_letter, 0)
        if correct_index >= len(options):
            correct_index = 0

        return {
            "question_description": q_text,
            "options": options,
            "correct_answer_index": correct_index,
            "correct_option": chr(65 + correct_index),
            "explanation": explanation,
        }


# ── Generator (questions list → CSV / JSON) ──────────────────────────────────

class CSVGenerator:
    @staticmethod
    def questions_to_csv(questions: List[Dict], output_path: Path) -> bool:
        """Write questions to CSV. Returns True on success."""
        if not questions:
            logger.warning("No questions to write to CSV")
            return False

        valid_count = 0
        try:
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
                writer.writeheader()
                for i, q in enumerate(questions):
                    q_text = (q.get("question_description") or "").strip()
                    options = q.get("options") or []
                    explanation = (q.get("explanation") or "").strip()
                    correct_index = q.get("correct_answer_index", 0)

                    if not q_text:
                        logger.warning(f"Question {i+1} has empty text — skipping")
                        continue
                    if len(options) < 2:
                        logger.warning(f"Question {i+1} has fewer than 2 options — skipping")
                        continue

                    # Ensure correct_index is valid
                    if not isinstance(correct_index, int) or correct_index < 0 or correct_index >= len(options):
                        logger.warning(f"Question {i+1} has invalid correct_index {correct_index!r} — defaulting to 0")
                        correct_index = 0

                    # Pad options to 4
                    while len(options) < 4:
                        options.append("")

                    correct_letter = chr(65 + correct_index)   # 0→A, 1→B …

                    row = {
                        "question": q_text,
                        "option_a": options[0],
                        "option_b": options[1],
                        "option_c": options[2],
                        "option_d": options[3],
                        "correct_answer": correct_letter,
                        "explanation": explanation,
                    }
                    writer.writerow(row)
                    valid_count += 1

            logger.info(f"CSV written: {valid_count}/{len(questions)} questions → {output_path}")
            return valid_count > 0
        except Exception as e:
            logger.error(f"Failed to write CSV: {e}")
            return False

    @staticmethod
    def questions_to_json(questions: List[Dict], output_path: Path) -> bool:
        """Write questions to JSON. Returns True on success."""
        if not questions:
            logger.warning("No questions to write to JSON")
            return False
        try:
            clean = []
            for q in questions:
                clean.append(
                    {
                        "question": (q.get("question_description") or "").strip(),
                        "options": q.get("options") or [],
                        "correct_answer_index": q.get("correct_answer_index", 0),
                        "correct_answer": q.get("correct_option", "A"),
                        "explanation": (q.get("explanation") or "").strip(),
                    }
                )
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(clean, f, ensure_ascii=False, indent=2)
            logger.info(f"JSON written: {len(clean)} questions → {output_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to write JSON: {e}")
            return False
