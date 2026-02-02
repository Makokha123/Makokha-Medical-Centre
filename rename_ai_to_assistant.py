#!/usr/bin/env python3
"""
Script to rename all AI references to Assistant in templates and backend
"""
import re
import os

# Define replacements
replacements = {
    # CSS Classes
    r'\.ai-toggle\b': '.assistant-toggle',
    r'\.ai-panel\b': '.assistant-panel',
    r'\.ai-tools\b': '.assistant-tools',
    r'\.ai-suggestions-content\b': '.assistant-suggestions-content',
    r'\.ai-suggestions-panel\b': '.assistant-suggestions-panel',
    r'\.ai-assistance-card\b': '.assistant-card',
    r'\.ai-generated\b': '.assistant-generated',
    r'\.ai-control-btn\b': '.assistant-control-btn',
    r'\.ai-buttons-disabled\b': '.assistant-buttons-disabled',
    r'\.ai-cell-loading\b': '.assistant-cell-loading',
    
    # Class attributes
    r'class="ai-toggle"': 'class="assistant-toggle"',
    r'class="ai-panel"': 'class="assistant-panel"',
    r'class="ai-tools"': 'class="assistant-tools"',
    r'class="ai-suggestions-content"': 'class="assistant-suggestions-content"',
    r'class="ai-suggestions-panel"': 'class="assistant-suggestions-panel"',
    r'class="ai-assistance-card': 'class="assistant-card',
    r'class="ai-generated': 'class="assistant-generated',
    r'class="ai-control-btn': 'class="assistant-control-btn',
    
    # IDs
    r'id="aiToggleDrug"': 'id="assistantToggleDrug"',
    r'id="aiToggleDrugInput"': 'id="assistantToggleDrugInput"',
    r'id="aiToggleControlled"': 'id="assistantToggleControlled"',
    r'id="aiToggleControlledInput"': 'id="assistantToggleControlledInput"',
    r'id="aiProgressCard"': 'id="assistantProgressCard"',
    r'id="aiProgressCounts"': 'id="assistantProgressCounts"',
    r'id="aiProgressText"': 'id="assistantProgressText"',
    r'id="ai-diagnosis-loading"': 'id="assistant-diagnosis-loading"',
    r'id="ai-diagnosis-results"': 'id="assistant-diagnosis-results"',
    r'id="ai-diagnosis-text"': 'id="assistant-diagnosis-text"',
    r'id="enable-ai-assistance"': 'id="enable-assistant"',
    r'id="generate-summary-ai"': 'id="generate-summary-assistant"',
    r'id="apply-ai-diagnosis"': 'id="apply-assistant-diagnosis"',
    r"getElementById\('aiToggleDrug'\)": "getElementById('assistantToggleDrug')",
    r"getElementById\('aiToggleDrugInput'\)": "getElementById('assistantToggleDrugInput')",
    r"getElementById\('aiToggleControlled'\)": "getElementById('assistantToggleControlled')",
    r"getElementById\('aiToggleControlledInput'\)": "getElementById('assistantToggleControlledInput')",
    r"getElementById\('aiProgressCard'\)": "getElementById('assistantProgressCard')",
    r"getElementById\('aiProgressCounts'\)": "getElementById('assistantProgressCounts')",
    r"getElementById\('aiProgressText'\)": "getElementById('assistantProgressText')",
    r"getElementById\('ai-diagnosis-loading'\)": "getElementById('assistant-diagnosis-loading')",
    r"getElementById\('ai-diagnosis-results'\)": "getElementById('assistant-diagnosis-results')",
    r"getElementById\('ai-diagnosis-text'\)": "getElementById('assistant-diagnosis-text')",
    r"#ai-diagnosis-loading": "#assistant-diagnosis-loading",
    r"#ai-diagnosis-results": "#assistant-diagnosis-results",
    r"#ai-diagnosis-text": "#assistant-diagnosis-text",
    r"#apply-ai-diagnosis": "#apply-assistant-diagnosis",
    
    # JavaScript function names
    r'\bhandleAIToggleDrug\b': 'handleAssistantToggleDrug',
    r'\bhandleAIToggleControlled\b': 'handleAssistantToggleControlled',
    r'\brunAIAgent\b': 'runAssistantAgent',
    r'\bstartAIDosageJob\b': 'startAssistantDosageJob',
    r'\bshowAIProgressCard\b': 'showAssistantProgressCard',
    r'\bhideAIProgressCard\b': 'hideAssistantProgressCard',
    r'\b_setProgressText\b': '_setAssistantProgressText',
    r'\b_hideProgress\b': '_hideAssistantProgress',
    r'\b_showProgressCard\b': '_showAssistantProgressCard',
    r'\b_setControlledProgressText\b': '_setControlledAssistantProgressText',
    r'\b_hideControlledProgress\b': '_hideControlledAssistantProgress',
    r'\b_showControlledProgressCard\b': '_showControlledAssistantProgressCard',
    r'\bgenerateROSQuestionsAI\b': 'generateROSQuestionsAssistant',
    r'\bgenerateHPIQuestionsAI\b': 'generateHPIQuestionsAssistant',
    r'\bgenerateHPIContentAI\b': 'generateHPIContentAssistant',
    r'\bgenerateDiagnosisAI\b': 'generateDiagnosisAssistant',
    r'\bgenerateTreatmentAI\b': 'generateTreatmentAssistant',
    r'\bshowAIError\b': 'showAssistantError',
    r'\bshowAISuccess\b': 'showAssistantSuccess',
    r'\bformatAIText\b': 'formatAssistantText',
    
    # JavaScript variables
    r'\b_aiJobPollTimer\b': '_assistantJobPollTimer',
    r'\b_aiJobLastSeq\b': '_assistantJobLastSeq',
    r'\b_aiProgressCardDismissed\b': '_assistantProgressCardDismissed',
    r'\b_aiControlledJobPollTimer\b': '_assistantControlledJobPollTimer',
    r'\b_aiControlledLastSeq\b': '_assistantControlledLastSeq',
    r'\b_aiControlledProgressCardDismissed\b': '_assistantControlledProgressCardDismissed',
    
    # Storage keys
    r"'ai_dosage_master_enabled'": "'assistant_dosage_master_enabled'",
    r"'ai_dosage_agent_enabled'": "'assistant_dosage_agent_enabled'",
    r'"ai_dosage_master_enabled"': '"assistant_dosage_master_enabled"',
    r'"ai_dosage_agent_enabled"': '"assistant_dosage_agent_enabled"',
    
    # Flask route names
    r"'admin_toggle_ai_dosage_agent'": "'admin_toggle_assistant_dosage_agent'",
    r'"admin_toggle_ai_dosage_agent"': '"admin_toggle_assistant_dosage_agent"',
    
    # API endpoints
    r'/admin/dosage/ai-': '/admin/dosage/assistant-',
    r'/doctor/patient/ai/': '/doctor/patient/assistant/',
    
    # Backend route decorators
    r"@app\.route\('/admin/dosage/ai-": "@app.route('/admin/dosage/assistant-",
    r"@app\.route\('/doctor/patient/ai/": "@app.route('/doctor/patient/assistant/",
    
    # Comments
    r'<!-- AI ': '<!-- Assistant ',
    r'<!-- Hidden AI ': '<!-- Hidden Assistant ',
    r'// AI ': '// Assistant ',
    r'/\* AI ': '/* Assistant ',
    r'# AI ': '# Assistant ',
    
    # HTML element references
    r'for="enable-ai-assistance"': 'for="enable-assistant"',
    r'name="ai_assistance"': 'name="assistant_enabled"',
}

files_to_process = [
    'templates/admin/dosage.html',
    'templates/admin/controlled_dosage.html',
    'templates/doctor/new_patient.html',
    'templates/doctor/patient_details.html',
    'app.py'
]

def process_file(filepath):
    print(f"Processing {filepath}...")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        for pattern, replacement in replacements.items():
            content = re.sub(pattern, replacement, content)
        
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  ✓ Updated {filepath}")
        else:
            print(f"  - No changes needed for {filepath}")
    except Exception as e:
        print(f"  ✗ Error processing {filepath}: {e}")

if __name__ == '__main__':
    base_dir = r'c:\Users\makok\Desktop\Makokha-Medical-Centre'
    os.chdir(base_dir)
    
    for file in files_to_process:
        if os.path.exists(file):
            process_file(file)
        else:
            print(f"File not found: {file}")
    
    print("\nDone!")
