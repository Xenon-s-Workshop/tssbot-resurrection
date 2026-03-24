"""
CSV Processor
"""

import csv
from pathlib import Path
from typing import List, Dict

class CSVProcessor:
    @staticmethod
    def csv_to_questions(csv_path: Path) -> List[Dict]:
        """Load questions from CSV"""
        questions = []
        
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                questions.append(row)
        
        return questions

class CSVGenerator:
    @staticmethod
    def questions_to_csv(questions: List[Dict], output_path: Path):
        """Save questions to CSV"""
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'questions', 'option1', 'option2', 'option3', 'option4', 'option5',
                'answer', 'explanation', 'type', 'section'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for q in questions:
                writer.writerow(q)
