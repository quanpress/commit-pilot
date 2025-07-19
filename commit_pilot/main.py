import subprocess
import sys
import os
import questionary
import logging
from transformers import pipeline

logging.getLogger("transformers").setLevel(logging.ERROR)  # Suppress warnings from transformers

def get_staged_diff():
    """Fetches the staged git diff using UTF-8 encoding."""
    command = ["git", "diff", "--staged"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8', errors='ignore')
        return result.stdout
    except subprocess.CalledProcessError:
        print("commit-pilot: Error fetching staged changes. Ensure you have staged files with 'git add .'")
        sys.exit(1)
    except FileNotFoundError:
        print("commit-pilot: Error: Git is not installed or not in your PATH.")
        sys.exit(1)

def generate_commit_message(diff):
    """Generates a commit message for the given diff using a local model."""
    if not diff:
        return None

    # --- NEW, more robust cleaning and truncation logic ---
    cleaned_lines = []
    for line in diff.split('\n'):
        # Ignore git headers and files that are not text
        if line.startswith(('diff --git', 'index', '---', '+++', 'Binary files')):
            continue
        # Keep only the actual code changes
        if line.startswith(('+', '-')):
            # Remove the leading '+' or '-' character for cleaner input
            cleaned_lines.append(line[1:])
    
    # If there are no meaningful changes, provide a default message
    if not cleaned_lines:
        return "chore: Update file metadata or permissions"
        
    cleaned_diff = "\n".join(cleaned_lines)
    
    # Truncate the CLEANED diff, not the whole prompt. This is key.
    max_length = 2000 # Limit the number of characters sent to the AI
    truncated_diff = cleaned_diff[:max_length]
    # --- End of new logic ---

    print("commit-pilot: Generating commit message from the following changes.")
    summarizer = pipeline("summarization", model="t5-small")
    
    # A prompt that is more direct for the t5-small model
    prompt = f"summarize the following code changes into a short git commit message: {truncated_diff}"

    summary_list = summarizer(prompt, max_new_tokens=40, min_length=5, do_sample=False)
    
    commit_message = summary_list[0]['summary_text'].strip()
    
    # Add a conventional commit prefix if it doesn't have one
    prefixes = ("feat:", "fix:", "chore:", "docs:", "style:", "refactor:", "perf:", "test:")
    if not any(commit_message.lower().startswith(p) for p in prefixes):
        commit_message = f"feat: {commit_message}"

    return commit_message.lower()

def perform_commit(message):
    """Performs the git commit with the given message."""
    try:
        command = ["git", "commit", "-m", message]
        subprocess.run(command, check=True)
        print("\n✅ commit-pilot: Commit successful!")
    except subprocess.CalledProcessError:
        print("\n❌ commit-pilot: Git commit failed.")
        sys.exit(1)

def main():
    """The main function for the script."""
    diff_output = get_staged_diff()
    
    if not diff_output:
        print("commit-pilot: No staged changes found. Please use 'git add' to stage your files.")
        sys.exit(0)
    
    ai_message = generate_commit_message(diff_output)

    print("\n--- commit-pilot: Suggested Commit Message ---")
    print(f"\n{ai_message}\n")
    print("---------------------------------")

    action = questionary.select(
        "Use this commit message?",
        choices=["Yes", "Edit", "No"]
    ).ask()

    if action == "Yes":
        perform_commit(ai_message)
    elif action == "Edit":
        edited_message = questionary.text(
            "Edit the commit message:",
            multiline=True,
            default=ai_message
        ).ask()
        if edited_message:
            perform_commit(edited_message)
        else:
            print("commit-pilot: Commit cancelled.")
    else:
        print("commit-pilot: Commit cancelled.")