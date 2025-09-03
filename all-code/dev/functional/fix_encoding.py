#!/usr/bin/env python3
"""
Quick fix for encoding issues in ultimate_comparison_test.py
"""

# Read the file
with open('tools/ultimate_comparison_test.py', 'r') as f:
    content = f.read()

# Fix the problematic null byte pattern
content = content.replace("b'\\x00' * 256", "bytes(256)")

# Write back
with open('tools/ultimate_comparison_test.py', 'w') as f:
    f.write(content)

print("✅ Fixed encoding issues in ultimate_comparison_test.py")
