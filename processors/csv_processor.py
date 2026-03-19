"""CSV Generator with Validation"""
import csv

class CSVGenerator:
    @staticmethod
    def questions_to_csv(questions, output_path):
        """Generate CSV with validation"""
        if not questions:
            raise ValueError("No questions to export")
        
        fieldnames = ['questions', 'option1', 'option2', 'option3', 'option4', 'option5', 
                     'answer', 'explanation', 'type', 'section']
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for q in questions:
                # Validate before writing
                if not q.get('questions'):
                    print(f"⚠️ Skipping question with empty text")
                    continue
                
                writer.writerow(q)
        
        print(f"✅ CSV written: {len(questions)} questions")
