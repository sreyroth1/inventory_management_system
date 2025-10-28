import os
# import subprocess
# import sys

def create_project_structure():
    """Create the complete project structure"""
    
    # Create directories
    directories = [
        'static/css',
        'static/js',
        'templates'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✓ Created directory: {directory}")
    
    # Create requirements.txt
    requirements = """Flask==2.3.3
Flask-SQLAlchemy==3.0.5
Flask-CORS==4.0.0"""

if __name__ == "__main__":
    create_project_structure()